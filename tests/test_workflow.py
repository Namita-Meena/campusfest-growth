"""Database-backed behaviour: the recruiter demo, persistence, budget controls and validation."""
import pytest

from core import analytics as an
from core import database as db


def _camp(ctx, cid):
    return next(c for c in ctx["campaigns"] if c["id"] == cid)


def test_seeded_scenario_is_week4_scale_with_reconciled_budget():
    ctx = an.build_context(4)
    assert _camp(ctx, "club")["registrations"] == 260
    assert ctx["decisions"]["club"]["state"] == "Scale" and ctx["decisions"]["club"]["details"]["pitches"] >= 20
    assert ctx["budget"]["allocated"] == 300000 == ctx["budget"]["approved_budget"]
    assert ctx["budget"]["reserve_uncommitted"] == 20000
    assert ctx["totals"]["actual_verified_attendees"] is None          # not available before the festival


def test_demo_edit_260_to_140_flips_to_stop_and_lowers_forecast():
    before = an.build_context(4)["forecast"]["expected_attendance"]
    res = an.save_cumulative("club", 4, {"registrations": 140})
    ctx = an.build_context(4)
    club = _camp(ctx, "club")
    assert club["registrations"] == 140 and club["confirmed"] <= 140 and res["notes"]
    assert sum(m["registrations"] for m in ctx["metrics"] if m["campaign_id"] == "club" and m["week"] <= 4) == 140
    assert ctx["decisions"]["club"]["state"] == "Stop"
    assert ctx["forecast"]["expected_attendance"] < before
    assert ctx["decisions"]["club"]["transfer"]["amount"] == min(40000, club["uncommitted"])


def test_changes_persist_in_the_database_file(tmp_path):
    path = tmp_path / "ws.sqlite"
    db.use_store(db.SQLiteStore(path))
    an.save_cumulative("club", 4, {"registrations": 140})
    tid = an.save_task(dict(title="Persisted task", campaign_id="club", owner="Meera Iyer", deadline="2027-01-10", priority="High", status="To Do"), is_new=True)
    db.use_store(db.SQLiteStore(path))                                   # simulates a restart / browser refresh
    ctx = an.build_context(4)
    assert _camp(ctx, "club")["registrations"] == 140
    assert any(t["id"] == tid for t in ctx["tasks"])


def test_reserve_cannot_be_allocated_twice():
    d = an.build_context(4)["decisions"]["club"]
    log = an.apply_decision(d, 4, True)
    assert log["amount_moved"] == 20000
    ctx = an.build_context(4)
    assert ctx["budget"]["reserve_uncommitted"] == 0 and ctx["budget"]["allocated"] == 300000
    assert ctx["decisions"]["club"]["transfer"] is None                  # nothing left to propose
    with pytest.raises(an.ValidationError):
        an.apply_decision(d, 4, True)                                    # same approval again
    with pytest.raises(an.ValidationError):
        an.apply_decision({**d, "key": "club2"}, 5, True)                # stale proposal, reserve already empty


def test_reject_changes_nothing_but_is_logged():
    d = an.build_context(4)["decisions"]["club"]
    an.apply_decision(d, 4, False, note="wait")
    ctx = an.build_context(4)
    assert ctx["budget"]["reserve_uncommitted"] == 20000 and ctx["decision_logs"][0]["outcome"] == "Rejected"


def test_validation_blocks_bad_inputs():
    with pytest.raises(an.ValidationError):
        an.save_cumulative("club", 4, {"registrations": -5})
    with pytest.raises(an.ValidationError):
        an.save_cumulative("club", 4, {"confirmed": 9999}, auto_adjust=False)
    with pytest.raises(an.ValidationError):                               # overspending the approved budget
        an.save_campaign(dict(id="paid", name="Paid Retargeting", status="Active", budget_allocated=60000, open_commitments=0))
    with pytest.raises(an.ValidationError):
        an.save_campaign(dict(id="paid", name="Paid Retargeting", status="Active", budget_allocated=-1, open_commitments=0))
    with pytest.raises(an.ValidationError):
        an.save_campaign(dict(id="paid", name="Paid Retargeting", status="Active", budget_allocated=25000, open_commitments=0, exp_confirm_rate=1.4))
    with pytest.raises(an.ValidationError):
        an.save_experiment("showup", 4, dict(control_starts=100, control_confirmed=120, treatment_starts=100, treatment_confirmed=80))
    with pytest.raises(an.ValidationError):
        an.save_experiment("guest", 8, dict(passes_issued=100, redeemed_new_people=90, redeemed_existing_registrants=20))
    with pytest.raises(an.ValidationError):
        an.save_task(dict(title="", owner="x", deadline="2027-01-01", priority="High", status="To Do"), is_new=True)
    with pytest.raises(an.ValidationError):
        an.save_task(dict(title="x", owner="x", deadline="not a date", priority="High", status="To Do"), is_new=True)


def test_reset_restores_seed_and_never_touches_history():
    from core import historical as h
    before = h.snapshot()["verified_attendees"]
    an.save_cumulative("club", 4, {"registrations": 10})
    db.reset_demo()
    assert _camp(an.build_context(4), "club")["registrations"] == 260
    assert h.snapshot()["verified_attendees"] == before == 2050


def test_week8_experiments_mature_and_guardrail_diagnoses_cause():
    ctx = an.build_context(8)
    assert ctx["decisions"]["showup"]["state"] == "Scale" and ctx["decisions"]["guest"]["state"] == "Scale"
    assert ctx["decisions"]["squad"]["state"] == "Change / Fix"
    for w in range(1, 7):                                                 # collapse the club campaign
        an.save_weekly_rows("club", [dict(week=w, reach=0, leads=10, reg_starts=8, registrations=6, confirmed=5, spend=3000)])
    g = an.build_context(6)["guardrail"]
    assert g["state"] == "Change / Fix" and g["details"]["bottleneck"] == "club" and "Paid Retargeting" in g["action"]
    assert an.build_context(5)["guardrail"]["state"] == "Continue Monitoring"   # not evaluated before week 6

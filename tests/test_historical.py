"""The 2025 figures quoted in the deck are re-derived from the raw dataset."""
import pandas as pd

from core import config as C
from core import historical as h


def test_headline_funnel_matches_deck():
    s = h.snapshot()
    assert s["reported_reach_sum"] == 666297
    assert s["campaign_attributed_leads"] == 3500
    assert s["registrations_external"] == 2800
    assert s["registered_attendees"] == 1925
    assert s["walk_ins"] == 125
    assert s["verified_attendees"] == 2050 == s["registered_attendees"] + s["walk_ins"]
    assert s["marketing_spend_inr"] == 274000
    assert s["confirmed"] == 2500 and s["unconfirmed"] == 300


def test_rates_use_correct_denominators():
    s = h.snapshot()
    assert s["attendance_rate_among_confirmed"] == 0.77          # 1,925 / 2,500
    assert s["attendance_rate_among_unconfirmed"] == 0.0         # 0 / 300
    assert s["confirmed_per_100_starts"] == 81.3                 # 2,500 / 3,075 starters
    assert s["attended_per_100_starts"] == 62.6


def test_cleaning_rules():
    d = h.load()
    assert d["_quality"]["daily_marketing"]["duplicate_ids_removed"] == 2
    assert d["_quality"]["registration_history"]["duplicate_ids_removed"] == 4
    assert d["_quality"]["checkins"]["duplicate_ids_removed"] == 20
    assert "person_name" not in d["people"].columns                 # names never exposed
    raw = pd.read_csv(h.DATA_DIR / "checkins.csv")
    assert len(raw) == 3390                                          # original file untouched


def test_as_of_snapshot_has_no_future_outcomes():
    early = h.snapshot("2025-03-10")
    assert early["verified_attendees"] == 0                          # festival was 12-13 April
    assert early["registrations_external"] < 2800
    assert early["targets_in_effect"]["target_version"] == "Attendee launch plan"
    assert h.snapshot("2025-03-20")["targets_in_effect"]["marketing_budget_inr"] == 300000


def test_channel_table_and_cost_screen():
    t = h.by_campaign().set_index("campaign_id")
    assert int(t.loc["C02", "cost_per_attendee"]) == 274            # paid social: the cost screen
    assert t.attended.sum() == 1925
    assert round(t.loc["C04", "attended_per_confirmed"], 3) == 0.917


def test_registration_curve_constant_is_from_data():
    wk = h.weekly_registrations()
    cum = [round(sum(wk[:i + 1]) / sum(wk), 4) for i in range(12)]
    assert cum == C.REG_CURVE


def test_safe_query():
    r = h.query("people_summary", ["person_type == external", "registered == true"], ["downloaded_brochure"], "mean", "attended_verified")
    vals = {x["downloaded_brochure"]: x["value"] for x in r["result"]}
    assert vals["True"] > vals["False"]
    assert "error" in h.query("people", [], None, "mean", "age")       # age does not exist
    assert "error" in h.query("secrets", [])
    assert "error" in h.query("people", ["__import__('os') == 1"])
    assert h.query("checkins", ["result == denied"])["result"] == 50

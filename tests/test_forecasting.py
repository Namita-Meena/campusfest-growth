import math

from core import analytics as an
from core import config as C
from core import forecasting as fc


def _plan_rows(col):
    return [{"registrations": c[col], "confirm_rate": c["exp_confirm_rate"], "p_attend_confirmed": c["p_attend_confirmed"]}
            for c in C.CAMPAIGN_SEED if c["type"] == "acquisition"]


def test_base_plan_reproduces_deck_target():
    out = fc.simple_forecast(_plan_rows("plan_regs_base"), C.DEFAULT_SETTINGS)
    assert out["projected_final_registrations"] == 2888
    assert abs(out["registered_attendees"] - 2351) <= 3
    assert out["expected_walkins"] == 150 and abs(out["expected_new_guests"] - 99) <= 1
    assert abs(out["expected_attendance"] - 2600) <= 4


def test_stretch_plan_reproduces_deck_target():
    s = {**C.DEFAULT_SETTINGS, "reminder_lift": 0.0735, "walkins_expected": 250, "guest_redemption_rate": 0.12}
    out = fc.simple_forecast(_plan_rows("plan_regs_stretch"), s)
    assert abs(out["expected_attendance"] - 3400) <= 5


def test_forecast_identity_counts_each_person_once():
    ctx = an.build_context(4)
    f = ctx["forecast"]
    assert f["expected_attendance"] == f["registered_attendees"] + f["expected_walkins"] + f["expected_new_guests"] or \
        abs(f["expected_attendance"] - (f["registered_attendees"] + f["expected_walkins"] + f["expected_new_guests"])) <= 1
    assert abs(f["projected_confirmed"] + f["projected_unconfirmed"] - f["projected_final_registrations"]) <= 1
    for c in ctx["campaigns"]:                      # interventions and event-day rows hold no registrations
        if c["type"] != "acquisition":
            assert c["projection"] is None and c["registrations"] == 0


def test_show_up_engine_changes_rates_not_people():
    state = an.db.load_all(force=True)
    on = an.build_context(4, state)["forecast"]
    off_state = {**state, "campaigns": [{**c, "status": "Stopped"} if c["id"] == "showup" else c for c in state["campaigns"]]}
    off = an.build_context(4, off_state)["forecast"]
    assert off["projected_final_registrations"] == on["projected_final_registrations"]
    assert off["registered_attendees"] < on["registered_attendees"]


def test_two_proportion_test_matches_reference_values():
    # Reference: scipy.stats.chi2_contingency(correction=False) gives z = 3.2566, p = 0.00113 for this table.
    r = fc.two_proportion_test(421, 520, 452, 512)
    assert round(r["diff_pts"], 2) == 7.32 and round(r["z"], 4) == 3.2566 and round(r["p_value"], 5) == 0.00113 and r["significant"]
    assert r["ci_low_pts"] < r["diff_pts"] < r["ci_high_pts"]
    r = fc.two_proportion_test(405, 500, 430, 500)
    assert round(r["diff_pts"], 1) == 5.0 and round(r["p_value"], 5) == 0.03318 and r["significant"]   # scipy reference
    assert not fc.two_proportion_test(10, 0, 5, 10)["valid"]
    assert not fc.two_proportion_test(11, 10, 5, 10)["valid"]


def test_sample_sizes_quoted_in_methodology():
    assert 380 <= fc.sample_size_per_arm(0.813, 7) <= 430
    assert 2300 <= fc.sample_size_per_arm(0.813, 3) <= 2600


def test_no_division_by_zero():
    assert fc.safe_div(5, 0) is None
    out = fc.simple_forecast([], {**C.DEFAULT_SETTINGS, "base_target": 0})
    assert out["pct_of_base"] is None and math.isfinite(out["expected_attendance"])

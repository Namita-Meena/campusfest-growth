"""Boundary values, minimum samples and mutual exclusivity of every decision rule."""
import pytest

from core import decision_engine as de

S, C_, X, M = de.SCALE, de.CHANGE, de.STOP, de.MONITOR


@pytest.mark.parametrize("week,pitches,regs,expected", [
    (3, 30, 400, M), (4, 19, 400, M), (4, 20, 250, S), (4, 20, 249, C_), (4, 20, 150, C_), (4, 20, 149, X), (4, 22, 260, S), (4, 22, 140, X), (9, 22, 0, X)])
def test_club(week, pitches, regs, expected):
    assert de.decide_club(week, pitches, regs, 20000, 38800)["state"] == expected


def test_club_transfers_respect_uncommitted_money():
    d = de.decide_club(4, 22, 140, 20000, 38800)
    assert d["transfer"] == {"from": "club", "to": "squad", "amount": 38800}      # below the 40,000 cap
    assert de.decide_club(4, 22, 140, 20000, 90000)["transfer"]["amount"] == 40000
    assert de.decide_club(4, 22, 140, 20000, 0)["transfer"] is None
    assert de.decide_club(4, 22, 260, 0, 38800)["transfer"] is None               # reserve already used
    assert de.decide_club(4, 22, 260, 20000, 38800)["transfer"]["from"] == "reserve"


def _show(c_n, c_x, t_n, t_x):
    return de.decide_showup(dict(control_starts=c_n, control_confirmed=c_x, treatment_starts=t_n, treatment_confirmed=t_x))


def test_showup_rules():
    assert _show(499, 400, 600, 560)["state"] == M                      # sample below 500 in one arm
    assert _show(520, 421, 512, 452)["state"] == S                      # +7.3 pts, significant
    assert _show(500, 405, 500, 430)["state"] == S                      # exactly +5.0 pts and significant (p = 0.033)
    assert _show(500, 250, 500, 276)["state"] == M                      # +5.2 pts but NOT significant (p = 0.10): keep testing
    assert _show(500, 405, 500, 429)["state"] == C_                     # +4.8 pts
    assert _show(500, 405, 500, 380)["state"] == C_                     # exactly -5.0 pts is still Change
    assert _show(500, 405, 500, 379)["state"] == X                      # below -5 pts
    assert _show(500, 600, 500, 400)["state"] == M                      # invalid counts never produce a verdict


@pytest.mark.parametrize("n_c,n_t,new_t,expected", [(300, 299, 90, M), (300, 300, 60, S), (300, 300, 59, C_), (300, 300, 30, C_), (300, 300, 29, X)])
def test_squad(n_c, n_t, new_t, expected):
    d = de.decide_squad(dict(control_registrants=n_c, control_new_people=30, treatment_registrants=n_t, treatment_new_people=new_t, squads_formed=10))
    assert d["state"] == expected


@pytest.mark.parametrize("n,new,expected", [(199, 50, M), (200, 12, S), (200, 11, C_), (200, 6, C_), (200, 5, X), (0, 0, M)])
def test_guest(n, new, expected):
    assert de.decide_guest(dict(passes_issued=n, redeemed_new_people=new, redeemed_existing_registrants=0))["state"] == expected


def test_guest_existing_registrants_do_not_count():
    d = de.decide_guest(dict(passes_issued=200, redeemed_new_people=5, redeemed_existing_registrants=40))
    assert d["state"] == X


@pytest.mark.parametrize("regs,fraud,cohort,expected", [(600, 0, 30, S), (599, 0, 30, C_), (120, 0, 30, C_), (119, 0, 30, X), (600, 0, 19, M), (900, 1, 30, X), (0, 2, 5, X)])
def test_ambassadors(regs, fraud, cohort, expected):
    d = de.decide_ambassadors(dict(cohort_checkin_pay=cohort, cohort_signup_pay=30, active_ambassadors=60,
                                   legit_registrations_last_2_weeks=regs, fraud_confirmed=fraud))
    assert d["state"] == expected
    if fraud:
        assert d["details"]["fraud_override"] and "deactivate" in d["action"].lower()

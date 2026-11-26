"""Attendance forecast and statistics. Pure functions: no database or UI access.

Forecast identity (each person counted once):

    expected attendance = confirmed registrants   x P(attend | confirmed)
                        + unconfirmed registrants x P(attend | unconfirmed)
                        + expected unique walk-ins
                        + expected unique new Day-2 guests

P(attend | confirmed) uses CONFIRMED registrants as its denominator (2025: 77%
overall), so the confirmation drop-off is not applied twice. The Show-Up Engine
is an intervention: it changes two rates (confirm rate and attendance among
confirmed) for people acquired by other campaigns and never adds people itself.
"""
from __future__ import annotations

import math

from . import config as C

MAX_CONFIRM, MAX_ATTEND = 0.99, 0.97


def curve_share(week: int, start_week: int = 1) -> float:
    """Share of a campaign's final registrations expected by the end of `week` (2025 curve)."""
    week = max(0, min(int(week), C.TOTAL_WEEKS))
    if week < start_week:
        return 0.0
    base = C.REG_CURVE[start_week - 2] if start_week > 1 else 0.0
    return (C.REG_CURVE[week - 1] - base) / (1 - base) if base < 1 else 1.0


def safe_div(a, b):
    return a / b if b else None


def project_campaign(c: dict, cum: dict, week: int, s: dict, showup_active: bool) -> dict | None:
    """Project one acquisition campaign to the end of the campaign."""
    if c.get("type") != "acquisition":
        return None
    plan_final = float(c.get("plan_regs_base") or 0)
    start = int(c.get("start_week") or 1)
    share = curve_share(week, start)
    regs, conf = float(cum.get("registrations", 0)), float(cum.get("confirmed", 0))
    plan_to_date = plan_final * share
    stopped = c.get("status") in ("Stopped", "Paused", "Archived")
    if share <= 0 or plan_to_date <= 0:
        pace, proj_final, basis = None, (regs if stopped else plan_final), "plan (campaign not started)"
    else:
        pace = regs / plan_to_date
        if stopped:
            proj_final, basis = regs, "registrations to date (campaign not active)"
        else:
            proj_final = regs + plan_final * (1 - share) * min(max(pace, 0.25), 2.0)
            basis = "registrations to date + remaining plan x current pace (pace limited to 0.25-2.0)"
    exp_rate = float(c.get("exp_confirm_rate") or 0)
    observed = conf / regs if regs >= 30 else None
    lift_c = float(s.get("waitlist_recovery", 0)) if showup_active else 0.0
    lift_p = float(s.get("reminder_lift", 0)) if showup_active else 0.0
    confirm_rate = min((observed if observed is not None else exp_rate) + lift_c, MAX_CONFIRM)
    p_conf = min(float(c.get("p_attend_confirmed") or 0) + lift_p, MAX_ATTEND)
    p_unconf = float(s.get("p_attend_unconfirmed", 0))
    proj_conf = proj_final * confirm_rate
    proj_unconf = proj_final - proj_conf
    attendees = proj_conf * p_conf + proj_unconf * p_unconf
    plan_att = plan_final * min(exp_rate + float(s.get("waitlist_recovery", 0)), MAX_CONFIRM) * \
        min(float(c.get("p_attend_confirmed") or 0) + float(s.get("reminder_lift", 0)), MAX_ATTEND)
    return {"plan_final_registrations": round(plan_final), "plan_registrations_to_date": round(plan_to_date, 1),
            "pace_vs_plan": None if pace is None else round(pace, 3),
            "projected_final_registrations": round(proj_final, 1), "projection_basis": basis,
            "confirm_rate_used": round(confirm_rate, 4),
            "confirm_rate_source": "observed to date" if observed is not None else "expected (2025 channel rate; fewer than 30 registrations so far)",
            "p_attend_confirmed_used": round(p_conf, 4),
            "projected_confirmed": round(proj_conf, 1), "projected_unconfirmed": round(proj_unconf, 1),
            "projected_attendees": round(attendees, 1), "plan_attendees": round(plan_att, 1),
            "attendee_gap_vs_plan": round(attendees - plan_att, 1)}


def total_forecast(projections: list, s: dict, guest_active: bool) -> dict:
    """Combine campaign projections with walk-ins and Day-2 guests (each person once)."""
    reg_att = sum(p["projected_attendees"] for p in projections if p)
    conf = sum(p["projected_confirmed"] for p in projections if p)
    unconf = sum(p["projected_unconfirmed"] for p in projections if p)
    regs = sum(p["projected_final_registrations"] for p in projections if p)
    walkins = float(s.get("walkins_expected", 0)) if guest_active else float(s.get("walkins_without_desk", 0))
    rate = float(s.get("guest_redemption_rate", 0)) if guest_active else 0.0
    day1 = reg_att * float(s.get("day1_share", 0.7))
    guests = day1 * rate
    total = reg_att + walkins + guests
    base, stretch = float(s.get("base_target", 0)), float(s.get("stretch_target", 0))
    cap = float(s.get("venue_capacity", 0))
    peak = total * float(s.get("day1_share", 0.7))
    return {"projected_final_registrations": round(regs), "projected_confirmed": round(conf),
            "projected_unconfirmed": round(unconf), "registered_attendees": round(reg_att),
            "day1_registered_attendees": round(day1), "guest_redemption_rate": rate,
            "expected_walkins": round(walkins), "expected_new_guests": round(guests),
            "expected_attendance": round(total), "base_target": round(base), "stretch_target": round(stretch),
            "gap_to_base": round(total - base), "gap_to_stretch": round(total - stretch),
            "pct_of_base": round(100 * total / base, 1) if base else None,
            "peak_day_estimate": round(peak), "venue_capacity": round(cap),
            "capacity_ok": bool(peak <= cap) if cap else True,
            "formula": "confirmed x P(attend|confirmed) + unconfirmed x P(attend|unconfirmed) + walk-ins + new Day-2 guests"}


def simple_forecast(rows: list, s: dict, showup_active=True, guest_active=True) -> dict:
    """Scenario forecast from explicit final registrations per campaign.

    rows: dicts with registrations, confirm_rate, p_attend_confirmed (rates already final, no lifts added
    unless showup_active, in which case the Show-Up Engine lifts in `s` are added).
    """
    proj = []
    for r in rows:
        regs = max(float(r.get("registrations") or 0), 0.0)
        cr = min(float(r.get("confirm_rate") or 0) + (float(s.get("waitlist_recovery", 0)) if showup_active else 0), MAX_CONFIRM)
        p = min(float(r.get("p_attend_confirmed") or 0) + (float(s.get("reminder_lift", 0)) if showup_active else 0), MAX_ATTEND)
        conf = regs * cr
        proj.append({"projected_final_registrations": regs, "projected_confirmed": conf, "projected_unconfirmed": regs - conf,
                     "projected_attendees": conf * p + (regs - conf) * float(s.get("p_attend_unconfirmed", 0))})
    return total_forecast(proj, s, guest_active)


# ---------------------------------------------------------------------------
def _phi(z: float) -> float:
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def two_proportion_test(x_control: int, n_control: int, x_treat: int, n_treat: int, alpha: float = 0.05) -> dict:
    """Two-sided two-proportion z-test (pooled SE) with an unpooled Wald confidence interval."""
    if min(n_control, n_treat) <= 0 or x_control < 0 or x_treat < 0 or x_control > n_control or x_treat > n_treat:
        return {"valid": False, "reason": "Counts must satisfy 0 <= successes <= sample size and sample size > 0."}
    p1, p2 = x_control / n_control, x_treat / n_treat
    diff = p2 - p1
    pooled = (x_control + x_treat) / (n_control + n_treat)
    se_pool = math.sqrt(pooled * (1 - pooled) * (1 / n_control + 1 / n_treat))
    z = diff / se_pool if se_pool > 0 else 0.0
    p_value = 2 * (1 - _phi(abs(z))) if se_pool > 0 else 1.0
    se = math.sqrt(p1 * (1 - p1) / n_control + p2 * (1 - p2) / n_treat)
    zc = 1.959964 if abs(alpha - 0.05) < 1e-9 else _z_for(alpha)
    return {"valid": True, "control_rate": p1, "treatment_rate": p2, "diff_pts": 100 * diff, "z": z, "p_value": p_value,
            "ci_low_pts": 100 * (diff - zc * se), "ci_high_pts": 100 * (diff + zc * se),
            "significant": bool(p_value < alpha), "alpha": alpha}


def _z_for(alpha: float) -> float:
    lo, hi = 0.0, 10.0
    for _ in range(80):
        mid = (lo + hi) / 2
        if 2 * (1 - _phi(mid)) > alpha:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def sample_size_per_arm(p_base: float, lift_pts: float, power: float = 0.80, alpha: float = 0.05) -> int | None:
    """Sample per arm needed to detect an absolute lift (in points) with a two-sided test."""
    d = lift_pts / 100
    q = p_base + d
    if d == 0 or not (0 < p_base < 1) or not (0 < q < 1):
        return None
    za = _z_for(alpha)
    lo, hi = 0.0, 10.0
    for _ in range(80):
        mid = (lo + hi) / 2
        if _phi(mid) < power:
            lo = mid
        else:
            hi = mid
    zb = (lo + hi) / 2
    return math.ceil((za + zb) ** 2 * (p_base * (1 - p_base) + q * (1 - q)) / d ** 2)

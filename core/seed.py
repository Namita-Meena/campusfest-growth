"""Deterministic SIMULATED campaign data for the hypothetical 2027 campaign.

Nothing in this file is an observed outcome. Weekly figures are generated from
the plan (core/config.py), the 2025 registration and spend curves, and a fixed
per-campaign performance factor, so every fresh or reset workspace is identical.
Demo scenario: at week 4 the Club Contingent League has 260 registrations from
22 completed club pitches.
"""
from __future__ import annotations

from datetime import datetime, timezone

from . import config as C

# Simulated performance versus plan (1.0 = exactly on the time-aligned plan).
_PERF = {"club": 1.25, "squad": 0.92, "amb": 0.90, "organic": 1.02, "community": 1.06, "paid": 0.86, "creators": 0.80}
# 2025 FACT ratios per channel: leads per registration, registration starts per registration, reported reach per registration.
_RATIOS = {"club": (1.111, 1.044, 219), "squad": (1.171, 1.086, 140), "amb": (1.154, 1.058, 171),
           "organic": (1.160, 1.060, 180), "community": (1.250, 1.050, 214), "paid": (1.412, 1.147, 295),
           "creators": (1.400, 1.200, 403)}
_CLUB_FIRST4 = [14, 46, 84, 116]  # cumulative 260 at week 4
_WOBBLE = [0.97, 1.04, 0.99, 1.02, 0.96, 1.03, 1.01, 0.98]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _inc(curve, w):
    return curve[w - 1] - (curve[w - 2] if w > 1 else 0.0)


def seed_campaigns() -> list:
    rows = []
    for c in C.CAMPAIGN_SEED:
        rows.append({**c, "status": "Active" if c["start_week"] <= 4 or c["type"] == "reserve" else "Planned",
                     "start_date": str(C.week_start(c["start_week"])), "end_date": str(C.week_end(C.TOTAL_WEEKS)),
                     "verified_attendees": None, "archived": False, "updated_at": now_iso()})
    return rows


def seed_metrics() -> list:
    rows = []
    for c in C.CAMPAIGN_SEED:
        if c["type"] == "reserve":
            continue
        cid, start = c["id"], c["start_week"]
        base_share = C.REG_CURVE[start - 2] if start > 1 else 0.0
        for w in range(1, C.SEEDED_WEEKS + 1):
            spend_share = _inc(C.SPEND_CURVE, w) if w >= start else 0.0
            spend = int(round(c["budget_allocated"] * spend_share * 0.95 / 50.0) * 50)
            reg = 0
            if c["type"] == "acquisition" and w >= start:
                share = _inc(C.REG_CURVE, w) / (1 - base_share) if w > start else (C.REG_CURVE[w - 1] - base_share) / (1 - base_share)
                reg = int(round(c["plan_regs_base"] * share * _PERF[cid] * _WOBBLE[w - 1]))
                if cid == "club" and w <= 4:
                    reg = _CLUB_FIRST4[w - 1]
            lead_r, start_r, reach_r = _RATIOS.get(cid, (0, 0, 0))
            conf = int(round(reg * (c["exp_confirm_rate"] or 0) * 0.98))
            rows.append({"id": f"{cid}-W{w:02d}", "campaign_id": cid, "week": w,
                         "reach": int(reg * reach_r), "leads": int(round(reg * lead_r)),
                         "reg_starts": int(round(reg * start_r)), "registrations": reg, "confirmed": conf,
                         "spend": spend, "updated_at": now_iso()})
    return rows


def seed_experiments() -> list:
    """Experiment inputs are recorded as snapshots at week 4 and week 8."""
    w4 = {
        "club": {"pitches_completed": 22},
        "showup": {"control_starts": 142, "control_confirmed": 115, "treatment_starts": 138, "treatment_confirmed": 113,
                   "control_attended": None, "treatment_attended": None},
        "squad": {"control_registrants": 96, "control_new_people": 12, "treatment_registrants": 104,
                  "treatment_new_people": 19, "squads_formed": 21},
        "guest": {"passes_issued": 0, "redeemed_new_people": 0, "redeemed_existing_registrants": 0},
        "amb": {"cohort_checkin_pay": 30, "cohort_signup_pay": 30, "active_ambassadors": 60,
                "legit_registrations_last_2_weeks": 372, "fraud_confirmed": 0, "verified_attendees": None},
    }
    w8 = {
        "club": {"pitches_completed": 58},
        "showup": {"control_starts": 520, "control_confirmed": 421, "treatment_starts": 512, "treatment_confirmed": 452,
                   "control_attended": None, "treatment_attended": None},
        "squad": {"control_registrants": 320, "control_new_people": 45, "treatment_registrants": 340,
                  "treatment_new_people": 58, "squads_formed": 96},
        "guest": {"passes_issued": 210, "redeemed_new_people": 15, "redeemed_existing_registrants": 6},
        "amb": {"cohort_checkin_pay": 30, "cohort_signup_pay": 30, "active_ambassadors": 60,
                "legit_registrations_last_2_weeks": 380, "fraud_confirmed": 0, "verified_attendees": None},
    }
    rows = []
    for week, snap in ((4, w4), (8, w8)):
        for exp, inputs in snap.items():
            rows.append({"id": f"{exp}-W{week:02d}", "experiment": exp, "week": week, "inputs": inputs, "updated_at": now_iso()})
    return rows


def seed_tasks() -> list:
    t = now_iso()
    mk = lambda i, title, desc, camp, owner, wk, pr, st, ev: {
        "id": f"seed-{i}", "title": title, "description": desc, "campaign_id": camp, "owner": owner,
        "deadline": str(C.week_end(wk)), "priority": pr, "status": st, "evidence": ev, "source": "Manual", "created_at": t}
    return [
        mk(1, "Sign 60 clubs by week 6", "Pitch remaining target clubs; 22 pitches completed so far.", "club", "Meera Iyer", 6, "High", "In Progress",
           "Plan: 60 clubs by W6 (deck slide 2)."),
        mk(2, "Launch deposit A/B test", "Randomise 50% of registration starts into the Rs 99 refundable-deposit arm.", "showup", "Dev Malhotra", 5, "High", "In Progress",
           "Needs 500 registration starts per arm before any decision."),
        mk(3, "Set up WhatsApp reminder flows", "7-day, 24-hour and 2-hour nudges plus automatic waitlist release.", "showup", "Dev Malhotra", 5, "Medium", "To Do",
           "2025: 88 registrants were still waitlisted when the festival opened."),
        mk(4, "Book Week-8 pre-fest pilot for guest passes", "Issue at least 200 Day-2 guest passes at the pilot event.", "guest", "Nisha Rao", 8, "Medium", "To Do",
           "Pilot needs 200 passes; result is directional only."),
        mk(5, "Publish ambassador leaderboard", "Weekly leaderboard of legitimate verified registrations per ambassador.", "amb", "Meera Iyer", 5, "Low", "Completed",
           "Payout: Rs 40 per verified attendee, Rs 1,000 to each of the top 10."),
    ]


def seed_settings() -> list:
    return [{"key": k, "value": v} for k, v in C.DEFAULT_SETTINGS.items()]

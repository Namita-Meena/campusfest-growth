"""Central configuration: festival plan, campaign seed values and decision thresholds.

Everything here is a PLANNING value or an ASSUMPTION for the hypothetical
CampusFest Bengaluru 2027 campaign, unless a comment says it is a 2025 fact
computed from the supplied historical dataset (see core/historical.py and
tests/test_historical.py, which re-derive those facts from the raw records).
"""
from __future__ import annotations

from datetime import date, timedelta

APP_NAME = "CampusFest Growth Intelligence"
CANDIDATE = "Namita Meena"
INSTITUTION = "IIT Kharagpur"
FESTIVAL = "CampusFest Bengaluru 2027"
FEST_DATES = "20–21 February 2027"
CAMPAIGN_START = date(2026, 11, 30)  # Monday of campaign week 1
TOTAL_WEEKS = 12
SEEDED_WEEKS = 8                     # simulated weekly data exists for weeks 1-8

# Colours (also set in .streamlit/config.toml)
NAVY, BLUE, ORANGE = "#14243C", "#2459D3", "#C65D28"
GREEN, AMBER, RED, GREY = "#2E7D4F", "#B7791F", "#B83232", "#7A8394"
PAPER, LINE = "#F7F6F2", "#E2DED3"

STATE_COLOURS = {"Scale": GREEN, "Change / Fix": AMBER, "Stop": RED, "Continue Monitoring": GREY}
OWNERS = ["Meera Iyer", "Arjun Verma", "Nisha Rao", "Dev Malhotra", "Namita Meena"]
CAMPAIGN_STATUSES = ["Planned", "Active", "Paused", "Stopped", "Archived"]
TASK_STATUSES = ["To Do", "In Progress", "Blocked", "Completed"]
TASK_PRIORITIES = ["High", "Medium", "Low"]


def week_start(week: int) -> date:
    return CAMPAIGN_START + timedelta(days=7 * (week - 1))


def week_end(week: int) -> date:
    return week_start(week) + timedelta(days=6)


# ---------------------------------------------------------------------------
# 2025 FACT: cumulative share of final registrations reached by the end of each
# of the 12 campaign weeks (external registrants, week 1 = 20-26 Jan 2025).
# Used to pace-align the 2027 plan. Re-derived in tests/test_historical.py.
REG_CURVE = [0.0129, 0.0521, 0.1236, 0.2232, 0.3304, 0.4193, 0.4814, 0.5736, 0.6893, 0.8157, 0.9393, 1.0]
# 2025 FACT: cumulative share of marketing spend posted by the end of each week.
SPEND_CURVE = [0.021, 0.099, 0.176, 0.268, 0.371, 0.494, 0.631, 0.706, 0.803, 0.876, 0.923, 1.0]

# ---------------------------------------------------------------------------
# Default settings (stored in the database, editable through the simulator).
DEFAULT_SETTINGS = {
    "base_target": 2600,
    "stretch_target": 3400,
    "total_budget": 300000,
    "venue_capacity": 3000,            # ASSUMPTION: simultaneous occupants
    "walkins_expected": 150,           # plan; 2025 fact was 125
    "walkins_without_desk": 125,       # 2025 fact, used if the guest/walk-in desk is not active
    "guest_redemption_rate": 0.06,     # ASSUMPTION (base). Stretch uses 0.12
    "day1_share": 0.70,                # 2025 fact: 1,430 of 2,050 unique visitors came on day 1
    "waitlist_recovery": 0.03,         # Show-Up Engine: +3 pts confirm rate (88 of 2,800 were stuck on the waitlist in 2025)
    "reminder_lift": 0.0265,           # Show-Up Engine: +2.65 pts attendance among confirmed (calibrated so plan = 2,351)
    "p_attend_unconfirmed": 0.0,       # 2025 fact: 0 of 300 unconfirmed registrants attended
    "guardrail_ratio": 0.90,
    "guardrail_week": 6,
    "cost_screen_inr": 274,            # 2025 fact: paid social cost per verified attendee
    "actual_walkins": None,            # entered after the festival
    "actual_new_guests": None,
}

# ---------------------------------------------------------------------------
# Campaign seed. exp_confirm_rate and p_attend_confirmed are 2025 FACTS for the
# matching historical channel (confirmed / registered, attended / confirmed).
# plan_regs_* come from the strategy model documented in the README.
CAMPAIGN_SEED = [
    dict(id="club", name="Club Contingent League", type="acquisition", owner="Meera Iyer", hist_channel="C04",
         description="College clubs enter as contingents for points, a reserved stand and an overall trophy.",
         start_week=1, budget_allocated=95000, open_commitments=32000, plan_regs_base=932, plan_regs_stretch=1102,
         exp_confirm_rate=0.933, p_attend_confirmed=0.917, base_incremental=389, stretch_incremental=535),
    dict(id="showup", name="Show-Up Engine", type="intervention", owner="Dev Malhotra", hist_channel=None,
         description="WhatsApp nudges 7d/24h/2h and automatic waitlist release. Rs 99 refundable deposit is an experiment only.",
         start_week=4, budget_allocated=25000, open_commitments=6000, plan_regs_base=0, plan_regs_stretch=0,
         exp_confirm_rate=None, p_attend_confirmed=None, base_incremental=144, stretch_incremental=298),
    dict(id="squad", name="Squad Pass", type="acquisition", owner="Dev Malhotra", hist_channel="C05",
         description="Squads of 4 get fast-lane entry (cap 300 squads); every confirmation carries a share link.",
         start_week=3, budget_allocated=30000, open_commitments=5000, plan_regs_base=481, plan_regs_stretch=781,
         exp_confirm_rate=0.914, p_attend_confirmed=0.859, base_incremental=86, stretch_incremental=322),
    dict(id="guest", name="Day-2 Guest Pass and Walk-ins", type="event_day", owner="Nisha Rao", hist_channel=None,
         description="Each Day-1 attendee gets one Day-2 guest pass; QR desk at the metro exit for walk-ins.",
         start_week=8, budget_allocated=10000, open_commitments=0, plan_regs_base=0, plan_regs_stretch=0,
         exp_confirm_rate=None, p_attend_confirmed=None, base_incremental=124, stretch_incremental=369),
    dict(id="amb", name="Pay-per-check-in Ambassadors", type="acquisition", owner="Meera Iyer", hist_channel="C01",
         description="60 campus ambassadors paid Rs 40 per verified attendee plus Rs 1,000 to each of the top 10.",
         start_week=1, budget_allocated=50000, open_commitments=18000, plan_regs_base=582, plan_regs_stretch=598,
         exp_confirm_rate=0.923, p_attend_confirmed=0.812, base_incremental=23, stretch_incremental=34),
    dict(id="organic", name="Organic", type="acquisition", owner="Arjun Verma", hist_channel="C06",
         description="Search and festival information pages for people actively looking for the event.",
         start_week=1, budget_allocated=15000, open_commitments=2000, plan_regs_base=262, plan_regs_stretch=264,
         exp_confirm_rate=0.900, p_attend_confirmed=0.867, base_incremental=None, stretch_incremental=None),
    dict(id="community", name="Community", type="acquisition", owner="Nisha Rao", hist_channel="C07",
         description="Student interest groups and community channels, nurtured without over-contacting.",
         start_week=1, budget_allocated=20000, open_commitments=3000, plan_regs_base=231, plan_regs_stretch=239,
         exp_confirm_rate=0.925, p_attend_confirmed=0.892, base_incremental=None, stretch_incremental=None),
    dict(id="paid", name="Paid Retargeting", type="acquisition", owner="Arjun Verma", hist_channel="C02",
         description="Paid social limited to retargeting people who already visited or started registration.",
         start_week=2, budget_allocated=25000, open_commitments=4000, plan_regs_base=290, plan_regs_stretch=290,
         exp_confirm_rate=0.853, p_attend_confirmed=0.586, base_incremental=None, stretch_incremental=None),
    dict(id="creators", name="Micro-creators", type="acquisition", owner="Nisha Rao", hist_channel="C03",
         description="Micro-creators from partner colleges, paid per completed registration.",
         start_week=2, budget_allocated=10000, open_commitments=2000, plan_regs_base=110, plan_regs_stretch=110,
         exp_confirm_rate=0.829, p_attend_confirmed=0.603, base_incremental=None, stretch_incremental=None),
    dict(id="reserve", name="Reserve", type="reserve", owner="Namita Meena", hist_channel=None,
         description="Uncommitted reserve. Released only through an approved decision; never allocated twice.",
         start_week=1, budget_allocated=20000, open_commitments=0, plan_regs_base=0, plan_regs_stretch=0,
         exp_confirm_rate=None, p_attend_confirmed=None, base_incremental=None, stretch_incremental=None),
]

# Strategic growth bridge from the three-slide deck (planning estimates, not measured outcomes).
WATERFALL = [
    ("2025 verified attendance", 2050, 2050, "absolute"),
    ("Same mix at Rs 3L (counterfactual)", 117, 117, "relative"),
    ("Cut cold paid + macro-creators", -346, -346, "relative"),
    ("Club Contingent League", 389, 535, "relative"),
    ("Show-Up Engine", 144, 298, "relative"),
    ("Squad Pass", 86, 322, "relative"),
    ("Guest passes + walk-ins", 124, 369, "relative"),
    ("Pay-per-check-in ambassadors", 23, 34, "relative"),
    ("Organic + community", 13, 21, "relative"),
    ("Target", 2600, 3400, "total"),
]

# Funnel planning table from the deck. The 2025 column is re-derived from raw data at runtime.
FUNNEL_PLAN = {
    "Reported platform reach": (666297, 687000, 805000),
    "Identified leads": (3500, 3610, 4230),
    "Registrations": (2800, 2888, 3384),
    "Registered attendees": (1925, 2351, 2906),
    "Unique walk-ins": (125, 150, 250),
    "Unique new Day-2 guests": (0, 99, 244),
    "Total verified attendees": (2050, 2600, 3400),
}

# ---------------------------------------------------------------------------
# Experiment decision thresholds (slide 3 of the deck).
THRESHOLDS = {
    "club": dict(decision_week=4, min_pitches=20, scale_at=250, change_at=150, stop_transfer_cap=40000),
    "showup": dict(min_starts_per_arm=500, scale_pts=5.0, stop_pts=-5.0, alpha=0.05, deposit_inr=99,
                   hist_confirmed_per_100=81.3, hist_attended_per_100=62.6),
    "squad": dict(min_registrants_per_arm=300, scale_k=0.20, change_k=0.10, squad_size=4, fast_lane_cap=300),
    "guest": dict(min_passes=200, scale_rate=0.06, change_rate=0.03, pilot_week=8),
    "amb": dict(min_cohort=20, scale_per_amb=10.0, change_per_amb=2.0, payout_per_attendee=40,
                top_bonus=1000, top_n=10, max_allocation=50000),
}

EXPERIMENT_NAMES = {
    "club": "Club Contingent League",
    "showup": "Show-Up Engine: Rs 99 refundable deposit vs no deposit",
    "squad": "Squad Pass: squad link vs plain link",
    "guest": "Day-2 Guest Pass pilot",
    "amb": "Campus ambassadors: pay-per-check-in",
}

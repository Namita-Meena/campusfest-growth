"""AI Growth Analyst and Copilot.

Architecture: the language model never sees raw tables and never does arithmetic
on its own. It calls a small set of deterministic Python tools (below) through
Gemini function calling; each tool reads the CURRENT database state at call
time, so answers always reflect the latest saved edits. The model has no tool
that writes data: draft_task only prepares a draft that a person must approve
in the UI. No model-generated code or SQL is ever executed.
"""
from __future__ import annotations

import json
import time
from datetime import date

from . import analytics as an
from . import config as C
from . import database as db
from . import forecasting as fc
from . import historical as hist

DEFAULT_MODELS = ["gemini-3.8-flash", "gemini-3.6-flash"]
MAX_TOOL_ROUNDS = 8

SYSTEM_INSTRUCTION = """You are the CampusFest AI Growth Analyst and Copilot. Your objective is to maximize unique, verified external attendees within the festival's approved budget.

Use current application data and the original historical dataset to answer data-dependent questions. Retrieve relevant data before responding.

Use deterministic calculation functions for numerical and statistical analysis.

For recommendations, clearly explain the finding, supporting evidence, business implication, recommended action and uncertainty.

Distinguish historical observations, current simulated data, forecasts and assumptions.

Do not fabricate missing information, infer causation without evidence or count attendees more than once.

Follow the configured campaign decision rules and minimum sample requirements.

Respect available uncommitted budgets and operational constraints.

When information is insufficient, clearly say what is missing.

When asked to create a task, propose a structured draft with its title, campaign, owner, description, deadline, priority and supporting evidence.

Never save or modify application data without explicit user approval.

Maintain conversational context while retrieving the latest relevant data.

Be concise, professional, analytical and action-oriented.

Operating rules for this application:
- CampusFest Bengaluru 2027 (20-21 Feb 2027) is a planning scenario. Live campaign numbers are SIMULATED for a selected campaign week; the 2025 dataset is the only observed history. Say which one you are quoting.
- Always call a tool before quoting any number, even if you saw it earlier in the conversation: data may have been edited since. Never do arithmetic in your head when a tool can return the figure; for a significance test call two_proportion_test.
- Every tool reads the latest saved data. Quote numbers exactly as returned, with units. Use the Indian rupee sign.
- Recommendations (Scale, Change / Fix, Stop, Continue Monitoring) come from get_experiment_decisions and get_campaign_metrics. Report the rule, the threshold, the sample check and the action; do not invent a different verdict. If you disagree, say so separately and explain why.
- Money can only move from uncommitted budget (allocation minus spend minus open commitments). Use get_budget_availability; never propose moving more than is uncommitted, and never count the reserve twice.
- The Show-Up Engine is an intervention that changes rates for people acquired by other campaigns; it never adds people. Walk-ins and Day-2 guests have no registration. Do not add the deck's incremental estimates to campaign attendance.
- For history use get_historical_metrics (optionally as of a date) or query_historical_data. If a needed field is not in the data dictionary (for example age, gender, college name), say the data cannot answer and name what would be needed. Do not estimate it.
- draft_task only creates a draft shown to the user with Approve and Reject buttons. You cannot save tasks or change data. After drafting, tell the user it is waiting for their approval; never say it has been saved or created.
- Keep answers short: lead with the answer, then evidence as a few bullets, then the action and the main uncertainty. No preamble.
"""


def _r(x, n=3):
    return None if x is None else round(float(x), n)


class Toolbox:
    """Deterministic data tools exposed to the model. One instance per question."""

    def __init__(self, week: int):
        self.week = int(week)
        self.calls: list = []
        self.pending_task: dict | None = None

    # -- helpers -------------------------------------------------------
    def _ctx(self):
        # Every write clears the cache, so this is always the latest saved state without re-reading the database per tool call.
        return an.build_context(self.week, db.load_all())

    @staticmethod
    def _find(ctx, name: str):
        n = (name or "").strip().lower()
        if not n:
            return None
        cs = ctx["campaigns"]
        for c in cs:
            if n in (c["id"].lower(), c["name"].lower()):
                return c
        hits = [c for c in cs if n in c["name"].lower() or any(w in c["name"].lower() for w in n.split() if len(w) > 3)]
        return hits[0] if len(hits) >= 1 else None

    @staticmethod
    def _campaign_view(c: dict) -> dict:
        p, r = c["projection"], c["recommendation"]
        v = {"campaign": c["name"], "type": c["type"], "owner": c["owner"], "status": c["status"],
             "dates": f"{c.get('start_date')} to {c.get('end_date')}",
             "budget": {"allocated": c["budget_allocated"], "spent_to_date": c["spent"], "open_commitments": c["open_commitments"],
                        "committed": c["committed"], "uncommitted": c["uncommitted"]}}
        if p:
            v["funnel_to_date"] = {"reported_reach_summed_not_unique": c["reach"], "leads": c["leads"], "registration_starts": c["reg_starts"],
                                   "registrations": c["registrations"], "confirmed": c["confirmed"],
                                   "lead_to_registration": _r(c["lead_to_registration"]), "start_to_registration": _r(c["start_to_registration"]),
                                   "confirm_rate": _r(c["confirm_rate"]), "expected_confirm_rate_2025_channel": c.get("exp_confirm_rate")}
            v["cost"] = {"per_registration": _r(c["cost_per_registration"], 0), "per_projected_attendee_full_allocation": _r(c["cost_per_projected_attendee"], 0)}
            v["projection_forecast"] = p
            v["verified_attendees_actual"] = c.get("verified_attendees") if c.get("verified_attendees") is not None else "not yet available (festival has not happened in the simulation)"
        else:
            v["note"] = ("Intervention: changes confirm and attendance rates of people acquired by other campaigns; has no registrations of its own."
                         if c["type"] == "intervention" else "Event-day campaign producing walk-ins and new Day-2 guests, who hold no registration."
                         if c["type"] == "event_day" else "Uncommitted reserve.")
            if c.get("base_incremental") is not None:
                v["strategic_incremental_estimate_from_deck"] = {"base": c["base_incremental"], "stretch": c["stretch_incremental"],
                                                                  "note": "Planning estimate, not a measured outcome and not total campaign attendance."}
        if r:
            v["recommendation"] = {k: r[k] for k in ("state", "metric_label", "metric_value", "threshold", "sample", "sample_ok", "action")}
        return v

    # -- tools ---------------------------------------------------------
    def get_dashboard_summary(self) -> dict:
        ctx = self._ctx()
        t = ctx["totals"]
        return {"data_label": ctx["data_label"], "simulated_week": ctx["week"], "week_dates": ctx["week_dates"],
                "latest_week_with_recorded_data": ctx["data_week"], "festival": f"{C.FESTIVAL}, {C.FEST_DATES}",
                "north_star": "unique, verified external attendees",
                "targets": {"base": ctx["forecast"]["base_target"], "stretch": ctx["forecast"]["stretch_target"], "attendance_2025_actual": 2050},
                "to_date": {"registrations": t["registrations"], "plan_registrations_to_date": t["plan_registrations_to_date"],
                            "confirmed": t["confirmed"], "confirm_rate": _r(t["confirm_rate"]), "leads": t["leads"],
                            "registration_starts": t["reg_starts"], "reported_reach_summed_not_unique": t["reach"],
                            "actual_verified_attendees": t["actual_verified_attendees"] if t["actual_verified_attendees"] is not None else "not yet available"},
                "forecast": ctx["forecast"], "budget": ctx["budget"],
                "cost": {"per_registration": _r(t["cost_per_registration"], 0), "per_projected_attendee": _r(t["cost_per_projected_attendee"], 0)},
                "alerts": [f"[{sev}] {txt}" for sev, txt in ctx["alerts"]]}

    def get_campaign_metrics(self, campaign: str = "") -> dict:
        ctx = self._ctx()
        if campaign:
            c = self._find(ctx, campaign)
            if not c:
                return {"error": f"No campaign matches '{campaign}'.", "available_campaigns": [x["name"] for x in ctx["campaigns"]]}
            return {"simulated_week": ctx["week"], "data_label": ctx["data_label"], **self._campaign_view(c)}
        return {"simulated_week": ctx["week"], "data_label": ctx["data_label"], "campaigns": [self._campaign_view(c) for c in ctx["campaigns"]]}

    def compare_campaigns(self, campaign_a: str, campaign_b: str) -> dict:
        ctx = self._ctx()
        a, b = self._find(ctx, campaign_a), self._find(ctx, campaign_b)
        if not a or not b:
            return {"error": "Could not match both campaigns.", "available_campaigns": [x["name"] for x in ctx["campaigns"]]}
        va, vb = self._campaign_view(a), self._campaign_view(b)
        diff = {}
        if a["projection"] and b["projection"]:
            for k in ("registrations", "confirmed", "spent"):
                diff[k] = a[k] - b[k]
            for k in ("confirm_rate", "lead_to_registration", "cost_per_registration", "cost_per_projected_attendee"):
                diff[k] = None if a[k] is None or b[k] is None else _r(a[k] - b[k])
            diff["projected_attendees"] = _r(a["projection"]["projected_attendees"] - b["projection"]["projected_attendees"], 1)
            diff["pace_vs_plan"] = None if a["projection"]["pace_vs_plan"] is None or b["projection"]["pace_vs_plan"] is None else _r(a["projection"]["pace_vs_plan"] - b["projection"]["pace_vs_plan"])
        return {"simulated_week": ctx["week"], "a": va, "b": vb, "a_minus_b": diff or "Not comparable on funnel metrics: at least one is not an acquisition campaign."}

    def get_experiment_decisions(self, experiment: str = "") -> dict:
        ctx = self._ctx()
        out = {}
        for k, d in {**ctx["decisions"], "guardrail": ctx["guardrail"]}.items():
            out[k] = {"name": d["name"] if k != "guardrail" else "Week-6 guardrail", "state": d["state"], "metric": f"{d['metric_label']}: {d['metric_value']}",
                      "thresholds": d["threshold"], "minimum_sample": d["sample"], "sample_ok": d["sample_ok"], "recommended_action": d["action"],
                      "proposed_transfer": d.get("transfer"), "inputs": d.get("inputs"), "inputs_recorded_week": d.get("inputs_recorded_week"),
                      "details": {kk: vv for kk, vv in d.get("details", {}).items()}}
        e = (experiment or "").strip().lower()
        if e:
            alias = {"club": "club", "contingent": "club", "show": "showup", "deposit": "showup", "squad": "squad", "referral": "squad",
                     "guest": "guest", "plus": "guest", "amb": "amb", "guard": "guardrail"}
            key = next((v for k, v in alias.items() if k in e), None)
            if key and key in out:
                out = {key: out[key]}
        return {"simulated_week": ctx["week"], "states_possible": ["Scale", "Change / Fix", "Stop", "Continue Monitoring"],
                "approval_rule": "Recommendations are never applied automatically; a person approves or rejects them on the Experiments page.",
                "decisions": json.loads(json.dumps(out, default=str))}

    def get_budget_availability(self) -> dict:
        ctx = self._ctx()
        club = next((c for c in ctx["campaigns"] if c["id"] == "club"), None)
        cap = C.THRESHOLDS["club"]["stop_transfer_cap"]
        return {"simulated_week": ctx["week"], "totals": ctx["budget"],
                "definition": "uncommitted = allocated - spent to date - open commitments. Only uncommitted money can be reallocated.",
                "by_campaign": [{"campaign": c["name"], "allocated": c["budget_allocated"], "spent_to_date": c["spent"],
                                 "open_commitments": c["open_commitments"], "uncommitted": c["uncommitted"]} for c in ctx["campaigns"]],
                "reallocation_limits": {"reserve_uncommitted": ctx["budget"]["reserve_uncommitted"],
                                        "club_league_stop_rule_cap": cap,
                                        "club_league_uncommitted": club["uncommitted"] if club else None,
                                        "club_league_transferable_now": max(0, min(cap, club["uncommitted"])) if club else None,
                                        "note": "The reserve is reduced when an approved decision moves it, so it cannot be allocated twice."},
                "approved_transfers_so_far": [{"week": l["week"], "from": l["transfer_from"], "to": l["transfer_to"], "amount": l["amount_moved"]}
                                              for l in ctx["decision_logs"] if l.get("amount_moved")]}

    def get_attendance_forecast(self) -> dict:
        ctx = self._ctx()
        return {"simulated_week": ctx["week"], "data_label": "FORECAST from simulated week data and stated assumptions", "forecast": ctx["forecast"],
                "by_campaign": [{"campaign": c["name"], **c["projection"]} for c in ctx["campaigns"] if c["projection"]],
                "assumptions": {k: ctx["settings"][k] for k in ("waitlist_recovery", "reminder_lift", "p_attend_unconfirmed", "walkins_expected",
                                                               "guest_redemption_rate", "day1_share", "venue_capacity")},
                "historical_basis_2025": {"attendance_among_confirmed": 0.77, "attendance_among_unconfirmed": 0.0, "walk_ins": 125},
                "guardrail": {"state": ctx["guardrail"]["state"], "detail": ctx["guardrail"]["action"]}}

    def simulate_scenario(self, campaign: str = "", registrations_to_date: int = -1, show_up_engine_active: bool = True,
                          expected_walkins: int = -1, guest_redemption_rate: float = -1.0, reminder_lift: float = -1.0) -> dict:
        state = db.load_all()
        base = an.build_context(self.week, state)
        sim_state = {**state, "campaigns": [dict(c) for c in state["campaigns"]], "campaign_metrics": [dict(m) for m in state["campaign_metrics"]],
                     "settings": dict(state["settings"])}
        changes = []
        if campaign and registrations_to_date >= 0:
            c = self._find(base, campaign)
            if not c or not c["projection"]:
                return {"error": f"'{campaign}' is not an acquisition campaign with registrations."}
            rows = sorted([m for m in sim_state["campaign_metrics"] if m["campaign_id"] == c["id"] and m["week"] <= base["data_week"]], key=lambda m: m["week"])
            cur = sum(m["registrations"] for m in rows)
            ratio = registrations_to_date / cur if cur else 0
            for m in rows:
                m["registrations"] = m["registrations"] * ratio
                m["confirmed"] = m["confirmed"] * ratio
            changes.append(f"{c['name']} registrations to date {cur} -> {registrations_to_date} (confirmed scaled in proportion)")
        if not show_up_engine_active:
            for c in sim_state["campaigns"]:
                if c["id"] == "showup":
                    c["status"] = "Stopped"
            changes.append("Show-Up Engine switched off")
        for key, val, lab in (("walkins_expected", expected_walkins, "expected walk-ins"), ("guest_redemption_rate", guest_redemption_rate, "guest redemption rate"),
                              ("reminder_lift", reminder_lift, "reminder lift")):
            if val is not None and val >= 0:
                sim_state["settings"][key] = val
                changes.append(f"{lab} = {val}")
        sim = an.build_context(self.week, sim_state)
        return {"note": "HYPOTHETICAL scenario. Nothing was saved.", "changes_applied": changes or ["none (returns the current forecast)"],
                "current_forecast": base["forecast"]["expected_attendance"], "scenario_forecast": sim["forecast"]["expected_attendance"],
                "difference": sim["forecast"]["expected_attendance"] - base["forecast"]["expected_attendance"],
                "scenario_detail": sim["forecast"], "scenario_guardrail": sim["guardrail"]["state"],
                "scenario_club_decision": sim["decisions"].get("club", {}).get("state")}

    def get_task_summary(self, status: str = "", campaign: str = "") -> dict:
        ctx = self._ctx()
        names = {c["id"]: c["name"] for c in ctx["campaigns"]}
        tasks = ctx["tasks"]
        if status:
            tasks = [t for t in tasks if t["status"].lower() == status.strip().lower()]
        if campaign:
            c = self._find(ctx, campaign)
            tasks = [t for t in tasks if c and t.get("campaign_id") == c["id"]]
        today = C.week_end(self.week)
        rows = [{"title": t["title"], "campaign": names.get(t.get("campaign_id"), t.get("campaign_id") or "General"), "owner": t["owner"],
                 "deadline": t["deadline"], "priority": t["priority"], "status": t["status"], "source": t["source"],
                 "overdue_in_simulated_week": bool(t["status"] != "Completed" and str(t["deadline"]) < str(today))} for t in tasks]
        rows.sort(key=lambda r: r["deadline"])
        counts = {}
        for r in rows:
            counts[r["status"]] = counts.get(r["status"], 0) + 1
        return {"simulated_week": ctx["week"], "simulated_week_ends": str(today), "count": len(rows), "by_status": counts, "tasks": rows[:40]}

    def get_decision_log(self) -> dict:
        ctx = self._ctx()
        logs = sorted(ctx["decision_logs"], key=lambda l: l["created_at"], reverse=True)[:25]
        return {"count": len(ctx["decision_logs"]), "latest": [{k: l.get(k) for k in ("created_at", "week", "decision_key", "recommendation", "outcome",
                                                                                 "metric", "action", "amount_moved", "transfer_from", "transfer_to", "note")} for l in logs]}

    def get_historical_metrics(self, as_of_date: str = "") -> dict:
        try:
            snap = hist.snapshot(as_of_date or None)
            camp = hist.by_campaign(as_of_date or None)
        except Exception as e:
            return {"error": f"Could not compute the snapshot: {e}. Use a date as YYYY-MM-DD between 2025-01-15 and 2025-04-20."}
        return {"data_label": "HISTORICAL CampusFest 2025 (observed; fictional synthetic dataset supplied by RISA Labs; festival 12-13 April 2025)",
                "snapshot": snap, "by_campaign": camp.to_dict("records"),
                "weekly_external_registrations_weeks_1_to_12": hist.weekly_registrations() if not as_of_date else "only for full history",
                "attribution": "Registrations and attendees are attributed to the recorded acquisition source of the registration; leads to the person's first campaign. Walk-ins are unattributed."}

    def query_historical_data(self, table: str, filters: list | None = None, group_by: list | None = None,
                              aggregate: str = "count_rows", column: str = "") -> dict:
        return hist.query(table, list(filters or []), list(group_by or []), aggregate or "count_rows", column or None)

    def get_data_dictionary(self) -> dict:
        d = hist.data_dictionary()
        live = {"campaigns": "one row per 2027 campaign: budget, owner, status, plan", "campaign_metrics": "weekly simulated reach, leads, registration starts, registrations, confirmed, spend",
                "experiment_results": "inputs of the five experiments", "tasks": "execution tasks", "decision_logs": "approved / rejected recommendations", "settings": "targets and forecast assumptions"}
        return {"historical_tables": d["tables"], "historical_field_meanings": [f"{x['source_table']}.{x['field']}: {x['meaning']}" for x in d["field_meanings"]][:90],
                "cleaning_rules": d["cleaning_rules"], "NOT_available_anywhere": d["not_available_in_dataset"], "live_simulated_tables": live}

    def two_proportion_test(self, control_successes: int, control_total: int, treatment_successes: int, treatment_total: int) -> dict:
        r = fc.two_proportion_test(int(control_successes), int(control_total), int(treatment_successes), int(treatment_total))
        if r.get("valid"):
            r = {k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()}
            r["method"] = "two-sided two-proportion z-test, pooled standard error; 95% Wald interval for the difference"
        return r

    def draft_task(self, title: str, campaign: str = "", owner: str = "", description: str = "", deadline: str = "",
                   priority: str = "Medium", supporting_evidence: str = "") -> dict:
        ctx = self._ctx()
        c = self._find(ctx, campaign)
        try:
            dl = str(date.fromisoformat(str(deadline)[:10]))
        except Exception:
            dl = str(C.week_end(min(self.week + 1, C.TOTAL_WEEKS)))
        pr = priority.capitalize() if priority and priority.capitalize() in C.TASK_PRIORITIES else "Medium"
        self.pending_task = {"title": (title or "Untitled task").strip()[:200], "campaign_id": c["id"] if c else None,
                             "campaign_name": c["name"] if c else "General", "owner": owner.strip() or (c["owner"] if c else "Unassigned"),
                             "description": description.strip(), "deadline": dl, "priority": pr, "status": "To Do",
                             "evidence": supporting_evidence.strip(), "source": "AI-generated"}
        return {"status": "DRAFT_ONLY_NOT_SAVED", "draft": self.pending_task,
                "next_step": "The draft is now shown to the user with Approve and Reject buttons. It is saved only if they press Approve."}


_S, _I, _N, _B = {"type": "string"}, {"type": "integer"}, {"type": "number"}, {"type": "boolean"}
_ARR = {"type": "array", "items": {"type": "string"}}


def _decl(name, desc, props=None, required=None):
    d = {"name": name, "description": desc}
    if props:                                    # tools without arguments carry no parameter schema at all
        d["parameters"] = {"type": "object", "properties": props}
        if required:
            d["parameters"]["required"] = required
    return d


DECLARATIONS = [
    _decl("get_dashboard_summary", "Current simulated-week overview: targets, registrations, confirmations, attendance forecast, budget position, costs and active alerts. Start here for 'are we on track' questions."),
    _decl("get_campaign_metrics", "Funnel, conversion rates, costs, budget, projection and the decision-engine recommendation for one campaign, or for all campaigns if 'campaign' is omitted.",
          {"campaign": {**_S, "description": "Campaign name or part of it, e.g. 'Club Contingent League'. Omit for all campaigns."}}),
    _decl("compare_campaigns", "Side-by-side metrics and differences for two campaigns.", {"campaign_a": _S, "campaign_b": _S}, ["campaign_a", "campaign_b"]),
    _decl("get_experiment_decisions", "Scale / Change / Stop / Monitor decisions for the five experiments and the week-6 guardrail, with metric, thresholds, minimum sample, statistical test and recommended action.",
          {"experiment": {**_S, "description": "Optional: club, deposit (Show-Up Engine), squad, guest, ambassadors or guardrail."}}),
    _decl("get_budget_availability", "Allocated, spent, committed and uncommitted budget per campaign, reserve available, and how much can actually be reallocated right now."),
    _decl("get_attendance_forecast", "Attendance forecast broken down by campaign plus walk-ins and Day-2 guests, with the formula and assumptions."),
    _decl("simulate_scenario", "Hypothetical what-if forecast. Nothing is saved. Change one campaign's registrations to date and/or forecast assumptions.",
          {"campaign": {**_S, "description": "Acquisition campaign whose registrations to change (optional)."},
           "registrations_to_date": {**_I, "description": "Hypothetical cumulative registrations for that campaign at the current week."},
           "show_up_engine_active": {**_B, "description": "Set false to see the forecast without the Show-Up Engine."},
           "expected_walkins": _I, "guest_redemption_rate": {**_N, "description": "0-1, e.g. 0.06"}, "reminder_lift": {**_N, "description": "0-1 points added to attendance among confirmed, e.g. 0.0265"}}),
    _decl("get_task_summary", "Tasks with owner, deadline, priority, status and overdue flag. Optional filters.",
          {"status": {**_S, "description": "To Do, In Progress, Blocked or Completed"}, "campaign": _S}),
    _decl("get_decision_log", "Recommendations that were approved or rejected, including budget actually moved."),
    _decl("get_historical_metrics", "Observed CampusFest 2025 funnel from the original dataset (cleaned): reach, leads, registrations, status counts, attendees, walk-ins, spend, targets in effect, plus a per-campaign table. Optionally as of the end of a given day.",
          {"as_of_date": {**_S, "description": "YYYY-MM-DD between 2025-01-15 and 2025-04-20. Omit for the full history."}}),
    _decl("query_historical_data", "Restricted analytical query on one cleaned 2025 table for unfamiliar questions: filter, group and aggregate. Tables: people_summary (one row per identified person with funnel outcome flags), people, registrations, registration_history, checkins, interactions, daily_marketing, campaigns, targets. Call get_data_dictionary first if unsure of column names.",
          {"table": _S,
           "filters": {**_ARR, "description": "Each filter is 'column op value'. Ops: ==, !=, >, >=, <, <=, in, contains. Examples: 'person_type == external', 'attended_verified == true', 'occurred_at <= 2025-04-12', 'result in admitted,denied'."},
           "group_by": {**_ARR, "description": "Up to two columns to group by."},
           "aggregate": {**_S, "description": "count_rows (default), count_distinct, sum, mean, min or max. The mean of a true/false column is a rate."},
           "column": {**_S, "description": "Column to aggregate (not needed for count_rows)."}}, ["table"]),
    _decl("get_data_dictionary", "Tables, columns and field meanings available in the historical dataset and the live workspace, plus an explicit list of things that are NOT available (e.g. age, gender, college). Use it to decide whether a question can be answered."),
    _decl("two_proportion_test", "Two-sided two-proportion z-test with a 95% confidence interval. Use for any 'is this difference significant' question.",
          {"control_successes": _I, "control_total": _I, "treatment_successes": _I, "treatment_total": _I},
          ["control_successes", "control_total", "treatment_successes", "treatment_total"]),
    _decl("draft_task", "Prepare a task DRAFT for the user to approve or reject. This does NOT save anything.",
          {"title": _S, "campaign": {**_S, "description": "Campaign name the task belongs to."},
           "owner": {**_S, "description": f"One of: {', '.join(C.OWNERS)}. Defaults to the campaign owner."},
           "description": _S, "deadline": {**_S, "description": "YYYY-MM-DD"}, "priority": {**_S, "description": "High, Medium or Low"},
           "supporting_evidence": {**_S, "description": "The numbers and rule that justify the task."}}, ["title", "campaign", "description", "supporting_evidence"]),
]
TOOL_NAMES = [d["name"] for d in DECLARATIONS]


def run_tool(box: Toolbox, name: str, args: dict) -> dict:
    """Execute one whitelisted tool with defensive error handling."""
    if name not in TOOL_NAMES:
        return {"error": f"Unknown tool '{name}'."}
    try:
        out = getattr(box, name)(**(args or {}))
    except TypeError as e:
        out = {"error": f"Bad arguments for {name}: {e}"}
    except Exception as e:  # never crash the chat on a data problem
        out = {"error": f"{type(e).__name__}: {e}"}
    box.calls.append({"tool": name, "args": args or {}, "ok": "error" not in out})
    return json.loads(json.dumps(out, default=str))


def is_configured() -> bool:
    return bool(db.get_secret("GEMINI_API_KEY"))


def model_candidates() -> list:
    chosen = db.get_secret("GEMINI_MODEL")
    return ([str(chosen)] if chosen else []) + [m for m in DEFAULT_MODELS if m != chosen]


_discovered: list = []


def available_models(client) -> list:
    """Ask the API which text models this key may actually call (cached per process).

    Model availability differs from key to key and changes over time, so the app never
    depends on a hard-coded name alone: if every configured candidate is rejected, it
    picks a usable model from this list instead of failing.
    """
    global _discovered
    if _discovered:
        return _discovered
    out = []
    try:
        for m in client.models.list():
            name = (getattr(m, "name", "") or "").split("/")[-1]
            actions = getattr(m, "supported_actions", None) or []
            if not name or (actions and "generateContent" not in actions):
                continue
            low = name.lower()
            if any(w in low for w in ("embedding", "aqa", "imagen", "veo", "tts", "image", "audio", "live",
                                      "native", "learnlm", "gemma", "robotics", "computer-use")):
                continue
            out.append(name)
    except Exception as e:
        print(f"[copilot] could not list models: {type(e).__name__}", flush=True)
        return []

    def rank(n: str):
        low = n.lower()
        ver = 0.0
        for part in low.replace("gemini-", "").split("-"):
            try:
                ver = float(part)
                break
            except ValueError:
                continue
        return (0 if ("flash" in low and "lite" not in low) else 1 if "flash" in low else 2,
                1 if any(w in low for w in ("preview", "exp", "thinking", "latest")) else 0,
                -ver, len(n))

    _discovered = sorted(out, key=rank)
    print(f"[copilot] models available to this key: {', '.join(_discovered[:8])}", flush=True)
    return _discovered


def _friendly_error(e: Exception) -> str:
    msg = str(e)
    low = msg.lower()
    if "429" in msg or "resource_exhausted" in low or "quota" in low:
        return "The AI model's rate limit or free quota has been reached. Please wait a minute and try again."
    if "timeout" in low or "timed out" in low or "deadline" in low:
        return "The AI model took too long to respond. Please try again; shorter, more specific questions are faster."
    if "api key" in low or "api_key" in low or "401" in msg or "403" in msg or "permission" in low:
        return "The AI model rejected the API key. Check GEMINI_API_KEY in the app secrets."
    return f"The AI model could not answer. Please try again. First error: {msg[:400]}"


def ask(question: str, history: list, week: int, client=None) -> dict:
    """Answer one question. history: [{'role': 'user'|'assistant', 'content': str}, ...] of earlier turns."""
    from google import genai
    from google.genai import types

    box = Toolbox(week)
    if client is None:
        key = db.get_secret("GEMINI_API_KEY")
        if not key:
            return {"text": None, "error": "The AI model is not configured (GEMINI_API_KEY is missing).", "calls": [], "pending_task": None, "model": None, "details": []}
        client = genai.Client(api_key=str(key).strip(), http_options=types.HttpOptions(timeout=75_000))
    db.load_all(force=True)  # one fresh read from the database per question
    names = [c["name"] for c in an.build_context(week)["campaigns"]]
    system = (SYSTEM_INSTRUCTION + f"\nCurrent simulated campaign week: {week} of {C.TOTAL_WEEKS} ({C.week_start(week)} to {C.week_end(week)}). "
              f"Campaign start {C.CAMPAIGN_START}; festival {C.FEST_DATES}.\nCampaigns: {', '.join(names)}.\nTask owners: {', '.join(C.OWNERS)}.")
    def make_config(fast: bool):
        return types.GenerateContentConfig(
            system_instruction=system, temperature=0.2,
            tools=[types.Tool(function_declarations=DECLARATIONS)],
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            thinking_config=types.ThinkingConfig(thinking_level="low") if fast else None)
    contents = []
    for h in history[-12:]:
        if h.get("content"):
            contents.append(types.Content(role="user" if h["role"] == "user" else "model", parts=[types.Part(text=str(h["content"])[:6000])]))
    contents.append(types.Content(role="user", parts=[types.Part(text=question)]))

    errors, queue, tried, discovered_added = [], list(model_candidates()), set(), False
    while queue:
        model = queue.pop(0)
        if model in tried:
            continue
        tried.add(model)
        # Gemini 3 models accept a low thinking level (faster answers); if a model rejects it, retry without.
        variants = [True, False] if model.startswith("gemini-3") else [False]
        attempt = 0
        while variants:
            fast = variants.pop(0)
            attempt += 1
            try:
                box.calls.clear()
                box.pending_task = None
                text = _converse(client, types, model, contents, make_config(fast), box)
                return {"text": text, "error": None, "calls": box.calls, "pending_task": box.pending_task, "model": model, "details": errors}
            except Exception as e:
                msg = f"{type(e).__name__}: {str(e)[:600]}"
                errors.append(f"{model}{' (low thinking)' if fast else ''}: {msg}")
                print(f"[copilot] {errors[-1]}", flush=True)       # visible in the hosting logs; never contains the API key
                low = msg.lower()
                if ("503" in low or "overloaded" in low or "unavailable" in low) and attempt <= 2:
                    time.sleep(3)                                   # busy model: one more try with the same settings
                    variants.insert(0, fast)
                    continue
                if not (fast and ("thinking" in low or "invalid_argument" in low or "400" in low)):
                    break                                           # move on to the next model
        if not queue and not discovered_added:
            # Every configured name was rejected. Ask the API which models this key can use.
            discovered_added = True
            queue = [m for m in available_models(client) if m not in tried][:3]
            if queue:
                errors.append("Falling back to models reported as available for this key: " + ", ".join(queue))
    avail = available_models(client)
    if avail:
        errors.append("Models this key reports as available: " + ", ".join(avail[:10]))
    message = _friendly_error(Exception(errors[0] if errors else "unknown error"))
    if tried:
        message += f" Tried: {', '.join(sorted(tried))}."
        message += (f" Models this key can use include: {', '.join(avail[:5])}. Set GEMINI_MODEL in the app secrets to one of them."
                    if avail else " The key could not list any usable model either, so it may be restricted or from another project.")
    return {"text": None, "error": message, "calls": box.calls, "pending_task": None, "model": None, "details": errors}


def _converse(client, types, model, contents, config, box) -> str:
    contents = list(contents)
    resp = None
    for _ in range(MAX_TOOL_ROUNDS):
        resp = client.models.generate_content(model=model, contents=contents, config=config)
        calls = resp.function_calls or []
        if not calls:
            break
        contents.append(resp.candidates[0].content)  # unchanged, so thought signatures are preserved
        parts = []
        for fc_ in calls:
            result = run_tool(box, fc_.name, dict(fc_.args or {}))
            parts.append(types.Part(function_response=types.FunctionResponse(name=fc_.name, response={"result": result}, id=getattr(fc_, "id", None))))
        contents.append(types.Content(role="user", parts=parts))
    text = None
    try:
        text = resp.text if resp is not None else None
    except Exception:
        text = None
    if not text:
        text = "I retrieved the data but could not compose an answer. Please rephrase the question or ask about one campaign at a time."
    return text

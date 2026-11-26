"""Single source of truth for live (simulated 2027) analytics and all validated writes.

Every page and the AI copilot call build_context(week); nothing keeps its own
copy of the numbers, so an edit saved anywhere is reflected everywhere.
"""
from __future__ import annotations

import uuid
from datetime import date

from . import config as C
from . import database as db
from . import decision_engine as de
from . import forecasting as fc
from .seed import now_iso

_ORDER = {c["id"]: i for i, c in enumerate(C.CAMPAIGN_SEED)}
METRIC_FIELDS = ["reach", "leads", "reg_starts", "registrations", "confirmed", "spend"]


class ValidationError(ValueError):
    pass


def _i(x, default=0):
    try:
        return int(round(float(x)))
    except (TypeError, ValueError):
        return default


def data_week(week: int, metrics: list) -> int:
    last = max((m["week"] for m in metrics), default=0)
    return max(0, min(int(week), last))


def cumulative(metrics: list, campaign_id: str, week: int) -> dict:
    out = {f: 0 for f in METRIC_FIELDS}
    for m in metrics:
        if m["campaign_id"] == campaign_id and m["week"] <= week:
            for f in METRIC_FIELDS:
                out[f] += _i(m.get(f))
    return out


def latest_experiment(rows: list, exp: str, week: int) -> tuple:
    cands = [r for r in rows if r["experiment"] == exp and r["week"] <= week]
    if not cands:
        return {}, None
    r = max(cands, key=lambda x: x["week"])
    return dict(r.get("inputs") or {}), r["week"]


def build_context(week: int, state: dict | None = None) -> dict:
    """Compute every live metric for the selected simulated week."""
    state = state or db.load_all()
    s = {**C.DEFAULT_SETTINGS, **state["settings"]}
    week = max(1, min(int(week), C.TOTAL_WEEKS))
    metrics = state["campaign_metrics"]
    dw = data_week(week, metrics)
    raw = sorted([c for c in state["campaigns"] if not c.get("archived")], key=lambda c: (_ORDER.get(c["id"], 99), c["name"]))
    by_id = {c["id"]: c for c in raw}
    showup_active = by_id.get("showup", {}).get("status") == "Active" if "showup" in by_id else False
    guest_active = by_id.get("guest", {}).get("status") in ("Active", "Planned") if "guest" in by_id else False

    campaigns = []
    for c in raw:
        cum = cumulative(metrics, c["id"], dw)
        e = {**c, **cum}
        e["spent"] = cum["spend"]
        e["budget_allocated"] = _i(c.get("budget_allocated"))
        e["open_commitments"] = _i(c.get("open_commitments"))
        e["committed"] = e["spent"] + e["open_commitments"]
        e["uncommitted"] = e["budget_allocated"] - e["committed"]
        e["lead_to_registration"] = fc.safe_div(cum["registrations"], cum["leads"])
        e["start_to_registration"] = fc.safe_div(cum["registrations"], cum["reg_starts"])
        e["confirm_rate"] = fc.safe_div(cum["confirmed"], cum["registrations"])
        e["cost_per_registration"] = fc.safe_div(e["spent"], cum["registrations"])
        e["projection"] = fc.project_campaign(c, cum, dw, s, showup_active)
        pa = (e["projection"] or {}).get("projected_attendees")
        e["cost_per_projected_attendee"] = fc.safe_div(e["budget_allocated"], pa) if pa else None
        campaigns.append(e)

    forecast = fc.total_forecast([c["projection"] for c in campaigns], s, guest_active)
    forecast["show_up_engine_active"] = showup_active
    forecast["guest_pass_active"] = guest_active

    alloc = sum(c["budget_allocated"] for c in campaigns)
    spent = sum(c["spent"] for c in campaigns)
    committed = sum(c["committed"] for c in campaigns)
    reserve = by_id.get("reserve")
    reserve_unc = next((c["uncommitted"] for c in campaigns if c["id"] == "reserve"), 0)
    budget = {"approved_budget": _i(s["total_budget"]), "allocated": alloc, "unallocated": _i(s["total_budget"]) - alloc,
              "spent_to_date": spent, "open_commitments": committed - spent, "committed": committed,
              "uncommitted": alloc - committed, "reserve_uncommitted": reserve_unc,
              "over_budget": alloc > _i(s["total_budget"])}

    tot = {f: sum(c[f] for c in campaigns) for f in ("reach", "leads", "reg_starts", "registrations", "confirmed")}
    plan_regs_to_date = sum((c["projection"] or {}).get("plan_registrations_to_date", 0) for c in campaigns)
    totals = {**tot, "plan_registrations_to_date": round(plan_regs_to_date),
              "plan_final_registrations": sum((c["projection"] or {}).get("plan_final_registrations", 0) for c in campaigns),
              "cost_per_registration": fc.safe_div(spent, tot["registrations"]),
              "cost_per_projected_attendee": fc.safe_div(alloc, forecast["expected_attendance"]),
              "confirm_rate": fc.safe_div(tot["confirmed"], tot["registrations"])}

    # Actual verified attendance exists only after the festival (week 12) and only if someone entered it.
    entered = [c.get("verified_attendees") for c in campaigns if c.get("verified_attendees") is not None]
    actual = None
    if week >= C.TOTAL_WEEKS and entered:
        actual = sum(_i(v) for v in entered) + _i(s.get("actual_walkins")) + _i(s.get("actual_new_guests"))
    totals["actual_verified_attendees"] = actual
    totals["actual_cost_per_verified_attendee"] = fc.safe_div(spent, actual) if actual else None

    # Experiments -------------------------------------------------------
    exps = state["experiment_results"]
    inputs = {k: latest_experiment(exps, k, week) for k in C.EXPERIMENT_NAMES}
    club = next((c for c in campaigns if c["id"] == "club"), None)
    t = C.THRESHOLDS["club"]
    decisions = {}
    if club:
        regs_w4 = cumulative(metrics, "club", min(dw, t["decision_week"]))["registrations"]
        decisions["club"] = de.decide_club(week, _i(inputs["club"][0].get("pitches_completed")), regs_w4, reserve_unc, club["uncommitted"])
    decisions["showup"] = de.decide_showup(inputs["showup"][0])
    decisions["squad"] = de.decide_squad(inputs["squad"][0])
    decisions["guest"] = de.decide_guest(inputs["guest"][0])
    decisions["amb"] = de.decide_ambassadors(inputs["amb"][0])
    for k, d in decisions.items():
        d["inputs"], d["inputs_recorded_week"] = inputs[k]
    for c in campaigns:
        if c["id"] in decisions:
            c["recommendation"] = decisions[c["id"]]
        elif c["type"] == "acquisition":
            c["recommendation"] = de.decide_generic(c, float(s.get("cost_screen_inr", 274)))
        else:
            c["recommendation"] = None
    guardrail = de.decide_guardrail(week, forecast, campaigns, decisions, s, reserve_unc)

    ctx = {"week": week, "data_week": dw, "week_dates": f"{C.week_start(week):%d %b %Y} – {C.week_end(week):%d %b %Y}",
           "settings": s, "campaigns": campaigns, "forecast": forecast, "budget": budget, "totals": totals,
           "decisions": decisions, "guardrail": guardrail, "tasks": state["tasks"], "decision_logs": state["decision_logs"],
           "metrics": metrics, "experiment_rows": exps, "has_reserve": reserve is not None,
           "data_label": "SIMULATED 2027 campaign data (not observed outcomes)"}
    ctx["alerts"] = build_alerts(ctx)
    return ctx


def build_alerts(ctx: dict) -> list:
    a, f, b, s = [], ctx["forecast"], ctx["budget"], ctx["settings"]
    if f["gap_to_base"] < 0:
        sev = "red" if f["pct_of_base"] < 100 * float(s.get("guardrail_ratio", 0.9)) else "amber"
        a.append((sev, f"Forecast {f['expected_attendance']:,} is {abs(f['gap_to_base']):,} below the base target of {f['base_target']:,}."))
    else:
        a.append(("green", f"Forecast {f['expected_attendance']:,} is {f['gap_to_base']:,} above the base target; {abs(f['gap_to_stretch']):,} short of stretch."
                  if f["gap_to_stretch"] < 0 else f"Forecast {f['expected_attendance']:,} exceeds the stretch target."))
    if ctx["guardrail"]["state"] == de.CHANGE:
        a.append(("red", "Week-6 guardrail triggered. " + ctx["guardrail"]["action"]))
    for k, d in ctx["decisions"].items():
        if d["state"] != de.MONITOR:
            a.append(({"Scale": "green", "Stop": "red"}.get(d["state"], "amber"), f"{C.EXPERIMENT_NAMES[k]}: {d['state']}. {d['action']}"))
    for c in ctx["campaigns"]:
        if c["uncommitted"] < 0:
            a.append(("red", f"{c['name']} is over-committed by Rs {abs(c['uncommitted']):,} (spent + open commitments exceed its allocation)."))
        r = c.get("recommendation")
        if r and r["key"].startswith("generic") and r["state"] in (de.STOP, de.CHANGE):
            a.append(("amber", f"{c['name']}: {r['state']}. {r['metric_value']}."))
    if b["over_budget"]:
        a.append(("red", f"Allocations (Rs {b['allocated']:,}) exceed the approved budget (Rs {b['approved_budget']:,})."))
    if not f["capacity_ok"]:
        a.append(("red", f"Capacity risk: estimated peak day {f['peak_day_estimate']:,} exceeds the assumed venue capacity of {f['venue_capacity']:,}."))
    return a


# ---------------------------------------------------------------------------
# Validated writes
def save_cumulative(campaign_id: str, week: int, new: dict, auto_adjust: bool = True) -> dict:
    """Set cumulative-to-date values for a campaign as of `week`.

    Weekly rows up to that week are rescaled proportionally so they still add up.
    """
    state = db.load_all(force=True)
    rows = sorted([dict(m) for m in state["campaign_metrics"] if m["campaign_id"] == campaign_id and m["week"] <= week],
                  key=lambda m: m["week"])
    vals = {}
    for f in METRIC_FIELDS:
        if f in new and new[f] is not None:
            v = float(new[f])
            if v < 0 or v != v:
                raise ValidationError(f"{f} cannot be negative.")
            vals[f] = _i(v)
    cur = cumulative(state["campaign_metrics"], campaign_id, week)
    final = {**cur, **vals}
    notes = []
    chain = [("confirmed", "registrations"), ("registrations", "reg_starts"), ("reg_starts", "leads")]
    if auto_adjust and "registrations" in vals and final["confirmed"] > final["registrations"]:
        ratio = cur["confirmed"] / cur["registrations"] if cur["registrations"] else 0
        final["confirmed"] = min(final["registrations"], _i(final["registrations"] * ratio))
        notes.append(f"Confirmed registrations were scaled to {final['confirmed']} to stay below registrations.")
    for lower, upper in chain:
        if final[lower] > final[upper] and final[upper] >= 0 and (lower in vals or upper in vals):
            if auto_adjust and upper not in vals:
                final[upper] = final[lower]
                notes.append(f"{upper} was raised to {final[upper]} so the funnel stays consistent.")
            else:
                raise ValidationError(f"{lower} ({final[lower]}) cannot exceed {upper} ({final[upper]}).")
    if not rows:
        rows = [{"id": f"{campaign_id}-W{week:02d}", "campaign_id": campaign_id, "week": week, **{f: 0 for f in METRIC_FIELDS}}]
    for f in METRIC_FIELDS:
        target, current = final[f], sum(_i(r.get(f)) for r in rows)
        if target == current:
            continue
        if current > 0:
            scaled = [_i(r.get(f)) * target / current for r in rows]
            ints = [int(x) for x in scaled]
            rem = target - sum(ints)
            order = sorted(range(len(rows)), key=lambda j: scaled[j] - ints[j], reverse=True)
            for j in order[:rem]:
                ints[j] += 1
        else:
            ints = [0] * (len(rows) - 1) + [target]
        for r, v in zip(rows, ints):
            r[f] = v
    for r in rows:
        r["updated_at"] = now_iso()
    db.upsert("campaign_metrics", rows)
    return {"saved": final, "notes": notes}


def save_weekly_rows(campaign_id: str, rows: list):
    """Save edited weekly rows (one per week) after validation."""
    clean = []
    for r in rows:
        w = _i(r.get("week"), -1)
        if not 1 <= w <= C.TOTAL_WEEKS:
            raise ValidationError(f"Week must be between 1 and {C.TOTAL_WEEKS}.")
        row = {"id": f"{campaign_id}-W{w:02d}", "campaign_id": campaign_id, "week": w, "updated_at": now_iso()}
        for f in METRIC_FIELDS:
            v = _i(r.get(f))
            if v < 0 and f != "spend":
                raise ValidationError(f"Week {w}: {f} cannot be negative.")
            row[f] = v
        if row["confirmed"] > row["registrations"]:
            raise ValidationError(f"Week {w}: confirmed cannot exceed registrations.")
        clean.append(row)
    if len({r["week"] for r in clean}) != len(clean):
        raise ValidationError("Each week can appear only once.")
    db.upsert("campaign_metrics", clean)


def save_campaign(c: dict, is_new: bool = False) -> str:
    state = db.load_all(force=True)
    name = (c.get("name") or "").strip()
    if not name:
        raise ValidationError("Campaign name is required.")
    for f in ("budget_allocated", "open_commitments"):
        if float(c.get(f) or 0) < 0:
            raise ValidationError(f"{f.replace('_', ' ').capitalize()} cannot be negative.")
    for f in ("exp_confirm_rate", "p_attend_confirmed"):
        v = c.get(f)
        if v is not None and not 0 <= float(v) <= 1:
            raise ValidationError(f"{f} must be between 0 and 1.")
    if c.get("status") not in C.CAMPAIGN_STATUSES:
        raise ValidationError("Invalid status.")
    if is_new:
        cid = "c-" + uuid.uuid4().hex[:8]
        if any(x["name"].lower() == name.lower() and not x.get("archived") for x in state["campaigns"]):
            raise ValidationError("A campaign with this name already exists.")
        base = {k: None for k in state["campaigns"][0]} if state["campaigns"] else {}
        row = {**base, "id": cid, "archived": False, "verified_attendees": None, "hist_channel": None,
               "base_incremental": None, "stretch_incremental": None}
    else:
        cid = c["id"]
        row = dict(next(x for x in state["campaigns"] if x["id"] == cid))
    others = sum(_i(x.get("budget_allocated")) for x in state["campaigns"] if x["id"] != cid and not x.get("archived"))
    total = _i({**C.DEFAULT_SETTINGS, **state["settings"]}["total_budget"])
    if others + _i(c.get("budget_allocated")) > total:
        raise ValidationError(f"This would allocate Rs {others + _i(c.get('budget_allocated')):,}, above the approved budget of Rs {total:,}. "
                              "Reduce another allocation first (or move money through an approved decision).")
    if not is_new:
        spent = cumulative(state["campaign_metrics"], cid, C.TOTAL_WEEKS)["spend"]
        if _i(c.get("budget_allocated")) < spent:
            raise ValidationError(f"Allocation cannot be below the Rs {spent:,} already spent.")
    for k in ("name", "owner", "description", "status", "type", "start_date", "end_date", "start_week"):
        if k in c:
            row[k] = c[k]
    for k in ("budget_allocated", "open_commitments", "plan_regs_base", "plan_regs_stretch"):
        if k in c:
            row[k] = _i(c[k])
    for k in ("exp_confirm_rate", "p_attend_confirmed"):
        if k in c:
            row[k] = None if c[k] is None else round(float(c[k]), 4)
    if "verified_attendees" in c:
        v = c["verified_attendees"]
        if v is not None and float(v) < 0:
            raise ValidationError("Verified attendees cannot be negative.")
        row["verified_attendees"] = None if v is None else _i(v)
    row["name"], row["updated_at"] = name, now_iso()
    db.upsert("campaigns", [row])
    return cid


def archive_campaign(cid: str):
    if cid == "reserve":
        raise ValidationError("The reserve cannot be archived.")
    state = db.load_all(force=True)
    row = dict(next(x for x in state["campaigns"] if x["id"] == cid))
    row.update(archived=True, status="Archived", updated_at=now_iso())
    db.upsert("campaigns", [row])


def save_experiment(exp: str, week: int, inputs: dict):
    for k, v in inputs.items():
        if v is not None and not isinstance(v, bool) and float(v) < 0:
            raise ValidationError(f"{k.replace('_', ' ')} cannot be negative.")
    pairs = [("control_confirmed", "control_starts"), ("treatment_confirmed", "treatment_starts"),
             ("control_attended", "control_starts"), ("treatment_attended", "treatment_starts")]
    for a, b in pairs:
        if inputs.get(a) is not None and inputs.get(b) is not None and float(inputs[a]) > float(inputs[b]):
            raise ValidationError(f"{a.replace('_', ' ')} cannot exceed {b.replace('_', ' ')}.")
    if exp == "guest" and _i(inputs.get("redeemed_new_people")) + _i(inputs.get("redeemed_existing_registrants")) > _i(inputs.get("passes_issued")):
        raise ValidationError("Redemptions cannot exceed passes issued.")
    clean = {k: (None if v is None else _i(v)) for k, v in inputs.items()}
    db.upsert("experiment_results", [{"id": f"{exp}-W{week:02d}", "experiment": exp, "week": week, "inputs": clean, "updated_at": now_iso()}])


def apply_decision(decision: dict, week: int, approve: bool, decided_by: str = "Growth lead", note: str = "") -> dict:
    """Record an approval/rejection. Approved budget transfers move only uncommitted money, once."""
    state = db.load_all(force=True)
    key = decision["key"]
    dup = [l for l in state["decision_logs"] if l["decision_key"] == key and l["week"] == week
           and l["recommendation"] == decision["state"] and l["outcome"] == "Approved"]
    if approve and dup:
        raise ValidationError("This recommendation was already approved for this week. It cannot be applied twice.")
    moved, tr = 0, decision.get("transfer")
    if approve and tr:
        ctx = build_context(week, state)
        src = next((c for c in ctx["campaigns"] if c["id"] == tr["from"]), None)
        dst = next((c for c in ctx["campaigns"] if c["id"] == tr["to"]), None)
        if not src or not dst:
            raise ValidationError("Source or destination campaign no longer exists.")
        moved = max(0, min(_i(tr["amount"]), src["uncommitted"]))
        if moved <= 0:
            raise ValidationError(f"No uncommitted money is left in {src['name']}; nothing can be moved.")
        raw = {c["id"]: dict(c) for c in state["campaigns"]}
        raw[src["id"]]["budget_allocated"] = _i(raw[src["id"]]["budget_allocated"]) - moved
        raw[dst["id"]]["budget_allocated"] = _i(raw[dst["id"]]["budget_allocated"]) + moved
        for r in (raw[src["id"]], raw[dst["id"]]):
            r["updated_at"] = now_iso()
        db.upsert("campaigns", [raw[src["id"]], raw[dst["id"]]])
    log = {"id": "d-" + uuid.uuid4().hex[:10], "created_at": now_iso(), "week": week, "decision_key": key,
           "campaign_id": decision.get("campaign_id"), "recommendation": decision["state"],
           "metric": f"{decision['metric_label']}: {decision['metric_value']}", "action": decision["action"],
           "outcome": "Approved" if approve else "Rejected", "amount_moved": moved,
           "transfer_from": tr["from"] if (tr and moved) else None, "transfer_to": tr["to"] if (tr and moved) else None,
           "decided_by": decided_by, "note": note or ""}
    db.upsert("decision_logs", [log])
    return log


def save_task(t: dict, is_new: bool = False) -> str:
    title = (t.get("title") or "").strip()
    if not title:
        raise ValidationError("Task title is required.")
    if t.get("status") not in C.TASK_STATUSES:
        raise ValidationError("Invalid task status.")
    if t.get("priority") not in C.TASK_PRIORITIES:
        raise ValidationError("Invalid task priority.")
    try:
        deadline = str(date.fromisoformat(str(t.get("deadline"))[:10]))
    except Exception:
        raise ValidationError("Deadline must be a valid date (YYYY-MM-DD).")
    row = {"id": t.get("id") if not is_new else "t-" + uuid.uuid4().hex[:10], "title": title[:200],
           "description": (t.get("description") or "")[:2000], "campaign_id": t.get("campaign_id"),
           "owner": t.get("owner") or "Unassigned", "deadline": deadline, "priority": t["priority"], "status": t["status"],
           "evidence": (t.get("evidence") or "")[:2000], "source": t.get("source") or "Manual",
           "created_at": t.get("created_at") or now_iso()}
    db.upsert("tasks", [row])
    return row["id"]


def delete_task(task_id: str):
    db.delete("tasks", [task_id])


def save_settings(values: dict):
    for k, v in values.items():
        if k in ("base_target", "stretch_target", "venue_capacity", "walkins_expected") and (v is None or float(v) < 0):
            raise ValidationError(f"{k} cannot be negative.")
        if k in ("guest_redemption_rate", "day1_share", "waitlist_recovery", "reminder_lift", "p_attend_unconfirmed") and not 0 <= float(v) <= 1:
            raise ValidationError(f"{k} must be between 0 and 1.")
    db.upsert("settings", [{"key": k, "value": v} for k, v in values.items()])

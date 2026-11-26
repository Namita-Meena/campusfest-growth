"""Read-only access to the original CampusFest 2025 dataset supplied by RISA Labs.

The raw CSV exports in data/historical/ are never modified. This module applies
the cleaning rules from the dataset's own "Read me" sheet:
  * exact repeated IDs (import retries) count once;
  * only person_type == external counts toward attendee metrics;
  * only admitted + verified check-ins establish attendance;
  * for any date, use the latest registration-status version effective by then.
Person names are dropped on load: they are synthetic display labels and are not
needed for analysis, so they are never shown in the app or sent to the AI model.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "historical"

_FILES = {
    "event": ([], None),
    "targets": (["effective_at"], None),
    "campaigns": (["created_at", "planned_start_at", "planned_end_at"], None),
    "daily_marketing": (["activity_date"], "activity_id"),
    "people": (["first_seen_at"], "person_id"),
    "interactions": (["occurred_at"], "interaction_id"),
    "registrations": (["registered_at"], "registration_id"),
    "registration_history": (["effective_at"], "history_id"),
    "checkins": (["occurred_at"], "event_id"),
}

NOT_IN_DATASET = [
    "age", "gender", "college or university name", "course or year of study", "home city or pin code",
    "phone number", "email address", "ticket price or revenue", "satisfaction or NPS scores",
    "which events or stages a visitor attended", "per-ambassador or per-club performance",
    "device or browser", "weather", "sponsor data", "unique (de-duplicated) reach across days",
]


@lru_cache(maxsize=1)
def load() -> dict:
    """Load, de-duplicate and lightly enrich every historical table."""
    out, quality = {}, {}
    for name, (dates, key) in _FILES.items():
        raw = pd.read_csv(DATA_DIR / f"{name}.csv", parse_dates=dates)
        dup = int(raw.duplicated(key).sum()) if key else 0
        df = raw.drop_duplicates(key) if key else raw
        df = df.drop(columns=[c for c in ("person_name",) if c in df.columns]).reset_index(drop=True)
        quality[name] = {"raw_rows": len(raw), "duplicate_ids_removed": dup, "rows_used": len(df),
                         "missing_values": {c: int(n) for c, n in raw.isna().sum().items() if n}}
        out[name] = df
    ext = set(out["people"].loc[out["people"].person_type == "external", "person_id"])
    for t in ("registrations", "registration_history", "checkins", "interactions"):
        out[t]["is_external"] = out[t]["person_id"].isin(ext)
    out["registrations"]["registered_date"] = out["registrations"].registered_at.dt.date.astype(str)
    out["registrations"]["registered_month"] = out["registrations"].registered_at.dt.strftime("%Y-%m")
    out["checkins"]["checkin_date"] = out["checkins"].occurred_at.dt.date.astype(str)
    out["interactions"]["event_month"] = out["interactions"].occurred_at.dt.strftime("%Y-%m")
    out["daily_marketing"]["month"] = out["daily_marketing"].activity_date.dt.strftime("%Y-%m")
    out["people"]["first_seen_month"] = out["people"].first_seen_at.dt.strftime("%Y-%m")
    out["people_summary"] = _people_summary(out)
    out["_quality"] = quality
    return out


def _end_of_day(as_of) -> pd.Timestamp:
    if as_of is None:
        return pd.Timestamp("2025-04-20 23:59:59")
    return pd.Timestamp(as_of).normalize() + pd.Timedelta(hours=23, minutes=59, seconds=59)


def _verified(ck: pd.DataFrame) -> pd.DataFrame:
    return ck[(ck.result == "admitted") & (ck.verification == "verified") & ck.is_external]


def _latest_status(rh: pd.DataFrame, cutoff: pd.Timestamp) -> pd.DataFrame:
    rh = rh[rh.effective_at <= cutoff]
    return rh.sort_values("effective_at").groupby("registration_id").tail(1)


def _people_summary(d: dict) -> pd.DataFrame:
    """One row per identified person with their funnel outcome (final state)."""
    p = d["people"][["person_id", "person_type", "first_touch_source", "first_campaign_id",
                     "first_campaign_name", "first_seen_at"]].copy()
    rg = d["registrations"].set_index("person_id")
    p["registered"] = p.person_id.isin(rg.index)
    p["registration_campaign"] = p.person_id.map(rg.campaign_name)
    p["registered_at"] = p.person_id.map(rg.registered_at)
    last = _latest_status(d["registration_history"], pd.Timestamp("2025-04-11 23:59:59")).set_index("person_id")
    p["status_before_event"] = p.person_id.map(last.status)
    v = _verified(d["checkins"])
    days = v.assign(day=v.occurred_at.dt.date).groupby("person_id").day.nunique()
    p["attended_verified"] = p.person_id.isin(days.index)
    p["days_attended"] = p.person_id.map(days).fillna(0).astype(int)
    ie = d["interactions"]
    for col, ev in [("started_registration", "registration_start"), ("downloaded_brochure", "brochure_download"),
                    ("asked_question", "event_question_submitted"), ("email_opened", "nurture_email_opened"),
                    ("email_clicked", "nurture_email_clicked"), ("opted_out", "opted_out")]:
        p[col] = p.person_id.isin(ie.loc[ie.event_type == ev, "person_id"])
    p["days_registered_before_event"] = (pd.Timestamp("2025-04-12") - p.registered_at).dt.days
    return p


def snapshot(as_of=None) -> dict:
    """Historical funnel as of the end of a given day (default: full history)."""
    d = load()
    cut = _end_of_day(as_of)
    ppl = d["people"]
    ext = ppl[(ppl.person_type == "external") & (ppl.first_seen_at <= cut)]
    dm = d["daily_marketing"][d["daily_marketing"].activity_date <= cut]
    rg = d["registrations"][d["registrations"].is_external & (d["registrations"].registered_at <= cut)]
    last = _latest_status(d["registration_history"], cut)
    last = last[last.registration_id.isin(rg.registration_id)]
    status = last.status.value_counts().to_dict()
    v = _verified(d["checkins"])
    v = v[v.occurred_at <= cut]
    visitors = v.drop_duplicates("person_id")
    reg_att = int(visitors.person_id.isin(rg.person_id).sum())
    tg = d["targets"][d["targets"].effective_at <= cut].sort_values("effective_at").tail(1)
    ie = d["interactions"]
    starters = set(ie[(ie.event_type == "registration_start") & ie.is_external & (ie.occurred_at <= cut)].person_id)
    confirmed_people = set(last[last.status == "confirmed"].person_id)
    n_start = len(starters)
    res = {
        "as_of": str(cut.date()),
        "reported_reach_sum": int(dm.reported_reach.sum()),
        "impressions": int(dm.impressions.sum()),
        "clicks": int(dm.clicks.sum()),
        "landing_page_sessions": int(dm.landing_page_sessions.sum()),
        "anonymous_registration_starts": int(dm.registration_starts.sum()),
        "marketing_spend_inr": int(dm.marketing_spend_inr.sum()),
        "identified_external_people": int(len(ext)),
        "campaign_attributed_leads": int((ext.first_touch_source == "campaign").sum()),
        "identified_registration_starters": n_start,
        "registrations_external": int(rg.person_id.nunique()),
        "status_counts_latest_version": {k: int(x) for k, x in status.items()},
        "confirmed": int(status.get("confirmed", 0)),
        "unconfirmed": int(len(last) - status.get("confirmed", 0)),
        "registered_attendees": reg_att,
        "walk_ins": int(len(visitors) - reg_att),
        "new_day2_guests": 0,
        "verified_attendees": int(len(visitors)),
        "verified_by_day": {str(k): int(x) for k, x in v.assign(day=v.occurred_at.dt.date).groupby("day").person_id.nunique().items()},
        "confirmed_per_100_starts": round(100 * len(confirmed_people & starters) / n_start, 1) if n_start else None,
        "attended_per_100_starts": round(100 * len(set(visitors.person_id) & starters) / n_start, 1) if n_start else None,
        "attendance_rate_among_confirmed": None,
        "attendance_rate_among_unconfirmed": None,
        "targets_in_effect": tg.drop(columns=["effective_at"]).iloc[0].to_dict() if len(tg) else None,
        "notes": ["reported_reach_sum adds daily platform reach and is NOT unique people.",
                  "new_day2_guests is 0 by definition: no guest-pass programme existed in 2025.",
                  "Excluded from attendee metrics: internal, staff and test identities; denied, pending or unverified check-ins."],
    }
    if res["targets_in_effect"]:
        res["targets_in_effect"] = {k: (int(x) if hasattr(x, "item") and not isinstance(x, str) else x)
                                    for k, x in res["targets_in_effect"].items()}
    if len(last):
        att = last.person_id.isin(visitors.person_id)
        conf = last.status == "confirmed"
        if conf.sum():
            res["attendance_rate_among_confirmed"] = round(float(att[conf].mean()), 4)
        if (~conf).sum():
            res["attendance_rate_among_unconfirmed"] = round(float(att[~conf].mean()), 4)
    return res


def by_campaign(as_of=None) -> pd.DataFrame:
    """Per-campaign 2025 funnel using the recorded acquisition source of each registration."""
    d = load()
    cut = _end_of_day(as_of)
    dm = d["daily_marketing"][d["daily_marketing"].activity_date <= cut]
    t = d["campaigns"][["campaign_id", "campaign_name", "channel"]].set_index("campaign_id")
    agg = dm.groupby("campaign_id")[["reported_reach", "landing_page_sessions", "registration_starts", "marketing_spend_inr"]].sum()
    ppl = d["people"]
    ext = ppl[(ppl.person_type == "external") & (ppl.first_seen_at <= cut)]
    rg = d["registrations"][d["registrations"].is_external & (d["registrations"].registered_at <= cut)]
    last = _latest_status(d["registration_history"], cut)
    last = last[last.registration_id.isin(rg.registration_id)]
    v = _verified(d["checkins"])
    vis = v[v.occurred_at <= cut].drop_duplicates("person_id")
    t = t.join(agg)
    t["leads"] = ext.groupby("first_campaign_id").person_id.nunique()
    t["registrations"] = rg.groupby("campaign_id").person_id.nunique()
    t["confirmed"] = last[last.status == "confirmed"].groupby("campaign_id").person_id.nunique()
    t["attended"] = rg[rg.person_id.isin(vis.person_id)].groupby("campaign_id").person_id.nunique()
    t = t.fillna(0)
    for c in ("leads", "registrations", "confirmed", "attended"):
        t[c] = t[c].astype(int)
    t["lead_to_registration"] = (t.registrations / t.leads).round(3)
    t["confirm_rate"] = (t.confirmed / t.registrations).round(3)
    t["attended_per_registered"] = (t.attended / t.registrations).round(3)
    t["attended_per_confirmed"] = (t.attended / t.confirmed).round(3)
    t["cost_per_registration"] = (t.marketing_spend_inr / t.registrations).round(0)
    t["cost_per_attendee"] = (t.marketing_spend_inr / t.attended).round(0)
    return t.reset_index()


def weekly_registrations() -> list:
    """External registrations per campaign week of 2025 (week 1 = 20-26 Jan)."""
    rg = load()["registrations"]
    rg = rg[rg.is_external]
    wk = ((rg.registered_at - pd.Timestamp("2025-01-20")).dt.days // 7 + 1).clip(1, 12)
    c = wk.value_counts().reindex(range(1, 13), fill_value=0)
    return [int(x) for x in c.tolist()]


def data_dictionary() -> dict:
    d = load()
    fg = pd.read_csv(DATA_DIR / "field_guide.csv")
    tables = {}
    for name in list(_FILES) + ["people_summary"]:
        df = d[name]
        tables[name] = {"rows": int(len(df)), "columns": {c: str(t) for c, t in df.dtypes.items()}}
    return {"tables": tables,
            "field_meanings": fg.to_dict("records"),
            "not_available_in_dataset": NOT_IN_DATASET,
            "cleaning_rules": ["Deduplicate identical source IDs", "External people only for attendee metrics",
                               "Attendance = admitted + verified check-in", "Latest status version as of the selected day"]}


def quality_report() -> dict:
    d = load()
    ck, ppl = d["checkins"], d["people"]
    return {"tables": d["_quality"],
            "person_types": ppl.person_type.value_counts().to_dict(),
            "checkin_results": ck.result.value_counts().to_dict(),
            "checkin_verification": ck.verification.value_counts().to_dict(),
            "negative_spend_rows_vendor_credits": int((d["daily_marketing"].marketing_spend_inr < 0).sum()),
            "people_without_campaign": int(ppl.first_campaign_id.isna().sum())}


# ---------------------------------------------------------------------------
# Safe, restricted analytical query used by the AI copilot for unfamiliar questions.
_QUERYABLE = ["people_summary", "people", "registrations", "registration_history", "checkins",
              "interactions", "daily_marketing", "campaigns", "targets"]
_OPS = ("==", "!=", ">=", "<=", ">", "<", " in ", " contains ")
_AGGS = ("count_rows", "count_distinct", "sum", "mean", "min", "max")


def _cast(series: pd.Series, raw: str):
    raw = raw.strip().strip("'\"")
    if pd.api.types.is_bool_dtype(series):
        return raw.lower() in ("true", "1", "yes")
    if pd.api.types.is_datetime64_any_dtype(series):
        return pd.Timestamp(raw)
    if pd.api.types.is_numeric_dtype(series):
        return float(raw)
    return raw


def query(table: str, filters: list | None = None, group_by: list | None = None,
          aggregate: str = "count_rows", column: str | None = None, limit: int = 40) -> dict:
    """Filter / group / aggregate one historical table. No free-form code is executed."""
    d = load()
    if table not in _QUERYABLE:
        return {"error": f"Unknown table '{table}'. Available: {_QUERYABLE}"}
    df = d[table]
    if aggregate not in _AGGS:
        return {"error": f"aggregate must be one of {_AGGS}"}
    applied = []
    for f in filters or []:
        m = re.match(r"^\s*(\w+)\s*(==|!=|>=|<=|>|<|\bin\b|\bcontains\b)\s*(.+)$", str(f))
        if not m:
            return {"error": f"Could not parse filter '{f}'. Use 'column op value' with ops ==, !=, >, >=, <, <=, in, contains."}
        col, op, val = m.group(1), m.group(2), m.group(3)
        if col not in df.columns:
            return {"error": f"Column '{col}' is not in table '{table}'. Columns: {list(df.columns)}"}
        s = df[col]
        try:
            if op == "in":
                vals = [_cast(s, x) for x in val.strip("[]() ").split(",")]
                mask = s.isin(vals)
            elif op == "contains":
                mask = s.astype(str).str.contains(val.strip().strip("'\""), case=False, regex=False)
            else:
                x = _cast(s, val)
                if pd.api.types.is_datetime64_any_dtype(s) and op in ("<=",) and len(val.strip()) <= 12:
                    x = x + pd.Timedelta(hours=23, minutes=59, seconds=59)
                mask = {"==": s == x, "!=": s != x, ">": s > x, ">=": s >= x, "<": s < x, "<=": s <= x}[op]
        except Exception as e:  # bad value for the column type
            return {"error": f"Bad value in filter '{f}': {e}"}
        df = df[mask.fillna(False)]
        applied.append(f"{col} {op} {val.strip()}")
    group_by = [g for g in (group_by or []) if g]
    for g in group_by:
        if g not in df.columns:
            return {"error": f"Column '{g}' is not in table '{table}'. Columns: {list(df.columns)}"}
    if aggregate != "count_rows":
        if not column or column not in df.columns:
            return {"error": f"aggregate '{aggregate}' needs a valid 'column'. Columns: {list(df.columns)}"}
        if aggregate in ("sum", "mean") and not (pd.api.types.is_numeric_dtype(df[column]) or pd.api.types.is_bool_dtype(df[column])):
            return {"error": f"Column '{column}' is not numeric, so '{aggregate}' is not possible."}

    def agg(frame):
        if aggregate == "count_rows":
            return int(len(frame))
        s = frame[column]
        if aggregate == "count_distinct":
            return int(s.nunique())
        if len(s) == 0:
            return None
        val = getattr(s.astype(float) if pd.api.types.is_bool_dtype(s) else s, aggregate)()
        return str(val) if isinstance(val, pd.Timestamp) else round(float(val), 4)

    meta = {"table": table, "filters_applied": applied, "aggregate": aggregate, "column": column,
            "rows_matched": int(len(df)), "note": "Duplicated source IDs already removed. Filter is_external == true (or person_type == external) for attendee metrics."}
    if not group_by:
        return {**meta, "result": agg(df)}
    rows = []
    for key, frame in df.groupby(group_by, dropna=False):
        key = key if isinstance(key, tuple) else (key,)
        rows.append({**{g: (None if pd.isna(k) else str(k)) for g, k in zip(group_by, key)}, "value": agg(frame)})
    rows.sort(key=lambda r: (r["value"] is None, -(r["value"] or 0) if isinstance(r["value"], (int, float)) else 0))
    return {**meta, "group_by": group_by, "groups_total": len(rows), "result": rows[:limit]}

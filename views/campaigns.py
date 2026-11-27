"""Page 2 - Campaign Intelligence: compare, diagnose and edit campaigns."""
from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import analytics as an
from core import config as C
from core import ui

W = ui.week()
ctx = an.build_context(W)
ui.header("Campaign Intelligence", "Which campaigns are working, and what should we do about each?",
          f"Week {W} ({ctx['week_dates']}) · {ui.tag('Simulated 2027')} Registrations are attributed to one acquisition campaign each "
          "(the recorded source), so no person is counted twice. Interventions change rates and never add people.")
ui.show_flashes()

cs = ctx["campaigns"]
rows = []
for c in cs:
    p, r = c["projection"], c["recommendation"]
    rows.append({"Campaign": c["name"], "Type": c["type"].replace("_", " "), "Owner": c["owner"], "Status": c["status"],
                 "Budget": c["budget_allocated"], "Spent": c["spent"], "Uncommitted": c["uncommitted"],
                 "Registrations": c["registrations"] if p else None, "Confirmed": c["confirmed"] if p else None,
                 "Pace vs plan": p["pace_vs_plan"] if p else None, "Projected attendees": p["projected_attendees"] if p else None,
                 "Plan attendees": p["plan_attendees"] if p else None, "₹ / registration": c["cost_per_registration"] if p else None,
                 "₹ / projected attendee": c["cost_per_projected_attendee"], "Recommended action": r["state"] if r else "—"})
df = pd.DataFrame(rows)
for _col in ("Registrations", "Confirmed", "Pace vs plan", "Projected attendees", "Plan attendees", "₹ / registration", "₹ / projected attendee"):
    df[_col] = pd.to_numeric(df[_col], errors="coerce")


def colour_state(v):
    name = C.STATE_TONES.get(v)
    return f"color: {ui.grid_tone(name)}; font-weight: 600" if name else ""


fmt = {"Budget": "₹{:,.0f}", "Spent": "₹{:,.0f}", "Uncommitted": "₹{:,.0f}", "Registrations": "{:,.0f}", "Confirmed": "{:,.0f}",
       "Pace vs plan": "{:.2f}×", "Projected attendees": "{:,.0f}", "Plan attendees": "{:,.0f}", "₹ / registration": "₹{:,.0f}",
       "₹ / projected attendee": "₹{:,.0f}"}
show_df = df.copy()
for _col, _f in fmt.items():   # format to text so empty cells show a dash instead of "None"
    show_df[_col] = [("—" if pd.isna(v) else _f.format(v)) for v in df[_col]]
st.dataframe(show_df.style.map(colour_state, subset=["Recommended action"]), hide_index=True, width="stretch")
st.caption("Pace = registrations to date ÷ time-aligned plan. Projected attendees = projected confirmed × P(attend | confirmed). "
           "₹ / projected attendee uses the full allocation. Recommended action is computed by the decision engine from current data.")

st.divider()
names = [c["name"] for c in cs]
sel = st.selectbox("Select a campaign", names, key="camp_sel")
c = next(x for x in cs if x["name"] == sel)
p, r = c["projection"], c["recommendation"]

left, right = st.columns([3, 2])
with left:
    st.subheader(c["name"])
    st.caption(f"{c['description'] or ''}\n\nOwner: {c['owner']} · Status: {c['status']} · {c.get('start_date')} → {c.get('end_date')}")
    ui.cards([("Allocated", ui.inr(c["budget_allocated"]), "", None), ("Spent", ui.inr(c["spent"]), "to date", None),
              ("Open commitments", ui.inr(c["open_commitments"]), "contracted, unpaid", None),
              ("Uncommitted", ui.inr(c["uncommitted"]), "can be reallocated", None)], 4)
    if p:
        ui.cards([("Registrations", ui.num(c["registrations"]), f"Plan to date {p['plan_registrations_to_date']:.0f}", None),
                  ("Confirmed", ui.num(c["confirmed"]), f"{ui.pct(c['confirm_rate'])} confirm rate", None),
                  ("Projected final registrations", ui.num(p["projected_final_registrations"]), f"Plan {p['plan_final_registrations']:,}", "Forecast"),
                  ("Projected attendees", ui.num(p["projected_attendees"]), f"Plan {p['plan_attendees']:.0f}", "Forecast")], 4)
        ui.cards([("Lead → registration", ui.pct(c["lead_to_registration"]), f"{c['leads']:,} leads", None),
                  ("Start → registration", ui.pct(c["start_to_registration"]), f"{c['reg_starts']:,} starts", None),
                  ("Cost per registration", ui.inr(c["cost_per_registration"]), "spent ÷ registrations", None),
                  ("Cost per projected attendee", ui.inr(c["cost_per_projected_attendee"]), "allocation ÷ projected", "Forecast")], 4)
        st.caption(f"Projection basis: {p['projection_basis']}. Confirm rate used: {ui.pct(p['confirm_rate_used'])} ({p['confirm_rate_source']}"
                   f"{', plus Show-Up Engine waitlist recovery' if ctx['forecast']['show_up_engine_active'] else ''}). "
                   f"P(attend | confirmed) used: {ui.pct(p['p_attend_confirmed_used'])}. Verified attendance: "
                   f"{ui.num(c.get('verified_attendees')) if c.get('verified_attendees') is not None else 'not yet available (entered after the festival)'}.")
    elif c["type"] == "intervention":
        st.info("This is an attendance-improvement intervention. It raises the confirm rate and the attendance rate of people acquired by "
                "other campaigns, so it has no registrations of its own and adds nobody twice. Its planned contribution "
                f"(+{c.get('base_incremental')} base / +{c.get('stretch_incremental')} stretch) is a strategic estimate.")
    elif c["type"] == "event_day":
        st.info(f"Event-day campaign: forecast {ctx['forecast']['expected_new_guests']:,} new Day-2 guests and "
                f"{ctx['forecast']['expected_walkins']:,} walk-ins. Guests = Day-1 registered attendees × redemption rate "
                f"({ui.pct(ctx['forecast']['guest_redemption_rate'], 0)}). Neither group holds a registration, so nobody is counted twice.")
with right:
    st.subheader("Recommended action")
    if r:
        st.markdown(ui.pill(r["state"]), unsafe_allow_html=True)
        st.markdown(f"**{r['metric_label']}:** {r['metric_value']}")
        st.markdown(f"**Rule:** {r['threshold']}")
        st.markdown(f"**Sample:** {r['sample']} {'✓' if r['sample_ok'] else '(below minimum)'}")
        st.markdown(f"**Action:** {r['action']}")
        st.caption("Approve or reject this on the Experiments and Budget page. Nothing is applied automatically.")
    else:
        st.caption("No decision rule applies to this row.")
    if p:
        wk = [m for m in ctx["metrics"] if m["campaign_id"] == c["id"]]
        wk.sort(key=lambda m: m["week"])
        fig = go.Figure()
        fig.add_bar(x=[m["week"] for m in wk if m["week"] <= ctx["data_week"]], y=[m["registrations"] for m in wk if m["week"] <= ctx["data_week"]],
                    name="Registrations", marker_color=ui.P().primary)
        fig.add_scatter(x=list(range(1, 13)), y=[p["plan_final_registrations"] * (an.fc.curve_share(w, c["start_week"]) - an.fc.curve_share(w - 1, c["start_week"]))
                                                 for w in range(1, 13)], name="Plan", line=dict(color=ui.P().second, dash="dash"))
        fig.update_xaxes(dtick=1, title="Week")
        ui.show(ui.style(fig, 230), "camp_week")

st.divider()
tab1, tab2, tab3, tab4 = st.tabs(["Update results to date", "Weekly records", "Edit campaign and budget", "Create or archive"])

with tab1:
    if c["type"] == "reserve":
        st.caption("The reserve has no performance metrics.")
    else:
        st.caption(f"Enter cumulative totals as of week {ctx['data_week'] if ctx['data_week'] == W else W}. Weekly records are rescaled proportionally so they still add up. "
                   "Saved changes update every page and the AI copilot immediately.")
        cum = an.cumulative(ctx["metrics"], c["id"], W)
        with st.form(f"cum_{c['id']}_{W}"):
            a, b2, c3 = st.columns(3)
            reach = a.number_input("Reported reach", min_value=0, value=int(cum["reach"]), step=100)
            leads = b2.number_input("Identified leads", min_value=0, value=int(cum["leads"]), step=1)
            starts = c3.number_input("Registration starts", min_value=0, value=int(cum["reg_starts"]), step=1)
            regs = a.number_input("Completed registrations", min_value=0, value=int(cum["registrations"]), step=1)
            conf = b2.number_input("Confirmed registrations", min_value=0, value=int(cum["confirmed"]), step=1)
            spend = c3.number_input("Actual spend (₹)", min_value=0, value=int(cum["spend"]), step=500)
            auto = st.checkbox("Keep related fields logically valid automatically (e.g. scale confirmed down with registrations)", value=True)
            if st.form_submit_button("Save results", type="primary"):
                new = {k: v for k, v in dict(reach=reach, leads=leads, reg_starts=starts, registrations=regs, confirmed=conf, spend=spend).items()
                       if v != cum[k]}
                try:
                    if not new:
                        st.warning("No values were changed.")
                    else:
                        if "spend" in new and spend + c["open_commitments"] > c["budget_allocated"]:
                            raise an.ValidationError(f"Spend plus open commitments (₹{spend + c['open_commitments']:,}) would exceed the allocation "
                                                     f"(₹{c['budget_allocated']:,}). Raise the allocation or reduce commitments first.")
                        res = an.save_cumulative(c["id"], W, new, auto)
                        ui.flash(f"Saved {c['name']} as of week {W}: " + ", ".join(f"{k.replace('_', ' ')} = {v:,}" for k, v in res["saved"].items() if k in new)
                                 + ". " + " ".join(res["notes"]))
                        st.rerun()
                except an.ValidationError as e:
                    st.error(str(e))

with tab2:
    if c["type"] == "reserve":
        st.caption("The reserve has no weekly records.")
    else:
        st.caption("One row per campaign week (increments for that week, not cumulative). Add rows for weeks without data.")
        wk = sorted([m for m in ctx["metrics"] if m["campaign_id"] == c["id"]], key=lambda m: m["week"])
        wdf = pd.DataFrame(wk, columns=["week", *an.METRIC_FIELDS]) if wk else pd.DataFrame(columns=["week", *an.METRIC_FIELDS])
        edited = st.data_editor(wdf, num_rows="dynamic", hide_index=True, width="stretch", key=f"wk_{c['id']}",
                                column_config={"week": st.column_config.NumberColumn("Week", min_value=1, max_value=12, step=1, required=True),
                                               **{f: st.column_config.NumberColumn(f.replace("_", " ").capitalize(), min_value=0, step=1, default=0)
                                                  for f in an.METRIC_FIELDS}})
        if st.button("Save weekly records", key=f"wksave_{c['id']}", type="primary"):
            try:
                recs = edited.dropna(subset=["week"]).fillna(0).to_dict("records")
                an.save_weekly_rows(c["id"], recs)
                kept = {int(r["week"]) for r in recs}
                gone = [m["id"] for m in wk if m["week"] not in kept]
                if gone:
                    an.db.delete("campaign_metrics", gone)
                ui.flash(f"Saved {len(recs)} weekly records for {c['name']}.")
                st.rerun()
            except an.ValidationError as e:
                st.error(str(e))

with tab3:
    with st.form(f"edit_{c['id']}"):
        a, b2 = st.columns(2)
        name = a.text_input("Campaign name", c["name"])
        owner = b2.selectbox("Owner", sorted(set(C.OWNERS + [c["owner"]])), index=sorted(set(C.OWNERS + [c["owner"]])).index(c["owner"]))
        desc = st.text_area("Description", c.get("description") or "", height=80)
        a, b2, c3 = st.columns(3)
        status = a.selectbox("Status", C.CAMPAIGN_STATUSES[:-1], index=C.CAMPAIGN_STATUSES.index(c["status"]) if c["status"] in C.CAMPAIGN_STATUSES[:-1] else 0)
        sd = b2.date_input("Start date", date.fromisoformat(str(c.get("start_date") or C.CAMPAIGN_START)[:10]))
        ed = c3.date_input("End date", date.fromisoformat(str(c.get("end_date") or C.week_end(12))[:10]))
        alloc = a.number_input("Allocated budget (₹)", min_value=0, value=int(c["budget_allocated"]), step=1000)
        oc = b2.number_input("Open commitments (₹, contracted but unpaid)", min_value=0, value=int(c["open_commitments"]), step=500)
        va = c3.number_input("Verified attendees (after the festival; leave 0 if not available)", min_value=0, value=int(c.get("verified_attendees") or 0), step=1)
        if p:
            plan_regs = a.number_input("Planned registrations (base)", min_value=0, value=int(c.get("plan_regs_base") or 0), step=10)
            ecr = b2.number_input("Expected confirm rate", min_value=0.0, max_value=1.0, value=float(c.get("exp_confirm_rate") or 0), step=0.01, format="%.3f")
            pac = c3.number_input("P(attend | confirmed)", min_value=0.0, max_value=1.0, value=float(c.get("p_attend_confirmed") or 0), step=0.01, format="%.3f")
        if st.form_submit_button("Save campaign", type="primary"):
            try:
                if ed < sd:
                    raise an.ValidationError("End date cannot be before the start date.")
                if c["spent"] + oc > alloc:
                    raise an.ValidationError(f"Spent (₹{c['spent']:,}) plus open commitments (₹{oc:,}) cannot exceed the allocation (₹{alloc:,}).")
                upd = dict(id=c["id"], name=name, owner=owner, description=desc, status=status, start_date=str(sd), end_date=str(ed),
                           budget_allocated=alloc, open_commitments=oc, verified_attendees=va if va > 0 else None)
                if p:
                    upd.update(plan_regs_base=plan_regs, exp_confirm_rate=ecr, p_attend_confirmed=pac)
                an.save_campaign(upd)
                ui.flash(f"Saved {name}.")
                st.rerun()
            except an.ValidationError as e:
                st.error(str(e))
    st.caption("Budget moves between campaigns should normally go through an approved decision on the Experiments page, which only moves uncommitted money. "
               "Here an allocation can be raised only while the total stays within the approved ₹3,00,000.")

with tab4:
    a, b2 = st.columns(2)
    with a:
        st.markdown("**Create a campaign**")
        with st.form("new_camp", clear_on_submit=True):
            n_name = st.text_input("Name")
            n_type = st.selectbox("Type", ["acquisition", "intervention", "event_day"], help="Only acquisition campaigns hold registrations.")
            n_owner = st.selectbox("Owner", C.OWNERS)
            n_desc = st.text_area("Description", height=70)
            n_start = st.number_input("Start week", min_value=1, max_value=12, value=min(W + 1, 12))
            n_budget = st.number_input("Allocated budget (₹)", min_value=0, value=0, step=1000,
                                       help=f"Unallocated budget available: {ui.inr(ctx['budget']['unallocated'])}. Free up money first if this is zero.")
            n_plan = st.number_input("Planned registrations (acquisition only)", min_value=0, value=0, step=10)
            if st.form_submit_button("Create campaign", type="primary"):
                try:
                    an.save_campaign(dict(name=n_name, type=n_type, owner=n_owner, description=n_desc, status="Planned", start_week=int(n_start),
                                          start_date=str(C.week_start(int(n_start))), end_date=str(C.week_end(12)), budget_allocated=n_budget,
                                          open_commitments=0, plan_regs_base=n_plan, plan_regs_stretch=n_plan,
                                          exp_confirm_rate=0.90 if n_type == "acquisition" else None,
                                          p_attend_confirmed=0.77 if n_type == "acquisition" else None), is_new=True)
                    ui.flash(f"Created campaign '{n_name}'. Expected confirm rate and attendance default to the 2025 overall rates; edit them if needed.")
                    st.rerun()
                except an.ValidationError as e:
                    st.error(str(e))
    with b2:
        st.markdown("**Archive the selected campaign**")
        st.caption(f"Archiving hides '{c['name']}' from analytics and returns its allocation to the unallocated pool. Its records are kept in the database.")
        sure = st.checkbox(f"Yes, archive {c['name']}", key=f"arch_ok_{c['id']}")
        if st.button("Archive campaign", disabled=not sure or c["id"] == "reserve"):
            try:
                an.archive_campaign(c["id"])
                st.session_state.pop("camp_sel", None)
                ui.flash(f"Archived {c['name']}.")
                st.rerun()
            except an.ValidationError as e:
                st.error(str(e))

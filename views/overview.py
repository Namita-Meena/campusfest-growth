"""Page 1 - Growth Overview: are we on track, and where is the gap?"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import analytics as an
from core import config as C
from core import historical as hist
from core import ui

ctx = an.build_context(ui.week())
f, b, t, s = ctx["forecast"], ctx["budget"], ctx["totals"], ctx["settings"]

ui.header("Growth Overview", "Are we on track for 2,600 verified attendees?" if s["base_target"] == 2600 else "Are we on track?",
          f"Week {ctx['week']} of {C.TOTAL_WEEKS} ({ctx['week_dates']}) · North Star: unique, verified external attendees · "
          f"{ui.tag('Simulated 2027')} campaign data, {ui.tag('Historical 2025')} facts and {ui.tag('Forecast')} values are labelled throughout.")
ui.show_flashes()
if ctx["data_week"] < ctx["week"]:
    st.info(f"Simulated weekly data is recorded up to week {ctx['data_week']}. Later weeks show the latest recorded position; "
            "add weekly numbers on the Campaign Intelligence page.")

actual = t["actual_verified_attendees"]
ui.cards([
    ("Projected attendance", ui.num(f["expected_attendance"]), f"{f['pct_of_base']:.0f}% of base target", "Forecast"),
    ("Base target", ui.num(f["base_target"]), f"Gap {f['gap_to_base']:+,}", "Target"),
    ("Stretch target", ui.num(f["stretch_target"]), f"Gap {f['gap_to_stretch']:+,}", "Target"),
    ("Registrations", ui.num(t["registrations"]), f"Plan to date {ui.num(t['plan_registrations_to_date'])}", "Simulated 2027"),
    ("Confirmed registrations", ui.num(t["confirmed"]), f"{ui.pct(t['confirm_rate'])} of registrations", "Simulated 2027"),
])
ui.cards([
    ("Actual verified attendees", ui.num(actual) if actual is not None else "—",
     "Entered after the festival (week 12)" if actual is None else "Entered check-in results", "Simulated 2027" if actual is not None else "Not yet available"),
    ("Approved budget", ui.inr(b["approved_budget"]), f"Allocated {ui.inr(b['allocated'])}", "Target"),
    ("Spent to date", ui.inr(b["spent_to_date"]), f"Committed incl. open orders {ui.inr(b['committed'])}", "Simulated 2027"),
    ("Uncommitted budget", ui.inr(b["uncommitted"]), f"of which reserve {ui.inr(b['reserve_uncommitted'])}", "Simulated 2027"),
    ("Cost per registration", ui.inr(t["cost_per_registration"]), f"Per projected attendee {ui.inr(t['cost_per_projected_attendee'])}"
     + (f" · actual per verified attendee {ui.inr(t['actual_cost_per_verified_attendee'])}" if actual else ""), "Simulated 2027"),
])

st.subheader("Performance alerts")
for sev, text in ctx["alerts"]:
    ui.alert(sev, text)

st.divider()
c1, c2 = st.columns(2)
with c1:
    st.subheader("Projected attendance vs targets")
    parts = [("Registered attendees", f["registered_attendees"], C.BLUE), ("Walk-ins", f["expected_walkins"], C.GREY),
             ("New Day-2 guests", f["expected_new_guests"], C.ORANGE)]
    fig = go.Figure()
    for name, val, col in parts:
        fig.add_bar(y=["Forecast"], x=[val], name=name, orientation="h", marker_color=col, text=[f"{val:,}"], textposition="inside")
    for label, val, col, pos in (("Base", f["base_target"], C.NAVY, "top right"), ("Stretch", f["stretch_target"], C.ORANGE, "top left"),
                                 ("2025 actual", 2050, C.GREY, "bottom left")):
        fig.add_vline(x=val, line_color=col, line_dash="dash", annotation_text=f"{label} {val:,}", annotation_position=pos)
    fig.update_layout(barmode="stack", xaxis_range=[0, max(f["stretch_target"], f["expected_attendance"]) * 1.15], bargap=0.55)
    fig = ui.style(fig, 260)
    fig.update_layout(legend=dict(orientation="h", yanchor="top", y=-0.25, xanchor="left", x=0), margin=dict(t=30, b=10))
    ui.show(fig, "fc_vs_target")
    st.caption("Forecast = confirmed × P(attend | confirmed) + unconfirmed × P(attend | unconfirmed) + walk-ins + new Day-2 guests. "
               f"Show-Up Engine {'active' if f['show_up_engine_active'] else 'not active'}; each person is counted once.")
with c2:
    st.subheader("Weekly registrations vs time-aligned plan")
    plan_final = t["plan_final_registrations"]
    weeks = list(range(1, C.TOTAL_WEEKS + 1))
    actual_w = [sum(m["registrations"] for m in ctx["metrics"] if m["week"] == w and any(c["id"] == m["campaign_id"] for c in ctx["campaigns"]))
                if w <= ctx["data_week"] else None for w in weeks]
    plan_w = [sum(c["projection"]["plan_final_registrations"] * (an.fc.curve_share(w, c["start_week"]) - an.fc.curve_share(w - 1, c["start_week"]))
                  for c in ctx["campaigns"] if c["projection"]) for w in weeks]
    fig = go.Figure()
    fig.add_bar(x=weeks, y=actual_w, name="Registrations (simulated)", marker_color=C.BLUE)
    fig.add_scatter(x=weeks, y=plan_w, name="Plan (2025 curve)", mode="lines+markers", line=dict(color=C.ORANGE, dash="dash"))
    fig.add_vline(x=ctx["week"], line_color=C.NAVY, line_dash="dot", annotation_text=f"W{ctx['week']}")
    fig.update_xaxes(title="Campaign week", dtick=1)
    ui.show(ui.style(fig, 280), "weekly_regs")
    st.caption(f"Plan = {plan_final:,} base registrations spread by the 2025 weekly registration curve (22% arrive by week 4).")

c1, c2 = st.columns(2)
with c1:
    st.subheader("Live funnel to date")
    stages = [("Reported reach (summed, not unique)", t["reach"]), ("Identified leads", t["leads"]), ("Registration starts", t["reg_starts"]),
              ("Registrations", t["registrations"]), ("Confirmed", t["confirmed"])]
    fig = go.Figure(go.Funnel(y=[x[0] for x in stages[1:]], x=[x[1] for x in stages[1:]], marker_color=[C.NAVY, C.BLUE, C.BLUE, C.ORANGE],
                              textinfo="value+percent previous"))
    ui.show(ui.style(fig, 300), "funnel")
    st.caption(f"Reported reach to date: {t['reach']:,} (platform-reported, summed across days; not unique people, so it is kept out of the funnel shape).")
with c2:
    st.subheader("Campaign projection vs plan (attendees)")
    acq = [c for c in ctx["campaigns"] if c["projection"]]
    fig = go.Figure()
    fig.add_bar(x=[c["name"] for c in acq], y=[c["projection"]["plan_attendees"] for c in acq], name="Plan", marker_color="#C9D3E6")
    fig.add_bar(x=[c["name"] for c in acq], y=[c["projection"]["projected_attendees"] for c in acq], name="Projected", marker_color=C.BLUE)
    fig.update_layout(barmode="group")
    ui.show(ui.style(fig, 320), "camp_proj")

c1, c2 = st.columns(2)
with c1:
    st.subheader("Budget utilisation")
    cs = ctx["campaigns"]
    fig = go.Figure()
    fig.add_bar(y=[c["name"] for c in cs], x=[c["spent"] for c in cs], name="Spent", orientation="h", marker_color=C.NAVY)
    fig.add_bar(y=[c["name"] for c in cs], x=[c["open_commitments"] for c in cs], name="Open commitments", orientation="h", marker_color=C.AMBER)
    fig.add_bar(y=[c["name"] for c in cs], x=[max(c["uncommitted"], 0) for c in cs], name="Uncommitted", orientation="h", marker_color="#C9D3E6")
    fig.update_layout(barmode="stack", yaxis=dict(autorange="reversed"), xaxis_tickprefix="₹")
    ui.show(ui.style(fig, 360), "budget")
with c2:
    st.subheader("Strategic growth bridge")
    scen = st.radio("Scenario", ["Base", "Stretch"], horizontal=True, label_visibility="collapsed", key="wf_scen")
    idx = 1 if scen == "Base" else 2
    rows = C.WATERFALL
    check = rows[0][idx] + sum(r[idx] for r in rows[1:-1])
    fig = go.Figure(go.Waterfall(x=[r[0] for r in rows], y=[r[idx] if r[3] != "total" else 0 for r in rows],
                                 measure=[r[3] for r in rows], text=[f"{r[idx]:+,}" if r[3] == "relative" else f"{r[idx]:,}" for r in rows],
                                 textposition="outside", connector=dict(line=dict(color=C.LINE)),
                                 increasing=dict(marker=dict(color=C.BLUE)), decreasing=dict(marker=dict(color=C.ORANGE)),
                                 totals=dict(marker=dict(color=C.NAVY))))
    fig.update_yaxes(range=[1500, max(r[idx] for r in rows) * 1.12])
    ui.show(ui.style(fig, 360), "waterfall")
    st.caption(f"{ui.tag('Assumption')} Strategic planning estimates from the deck, measured against one counterfactual (2025 mix at ₹3L). "
               f"Not measured campaign outcomes. Reconciliation check: bars sum to {check:,} "
               f"({'matches' if check == rows[-1][idx] else 'DOES NOT match'} the {scen.lower()} target of {rows[-1][idx]:,}).", unsafe_allow_html=True)

st.divider()
st.subheader("Funnel plan: 2025 actual vs 2027 base and stretch")
h = hist.snapshot()
hist_vals = {"Reported platform reach": h["reported_reach_sum"], "Identified leads": h["campaign_attributed_leads"],
             "Registrations": h["registrations_external"], "Registered attendees": h["registered_attendees"],
             "Unique walk-ins": h["walk_ins"], "Unique new Day-2 guests": h["new_day2_guests"], "Total verified attendees": h["verified_attendees"]}
rows = [{"Stage": k, "2025 actual (from raw data)": hist_vals[k], "Base 2027": v[1], "Stretch 2027": v[2]} for k, v in C.FUNNEL_PLAN.items()]
df = pd.DataFrame(rows)


def rate(a, bb):
    return [f"{100 * df.loc[df.Stage == a, col].iloc[0] / df.loc[df.Stage == bb, col].iloc[0]:.1f}%" for col in df.columns[1:]]


conv = pd.DataFrame([["Lead → registration", *rate("Registrations", "Identified leads")],
                     ["Registration → attended", *rate("Registered attendees", "Registrations")],
                     ["Attendees per 1,000 reported reach", *[f"{1000 * df.loc[6, c] / df.loc[0, c]:.2f}" for c in df.columns[1:]]]],
                    columns=["Conversion (calculated)", "2025", "Base", "Stretch"])
c1, c2 = st.columns([3, 2])
c1.dataframe(df.style.format({c: "{:,.0f}" for c in df.columns[1:]}), hide_index=True, width="stretch")
c2.dataframe(conv, hide_index=True, width="stretch")
st.caption("The 2025 column is recomputed from the original dataset each time (duplicates removed; external people; admitted + verified check-ins only). "
           "Reported reach is summed platform reach, not unique people. Base and stretch columns are planning targets.")

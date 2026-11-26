"""Page 3 - Experiments and Budget: decision engine, scenario simulator and decision log."""
import pandas as pd
import streamlit as st

from core import analytics as an
from core import config as C
from core import forecasting as fc
from core import ui

W = ui.week()
ctx = an.build_context(W)
s = ctx["settings"]
ui.header("Experiments and Budget", "What should we scale, change or stop this week?",
          f"Week {W} ({ctx['week_dates']}) · Recommendations are calculated from current data by rules with fixed thresholds and minimum samples. "
          "Nothing is applied until a person approves it.")
ui.show_flashes()

tab_dec, tab_sim, tab_log = st.tabs(["Decision engine", "Budget and forecast simulator", "Decision log"])

FIELD_HELP = {
    "pitches_completed": "Club pitches completed so far",
    "control_starts": "No-deposit arm: registration starts", "control_confirmed": "No-deposit arm: confirmed registrants",
    "treatment_starts": "Deposit arm: registration starts", "treatment_confirmed": "Deposit arm: confirmed registrants",
    "control_attended": "No-deposit arm: verified attendees (after the festival)", "treatment_attended": "Deposit arm: verified attendees (after the festival)",
    "control_registrants": "Plain-link arm: registrants", "control_new_people": "Plain-link arm: NEW people they brought",
    "treatment_registrants": "Squad-link arm: registrants", "treatment_new_people": "Squad-link arm: NEW people they brought",
    "squads_formed": "Squads formed (fast lane capped at 300)",
    "passes_issued": "Guest passes issued in the pilot", "redeemed_new_people": "Redeemed by genuinely new people",
    "redeemed_existing_registrants": "Redeemed by people already registered (not counted)",
    "cohort_checkin_pay": "Ambassadors in the pay-per-check-in cohort", "cohort_signup_pay": "Ambassadors in the pay-per-sign-up cohort",
    "active_ambassadors": "Active ambassadors", "legit_registrations_last_2_weeks": "Legitimate verified registrations, last 2 weeks",
    "fraud_confirmed": "Ambassadors with CONFIRMED fake registrations", "verified_attendees": "Verified attendees via ambassadors (after the festival)",
}
OPTIONAL = {"control_attended", "treatment_attended", "verified_attendees"}


def decision_card(d: dict, editable: bool = True):
    with st.container(border=True):
        top = st.columns([5, 2])
        top[0].markdown(f"#### {d['name']}")
        top[1].markdown(f"<div style='text-align:right;padding-top:10px'>{ui.pill(d['state'])}</div>", unsafe_allow_html=True)
        a, b = st.columns(2)
        a.markdown(f"**Decision metric**  \n{d['metric_label']}: **{d['metric_value']}**")
        a.markdown(f"**Minimum sample**  \n{d['sample']} {'✓' if d['sample_ok'] else '— not met'}")
        b.markdown(f"**Thresholds**  \n{d['threshold']}")
        b.markdown(f"**Recommended action**  \n{d['action']}")
        det = d.get("details", {})
        test = det.get("test")
        if test and test.get("valid"):
            st.caption(f"Two-proportion z-test: control {100 * test['control_rate']:.1f}%, deposit {100 * test['treatment_rate']:.1f}%, difference "
                       f"{test['diff_pts']:+.1f} pts (95% CI {test['ci_low_pts']:+.1f} to {test['ci_high_pts']:+.1f}), z = {test['z']:.2f}, p = {test['p_value']:.4f} → "
                       f"{'statistically significant' if test['significant'] else 'not statistically significant'} at 5%. "
                       f"2025 baselines: {C.THRESHOLDS['showup']['hist_confirmed_per_100']} confirmed and {C.THRESHOLDS['showup']['hist_attended_per_100']} attended per 100 starts. "
                       "Confirmation is an early indicator; the final judgement uses verified attendees per 100 starts.")
            ft = det.get("final_test")
            if ft and ft.get("valid"):
                st.caption(f"Final metric (verified attendees per 100 starts): control {100 * ft['control_rate']:.1f}, deposit {100 * ft['treatment_rate']:.1f}, "
                           f"difference {ft['diff_pts']:+.1f} pts, p = {ft['p_value']:.4f}.")
        if det.get("note"):
            st.caption(det["note"])
        if d.get("inputs_recorded_week") and d["inputs_recorded_week"] != W:
            st.caption(f"Experiment inputs shown were recorded in week {d['inputs_recorded_week']}; saving below records a week-{W} snapshot.")
        if not editable:
            return
        key = d["key"]
        with st.expander("Update experiment data"):
            if key == "club":
                st.caption("Club registrations come from the Club Contingent League campaign record (Campaign Intelligence page), so there is one source of truth.")
            with st.form(f"exp_{key}_{W}"):
                vals, cols = {}, st.columns(2)
                for j, (k, v) in enumerate((d.get("inputs") or {}).items()):
                    label = FIELD_HELP.get(k, k.replace("_", " "))
                    if k in OPTIONAL:
                        known = cols[j % 2].checkbox(f"{label}: available", value=v is not None, key=f"k_{key}_{k}_{W}")
                        num = cols[j % 2].number_input(label, min_value=0, value=int(v or 0), step=1, key=f"n_{key}_{k}_{W}", label_visibility="collapsed")
                        vals[k] = num if known else None
                    else:
                        vals[k] = cols[j % 2].number_input(label, min_value=0, value=int(v or 0), step=1, key=f"n_{key}_{k}_{W}")
                if st.form_submit_button("Save experiment data"):
                    try:
                        an.save_experiment(key, W, vals)
                        ui.flash(f"Saved week-{W} data for {d['name']}.")
                        st.rerun()
                    except an.ValidationError as e:
                        st.error(str(e))
        done = [l for l in ctx["decision_logs"] if l["decision_key"] == key and l["week"] == W and l["recommendation"] == d["state"]]
        if done:
            last = max(done, key=lambda l: l["created_at"])
            st.caption(f"Already {last['outcome'].lower()} this week by {last['decided_by']}"
                       + (f" (₹{last['amount_moved']:,} moved)." if last.get("amount_moved") else "."))
        if d["state"] != "Continue Monitoring":
            c1, c2, c3 = st.columns([2, 1, 1])
            note = c1.text_input("Note (optional)", key=f"note_{key}", label_visibility="collapsed", placeholder="Decision note (optional)")
            if c2.button("Approve", key=f"ap_{key}", type="primary", width="stretch"):
                try:
                    log = an.apply_decision(d, W, True, note=note)
                    ui.flash(f"Approved: {d['name']} → {d['state']}." + (f" Moved ₹{log['amount_moved']:,} from {log['transfer_from']} to {log['transfer_to']}." if log["amount_moved"] else ""))
                    st.rerun()
                except an.ValidationError as e:
                    st.error(str(e))
            if c3.button("Reject", key=f"rj_{key}", width="stretch"):
                an.apply_decision(d, W, False, note=note)
                ui.flash(f"Rejected the recommendation for {d['name']}. Nothing was changed.", "info")
                st.rerun()


with tab_dec:
    st.caption("Four states: Scale, Change / Fix, Stop, Continue Monitoring. Bands do not overlap; below the minimum sample every rule returns Continue Monitoring. "
               "Budget transfers move only uncommitted money and the reserve can never be allocated twice.")
    for k in C.EXPERIMENT_NAMES:
        if k in ctx["decisions"]:
            decision_card(ctx["decisions"][k])
    g = ctx["guardrail"]
    g = {**g, "name": "Week-6 guardrail: forecast vs plan"}
    decision_card(g, editable=False)
    if g["state"] != "Continue Monitoring":
        c1, c2 = st.columns(2)
        if c1.button("Acknowledge guardrail diagnosis", type="primary"):
            try:
                an.apply_decision(g, W, True, note="Guardrail diagnosis acknowledged")
                ui.flash("Guardrail diagnosis logged. Use the AI copilot or Task Manager to assign the recovery task.")
                st.rerun()
            except an.ValidationError as e:
                st.error(str(e))
    others = [c for c in ctx["campaigns"] if c.get("recommendation") and c["recommendation"]["key"].startswith("generic")]
    if others:
        st.markdown("#### Campaigns without a dedicated experiment")
        st.dataframe(pd.DataFrame([{"Campaign": c["name"], "Recommendation": c["recommendation"]["state"], "Evidence": c["recommendation"]["metric_value"],
                                    "Sample": c["recommendation"]["sample"], "Action": c["recommendation"]["action"]} for c in others]),
                     hide_index=True, width="stretch")
        st.caption(f"Rule: {others[0]['recommendation']['threshold']}. ₹{int(s['cost_screen_inr'])} is paid social's 2025 cost per attendee, used as a conservative screen, not a like-for-like cost.")

# ---------------------------------------------------------------------------
with tab_sim:
    st.caption("Scenario planning. Nothing here changes live data unless you press Apply at the bottom. "
               "Budgets do not change registrations unless you switch on the explicit budget-elasticity assumption.")
    acq = [c for c in ctx["campaigns"] if c["projection"]]
    base_rows = pd.DataFrame([{"Campaign": c["name"], "Expected registrations": int(c["plan_regs_base"] or 0),
                               "Confirm rate": float(c["exp_confirm_rate"] or 0), "P(attend | confirmed)": float(c["p_attend_confirmed"] or 0),
                               "Budget (₹)": int(c["budget_allocated"])} for c in acq])
    preset = st.radio("Start from", ["Base plan", "Current projection (live pace)", "Stretch plan", "Downside"], horizontal=True, key="sim_preset")
    start = base_rows.copy()
    if preset == "Current projection (live pace)":
        start["Expected registrations"] = [int(round(c["projection"]["projected_final_registrations"])) for c in acq]
    elif preset == "Stretch plan":
        start["Expected registrations"] = [int(c["plan_regs_stretch"] or 0) for c in acq]
    elif preset == "Downside":
        start["Expected registrations"] = (start["Expected registrations"] * 0.85).round().astype(int)
    defaults = {"Base plan": (0.0265, 150, 0.06), "Current projection (live pace)": (float(s["reminder_lift"]), int(s["walkins_expected"]), float(s["guest_redemption_rate"])),
                "Stretch plan": (0.0735, 250, 0.12), "Downside": (0.0, 125, 0.03)}[preset]

    left, right = st.columns([3, 2])
    with left:
        edited = st.data_editor(start, hide_index=True, width="stretch", key=f"sim_tbl_{preset}", disabled=["Campaign"],
                                column_config={"Expected registrations": st.column_config.NumberColumn(min_value=0, step=10),
                                               "Confirm rate": st.column_config.NumberColumn(min_value=0.0, max_value=1.0, step=0.01, format="%.3f"),
                                               "P(attend | confirmed)": st.column_config.NumberColumn(min_value=0.0, max_value=1.0, step=0.01, format="%.3f"),
                                               "Budget (₹)": st.column_config.NumberColumn(min_value=0, step=1000)})
        use_k = st.checkbox("Derive Squad Pass registrations from the referral coefficient k", value=False, key=f"usek_{preset}")
        k = st.slider("Referral coefficient k (new registrants per registrant from other campaigns)", 0.0, 0.5, 0.20, 0.01, key=f"k_{preset}", disabled=not use_k)
        link = st.checkbox("Assumption: link budget changes to registrations (cost per registration rises as spend doubles)", value=False, key=f"link_{preset}")
        elast = st.slider("Cost-per-registration increase per doubling of spend", 0, 60, 27, 1, format="%d%%", key=f"el_{preset}", disabled=not link,
                          help="The strategy deck assumes 27% (base). 0% means registrations scale 1:1 with budget.")
    with right:
        show_on = st.checkbox("Show-Up Engine active (reminders + waitlist release)", value=True, key=f"so_{preset}")
        wl = st.slider("Waitlist recovery (points added to confirm rate)", 0.0, 0.08, float(s["waitlist_recovery"]), 0.005, format="%.3f", key=f"wl_{preset}", disabled=not show_on)
        rl = st.slider("Reminder / deposit lift (points added to P(attend | confirmed))", 0.0, 0.12, defaults[0], 0.0005, format="%.4f", key=f"rl_{preset}", disabled=not show_on)
        pu = st.slider("P(attend | unconfirmed)", 0.0, 0.30, float(s["p_attend_unconfirmed"]), 0.01, key=f"pu_{preset}", help="2025 fact: 0 of 300 unconfirmed registrants attended.")
        walk = st.number_input("Expected unique walk-ins", min_value=0, value=defaults[1], step=5, key=f"walk_{preset}")
        gr = st.slider("Day-2 guest redemption rate (new people)", 0.0, 0.25, defaults[2], 0.005, format="%.3f", key=f"gr_{preset}")
        cap = st.number_input("Venue capacity (simultaneous)", min_value=0, value=int(s["venue_capacity"]), step=100, key=f"cap_{preset}")
        a, b = st.columns(2)
        base_t = a.number_input("Base target", min_value=0, value=int(s["base_target"]), step=50, key=f"bt_{preset}")
        str_t = b.number_input("Stretch target", min_value=0, value=int(s["stretch_target"]), step=50, key=f"st_{preset}")

    import math
    sim = edited.copy()
    orig_budget = dict(zip(base_rows["Campaign"], base_rows["Budget (₹)"]))
    if link:
        el = math.log2(1 + elast / 100)
        for idx, row in sim.iterrows():
            ob = orig_budget.get(row["Campaign"], 0)
            if ob > 0 and row["Budget (₹)"] > 0:
                sim.loc[idx, "Expected registrations"] = round(row["Expected registrations"] * (row["Budget (₹)"] / ob) ** (1 - el))
            elif row["Budget (₹)"] == 0:
                sim.loc[idx, "Expected registrations"] = 0
    if use_k:
        sq = sim["Campaign"] == "Squad Pass"
        if sq.any():
            sim.loc[sq, "Expected registrations"] = round(float(sim.loc[~sq, "Expected registrations"].sum()) * k)
    s2 = {**s, "waitlist_recovery": wl, "reminder_lift": rl, "p_attend_unconfirmed": pu, "walkins_expected": walk,
          "guest_redemption_rate": gr, "venue_capacity": cap, "base_target": base_t, "stretch_target": str_t}
    rows = [{"registrations": r["Expected registrations"], "confirm_rate": r["Confirm rate"], "p_attend_confirmed": r["P(attend | confirmed)"]}
            for _, r in sim.iterrows()]
    out = fc.simple_forecast(rows, s2, showup_active=show_on, guest_active=True)
    non_acq = sum(c["budget_allocated"] for c in ctx["campaigns"] if not c["projection"])
    sim_budget = int(sim["Budget (₹)"].sum()) + non_acq
    st.divider()
    ui.cards([("Expected attendance", ui.num(out["expected_attendance"]), f"{out['registered_attendees']:,} registered + {out['expected_walkins']:,} walk-ins + {out['expected_new_guests']:,} guests", "Forecast"),
              ("Gap to base", f"{out['gap_to_base']:+,}", f"Base {out['base_target']:,}", None),
              ("Gap to stretch", f"{out['gap_to_stretch']:+,}", f"Stretch {out['stretch_target']:,}", None),
              ("Cost per attendee", ui.inr(fc.safe_div(sim_budget, out["expected_attendance"])), f"Scenario budget {ui.inr(sim_budget)}", None),
              ("Budget available", ui.inr(int(s["total_budget"]) - sim_budget), f"Approved {ui.inr(s['total_budget'])}", None)])
    if sim_budget > int(s["total_budget"]):
        st.error(f"This scenario allocates {ui.inr(sim_budget)}, which is {ui.inr(sim_budget - int(s['total_budget']))} over the approved budget.")
    if not out["capacity_ok"]:
        st.error(f"Capacity warning: estimated peak day {out['peak_day_estimate']:,} exceeds the venue capacity of {out['venue_capacity']:,}.")
    else:
        st.caption(f"Capacity check: estimated peak day {out['peak_day_estimate']:,} (70% of unique attendees, 2025 pattern) vs capacity {out['venue_capacity']:,}.")
    if use_k or link:
        st.caption("Registrations after assumptions: " + ", ".join(f"{r['Campaign']} {int(r['Expected registrations']):,}" for _, r in sim.iterrows()))

    def preset_forecast(reg_col, lift, w_in, g_rate, factor=1.0, engine=True):
        rr = [{"registrations": (c[reg_col] or 0) * factor, "confirm_rate": c["exp_confirm_rate"], "p_attend_confirmed": c["p_attend_confirmed"]} for c in acq]
        return fc.simple_forecast(rr, {**s, "reminder_lift": lift, "walkins_expected": w_in, "guest_redemption_rate": g_rate}, showup_active=engine)

    sc = {"Downside (85% registrations, no Show-Up Engine, 3% guests)": preset_forecast("plan_regs_base", 0.0, 125, 0.03, 0.85, False),
          "Base plan": preset_forecast("plan_regs_base", 0.0265, 150, 0.06),
          "Stretch plan (deposit wins its test, k = 0.30, 12% guests)": preset_forecast("plan_regs_stretch", 0.0735, 250, 0.12),
          "Your scenario above": out}
    st.dataframe(pd.DataFrame([{"Scenario": n, "Registrations": o["projected_final_registrations"], "Registered attendees": o["registered_attendees"],
                                "Walk-ins": o["expected_walkins"], "New guests": o["expected_new_guests"], "Expected attendance": o["expected_attendance"],
                                "vs base": o["expected_attendance"] - base_t, "vs stretch": o["expected_attendance"] - str_t} for n, o in sc.items()]),
                 hide_index=True, width="stretch")
    st.caption("The base and stretch rows reproduce the deck's 2,600 and 3,400 targets from the same formula (small rounding differences are expected).")

    with st.expander("Apply this scenario to the live plan"):
        st.warning("This overwrites the live plan: planned registrations, expected rates and budgets of the acquisition campaigns, plus targets, capacity, "
                   "walk-ins, guest redemption and Show-Up Engine lifts. Recorded weekly results are not changed.")
        sure = st.checkbox("I understand and want to apply this scenario", key=f"apply_ok_{preset}")
        if st.button("Apply scenario to live plan", disabled=not sure, type="primary"):
            try:
                if sim_budget > int(s["total_budget"]):
                    raise an.ValidationError("The scenario is over the approved budget. Reduce budgets first.")
                order = sorted(range(len(acq)), key=lambda j: sim.iloc[j]["Budget (₹)"] - acq[j]["budget_allocated"])  # decreases first so the cap is never broken mid-way
                for j in order:
                    c, r = acq[j], sim.iloc[j]
                    if int(r["Budget (₹)"]) < c["committed"]:
                        raise an.ValidationError(f"{c['name']}: budget cannot go below the ₹{c['committed']:,} already spent or committed.")
                for j in order:
                    c, r = acq[j], sim.iloc[j]
                    an.save_campaign(dict(id=c["id"], name=c["name"], status=c["status"], budget_allocated=int(r["Budget (₹)"]),
                                          open_commitments=c["open_commitments"], plan_regs_base=int(r["Expected registrations"]),
                                          exp_confirm_rate=float(r["Confirm rate"]), p_attend_confirmed=float(r["P(attend | confirmed)"])))
                an.save_settings({"waitlist_recovery": wl if show_on else 0.0, "reminder_lift": rl if show_on else 0.0, "p_attend_unconfirmed": pu,
                                  "walkins_expected": int(walk), "guest_redemption_rate": gr, "venue_capacity": int(cap),
                                  "base_target": int(base_t), "stretch_target": int(str_t)})
                ui.flash("Scenario applied to the live plan. All pages and the AI copilot now use it.")
                st.rerun()
            except an.ValidationError as e:
                st.error(str(e))

# ---------------------------------------------------------------------------
with tab_log:
    logs = sorted(ctx["decision_logs"], key=lambda l: l["created_at"], reverse=True)
    if not logs:
        st.info("No decisions have been approved or rejected yet.")
    else:
        names = {c["id"]: c["name"] for c in ctx["campaigns"]}
        st.dataframe(pd.DataFrame([{"When (UTC)": l["created_at"][:16].replace("T", " "), "Week": l["week"], "Decision": C.EXPERIMENT_NAMES.get(l["decision_key"], l["decision_key"]),
                                    "Recommendation": l["recommendation"], "Outcome": l["outcome"], "Evidence": l["metric"], "Action": l["action"],
                                    "₹ moved": l.get("amount_moved") or 0, "From": names.get(l.get("transfer_from"), "—"), "To": names.get(l.get("transfer_to"), "—"),
                                    "By": l["decided_by"], "Note": l.get("note") or ""} for l in logs]), hide_index=True, width="stretch")

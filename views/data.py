"""Reference - Historical Data Explorer and Methodology."""
import pandas as pd
import streamlit as st

from core import config as C
from core import forecasting as fc
from core import historical as hist
from core import ui

ui.header("Historical Data and Methodology", "CampusFest 2025: the evidence behind the plan",
          f"{ui.tag('Historical 2025')} Original dataset supplied by RISA Labs (fictional, synthetic). It is read-only: editing the simulated 2027 campaign never changes it.")

d = hist.load()
tab1, tab2, tab3, tab4, tab5 = st.tabs(["2025 funnel", "Campaign summary", "Explore tables", "Data dictionary and quality", "Methodology"])

with tab1:
    as_of = st.date_input("Snapshot as of the end of day", pd.Timestamp("2025-04-20").date(), min_value=pd.Timestamp("2025-01-15").date(),
                          max_value=pd.Timestamp("2025-04-20").date(),
                          help="Uses the latest registration-status version effective by that day; no later outcome appears in an earlier snapshot.")
    s = hist.snapshot(str(as_of))
    ui.cards([("Verified attendees", ui.num(s["verified_attendees"]), f"{s['registered_attendees']:,} registered + {s['walk_ins']:,} walk-ins", None),
              ("Registrations", ui.num(s["registrations_external"]), "distinct external people", None),
              ("Confirmed", ui.num(s["confirmed"]), f"{s['unconfirmed']:,} not confirmed", None),
              ("Campaign leads", ui.num(s["campaign_attributed_leads"]), f"{s['identified_external_people']:,} identified external people in total", None),
              ("Marketing spend", ui.inr(s["marketing_spend_inr"]), f"Budget in effect {ui.inr((s['targets_in_effect'] or {}).get('marketing_budget_inr'))}", None)])
    a, b = st.columns(2)
    with a:
        st.markdown("**Funnel**")
        rows = [("Reported reach (summed platform reach, not unique people)", s["reported_reach_sum"]), ("Landing-page sessions (anonymous)", s["landing_page_sessions"]),
                ("Identified external people", s["identified_external_people"]), ("of which campaign-attributed leads", s["campaign_attributed_leads"]),
                ("Identified registration starters", s["identified_registration_starters"]), ("Registrations (external)", s["registrations_external"]),
                ("Confirmed (latest status)", s["confirmed"]), ("Registered attendees (admitted + verified)", s["registered_attendees"]),
                ("Walk-ins (no registration)", s["walk_ins"]), ("New Day-2 guests (no programme in 2025)", s["new_day2_guests"]),
                ("Total verified attendees", s["verified_attendees"])]
        st.dataframe(pd.DataFrame(rows, columns=["Stage", "Count"]).style.format({"Count": "{:,.0f}"}), hide_index=True, width="stretch")
    with b:
        st.markdown("**Rates used by the plan**")
        rr = [("Confirmed per 100 registration starts", s["confirmed_per_100_starts"]), ("Attended per 100 registration starts", s["attended_per_100_starts"]),
              ("Attendance among confirmed registrants", None if s["attendance_rate_among_confirmed"] is None else 100 * s["attendance_rate_among_confirmed"]),
              ("Attendance among unconfirmed registrants", None if s["attendance_rate_among_unconfirmed"] is None else 100 * s["attendance_rate_among_unconfirmed"])]
        st.dataframe(pd.DataFrame(rr, columns=["Rate", "Value (%)"]), hide_index=True, width="stretch")
        st.markdown("**Registration status (latest version as of the snapshot)**")
        st.dataframe(pd.DataFrame(list(s["status_counts_latest_version"].items()), columns=["Status", "Registrations"]), hide_index=True, width="stretch")
        tg = s["targets_in_effect"]
        if tg:
            st.caption(f"Targets in effect ({tg['target_version']}): {tg['identified_external_people_goal']:,} identified people, {tg['registration_goal']:,} registrations, "
                       f"{tg['unique_external_visitors_goal']:,} verified visitors, budget {ui.inr(tg['marketing_budget_inr'])}.")
    for n in s["notes"]:
        st.caption("• " + n)

with tab2:
    bc = hist.by_campaign()
    show = bc.rename(columns={"campaign_name": "Campaign", "channel": "Channel", "reported_reach": "Reported reach", "marketing_spend_inr": "Spend",
                              "leads": "Leads", "registrations": "Registrations", "confirmed": "Confirmed", "attended": "Attended",
                              "confirm_rate": "Confirm rate", "attended_per_registered": "Attended / registered", "attended_per_confirmed": "Attended / confirmed",
                              "cost_per_registration": "₹ / registration", "cost_per_attendee": "₹ / attendee"})
    cols = ["Campaign", "Channel", "Reported reach", "Spend", "Leads", "Registrations", "Confirmed", "Attended", "Confirm rate",
            "Attended / registered", "Attended / confirmed", "₹ / registration", "₹ / attendee"]
    st.dataframe(show[cols].style.format({"Reported reach": "{:,.0f}", "Spend": "₹{:,.0f}", "Confirm rate": "{:.1%}", "Attended / registered": "{:.1%}",
                                          "Attended / confirmed": "{:.1%}", "₹ / registration": "₹{:,.0f}", "₹ / attendee": "₹{:,.0f}"}),
                 hide_index=True, width="stretch")
    st.caption("Registrations and attendees are attributed to the recorded acquisition source of the registration (a source relationship, not proof of incrementality). "
               "Paid social and creators took 55% of spend (₹1,52,000 of ₹2,74,000) and produced 27% of registered attendees at about a 50% show rate. "
               "The 125 walk-ins are unattributed.")
    wk = hist.weekly_registrations()
    cum = [sum(wk[:i + 1]) / sum(wk) for i in range(12)]
    st.markdown("**Weekly registration curve (used to pace the 2027 plan)**")
    st.dataframe(pd.DataFrame({"Campaign week": [f"W{i}" for i in range(1, 13)], "Registrations": [f"{x:,}" for x in wk],
                               "Cumulative share": [f"{x:.1%}" for x in cum]}).set_index("Campaign week").T, width="stretch")

with tab3:
    names = {"people_summary": "People summary (one row per identified person, derived)", "people": "People", "registrations": "Registrations",
             "registration_history": "Registration status history", "checkins": "Check-ins", "interactions": "Interest and engagement",
             "daily_marketing": "Daily marketing", "campaigns": "Campaigns", "targets": "Targets", "event": "Event"}
    t = st.selectbox("Table", list(names), format_func=names.get)
    df = d[t]
    a, b = st.columns(2)
    cat_cols = [c for c in df.columns if df[c].nunique(dropna=False) <= 12]
    col = a.selectbox("Filter column (optional)", ["(none)"] + cat_cols)
    if col != "(none)":
        vals = b.multiselect("Values", sorted(df[col].dropna().astype(str).unique()))
        if vals:
            df = df[df[col].astype(str).isin(vals)]
    q = st.text_input("Search text in any column (e.g. a person ID such as E0001)")
    if q:
        mask = df.astype(str).apply(lambda s_: s_.str.contains(q, case=False, regex=False)).any(axis=1)
        df = df[mask]
    st.caption(f"{len(df):,} rows (duplicated source IDs already removed). Showing up to 2,000. Person names are removed: they are synthetic display labels and are not needed for analysis.")
    st.dataframe(df.head(2000), hide_index=True, width="stretch", height=420)
    st.download_button("Download filtered rows (CSV)", df.to_csv(index=False).encode(), file_name=f"campusfest2025_{t}.csv", mime="text/csv")

with tab4:
    q = hist.quality_report()
    st.markdown("**Data quality checks**")
    st.dataframe(pd.DataFrame([{"Table": k, "Raw rows": v["raw_rows"], "Duplicate IDs removed": v["duplicate_ids_removed"], "Rows used": v["rows_used"],
                                "Missing values": ", ".join(f"{c}: {n}" for c, n in v["missing_values"].items()) or "none"} for k, v in q["tables"].items()]),
                 hide_index=True, width="stretch")
    st.caption(f"Person types: {q['person_types']} (only external counts toward attendee targets). Check-in results: {q['checkin_results']}; "
               f"verification: {q['checkin_verification']} (only admitted + verified counts). Vendor-credit rows with negative spend: "
               f"{q['negative_spend_rows_vendor_credits']}. People with no campaign assignment (walk-ins, event access, internal): {q['people_without_campaign']}. "
               "Missing registration IDs on check-ins are walk-ins and non-registered identities, not errors.")
    st.markdown("**Not available in the dataset** (the AI copilot says so instead of guessing)")
    st.write(", ".join(hist.NOT_IN_DATASET))
    st.markdown("**Data dictionary (from the dataset's own field guide)**")
    st.dataframe(pd.read_csv(hist.DATA_DIR / "field_guide.csv"), hide_index=True, width="stretch", height=380)

with tab5:
    n3 = fc.sample_size_per_arm(0.813, 3)
    n7 = fc.sample_size_per_arm(0.813, 7)
    st.markdown(f"""
**What is fact, what is simulated, what is assumed**

| Kind | Source | Examples |
|---|---|---|
| Historical 2025 (fact) | Original dataset, recomputed on load | 2,050 verified attendees; 77% attendance among confirmed; ₹274 per attendee for paid social |
| Simulated 2027 | Seeded demo data, editable | Weekly registrations, spend, experiment counts |
| Target | Three-slide strategy deck | 2,600 base, 3,400 stretch, ₹3,00,000 budget |
| Forecast | Formula below on simulated data | Projected attendance |
| Assumption | Stated and adjustable in the simulator | Venue capacity 3,000; guest redemption 6%; reminder lift |

**Forecast**
`expected attendance = confirmed × P(attend | confirmed) + unconfirmed × P(attend | unconfirmed) + walk-ins + new Day-2 guests`
- Projected final registrations per campaign = registrations to date + remaining plan × current pace (pace limited to 0.25–2.0×). The time-aligned plan uses the 2025 weekly registration curve.
- Confirm rate = observed to date once a campaign has 30 registrations, otherwise the 2025 rate of the matching channel.
- P(attend | confirmed) is each channel's 2025 rate with **confirmed** registrants as the denominator, so the confirmation drop is not applied twice. P(attend | unconfirmed) = 0 (2025: 0 of 300).
- The Show-Up Engine is an intervention: +{100 * C.DEFAULT_SETTINGS['waitlist_recovery']:.1f} points confirm rate (waitlist release; 88 of 2,800 were stuck in 2025) and +{100 * C.DEFAULT_SETTINGS['reminder_lift']:.2f} points attendance among confirmed (calibrated so the base plan reproduces 2,351 registered attendees). It never adds people.
- New Day-2 guests = Day-1 registered attendees (70% of registered attendees, 2025 pattern) × redemption rate. Walk-ins and guests hold no registration, so every person is counted once.

**Attribution**
Each registration belongs to exactly one acquisition campaign (its recorded source), the same rule as the 2025 dataset. The deck's incremental estimates (+389, +144, …) are strategic planning numbers against one counterfactual and are never added to campaign attendance.

**Decision rules**
Fixed thresholds from slide 3, mutually exclusive bands, minimum samples, and *Continue Monitoring* as the default. The deposit test uses a two-sided two-proportion z-test at 5%: with 500 starts per arm a gap of about 5 points is significant, a true 7-point lift is detected about 80% of the time (needs {n7:,} per arm), and detecting a 3-point lift would need about {n3:,} per arm. The Day-2 guest pilot (200 passes ≈ 12 redemptions at 6%) is directional only.

**Budget control**
Uncommitted = allocation − spend − open commitments. Approved transfers move only uncommitted money and reduce the source, so the reserve cannot be allocated twice. Total allocations cannot exceed ₹3,00,000.

**AI copilot**
Gemini with function calling. The model calls deterministic Python tools that read the current database and the cleaned 2025 dataset; it does not do arithmetic itself, cannot run code or SQL, and cannot write data. Task drafts need explicit approval.
""")

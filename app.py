"""CampusFest Growth Intelligence - entry point.

Run locally:  python -m streamlit run app.py
"""
from __future__ import annotations

import streamlit as st

from core import config as C
from core import database as db
from core import ui

st.set_page_config(page_title=C.APP_NAME, page_icon=":material/monitoring:", layout="wide")

pages = {
    "Command centre": [
        st.Page("views/overview.py", title="Growth Overview", icon=":material/monitoring:", default=True),
        st.Page("views/campaigns.py", title="Campaign Intelligence", icon=":material/campaign:"),
        st.Page("views/experiments.py", title="Experiments and Budget", icon=":material/science:"),
        st.Page("views/tasks.py", title="Task Manager", icon=":material/checklist:"),
        st.Page("views/copilot.py", title="AI Growth Copilot", icon=":material/smart_toy:"),
    ],
    "Reference": [
        st.Page("views/data.py", title="Historical Data and Methodology", icon=":material/database:"),
    ],
}
nav = st.navigation(pages)

with st.sidebar:
    st.markdown(f"### {C.APP_NAME}")
    st.caption(f"{C.FESTIVAL} · {C.FEST_DATES}\n\nChallenge A: Attendee Growth")
    st.session_state.setdefault("sim_week", 4)
    st.select_slider("Simulated campaign week", options=list(range(1, C.TOTAL_WEEKS + 1)), key="sim_week",
                     help="The 2027 campaign is a planning scenario, so the app runs on a simulated week instead of today's date. "
                          f"Week 1 starts {C.CAMPAIGN_START:%d %b %Y}; the festival is in week 12. Simulated weekly data is seeded for weeks 1-{C.SEEDED_WEEKS}.")
    w = st.session_state["sim_week"]
    st.caption(f"Week {w}: {C.week_start(w):%d %b} – {C.week_end(w):%d %b %Y}")
    st.divider()
    try:
        store = db.get_store()
        persistent = store.backend.startswith("Supabase")
        st.caption(f"Storage: {'🟢' if persistent else '🟠'} {store.backend}")
        if db.last_error:
            st.caption(f"⚠ {db.last_error}")
    except Exception as e:  # pragma: no cover - shown to the user
        st.error(f"Database error: {e}")
        st.stop()
    with st.expander("Demo workspace"):
        st.caption("All visitors share one persistent demo workspace. Edits are saved for everyone. "
                   "Reset restores the seeded week-4 scenario; the original 2025 dataset is read-only and is never changed.")
        ok = st.checkbox("I want to reset the demo data", key="reset_ok")
        if st.button("Reset demo workspace", disabled=not ok, width="stretch"):
            db.reset_demo()
            for k in ("chat", "pending_task"):
                st.session_state.pop(k, None)
            ui.flash("Demo workspace reset to the seeded week-4 scenario.")
            st.rerun()
    st.caption(f"Built by {C.CANDIDATE}, {C.INSTITUTION}\n\nRISA Labs Growth APM assignment")

nav.run()

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
        st.Page("views/overview.py", title="Growth Overview", default=True),
        st.Page("views/campaigns.py", title="Campaign Intelligence"),
        st.Page("views/experiments.py", title="Experiments and Budget"),
        st.Page("views/tasks.py", title="Task Manager"),
        st.Page("views/copilot.py", title="AI Growth Copilot"),
    ],
    "Reference": [
        st.Page("views/data.py", title="Historical Data and Methodology"),
    ],
}
nav = st.navigation(pages, position="hidden")     # the menu is drawn below so the brand can sit above it

with st.sidebar:
    st.markdown(
        f"<div class='cf-brand'><div class='mark'>CF</div><div><div class='t'>CampusFest</div>"
        f"<div class='s'>Growth Intelligence</div></div></div>", unsafe_allow_html=True)
    for section, items in pages.items():
        st.markdown(f"<div class='cf-side-lab cf-nav-lab'>{section}</div>", unsafe_allow_html=True)
        for page in items:
            here = page.url_path == nav.url_path
            with st.container(key=f"nav_{'active' if here else 'item'}_{page.url_path or 'home'}"):
                st.page_link(page, label=page.title.replace(" and Methodology", ""))
    ui.theme_control()            # one Dark / Light switch for the whole app
    ui.inject_css()               # every page below is drawn in the chosen theme
    st.session_state.setdefault("sim_week", 4)
    w = st.session_state["sim_week"]
    st.markdown(f"<div class='cf-panel'><div class='k'>Simulated campaign week</div>"
                f"<div class='wk'>{w:02d} <span>/ {C.TOTAL_WEEKS}</span></div>"
                f"<div class='d'>{C.week_start(w):%d %b} – {C.week_end(w):%d %b %Y}</div></div>", unsafe_allow_html=True)
    st.select_slider("Move the week", options=list(range(1, C.TOTAL_WEEKS + 1)), key="sim_week",
                     label_visibility="collapsed",
                     help="The 2027 campaign is a planning scenario, so the app runs on a simulated week instead of today's date. "
                          f"Week 1 starts {C.CAMPAIGN_START:%d %b %Y}; the festival is in week 12. Simulated weekly data is seeded for weeks 1-{C.SEEDED_WEEKS}.")
    try:
        from core import analytics as _an
        _f = _an.build_context(w)["forecast"]
        _pct = float(_f["pct_of_base"] or 0)
        _tone = ui.tone("green" if _f["gap_to_base"] >= 0 else ("amber" if _pct >= 90 else "red"))
        if ui.mode() == "light":      # the sidebar stays dark in both themes, so use the dark-surface status colours
            _tone = C.THEMES["dark"]["green" if _f["gap_to_base"] >= 0 else ("amber" if _pct >= 90 else "red")]
        _word = "On track" if _f["gap_to_base"] >= 0 else ("Behind plan" if _pct >= 90 else "At risk")
        st.markdown(f"<div class='cf-panel'><div class='k'>Forecast vs base target</div>"
                    f"<div class='row'><span class='v'>{_f['expected_attendance']:,}</span>"
                    f"<span class='o'>of {_f['base_target']:,}</span></div>"
                    f"<div class='cf-mini'><span style='width:{max(0.0, min(100.0, _pct)):.0f}%'></span></div>"
                    f"<div class='cf-dotline' style='color:{_tone}'><span class='d' style='background:{_tone}'></span>{_word} · {_pct:.0f}% of base</div>"
                    f"</div>", unsafe_allow_html=True)
    except Exception:
        pass                      # the sidebar readout is a convenience; never block the app on it
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
    st.caption(f"{C.FESTIVAL} · {C.FEST_DATES}\n\nChallenge A: Attendee Growth\n\nBuilt by {C.CANDIDATE}, {C.INSTITUTION} · RISA Labs Growth APM assignment")

nav.run()

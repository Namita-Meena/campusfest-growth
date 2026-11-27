"""Shared UI: the two themes, their CSS, and the helpers every page uses.

One switch (Dark / Light, in the sidebar) drives everything here. Pages never hard-code a
colour: they ask ``ui.P()`` for the active palette, so every page changes together.
"""
from __future__ import annotations

import html
from types import SimpleNamespace

import plotly.graph_objects as go
import streamlit as st

from . import config as C

THEME_KEY = "theme_mode"          # session-state key written by the sidebar control


# ------------------------------------------------------------------ theme state
def mode() -> str:
    """'dark' or 'light' - the theme chosen for this browser session."""
    chosen = str(st.session_state.get(THEME_KEY, C.THEME_NAMES[C.DEFAULT_THEME])).lower()
    return "light" if chosen.startswith("light") else "dark"


def P(which: str | None = None) -> SimpleNamespace:
    """The active palette, e.g. ``ui.P().primary``."""
    return SimpleNamespace(**C.THEMES[which or mode()])


def native_base() -> str:
    """The theme Streamlit itself was started with (.streamlit/config.toml).

    Data grids are painted on a canvas by Streamlit and cannot be recoloured with CSS, so when
    the chosen theme differs from this one the grid is flipped with a CSS filter instead.
    """
    try:
        return "dark" if str(st.get_option("theme.base")).lower() == "dark" else "light"
    except Exception:
        return "light"


def tone(name: str) -> str:
    """Colour for a status tone ('green', 'amber', 'red', 'grey', 'blue') in the active theme."""
    p = C.THEMES[mode()]
    return p.get(name, p["grey"])


def grid_tone(name: str) -> str:
    """Status colour for text inside a data grid (chosen for the grid's own background)."""
    p = C.THEMES[native_base()]
    return p.get(name, p["grey"])


def _lum(colour: str) -> float:
    h = colour.lstrip("#")
    ch = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in ch]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a: str, b: str) -> float:
    """WCAG contrast ratio between two hex colours."""
    hi, lo = sorted((_lum(a), _lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def on(colour: str) -> str:
    """Readable text colour (near-black or white) for a label placed on ``colour``."""
    return "#08090B" if contrast("#08090B", colour) >= contrast("#FFFFFF", colour) else "#FFFFFF"


def theme_control():
    """The Dark / Light switch. Rendered once, in the sidebar, so it is on every page."""
    names = list(C.THEME_NAMES.values())
    if st.session_state.get(THEME_KEY) not in names:
        asked = str(st.query_params.get("theme", "")).lower()        # lets a refreshed tab keep its theme
        st.session_state[THEME_KEY] = C.THEME_NAMES.get(asked, C.THEME_NAMES[C.DEFAULT_THEME])
    icons = {"Dark": ":material/dark_mode: Dark", "Light": ":material/light_mode: Light"}
    st.markdown("<div class='cf-side-lab'>Theme</div>", unsafe_allow_html=True)
    st.segmented_control("Theme", names, key=THEME_KEY, required=True, label_visibility="collapsed",
                         format_func=lambda n: icons.get(n, n), width="stretch")
    if st.query_params.get("theme") != mode():
        st.query_params["theme"] = mode()


# ------------------------------------------------------------------ CSS
_FONTS = ("@import url('https://fonts.googleapis.com/css2?family=Inter:opsz,wght@14..32,400..800"
          "&family=Anonymous+Pro:wght@400;700&display=swap');")

# Shared rules. Every colour is a variable, so the two themes differ only in the :root block
# and in the short theme-specific sections further down.
_BASE = """
html, body, .stApp, [class*="st-"], .stMarkdown, p, li, td, th, label, input, textarea, select, button {
  font-family: 'Inter', -apple-system, 'Segoe UI', Arial, sans-serif;
}
[data-testid="stIconMaterial"], span[class*="material-symbols"] {font-family: 'Material Symbols Rounded' !important;}
code, pre, kbd, [data-testid="stCode"] *, [data-testid="stJson"] * {font-family: var(--mono) !important;}

/* ---------- canvas ---------- */
.stApp {background: var(--bg) !important; color: var(--text);}
[data-testid="stAppViewContainer"], .stMain {background: transparent !important;}
header[data-testid="stHeader"] {background: transparent !important;}
header[data-testid="stHeader"] button, header[data-testid="stHeader"] [data-testid="stIconMaterial"] {color: var(--text) !important;}
[data-testid="stBottom"], [data-testid="stBottom"] > div, [data-testid="stBottomBlockContainer"] {background: var(--bg) !important;}
.block-container {padding-top: 2.6rem; padding-bottom: 4rem; max-width: 1420px;}
::selection {background: var(--accent); color: var(--on-accent);}

/* ---------- text ---------- */
.stMain {color: var(--text2);}
.stMain [data-testid="stMarkdownContainer"],
.stMain [data-testid="stMarkdownContainer"] p,
.stMain [data-testid="stMarkdownContainer"] li,
.stMain [data-testid="stMarkdownContainer"] td,
.stMain [data-testid="stMarkdownContainer"] th {color: var(--text2);}
.stMain [data-testid="stMarkdownContainer"] strong {color: var(--text);}
.stMain [data-testid="stMarkdownContainer"] a {color: var(--accent-text);}
.stMain h1, .stMain h2, .stMain h3, .stMain h4 {
  font-family: var(--display); color: var(--text) !important; letter-spacing: -0.02em;}
.stMain h2 {font-size: 1.42rem !important; font-weight: 650;}
.stMain h3 {font-size: 1.14rem !important; font-weight: 650; margin-top: 0.5rem;}
.stMain h4 {font-size: 1rem !important; font-weight: 650;}
.stMain [data-testid="stCaptionContainer"],
.stMain [data-testid="stCaptionContainer"] p,
.stMain [data-testid="stCaptionContainer"] li {color: var(--muted) !important;}
.stMain [data-testid="stCaptionContainer"] {opacity: 1 !important;}
.stMain [data-testid="stWidgetLabel"] p, .stMain [data-testid="stWidgetLabel"] {
  color: var(--text2) !important;}
.stMain hr {border-color: var(--line) !important; background: var(--line) !important;}
.stMain [data-testid="stMarkdownContainer"] table {border-collapse: collapse;}
.stMain [data-testid="stMarkdownContainer"] th, .stMain [data-testid="stMarkdownContainer"] td {border-color: var(--line2) !important;}
.stMain [data-testid="stMarkdownContainer"] th {color: var(--text) !important; font-weight: 650;}
.stMain code {background: var(--field) !important; color: var(--accent-text) !important;
  border: 1px solid var(--line); border-radius: var(--r);}
.stMain [data-testid="stCode"], .stMain [data-testid="stJson"] {border: 1px solid var(--line2); border-radius: var(--r);}
.stMain [data-testid="stTooltipIcon"] svg {stroke: var(--muted) !important; color: var(--muted) !important;}

/* ---------- labels shared by every component ---------- */
.cf-lab {font-family: var(--lab-font); font-size: var(--lab-size); font-weight: var(--lab-weight);
  letter-spacing: var(--lab-track); text-transform: uppercase; color: var(--faint);}
.cf-dim {font-size: .8rem; color: var(--muted); font-weight: 500; letter-spacing: 0;}

/* ---------- page header ---------- */
.cf-top {margin-bottom: 4px;}
.cf-eye {font-family: var(--lab-font); font-size: .74rem; font-weight: var(--lab-strong); letter-spacing: var(--lab-track);
  text-transform: uppercase; color: var(--accent-text);}
.cf-h1 {font-family: var(--display); color: var(--text); font-weight: 650; font-size: 2rem; line-height: 1.14;
  letter-spacing: -0.03em; margin: 6px 0 0;}
.cf-top-r {display: none;}
.cf-sub {color: var(--muted) !important; font-size: .92rem; line-height: 1.6; margin: 10px 0 6px; max-width: 1150px;}

/* ---------- hero ---------- */
.cf-hero {display: flex; gap: 40px; flex-wrap: wrap; margin: 14px 0 16px;}
.cf-hero-l {flex: 0 0 340px; min-width: 260px;}
.cf-hero-r {flex: 1 1 420px; min-width: 300px;}
.cf-big {font-family: var(--display); color: var(--text); font-weight: 700; line-height: .9;
  letter-spacing: -0.05em; font-variant-numeric: tabular-nums; white-space: nowrap;}
.cf-big em {font-style: normal; letter-spacing: 0; margin-left: 12px;}
.cf-note {color: var(--muted); font-size: .88rem; line-height: 1.6; margin-top: 12px; max-width: 330px;}
.cf-verdict {display: inline-flex; align-items: center; gap: 8px; margin-top: 14px; font-family: var(--lab-font);
  font-size: .74rem; font-weight: var(--lab-strong); letter-spacing: var(--lab-track); text-transform: uppercase; color: var(--c);}
.cf-verdict i {width: 7px; height: 7px; background: var(--c); display: inline-block;}

/* progress to target */
.cf-track {position: relative; background: var(--track); margin: 12px 0 10px;}
.cf-fill {height: 100%;}
.cf-mark {position: absolute; background: var(--text);}
.cf-mark.s {background: var(--amber);}
.cf-legend {display: flex; gap: 22px; flex-wrap: wrap; font-family: var(--lab-font); font-size: .7rem;
  letter-spacing: var(--lab-track); text-transform: uppercase; color: var(--faint);}
.cf-legend b {color: var(--text); font-weight: var(--lab-strong); font-variant-numeric: tabular-nums; margin-left: 5px;}

/* weekly sparkline */
.cf-spark {display: flex; align-items: flex-end; gap: 8px; height: 76px; margin-top: 8px;}
.cf-spark span {flex: 1 1 0; max-width: 40px; min-height: 3px; background: var(--track);}
.cf-spark span.p {background: var(--done);}
.cf-spark span.c {background: var(--accent);}

/* ---------- alerts ---------- */
.cf-alert {display: flex; gap: 13px; align-items: flex-start; font-size: .92rem; line-height: 1.5; color: var(--text2);}
.cf-alert .b {flex: none; font-family: var(--lab-font); font-size: .66rem; font-weight: var(--lab-strong);
  letter-spacing: var(--lab-track); text-transform: uppercase; white-space: nowrap;}
.cf-alert b {color: var(--text); font-weight: 650;}

/* ---------- tiles (metric cards) ---------- */
.cf-tw {container-type: inline-size; margin: 6px 0 20px;}
.cf-tiles {display: grid; grid-template-columns: repeat(var(--n, 4), minmax(0, 1fr));}
.cf-tiles .t {padding: 15px 17px 14px; min-width: 0;}
.cf-tiles .v {font-family: var(--display); color: var(--text); font-weight: 650; font-size: 1.7rem; line-height: 1.15;
  letter-spacing: -0.03em; margin: 7px 0 3px; font-variant-numeric: tabular-nums; overflow-wrap: anywhere;}
.cf-tiles .k:empty {display: none;}
.cf-tiles .k {margin: 4px 0 3px;}
.cf-tiles .h {color: var(--muted); font-size: .79rem; line-height: 1.45;}
@container (max-width: 700px) {.cf-tiles .t {padding: 13px 12px 12px;} .cf-tiles .v {font-size: 1.32rem;}
  .cf-tiles .cf-lab {min-height: 3.7em; display: block; letter-spacing: .08em;}}
@container (max-width: 430px) {.cf-tiles {grid-template-columns: repeat(2, minmax(0, 1fr));}}
@media (max-width: 760px) {.cf-hero-l {flex-basis: 100%;} .cf-h1 {font-size: 1.6rem !important;} .cf-top-r {display: none !important;}
  .cf-hero-r {border-left: 0 !important; padding-left: 0 !important;} .cf-big {font-size: 4.4rem !important;}}

/* ---------- small labels ---------- */
.cf-pill {display: inline-block; font-family: var(--lab-font); font-size: .68rem; font-weight: var(--lab-strong);
  letter-spacing: var(--lab-track); text-transform: uppercase; white-space: nowrap; padding: 4px 10px;}
.cf-tag {display: inline-block; font-family: var(--lab-font); font-size: .62rem; font-weight: var(--lab-strong); letter-spacing: .07em;
  text-transform: uppercase; padding: 1px 6px; margin-right: 5px; border: 1px solid var(--c); color: var(--c);
  border-radius: var(--r); white-space: nowrap; vertical-align: 1px;}

/* ---------- Streamlit widgets, main area ---------- */
.stMain [data-testid="stTextInputRootElement"], .stMain [data-testid="stTextAreaRootElement"],
.stMain [data-testid="stSelectbox"] div[role="group"], .stMain [data-testid="stMultiSelect"] div[role="group"],
.stMain [data-testid="stNumberInputContainer"], .stMain [data-testid="stDateInputField"] {
  background: var(--field) !important; border-color: var(--line2) !important; border-radius: var(--r) !important;}
.stMain [data-testid="stTextInputRootElement"]:focus-within, .stMain [data-testid="stTextAreaRootElement"]:focus-within,
.stMain [data-testid="stSelectbox"] div[role="group"]:focus-within, .stMain [data-testid="stMultiSelect"] div[role="group"]:focus-within,
.stMain [data-testid="stNumberInputContainer"]:focus-within, .stMain [data-testid="stDateInputField"]:focus-within {
  border-color: var(--accent-text) !important;}
.stMain input, .stMain textarea {color: var(--text) !important; -webkit-text-fill-color: var(--text) !important;
  caret-color: var(--accent-text) !important; background: transparent !important;}
.stMain input::placeholder, .stMain textarea::placeholder {
  color: var(--muted) !important; -webkit-text-fill-color: var(--muted) !important; opacity: 1;}
.stMain input:disabled, .stMain textarea:disabled {color: var(--muted) !important; -webkit-text-fill-color: var(--muted) !important;}
.stMain [data-testid="stSelectbox"] button, .stMain [data-testid="stMultiSelect"] div[role="group"] > button,
.stMain [data-testid="stSelectbox"] svg, .stMain [data-testid="stMultiSelect"] div[role="group"] > button svg,
.stMain [data-testid="stDateInputCalendarButton"], .stMain [data-testid="stDateInputCalendarButton"] svg {color: var(--muted) !important;}
.stMain [data-testid="stDateInputField"] span {color: var(--text) !important;}
.stMain [data-testid="stNumberInputStepUp"], .stMain [data-testid="stNumberInputStepDown"] {
  background: var(--field) !important; color: var(--text2) !important; border-color: var(--line) !important;}
.stMain [data-testid="stNumberInputStepUp"]:hover, .stMain [data-testid="stNumberInputStepDown"]:hover {
  background: var(--accent) !important; color: var(--on-accent) !important;}
.stMain [data-testid="stMultiSelectTagsContainer"] span[role="group"] > span {background: var(--btn-bg) !important; border-radius: var(--r) !important;}
.stMain [data-testid="stMultiSelectTagsContainer"] span[role="group"] > span * {color: var(--btn-text) !important;}
/* checkbox and radio marks */
.stMain [data-testid="stCheckbox"] label > span + div {background: var(--field) !important; border-color: var(--line2) !important;}
.stMain [data-testid="stCheckbox"] label:has(input:checked) > span + div {background: var(--btn-bg) !important; border-color: var(--btn-bg) !important;}
.stMain [data-testid="stCheckbox"] label > span + div svg {color: var(--btn-text) !important;}
.stMain [data-testid="stRadioOption"] > div > div:first-child {background: var(--field) !important; border-color: var(--line2) !important;}
.stMain [data-testid="stRadioOption"]:has(input:checked) > div > div:first-child {background: var(--btn-bg) !important; border-color: var(--btn-bg) !important;}
.stMain [data-testid="stRadioOption"]:has(input:checked) > div > div:first-child > div {background: var(--btn-text) !important;}
.stMain [data-testid="stRadioOption"]:not(:has(input:checked)) > div > div:first-child > div {background: transparent !important;}
.stMain [data-testid="stSliderThumbValue"] p, .stMain [data-testid="stSliderTickBar"] p {color: var(--text2) !important;}

/* buttons */
.stMain .stButton > button, .stMain .stFormSubmitButton > button,
.stMain .stDownloadButton > button {border-radius: var(--r) !important; font-weight: 600;
  background: transparent !important; border: 1px solid var(--line2) !important; color: var(--text) !important;
  transition: background .12s ease, color .12s ease, border-color .12s ease;}
.stMain .stButton > button p, .stMain .stFormSubmitButton > button p,
.stMain .stDownloadButton > button p, .stMain .stButton > button div,
.stMain .stFormSubmitButton > button div {color: inherit !important;}
.stMain .stButton > button:hover, .stMain .stFormSubmitButton > button:hover,
.stMain .stDownloadButton > button:hover {border-color: var(--accent-text) !important; color: var(--accent-text) !important;}
.stMain .stButton > button[kind="primary"], .stMain .stFormSubmitButton > button[kind="primaryFormSubmit"] {
  background: var(--btn-bg) !important; border-color: var(--btn-bg) !important; color: var(--btn-text) !important;}
.stMain .stButton > button[kind="primary"]:hover,
.stMain .stFormSubmitButton > button[kind="primaryFormSubmit"]:hover {
  background: var(--btn-hover) !important; border-color: var(--btn-hover) !important; color: var(--btn-hover-text) !important;}
.stMain button:disabled {opacity: .45;}

/* tabs, expanders, forms, chat */
.stMain [data-testid="stTabs"] [role="tablist"] {gap: 6px;}
.stMain [data-testid="stTab"] {color: var(--muted) !important; background: transparent !important;}
.stMain [data-testid="stTab"] p {font-weight: 600; font-size: .9rem; color: var(--muted) !important;}
.stMain [data-testid="stTab"]:hover p {color: var(--text) !important;}
.stMain [data-testid="stTab"][aria-selected="true"] p {color: var(--text) !important;}
.stMain [data-testid="stTab"] > div:not([data-testid]) {background: var(--accent) !important;}
.stMain [data-testid="stExpander"] details {background: var(--panel) !important;
  border: 1px solid var(--line) !important; border-radius: var(--r) !important;}
.stMain [data-testid="stExpander"] summary {color: var(--text) !important; background: transparent !important;}
.stMain [data-testid="stExpander"] summary p {color: var(--text) !important; font-weight: 600;}
.stMain [data-testid="stExpander"] summary:hover p,
.stMain [data-testid="stExpander"] summary:hover [data-testid="stIconMaterial"] {color: var(--accent-text) !important;}
.stMain [data-testid="stExpander"] summary [data-testid="stIconMaterial"] {color: var(--muted) !important;}
.stMain [data-testid="stForm"] {background: var(--panel) !important; border: 1px solid var(--line) !important;
  border-radius: var(--r) !important; padding: 16px 18px;}
.stMain [data-testid="stVerticalBlockBorderWrapper"] {border-color: var(--line) !important; border-radius: var(--r) !important;}
.stMain [data-testid="stChatMessage"] {background: var(--panel) !important; border: 1px solid var(--line);
  border-radius: var(--r); padding: 6px 14px;}
.stMain [data-testid="stChatMessageAvatarUser"], .stMain [data-testid="stChatMessageAvatarAssistant"] {
  background: var(--accent) !important; color: var(--on-accent) !important; border-radius: var(--r) !important;}
.stMain [data-testid="stChatMessageAvatarUser"] svg,
.stMain [data-testid="stChatMessageAvatarAssistant"] svg {color: var(--on-accent) !important; fill: var(--on-accent) !important;}
[data-testid="stChatInput"] > div {background: var(--field) !important; border: 1px solid var(--line2) !important; border-radius: var(--r) !important;}
[data-testid="stChatInput"] textarea {color: var(--text) !important; -webkit-text-fill-color: var(--text) !important;
  caret-color: var(--accent-text) !important; background: transparent !important;}
[data-testid="stChatInput"] textarea::placeholder {color: var(--muted) !important; -webkit-text-fill-color: var(--muted) !important;}
[data-testid="stChatInput"] button {color: var(--text2) !important;}
[data-testid="stChatInput"] button:not(:disabled) {background: var(--accent) !important; color: var(--on-accent) !important; border-radius: var(--r) !important;}

/* message boxes: st.info / success / warning / error */
.stMain [data-testid="stAlertContainer"] {background: var(--panel) !important; color: var(--text2) !important;
  border: 1px solid var(--line) !important; border-left: 3px solid var(--kc, var(--muted)) !important; border-radius: var(--r) !important;}
.stMain [data-testid="stAlertContainer"] p, .stMain [data-testid="stAlertContainer"] li {color: var(--text2) !important;}
.stMain [data-testid="stAlertContainer"]:has([data-testid="stAlertContentInfo"]) {--kc: var(--blue);}
.stMain [data-testid="stAlertContainer"]:has([data-testid="stAlertContentSuccess"]) {--kc: var(--green);}
.stMain [data-testid="stAlertContainer"]:has([data-testid="stAlertContentWarning"]) {--kc: var(--amber);}
.stMain [data-testid="stAlertContainer"]:has([data-testid="stAlertContentError"]) {--kc: var(--red);}

/* data grids and charts */
.stMain [data-testid="stDataFrame"], .stMain [data-testid="stDataFrame"] > div {border-radius: var(--r) !important;}
.stMain [data-testid="stPlotlyChart"] {background: transparent !important;}
.stMain [data-testid="stMetric"] {background: var(--panel); border: 1px solid var(--line); border-radius: var(--r); padding: 12px 15px;}
.stMain [data-testid="stMetricValue"] {color: var(--text) !important;}
.stMain [data-testid="stMetricLabel"] p {color: var(--muted) !important;}
[data-testid="stSpinner"] p, [data-testid="stSpinner"] {color: var(--text2) !important;}

/* ---------- sidebar (dark in both themes) ---------- */
section[data-testid="stSidebar"] {background: var(--side-bg) !important; border-right: 1px solid var(--side-line);}
section[data-testid="stSidebar"] > div {background: transparent !important;}
section[data-testid="stSidebar"] hr {border-color: var(--side-line) !important; background: var(--side-line) !important;}
section[data-testid="stSidebar"] p, section[data-testid="stSidebar"] small,
section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] {color: var(--side-muted) !important;}
section[data-testid="stSidebar"] [data-testid="stSidebarHeader"] button,
section[data-testid="stSidebar"] [data-testid="stSidebarHeader"] [data-testid="stIconMaterial"] {color: var(--side-muted) !important;}
section[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"] {background: transparent !important; padding: 7px 10px; min-height: 0;}
section[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"] p {color: var(--side-muted) !important; font-size: .88rem; font-weight: 500;}
section[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"]:hover p {color: var(--side-text) !important;}
section[data-testid="stSidebar"] [class*="st-key-nav_active"] [data-testid="stPageLink-NavLink"] p {color: var(--side-text) !important; font-weight: 650;}
section[data-testid="stSidebar"] [class*="st-key-nav_"] {gap: 0 !important; margin-bottom: -0.82rem;}
section[data-testid="stSidebar"] [class*="st-key-nav_"] [data-testid="stPageLink"] {margin: 0;}
.cf-nav-lab {margin: 16px 0 2px 12px !important;}
.cf-brand {display: flex; gap: 10px; align-items: center; margin: 0 0 4px;}
.cf-brand .mark {width: 32px; height: 32px; flex: none; background: var(--side-accent); color: #08090B; font-weight: 800;
  font-size: .82rem; display: flex; align-items: center; justify-content: center; border-radius: 7px;}
.cf-brand .t {font-family: var(--display); font-weight: 700; font-size: 1rem; color: var(--side-text); line-height: 1.2; letter-spacing: -0.02em;}
.cf-brand .s {font-size: .72rem; color: var(--side-muted); margin-top: 1px;}
.cf-side-note {font-size: .74rem; color: var(--side-muted); line-height: 1.5; margin: 6px 0 2px;}
.cf-side-lab {font-family: var(--lab-font); font-size: .64rem; font-weight: var(--lab-weight); letter-spacing: var(--lab-track);
  text-transform: uppercase; color: var(--side-faint); margin: 10px 0 -2px;}
.cf-panel {border: 1px solid var(--side-line); padding: 11px 12px; margin-bottom: 4px; border-radius: var(--r);}
.cf-panel .k {font-family: var(--lab-font); font-size: .64rem; font-weight: var(--lab-weight); letter-spacing: var(--lab-track);
  text-transform: uppercase; color: var(--side-faint);}
.cf-panel .wk {font-family: var(--display); font-size: 1.5rem; font-weight: 650; color: var(--side-text); line-height: 1.1;
  margin-top: 4px; letter-spacing: -0.02em; font-variant-numeric: tabular-nums;}
.cf-panel .wk span {font-size: .86rem; font-weight: 500; color: var(--side-faint); letter-spacing: 0;}
.cf-panel .d {font-size: .74rem; color: var(--side-muted); margin-top: 3px;}
.cf-panel .row {display: flex; justify-content: space-between; align-items: baseline; margin-top: 6px;}
.cf-panel .row .v {font-family: var(--display); font-weight: 650; color: var(--side-text); font-size: 1.05rem; font-variant-numeric: tabular-nums;}
.cf-panel .row .o {font-size: .74rem; color: var(--side-muted);}
.cf-mini {height: 4px; background: var(--side-line); overflow: hidden; margin-top: 9px;}
.cf-mini > span {display: block; height: 100%; background: var(--side-accent);}
.cf-dotline {display: flex; align-items: center; gap: 7px; font-family: var(--lab-font); font-size: .64rem; font-weight: var(--lab-strong);
  letter-spacing: var(--lab-track); text-transform: uppercase; margin-top: 9px;}
.cf-dotline .d {width: 7px; height: 7px; flex: none; margin: 0;}
section[data-testid="stSidebar"] [data-testid="stExpander"] details {background: transparent !important;
  border: 1px solid var(--side-line) !important; border-radius: var(--r) !important;}
section[data-testid="stSidebar"] [data-testid="stExpander"] summary p {color: var(--side-text) !important; font-size: .84rem;}
section[data-testid="stSidebar"] [data-testid="stExpander"] summary [data-testid="stIconMaterial"] {color: var(--side-muted) !important;}
section[data-testid="stSidebar"] label p, section[data-testid="stSidebar"] .stCheckbox p {color: var(--side-muted) !important;}
section[data-testid="stSidebar"] .stButton > button {background: transparent !important; border: 1px solid var(--side-line) !important;
  color: var(--side-text) !important; border-radius: var(--r) !important;}
section[data-testid="stSidebar"] .stButton > button p {color: inherit !important;}
section[data-testid="stSidebar"] .stButton > button:hover:not(:disabled) {border-color: var(--side-accent) !important; color: var(--side-accent) !important;}
section[data-testid="stSidebar"] [data-testid="stSliderThumbValue"], section[data-testid="stSidebar"] [data-testid="stSliderTickBar"] {color: var(--side-muted) !important;}

/* the Dark / Light switch */
section[data-testid="stSidebar"] [data-testid="stButtonGroup"] {width: 100%;}
section[data-testid="stSidebar"] [data-testid="stButtonGroup"] button[role="radio"] {flex: 1 1 0; justify-content: center;
  background: transparent !important; border: 1px solid var(--side-line) !important; color: var(--side-muted) !important;
  border-radius: 0 !important; font-weight: 600; min-height: 36px;}
section[data-testid="stSidebar"] [data-testid="stButtonGroup"] button[role="radio"] p,
section[data-testid="stSidebar"] [data-testid="stButtonGroup"] button[role="radio"] [data-testid="stIconMaterial"] {color: inherit !important; font-size: .84rem;}
section[data-testid="stSidebar"] [data-testid="stButtonGroup"] button[role="radio"]:hover {color: var(--side-text) !important;}
section[data-testid="stSidebar"] [data-testid="stButtonGroup"] button[role="radio"][aria-checked="true"] {
  background: var(--side-accent) !important; border-color: var(--side-accent) !important; color: var(--side-on-accent) !important;}
"""

_DARK = """
.stApp {background:
  linear-gradient(var(--grid) 1px, transparent 1px) 0 0 / 100% 34px,
  linear-gradient(90deg, var(--grid) 1px, transparent 1px) 0 0 / 34px 100%, var(--bg) !important;}
.cf-h1 {font-size: 1.85rem; font-weight: 600;}
.cf-hero {border: 1px solid var(--line); background: var(--panel); padding: 24px 26px; border-radius: 3px;}
.cf-big {font-size: 5rem; margin-top: 10px;}
.cf-big em {font-size: 1.6rem; font-weight: 700;}
.cf-track {height: 6px;}
.cf-fill {background: linear-gradient(90deg, #5B8CFF, var(--accent));}
.cf-mark {top: -5px; height: 16px; width: 1px;}
.cf-spark-lab {margin-top: 20px;}
.cf-alert {border-left: 2px solid var(--c); background: var(--panel); padding: 11px 15px; margin-bottom: 7px;}
.cf-alert .b {color: var(--c); padding-top: 3px;}
.cf-tiles {gap: 1px; background: var(--line); border: 1px solid var(--line);}
.cf-tiles .t {background: var(--panel);}
.cf-pill {color: var(--c); border: 1px solid var(--c); border-radius: 2px;}
section[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"] {border-radius: 7px; border-left: 2px solid transparent;}
section[data-testid="stSidebar"] [class*="st-key-nav_active"] [data-testid="stPageLink-NavLink"] {
  background: var(--side-active) !important; border-left-color: var(--side-accent);}
"""

_LIGHT = """
.cf-top {display: flex; justify-content: space-between; align-items: flex-end; gap: 24px;
  border-bottom: 3px solid var(--text); padding-bottom: 12px;}
.cf-eye {letter-spacing: .18em;}
.cf-h1 {font-size: 2.15rem; font-weight: 700; max-width: 900px;}
.cf-top-r {display: block; text-align: right; font-size: .76rem; color: var(--muted); line-height: 1.6; white-space: nowrap;}
.cf-top-r b {display: block; font-family: var(--display); font-size: 2rem; color: var(--text); letter-spacing: -0.03em; line-height: 1.05;}
.cf-hero {margin-top: 26px; gap: 30px;}
.cf-hero-r {border-left: 1px solid var(--line); padding-left: 28px;}
.cf-big {font-size: 7rem; margin-top: 4px; line-height: .86;}
.cf-big em {display: none;}
.cf-badge {display: inline-block; background: var(--text); color: #D7F26B; font-size: .74rem; font-weight: 700;
  letter-spacing: .03em; text-transform: uppercase; padding: 6px 12px; margin-top: 16px;}
.cf-track {height: 30px;}
.cf-fill {background: var(--accent);}
.cf-mark {top: -4px; height: 38px; width: 2px;}
.cf-mark.s {background: var(--accent);}
.cf-alerts {margin-top: 20px;}
.cf-alert {padding: 12px 0; border-top: 1px solid var(--line);}
.cf-alert .b {background: var(--c); color: #FFFFFF; padding: 4px 8px; margin-top: 1px;}
.cf-tiles {border-top: 3px solid var(--text);}
.cf-tiles .t {border-right: 1px solid var(--line); border-bottom: 1px solid var(--line);}
.cf-tiles .v {font-weight: 700; font-size: 1.85rem;}
.cf-pill {background: var(--c); color: #FFFFFF;}
.stMain h2, .stMain h3 {font-weight: 700;}
section[data-testid="stSidebar"] {border-right: 0;}
.cf-brand .mark {display: none;}
.cf-brand .t {font-size: 1.12rem;}
.cf-nav-lab {margin-left: 0 !important; margin-bottom: 4px !important;}
section[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"] {border-radius: 0; border-bottom: 1px solid var(--side-line);
  padding: 9px 0; position: relative;}
section[data-testid="stSidebar"] [class*="st-key-nav_active"] [data-testid="stPageLink-NavLink"]::after {content: ""; position: absolute;
  right: 2px; top: 50%; margin-top: -3px; width: 6px; height: 6px; border-radius: 50%; background: var(--side-accent);}
"""

# Applied only when the chosen theme differs from the one Streamlit was started with: the canvas
# grids and a few native marks cannot be recoloured, so they are flipped with a filter.
_FLIP = """
.stMain [data-testid="stDataFrame"], .stMain [data-testid="stCode"], .stMain [data-testid="stJson"] {filter: invert(1) hue-rotate(180deg);}
.stMain [data-testid="stSlider"] div[role="group"] > div > div:not([data-testid]) {filter: grayscale(1) invert(1);}
.stMain [data-testid="stSliderThumbValue"] p {color: var(--flip-text) !important;}
"""


def css() -> str:
    """The stylesheet for the active theme."""
    m, p = mode(), C.THEMES[mode()]
    dark = m == "dark"
    v = {k.replace("_", "-"): val for k, val in p.items()}
    v.update({
        "mono": "'Anonymous Pro', 'JetBrains Mono', 'DejaVu Sans Mono', Menlo, Consolas, monospace",
        "display": "'Inter Display', 'Inter', -apple-system, 'Segoe UI', Arial, sans-serif",
        "r": "3px" if dark else "0px",
        "lab-font": "var(--mono)" if dark else "'Inter', Arial, sans-serif",
        "lab-size": ".7rem" if dark else ".66rem",
        "lab-weight": "400" if dark else "700", "lab-strong": "400" if dark else "800",
        "lab-track": ".1em" if dark else ".15em",
        "btn-bg": p["accent"] if dark else p["text"], "btn-text": p["on_accent"] if dark else p["bg"],
        "btn-hover": "#D9FF7A" if dark else p["accent_text"], "btn-hover-text": p["on_accent"] if dark else "#FFFFFF",
        "side-on-accent": "#08090B",
        "flip-text": C.THEMES[native_base()]["text2"],
    })
    root = ":root {" + " ".join(f"--{k}: {val};" for k, val in v.items()) + "}"
    flip = _FLIP if native_base() != m else ""
    return f"<style>{_FONTS}\n{root}\n{_BASE}\n{_DARK if dark else _LIGHT}\n{flip}</style>"


def inject_css():
    """Apply the active theme. Called once per run from app.py; safe to call again."""
    st.html(css())


# ------------------------------------------------------------------ formatting
BADGES = {"green": "On track", "amber": "Action", "red": "Risk", "grey": "Note"}


def inr(x, dash="—") -> str:
    """Indian rupee formatting with lakh grouping, e.g. Rs 3,00,000."""
    if x is None:
        return dash
    n = int(round(float(x)))
    sign, n = ("-" if n < 0 else ""), abs(n)
    s = str(n)
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts) + "," + tail
    return f"{sign}₹{s}"


def num(x, dash="—") -> str:
    return dash if x is None else f"{int(round(float(x))):,}"


def pct(x, digits=1, dash="—") -> str:
    return dash if x is None else f"{100 * float(x):.{digits}f}%"


def dim(text: str) -> str:
    """Secondary text shown beside a figure."""
    return f"<span class='cf-dim'>{text}</span>"


# ------------------------------------------------------------------ components
def header(eyebrow: str, title: str, sub: str = ""):
    w = week()
    st.markdown(
        f"<div class='cf-top'><div><div class='cf-eye'>{html.escape(eyebrow)}</div>"
        f"<div class='cf-h1' role='heading' aria-level='1'>{html.escape(title)}</div></div>"
        f"<div class='cf-top-r'>Week<b>{w:02d}</b>{C.week_start(w):%d %b} – {C.week_end(w):%d %b %Y}</div></div>"
        + (f"<div class='cf-sub'>{sub}</div>" if sub else ""), unsafe_allow_html=True)


def pill(state: str) -> str:
    return f"<span class='cf-pill' style='--c:{tone(C.STATE_TONES.get(state, 'grey'))}'>{html.escape(state)}</span>"


def tag(kind: str) -> str:
    p = C.THEMES[mode()]
    colours = {"Historical 2025": p["muted"], "Simulated 2027": p["blue"], "Forecast": p["accent_text"], "Target": p["text"],
               "Assumption": p["amber"], "Not yet available": p["muted"]}
    return f"<span class='cf-tag' style='--c:{colours.get(kind, p['muted'])}'>{html.escape(kind)}</span>"


def _tile(label: str, value: str, hint: str = "", kind: str | None = None, tone_name: str = "") -> str:
    colour = f" style='color:{tone(tone_name)}'" if tone_name in ("green", "amber", "red") else ""
    return (f"<div class='t'><div class='cf-lab'>{html.escape(label)}</div><div class='v'{colour}>{value}</div>"
            f"<div class='k'>{tag(kind) if kind else ''}</div><div class='h'>{hint}</div></div>")


def cards(items: list, per_row: int = 5):
    """A joined row of metric tiles. Each item is (label, value, hint, kind, tone); the last three are optional."""
    items = [tuple(it) for it in items]
    n = max(1, min(per_row, len(items)))
    cells = [_tile(*it) for it in items]
    cells += ["<div class='t'></div>"] * (-len(items) % n)          # keep the last row full so the grid lines close
    st.markdown(f"<div class='cf-tw'><div class='cf-tiles' style='--n:{n}'>{''.join(cells)}</div></div>", unsafe_allow_html=True)


def card(label: str, value: str, hint: str = "", kind: str | None = None, tone: str = ""):
    cards([(label, value, hint, kind, tone)], per_row=1)


def _alert(severity: str, text: str) -> str:
    sev = severity if severity in BADGES else "grey"
    body = html.escape(text)
    if ". " in body:                      # bold the first sentence so the point lands first
        head, rest = body.split(". ", 1)
        body = f"<b>{head}.</b> {rest}"
    else:
        body = f"<b>{body}</b>"
    return (f"<div class='cf-alert' style='--c:{tone(sev)}'><span class='b'>{BADGES[sev]}</span>"
            f"<div>{body}</div></div>")


def alert(severity: str, text: str):
    """A status line that reads at a glance: a labelled badge, then the point in bold."""
    st.markdown(_alert(severity, text), unsafe_allow_html=True)


def _track(value, base, stretch) -> str:
    top = max(stretch, value) * 1.02 or 1
    pos = lambda v: max(0.0, min(99.8, 100 * v / top))
    return (f"<div class='cf-track'><div class='cf-fill' style='width:{pos(value):.1f}%'></div>"
            f"<div class='cf-mark' style='left:{pos(base):.1f}%'></div>"
            f"<div class='cf-mark s' style='left:{pos(stretch):.1f}%'></div></div>"
            f"<div class='cf-legend'><span>Forecast<b>{value:,.0f}</b></span><span>Base<b>{base:,.0f}</b></span>"
            f"<span>Stretch<b>{stretch:,.0f}</b></span><span>2025<b>2,050</b></span></div>")


def target_bar(value: float, base: float, stretch: float):
    st.markdown(_track(value, base, stretch), unsafe_allow_html=True)


def _spark(actual: list, plan: list, current: int) -> str:
    """Twelve small bars: recorded weeks solid, the current week in the accent, later weeks at plan."""
    vals = [a if a is not None else pl for a, pl in zip(actual, plan)]
    top = max([v for v in vals if v] or [1])
    bars = []
    for i, (a, v) in enumerate(zip(actual, vals), start=1):
        cls = "c" if i == current and a is not None else ("p" if a is not None else "")
        bars.append(f"<span class='{cls}' style='height:{max(4.0, 100 * (v or 0) / top):.0f}%' title='W{i}: {v or 0:,.0f}'></span>")
    return (f"<div class='cf-lab cf-spark-lab'>Weekly registrations · W1–W{len(vals)}</div>"
            f"<div class='cf-spark'>{''.join(bars)}</div>")


def hero(label: str, value: str, chip: str, chip_tone: str, note: str, bar: tuple | None = None,
         delta: str = "", alerts: list | None = None, spark: tuple | None = None):
    """The page's one focal number with its verdict, progress to target and the alerts that explain it.

    Dark theme: a bordered console panel (number, progress, weekly bars) with the alerts listed beneath.
    Light theme: an oversized figure on the left and a ruled column (progress, then alerts) on the right.
    """
    dark, colour = mode() == "dark", tone(chip_tone)
    alerts = list(alerts or [])
    side = f"<div class='cf-lab'>Progress to target</div>{_track(*bar)}" if bar else ""
    if dark:
        verdict = (f"<div class='cf-verdict' style='--c:{colour}'><i></i>{html.escape(chip.split(' · ')[0])}</div>" if chip else "")
        em = f"<em style='color:{colour}'>{html.escape(delta)}</em>" if delta else ""
        if spark:
            side += _spark(*spark)
        below = "".join(_alert(s, t) for s, t in alerts)
    else:
        verdict = f"<div class='cf-badge'>{html.escape(chip)}</div>" if chip else ""
        em = ""
        inside, alerts = alerts[:3], alerts[3:]
        if inside:
            side += f"<div class='cf-alerts'>{''.join(_alert(s, t) for s, t in inside)}</div>"
        below = "".join(_alert(s, t) for s, t in alerts)
    st.markdown(
        f"<div class='cf-hero'><div class='cf-hero-l'><div class='cf-lab'>{html.escape(label)}</div>"
        f"<div class='cf-big'>{value}{em}</div>{verdict}<div class='cf-note'>{note}</div></div>"
        f"<div class='cf-hero-r'>{side}</div></div>{below}", unsafe_allow_html=True)


# ------------------------------------------------------------------ charts
def style(fig: go.Figure, height: int = 340, title: str | None = None) -> go.Figure:
    """Give a Plotly figure the active theme. Charts are drawn without Streamlit's own chart theme."""
    p = P()
    fig.update_layout(
        template="plotly_dark" if mode() == "dark" else "plotly_white",
        height=height, title=dict(text=title, font=dict(size=15, color=p.text)) if title else None,
        margin=dict(l=10, r=10, t=44 if title else 14, b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, Arial, sans-serif", color=p.text2, size=13),
        hoverlabel=dict(bgcolor=p.panel, bordercolor=p.line2, font=dict(color=p.text, size=13, family="Inter, Arial, sans-serif")),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(color=p.text2),
                    bgcolor="rgba(0,0,0,0)"),
        colorway=[p.primary, p.second, p.blue, p.amber, p.muted])
    axis = dict(gridcolor=p.line, zerolinecolor=p.line2, linecolor=p.line2, tickfont=dict(color=p.muted),
                title_font=dict(color=p.muted))
    fig.update_xaxes(**axis)
    fig.update_yaxes(**axis)
    return fig


def show(fig: go.Figure, key: str):
    st.plotly_chart(fig, width="stretch", key=key, theme=None, config={"displayModeBar": False})


# ------------------------------------------------------------------ session helpers
def week() -> int:
    return int(st.session_state.get("sim_week", 4))


def flash(msg: str, kind: str = "success"):
    """Queue a message to show after the next rerun."""
    st.session_state.setdefault("_flash", []).append((kind, msg))


def show_flashes():
    for kind, msg in st.session_state.pop("_flash", []):
        getattr(st, kind)(msg)

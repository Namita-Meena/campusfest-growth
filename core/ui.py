"""Shared UI helpers: formatting, status pills, metric cards and the Plotly theme."""
from __future__ import annotations

import html

import plotly.graph_objects as go
import streamlit as st

from . import config as C

CSS = f"""
<style>
.block-container {{padding-top: 3.6rem; padding-bottom: 3rem; max-width: 1350px;}}
h1, h2, h3, h4 {{color: {C.NAVY}; letter-spacing: -0.01em;}}
h1 {{font-size: 2.0rem !important; padding-bottom: 0.6rem !important;}}
h3 {{font-size: 1.2rem !important;}}
h4 {{font-size: 1.05rem !important;}}
.cf-eyebrow {{color: {C.ORANGE}; font-weight: 600; font-size: 0.8rem; letter-spacing: 0.06em; text-transform: uppercase; margin-bottom: -0.4rem;}}
.cf-sub {{color: #4A5568; font-size: 0.95rem; margin-top: -0.6rem;}}
.cf-pill {{display: inline-block; padding: 2px 10px; border-radius: 999px; font-size: 0.78rem; font-weight: 600; color: #fff; white-space: nowrap;}}
.cf-tag {{display: inline-block; padding: 1px 8px; border-radius: 4px; font-size: 0.72rem; font-weight: 600; border: 1px solid; margin-right: 6px;}}
.cf-card {{background: #fff; border: 1px solid {C.LINE}; border-radius: 8px; padding: 12px 14px; min-height: 128px;}}
.cf-card .l {{color: #4A5568; font-size: 0.78rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.03em;}}
.cf-card .v {{color: {C.NAVY}; font-size: 1.55rem; font-weight: 700; line-height: 1.25;}}
.cf-card .h {{color: #4A5568; font-size: 0.8rem; line-height: 1.35;}}
.cf-card .k {{margin: 2px 0 3px 0;}}
.cf-alert {{border-left: 5px solid; background: #fff; padding: 8px 12px; margin-bottom: 6px; border-radius: 4px; font-size: 0.92rem; color: {C.NAVY};}}
div[data-testid="stMetric"] {{background: #fff; border: 1px solid {C.LINE}; border-radius: 8px; padding: 10px 14px;}}
</style>
"""


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


def header(eyebrow: str, title: str, sub: str = ""):
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown(f"<div class='cf-eyebrow'>{html.escape(eyebrow)}</div>", unsafe_allow_html=True)
    st.title(title)
    if sub:
        st.markdown(f"<div class='cf-sub'>{sub}</div>", unsafe_allow_html=True)
    st.write("")


def pill(state: str) -> str:
    colour = C.STATE_COLOURS.get(state, C.GREY)
    return f"<span class='cf-pill' style='background:{colour}'>{html.escape(state)}</span>"


def tag(kind: str) -> str:
    colours = {"Historical 2025": C.GREY, "Simulated 2027": C.BLUE, "Forecast": C.ORANGE, "Target": C.NAVY,
               "Assumption": C.AMBER, "Not yet available": C.GREY}
    c = colours.get(kind, C.GREY)
    return f"<span class='cf-tag' style='color:{c};border-color:{c}'>{html.escape(kind)}</span>"


def card(label: str, value: str, hint: str = "", kind: str | None = None):
    k = tag(kind) if kind else ""
    st.markdown(f"<div class='cf-card'><div class='l'>{html.escape(label)}</div><div class='v'>{value}</div>"
                f"<div class='k'>{k}</div><div class='h'>{hint}</div></div>", unsafe_allow_html=True)


def cards(items: list, per_row: int = 5):
    for i in range(0, len(items), per_row):
        cols = st.columns(per_row)
        for col, it in zip(cols, items[i:i + per_row]):
            with col:
                card(*it)
        st.write("")


def alert(severity: str, text: str):
    colour = {"red": C.RED, "amber": C.AMBER, "green": C.GREEN}.get(severity, C.GREY)
    st.markdown(f"<div class='cf-alert' style='border-color:{colour}'>{html.escape(text)}</div>", unsafe_allow_html=True)


def style(fig: go.Figure, height: int = 340, title: str | None = None) -> go.Figure:
    fig.update_layout(
        height=height, title=dict(text=title, font=dict(size=15, color=C.NAVY)) if title else None,
        margin=dict(l=10, r=10, t=44 if title else 14, b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#FFFFFF",
        font=dict(family="Inter, 'Source Sans Pro', Arial, sans-serif", color=C.NAVY, size=13),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1), hoverlabel=dict(font_size=13),
        colorway=[C.BLUE, C.ORANGE, C.NAVY, C.GREEN, C.AMBER, C.GREY])
    fig.update_xaxes(gridcolor="#EEF1F6", zerolinecolor=C.LINE)
    fig.update_yaxes(gridcolor="#EEF1F6", zerolinecolor=C.LINE)
    return fig


def show(fig: go.Figure, key: str):
    st.plotly_chart(fig, width="stretch", key=key, config={"displayModeBar": False})


def week() -> int:
    return int(st.session_state.get("sim_week", 4))


def flash(msg: str, kind: str = "success"):
    """Queue a message to show after the next rerun."""
    st.session_state.setdefault("_flash", []).append((kind, msg))


def show_flashes():
    for kind, msg in st.session_state.pop("_flash", []):
        getattr(st, kind)(msg)

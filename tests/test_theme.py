"""The two themes: one switch, every page, readable colours."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from core import config as C
from core import ui

ROOT = Path(__file__).resolve().parent.parent
PAGES = ["overview", "campaigns", "experiments", "tasks", "copilot", "data"]


def _css(theme):
    """The stylesheet a page gets when the session has chosen ``theme``."""
    def script(name):
        import streamlit as st
        from core import ui as _ui
        st.session_state["theme_mode"] = name
        st.text(_ui.css())
    at = AppTest.from_function(script, args=(theme,), default_timeout=60).run()
    assert not at.exception, at.exception
    return at.text[0].value


def test_both_themes_define_the_same_tokens():
    assert set(C.THEMES) == {"dark", "light"} and C.DEFAULT_THEME == "dark"
    assert set(C.THEMES["dark"]) == set(C.THEMES["light"])


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_text_colours_meet_wcag_aa(theme):
    p = C.THEMES[theme]
    for surface in ("bg", "panel", "field"):
        for token in ("text", "text2", "muted", "faint", "accent_text", "green", "amber", "red", "grey", "blue"):
            ratio = ui.contrast(p[token], p[surface])
            assert ratio >= 4.5, f"{theme}: {token} on {surface} is only {ratio:.2f}:1"
    for token in ("side_text", "side_muted", "side_faint"):
        assert ui.contrast(p[token], p["side_bg"]) >= 4.5, f"{theme}: {token} on the sidebar"
    for fill in ("primary", "accent"):                      # bars and meters: graphical objects need 3:1
        assert ui.contrast(p[fill], p["bg"]) >= 3.0, f"{theme}: {fill} fill"
    for fill in ("primary", "second", "strong", "lead"):    # the label drawn on a bar must be readable
        assert ui.contrast(ui.on(p[fill]), p[fill]) >= 4.5, f"{theme}: label on {fill}"


def test_status_badges_are_readable_in_the_light_theme():
    p = C.THEMES["light"]
    for token in ("green", "amber", "red", "grey"):          # white label on a solid badge
        assert ui.contrast("#FFFFFF", p[token]) >= 4.5, token


def test_the_stylesheet_follows_the_chosen_theme():
    dark, light = _css("Dark"), _css("Light")
    assert "--bg: #08090B" in dark and "--accent: #C8F751" in dark
    assert "--bg: #FBF8F3" in light and "--accent: #E8502E" in light
    assert dark != light
    # the session default (nothing chosen yet) is the dark theme
    def script():
        import streamlit as st
        from core import ui as _ui
        st.text(_ui.mode())
    assert AppTest.from_function(script, default_timeout=60).run().text[0].value == "dark"


def test_grids_are_flipped_only_when_the_chosen_theme_differs_from_the_native_one():
    native = ui.native_base()
    same, other = ("Dark", "Light") if native == "dark" else ("Light", "Dark")
    assert "hue-rotate" not in _css(same)
    assert "hue-rotate" in _css(other)


@pytest.mark.parametrize("name", PAGES)
@pytest.mark.parametrize("theme", ["Dark", "Light"])
def test_every_page_renders_in_both_themes(name, theme):
    at = AppTest.from_file(str(ROOT / "views" / f"{name}.py"), default_timeout=90)
    at.session_state["sim_week"] = 4
    at.session_state["theme_mode"] = theme
    at.run()
    assert not at.exception, at.exception
    html = " ".join(m.value or "" for m in at.markdown)
    assert "cf-h1" in html                                   # the shared page header was drawn


def test_one_switch_in_the_sidebar_changes_every_page():
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120).run()
    assert not at.exception, at.exception
    switch = [w for w in at.sidebar.button_group if w.key == "theme_mode"]
    assert len(switch) == 1, "exactly one theme switch, in the sidebar"
    assert list(switch[0].options) and at.session_state["theme_mode"] == "Dark"
    assert any("--bg: #08090B" in (h.value if hasattr(h, "value") else str(h)) for h in at.get("html"))

    switch[0].set_value("Light").run()
    assert not at.exception, at.exception
    assert at.session_state["theme_mode"] == "Light"
    assert any("--bg: #FBF8F3" in (h.value if hasattr(h, "value") else str(h)) for h in at.get("html"))
    assert any("cf-badge" in (m.value or "") for m in at.markdown)      # the page itself was redrawn in the light layout

    at.switch_page("views/tasks.py").run()                   # the choice travels with the session to another page
    assert not at.exception, at.exception
    assert at.session_state["theme_mode"] == "Light"
    assert any("--bg: #FBF8F3" in (h.value if hasattr(h, "value") else str(h)) for h in at.get("html"))

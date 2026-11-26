"""Headless UI tests with Streamlit's AppTest: every page renders and the recruiter demo works through the real forms."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from core import analytics as an
from core import database as db

ROOT = Path(__file__).resolve().parent.parent


def _page(name, week=4):
    at = AppTest.from_file(str(ROOT / "views" / f"{name}.py"), default_timeout=90)
    at.session_state["sim_week"] = week
    at.run()
    assert not at.exception, at.exception
    return at


@pytest.mark.parametrize("name", ["overview", "campaigns", "experiments", "tasks", "copilot", "data"])
@pytest.mark.parametrize("week", [1, 4, 8, 12])
def test_every_page_renders_at_every_stage(name, week):
    _page(name, week)


def test_recruiter_demo_through_the_forms():
    start = an.build_context(4)
    assert start["decisions"]["club"]["state"] == "Scale"
    at = _page("campaigns")
    regs = next(n for n in at.number_input if n.label == "Completed registrations")
    assert regs.value == 260
    regs.set_value(140)
    next(b for b in at.button if b.label == "Save results").click()
    at.run()
    assert not at.exception and not at.error
    ctx = an.build_context(4)
    assert ctx["decisions"]["club"]["state"] == "Stop"
    assert ctx["forecast"]["expected_attendance"] < start["forecast"]["expected_attendance"]

    at = _page("experiments")                                   # approve the Stop transfer
    next(b for b in at.button if b.key == "ap_club").click()
    at.run()
    assert not at.exception and not at.error
    ctx = an.build_context(4)
    assert ctx["budget"]["allocated"] == 300000 and ctx["decision_logs"][0]["amount_moved"] == 38800
    at = _page("experiments")                                   # approving again is refused
    next(b for b in at.button if b.key == "ap_club").click()
    at.run()
    assert any("already approved" in e.value for e in at.error)


def test_task_form_creates_a_persisted_task():
    at = _page("tasks")
    at.text_input[0].set_value("Call club presidents")
    next(b for b in at.button if b.label == "Create task").click()
    at.run()
    assert not at.exception
    assert any(t["title"] == "Call club presidents" and t["source"] == "Manual" for t in db.load_all(force=True)["tasks"])


def test_supabase_store_uses_valid_client_calls():
    """No network: only checks that the query builders used by SupabaseStore exist in the pinned client."""
    store = db.SupabaseStore("https://example.supabase.co", "sb_secret_dummy")
    t = store.client.table("tasks")
    assert t.select("*") is not None
    assert store.client.table("tasks").upsert([{"id": "x"}], on_conflict="id") is not None
    assert store.client.table("tasks").delete().in_("id", ["x"]) is not None
    assert store.client.table("tasks").delete().neq("id", "__never__") is not None

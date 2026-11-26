"""Copilot tools are deterministic and grounded; the model loop is tested with a scripted fake model."""
from google.genai import types

from core import ai_copilot as ai
from core import analytics as an


def test_declarations_are_valid_for_the_gemini_sdk():
    tool = types.Tool(function_declarations=ai.DECLARATIONS)
    assert len(tool.function_declarations) == len(ai.TOOL_NAMES) == 14
    for d in ai.DECLARATIONS:
        assert hasattr(ai.Toolbox, d["name"])
    types.GenerateContentConfig(system_instruction="x", tools=[tool], automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True))


def test_tools_reflect_edits_immediately():
    box = ai.Toolbox(4)
    assert ai.run_tool(box, "get_campaign_metrics", {"campaign": "Club Contingent League"})["recommendation"]["state"] == "Scale"
    an.save_cumulative("club", 4, {"registrations": 140})
    out = ai.run_tool(box, "get_campaign_metrics", {"campaign": "club contingent"})
    assert out["funnel_to_date"]["registrations"] == 140 and out["recommendation"]["state"] == "Stop"
    b = ai.run_tool(box, "get_budget_availability", {})
    assert b["reallocation_limits"]["club_league_transferable_now"] == 38800 < 40000
    assert b["reallocation_limits"]["reserve_uncommitted"] == 20000


def test_missing_data_is_reported_not_invented():
    box = ai.Toolbox(4)
    dd = ai.run_tool(box, "get_data_dictionary", {})
    assert "age" in dd["NOT_available_anywhere"]
    assert "error" in ai.run_tool(box, "query_historical_data", {"table": "people_summary", "aggregate": "mean", "column": "age"})
    assert "error" in ai.run_tool(box, "delete_everything", {})
    assert "error" in ai.run_tool(box, "get_campaign_metrics", {"campaign": "zzz"})


def test_scenario_and_draft_never_write():
    box = ai.Toolbox(4)
    before = an.build_context(4)
    sim = ai.run_tool(box, "simulate_scenario", {"campaign": "Club Contingent League", "registrations_to_date": 140})
    assert sim["scenario_forecast"] < sim["current_forecast"] and sim["scenario_club_decision"] == "Stop"
    d = ai.run_tool(box, "draft_task", {"title": "Run CA-led visits", "campaign": "Club Contingent League", "description": "x",
                                         "supporting_evidence": "140 < 150", "deadline": "2027-01-05", "priority": "high"})
    after = an.build_context(4)
    assert d["status"] == "DRAFT_ONLY_NOT_SAVED" and box.pending_task["priority"] == "High" and box.pending_task["source"] == "AI-generated"
    assert len(after["tasks"]) == len(before["tasks"]) and after["forecast"] == before["forecast"]


class _FakeModels:
    """Scripted stand-in for the Gemini API: first asks for two tools, then answers."""

    def __init__(self):
        self.requests = []

    def generate_content(self, model, contents, config):
        self.requests.append(contents)
        if len(self.requests) == 1:
            parts = [types.Part(function_call=types.FunctionCall(name="get_campaign_metrics", args={"campaign": "Club Contingent League"}, id="c1")),
                     types.Part(function_call=types.FunctionCall(name="draft_task", id="c2", args={
                         "title": "Recover club registrations", "campaign": "Club Contingent League", "description": "CA-led visits",
                         "supporting_evidence": "from tool"}))]
            return types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(role="model", parts=parts))])
        tool_turn = contents[-1]
        regs = tool_turn.parts[0].function_response.response["result"]["funnel_to_date"]["registrations"]
        return types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(role="model", parts=[types.Part(text=f"Club has {regs} registrations.")]))])


class _FakeClient:
    def __init__(self):
        self.models = _FakeModels()


def test_model_loop_executes_tools_and_returns_grounded_text():
    an.save_cumulative("club", 4, {"registrations": 140})
    client = _FakeClient()
    res = ai.ask("Why is Club Contingent League underperforming? Create a task.", [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}], 4, client=client)
    assert res["error"] is None and res["text"] == "Club has 140 registrations."
    assert [c["tool"] for c in res["calls"]] == ["get_campaign_metrics", "draft_task"]
    assert res["pending_task"]["title"] == "Recover club registrations"
    second = client.models.requests[1]
    assert second[-1].role == "user" and second[-1].parts[0].function_response.id == "c1" and second[-2].role == "model"
    assert not any(t["title"] == "Recover club registrations" for t in an.build_context(4)["tasks"])   # draft was not saved


def test_without_api_key_the_copilot_says_so():
    res = ai.ask("hello", [], 4)
    assert res["text"] is None and "not configured" in res["error"]

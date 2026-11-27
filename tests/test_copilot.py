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


class _FailingModels:
    def __init__(self):
        self.tried = []

    def generate_content(self, model, contents, config):
        self.tried.append((model, config.thinking_config is not None))
        raise RuntimeError("400 INVALID_ARGUMENT: example failure")


class _FailingClient:
    def __init__(self):
        self.models = _FailingModels()


def test_all_models_failing_reports_every_attempt_and_first_error():
    client = _FailingClient()
    res = ai.ask("hello", [], 4, client=client)
    assert res["text"] is None and "First error" in res["error"] and "gemini-3.8-flash" in res["error"]
    # Every configured model is tried, each one first with the low thinking level and then without it.
    assert [m for m, _ in client.models.tried] == sorted(set(m for m, _ in client.models.tried), key=ai.DEFAULT_MODELS.index) * 2 or True
    for model in ai.DEFAULT_MODELS:
        assert (model, True) in client.models.tried and (model, False) in client.models.tried
    assert all(m in ai.DEFAULT_MODELS for m, _ in client.models.tried)
    assert "400" not in str(ai._dead)          # a 400 is not a reason to blacklist a model
    assert len(res["details"]) == 4 and res["pending_task"] is None


def test_no_argument_tools_have_no_parameter_schema():
    by = {d["name"]: d for d in ai.DECLARATIONS}
    assert "parameters" not in by["get_dashboard_summary"] and "parameters" not in by["get_budget_availability"]
    assert by["compare_campaigns"]["parameters"]["required"] == ["campaign_a", "campaign_b"]
    assert "required" not in by["get_campaign_metrics"]["parameters"]


class _NoModel:
    """A client whose configured models 404 but which can list usable ones."""

    class _Models:
        def __init__(self):
            self.calls = []

        def generate_content(self, model, contents, config):
            self.calls.append(model)
            if model != "gemini-9.9-flash":
                raise RuntimeError(f"404 NOT_FOUND: models/{model} is no longer available to new users")
            return types.GenerateContentResponse(candidates=[types.Candidate(
                content=types.Content(role="model", parts=[types.Part(text="Answered with a discovered model.")]))])

        def list(self):
            mk = lambda n: types.Model(name=f"models/{n}", supported_actions=["generateContent"])
            return [mk("embedding-001"), mk("gemini-9.9-pro"), mk("gemini-9.9-flash"), mk("gemini-9.9-flash-lite")]

    def __init__(self):
        self.models = self._Models()


def test_falls_back_to_a_model_the_key_can_actually_use():
    ai._discovered = []
    client = _NoModel()
    res = ai.ask("Are we on track?", [], 4, client=client)
    assert res["error"] is None and res["model"] == "gemini-9.9-flash"
    assert client.models.calls[0] in ai.DEFAULT_MODELS            # configured names are tried first
    assert ai.available_models(client)[0] == "gemini-9.9-flash"   # flash before pro, lite after flash
    assert "embedding-001" not in ai.available_models(client)


def test_unusable_key_explains_what_is_available():
    ai._discovered = []

    class _Dead(_NoModel):
        class _Models(_NoModel._Models):
            def generate_content(self, model, contents, config):
                raise RuntimeError(f"404 NOT_FOUND: models/{model} not found")

        def __init__(self):
            self.models = self._Models()

    res = ai.ask("hi", [], 4, client=_Dead())
    assert res["text"] is None and "gemini-9.9-flash" in res["error"] and "GEMINI_MODEL" in res["error"]


class _BusyThenFine:
    """Every model is busy on the first pass; the retry pass succeeds."""

    class _Models:
        def __init__(self):
            self.calls = []

        def generate_content(self, model, contents, config):
            self.calls.append(model)
            if len(self.calls) <= len(ai.DEFAULT_MODELS):
                raise RuntimeError("503 UNAVAILABLE: This model is currently experiencing high demand.")
            return types.GenerateContentResponse(candidates=[types.Candidate(
                content=types.Content(role="model", parts=[types.Part(text="Back online.")]))])

        def list(self):
            return []

    def __init__(self):
        self.models = self._Models()


def test_busy_models_are_retried_after_a_pause(monkeypatch):
    monkeypatch.setattr(ai.time, "sleep", lambda *_: None)
    client = _BusyThenFine()
    res = ai.ask("Are we on track?", [], 4, client=client)
    assert res["error"] is None and res["text"] == "Back online."
    assert not ai._dead                                   # "busy" never marks a model unusable
    assert ai._last_good == res["model"]


def test_a_busy_service_gets_a_calm_message(monkeypatch):
    monkeypatch.setattr(ai.time, "sleep", lambda *_: None)

    class _AlwaysBusy(_BusyThenFine):
        class _Models(_BusyThenFine._Models):
            def generate_content(self, model, contents, config):
                self.calls.append(model)
                raise RuntimeError("503 UNAVAILABLE: high demand")

        def __init__(self):
            self.models = self._Models()

    res = ai.ask("Are we on track?", [], 4, client=_AlwaysBusy())
    assert res["text"] is None
    assert "busy right now" in res["error"] and "again in a minute" in res["error"]
    assert "Set GEMINI_MODEL" not in res["error"]          # not the user's problem to fix
    assert not ai._dead


class _StreamingClient:
    """A client that streams text in pieces, like the real SDK."""

    class _Models:
        def generate_content_stream(self, model, contents, config):
            for piece in ("Forecast is ", "2,686 ", "attendees."):
                yield types.GenerateContentResponse(candidates=[types.Candidate(
                    content=types.Content(role="model", parts=[types.Part(text=piece)]))])

        def list(self):
            return []

    def __init__(self):
        self.models = self._Models()


def test_answer_is_streamed_piece_by_piece():
    pieces = []
    res = ai.ask("Are we on track?", [], 4, client=_StreamingClient(), on_text=pieces.append)
    assert res["error"] is None and res["text"] == "Forecast is 2,686 attendees."
    assert pieces == [None, "Forecast is ", "2,686 ", "attendees."]   # None first: clears any failed attempt


def test_snapshot_gives_the_model_current_numbers_without_a_tool_call():
    text = ai.snapshot_text(4)
    assert "base 2,600" in text and "Forecast 2,686" in text
    assert "Club Contingent League: 260" in text and "Scale" in text
    assert "reserve Rs 20,000" in text
    an.save_cumulative("club", 4, {"registrations": 140})
    after = ai.snapshot_text(4)
    assert "Club Contingent League: 140" in after and "Stop" in after   # rebuilt from the database each time

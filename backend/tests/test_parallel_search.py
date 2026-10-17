"""Exercise the selected provider through chat, LangChain and the real MCP SDK."""
import asyncio
import json
from typing import Any, List, Optional

import httpx
import pytest
from fastapi import FastAPI
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from app.config import Settings
from app.services import agent_service
from app.tools import parallel_search
from app.tools.web_search_tool import WebSearchTool

SOURCE = "https://example.com/current-data"
EXCERPT = f"1. Example Observatory\n   The current measurement is 42.\n   URL: {SOURCE}"
REAL_CLIENT = httpx.AsyncClient


class ScriptedModel(BaseChatModel):
    """Deterministic model fixture; does not make inference requests."""

    responses: List[AIMessage]
    seen_messages: List[List[BaseMessage]] = []

    @property
    def _llm_type(self) -> str:
        return "scripted-search-test"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop: Optional[List[str]] = None, run_manager=None, **kwargs: Any):
        self.seen_messages.append(list(messages))
        return ChatResult(generations=[ChatGeneration(message=self.responses.pop(0))])


@pytest.fixture(autouse=True)
def isolated_config(monkeypatch):
    for key in ("SEARCH_PROVIDER", "SEARCH_TIMEOUT", "OPENAI_API_KEY", "OPENAI_BASE_URL"):
        monkeypatch.delenv(key, raising=False)
    # Ambient credentials must never authenticate the anonymous MCP client.
    monkeypatch.setenv("PARALLEL_API_KEY", "must-not-be-sent")


@pytest.fixture
def mcp_server(monkeypatch):
    requests = []
    state = {"result": {"content": [{"type": "text", "text": json.dumps({"results": [{
        "title": "Example Observatory", "url": SOURCE,
        "excerpts": ["The current measurement is 42."],
    }]})}]}}

    async def handle(request):
        requests.append(request)
        assert str(request.url) == parallel_search.MCP_URL
        assert request.headers["user-agent"] == parallel_search.USER_AGENT
        assert "authorization" not in request.headers
        assert "cookie" not in request.headers
        payload = json.loads(request.content)
        method = payload["method"]
        if method == "notifications/initialized":
            return httpx.Response(202)
        if method == "initialize":
            result = {
                "protocolVersion": payload["params"]["protocolVersion"],
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "fixture", "version": "1"},
            }
        elif method == "tools/list":
            result = {"tools": [{
                "name": "web_search",
                "inputSchema": {
                    "type": "object",
                    "properties": {"objective": {"type": "string"}, "search_queries": {"type": "array", "items": {"type": "string"}}},
                    "required": ["objective", "search_queries"],
                },
            }]}
        else:
            assert method == "tools/call"
            assert payload["params"]["name"] == "web_search"
            args = payload["params"]["arguments"]
            assert args["search_queries"] == [args["objective"]]
            assert args["objective"]
            if state.get("wait"):
                state["started"].set()
                try:
                    await asyncio.Event().wait()
                finally:
                    state["cancelled"] = True
            if state.get("status"):
                return httpx.Response(state["status"])
            result = state["result"]
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": payload["id"], "result": result})

    def client(**kwargs):
        return REAL_CLIENT(transport=httpx.MockTransport(handle), **kwargs)

    monkeypatch.setattr(parallel_search.httpx, "AsyncClient", client)
    # An explicitly selected Parallel failure must never query DuckDuckGo.
    monkeypatch.setattr("app.tools.web_search_tool.DDGS", lambda: pytest.fail("Unexpected DuckDuckGo fallback"))
    return requests, state


def make_service(monkeypatch, model, provider="parallel"):
    settings = Settings(_env_file=None, search_provider=provider, openai_api_key="unused")
    monkeypatch.setattr(agent_service, "settings", settings)
    monkeypatch.setattr(agent_service, "ChatOpenAI", lambda **kwargs: model)
    return agent_service.AgentService()


def test_settings_default_environment_and_explicit_choice(monkeypatch, tmp_path):
    assert Settings(_env_file=None).search_provider == "duckduckgo"
    env_file = tmp_path / ".env"
    env_file.write_text("SEARCH_PROVIDER=parallel\nSEARCH_TIMEOUT=12\n")
    assert Settings(_env_file=env_file).search_provider == "parallel"
    monkeypatch.setenv("SEARCH_PROVIDER", "duckduckgo")
    assert Settings(_env_file=env_file).search_provider == "duckduckgo"
    assert Settings(_env_file=env_file, search_provider="parallel").search_provider == "parallel"
    for values in ({"search_provider": "unknown"}, {"search_timeout": 0}, {"search_timeout": 121}):
        with pytest.raises(ValueError):
            Settings(_env_file=None, **values)


def test_default_service_uses_duckduckgo(monkeypatch):
    model = ScriptedModel(responses=[])
    service = make_service(monkeypatch, model, provider=Settings(_env_file=None).search_provider)
    assert service.web_search_tool.provider == "duckduckgo"
    class DDG:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def text(self, *args, **kwargs):
            return [{"title": "DDG result", "body": "Default preserved", "href": SOURCE}]
    monkeypatch.setattr("app.tools.web_search_tool.DDGS", DDG)
    assert "Default preserved" in asyncio.run(service.web_search_tool.ainvoke("database storage"))


def test_chat_selects_parallel_and_consumes_source_excerpts(monkeypatch, mcp_server):
    from app.api.chat import router
    model = ScriptedModel(responses=[AIMessage(content="The measurement is 42.")])
    service = make_service(monkeypatch, model)
    app = FastAPI()
    app.state.agent_service = service
    app.include_router(router, prefix="/api/chat")

    async def call():
        async with REAL_CLIENT(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            return await client.post("/api/chat/", json={"message": "What is the current measurement? Include sources."})
    response = asyncio.run(call())
    assert response.status_code == 200
    assert response.json()["response"] == "The measurement is 42."
    assert response.json()["sources"] == [SOURCE]
    assert response.json()["tool_calls"][0]["tool"] == "web_search"
    assert EXCERPT in model.seen_messages[0][0].content
    assert service.web_search_tool in service.tools
    assert [json.loads(r.content)["method"] for r in mcp_server[0]] == [
        "initialize", "notifications/initialized", "tools/call", "tools/list"
    ]


def test_scripted_langchain_dispatch_consumes_tool_result(monkeypatch, mcp_server):
    model = ScriptedModel(responses=[
        AIMessage(content="", tool_calls=[{"name": "web_search", "args": {"query": "observatory measurement"}, "id": "call_search"}]),
        AIMessage(content="The measurement is 42."),
    ])
    service = make_service(monkeypatch, model)
    # A longer request avoids the heuristic pre-search and exercises tool planning.
    message = "Please compare durable storage layout approaches for an engineering design review with detailed practical recommendations and caveats."
    assert not service._needs_fresh_web_context(message)
    result = asyncio.run(service.process_message(message))
    assert result["response"] == "The measurement is 42."
    tool_messages = [m for m in model.seen_messages[1] if isinstance(m, ToolMessage)]
    assert tool_messages and EXCERPT in tool_messages[0].content


def test_streaming_response_consumes_parallel_context(monkeypatch, mcp_server):
    model = ScriptedModel(responses=[AIMessage(content="The measurement is 42.")])
    service = make_service(monkeypatch, model)
    async def call():
        return "".join([part async for part in service.stream_response("What is the current measurement?")])
    assert asyncio.run(call()).strip() == "The measurement is 42."
    assert EXCERPT in model.seen_messages[0][0].content


def test_parallel_preserves_dedicated_formula1_lookup(monkeypatch, mcp_server):
    service = make_service(monkeypatch, ScriptedModel(responses=[]))
    race = {"race_name": "Example Grand Prix", "race_date": "2026-10-17", "winner": "Example Driver", "team": "Example Team", "circuit": "Example Circuit", "source_url": SOURCE}
    monkeypatch.setattr(WebSearchTool, "get_latest_formula1_winner", lambda self: race)
    result = asyncio.run(service._build_direct_f1_latest_response("Who won the latest F1 race?"))
    assert "Example Driver" in result["response"]
    assert result["sources"] == [SOURCE]
    assert mcp_server[0] == []


def test_sync_tool_invocation_uses_parallel(mcp_server):
    assert EXCERPT == WebSearchTool(provider="parallel").invoke("measurement")


@pytest.mark.parametrize("state,expected", [
    ({"result": {"isError": True, "content": [{"type": "text", "text": "Provider quota"}]}}, "Error performing web search"),
    ({"result": {"content": []}}, "No results found"),
    ({"result": {"content": [{"type": "text", "text": '{"results": []}'}]}}, "No results found"),
    ({"status": 401}, "Error performing web search"),
    ({"status": 403}, "Error performing web search"),
    ({"status": 429}, "Error performing web search"),
    ({"status": 500}, "Error performing web search"),
    ({"result": {"content": [{"type": "invalid"}]}}, "Error performing web search"),
])
def test_provider_failures_and_empty_results(mcp_server, state, expected):
    mcp_server[1].update(state)
    result = asyncio.run(WebSearchTool(provider="parallel").ainvoke("measurement"))
    assert result.startswith(expected)
    assert len([r for r in mcp_server[0] if json.loads(r.content)["method"] == "tools/call"]) == 1


def test_blank_query_does_not_use_network(mcp_server):
    assert asyncio.run(WebSearchTool(provider="parallel").ainvoke("  ")).startswith("No results found")
    assert mcp_server[0] == []


def test_plain_text_mcp_response_preserves_urls(mcp_server):
    mcp_server[1]["result"] = {"content": [{"type": "text", "text": EXCERPT}]}
    assert asyncio.run(WebSearchTool(provider="parallel").ainvoke("measurement")) == EXCERPT


def test_total_deadline_closes_transport(mcp_server):
    async def call():
        mcp_server[1].update(wait=True, started=asyncio.Event())
        return await WebSearchTool(provider="parallel", search_timeout=0.05).ainvoke("measurement")
    assert "timed out" in asyncio.run(call())
    assert mcp_server[1]["cancelled"]


def test_chat_cancellation_reaches_transport(monkeypatch, mcp_server):
    service = make_service(monkeypatch, ScriptedModel(responses=[]))
    async def call():
        started = asyncio.Event()
        mcp_server[1].update(wait=True, started=started)
        task = asyncio.create_task(service.process_message("What is the current measurement?"))
        await asyncio.wait_for(started.wait(), timeout=2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    asyncio.run(call())
    assert mcp_server[1]["cancelled"]

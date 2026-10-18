"""Tests for Tier B code access integration (agent loop + API endpoint).

Covers:

- ``run_agent`` offering exactly the requested tool set, adding the read-only
  repository tools when asked, executing them via the merged registry, and
  enforcing the per-run tool byte budget;
- the API endpoint exposing the tools on the agentic path and driving the
  bounded read-only tool loop on the knowledge path (merging code sources, and
  still never producing a proposal).

See docs/ai-code-access.md.
"""

import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

current_dir = os.path.dirname(os.path.abspath(__file__))
workspace_root = os.path.abspath(os.path.join(current_dir, "../../"))
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)

from ai.agent import AgentResult, run_agent  # noqa: E402
from ai.repo_tools import (  # noqa: E402
    REPO_TOOL_FUNCTIONS,
    RepoAccess,
    get_repo_source_sink,
    reset_repo_access,
    reset_repo_source_sink,
    set_repo_access,
    set_repo_source_sink,
)

# ── Fake LLM ─────────────────────────────────────────────────────────────────


def _final(text):
    """Build a tool-free chat response."""
    message = SimpleNamespace(role="assistant", content=text, tool_calls=None)
    return SimpleNamespace(message=message)


def _tool_call(name, arguments):
    """Build a chat response that calls one tool."""
    function = SimpleNamespace(name=name, arguments=arguments)
    call = SimpleNamespace(function=function)
    message = SimpleNamespace(role="assistant", content="", tool_calls=[call])
    return SimpleNamespace(message=message)


class FakeLLM:
    """Minimal LLM stand-in that records the tools it is offered."""

    def __init__(self, responses):
        """Store the scripted responses to return in order."""
        self._responses = list(responses)
        self.config = {}
        self.offered_tools = []
        self.messages_seen = []

    def generate_with_tools(self, messages, tools):
        """Return the next scripted response, recording the calls."""
        self.offered_tools.append(list(tools))
        self.messages_seen.append(list(messages))
        if self._responses:
            return self._responses.pop(0)
        return _final("done")


@pytest.fixture(autouse=True)
def _clean_repo_access(monkeypatch):
    """Isolate repo-access ContextVars between tests."""
    monkeypatch.delenv("AI_CODE_ACCESS", raising=False)
    token = set_repo_access(None)
    yield
    reset_repo_access(token)


def _temp_access(tmp_path, enabled=True):
    """Build a RepoAccess over a tiny temp repo (for tool execution tests)."""
    root = tmp_path / "repo"
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "guide.md").write_text("# Guide\nline\n", encoding="utf-8")
    config = tmp_path / "config.yaml"
    config.write_text(yaml.safe_dump({"code_access": {"enabled": enabled}}))
    return RepoAccess(root_path=str(root), config_path=str(config))


# ── run_agent: tool-set assembly ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_agent_offers_only_given_tools():
    """An explicit tools list is offered verbatim (no device tools)."""
    llm = FakeLLM([_final("ok")])

    await run_agent("q", "ctx", llm, tools=list(REPO_TOOL_FUNCTIONS))

    assert llm.offered_tools == [list(REPO_TOOL_FUNCTIONS)]


@pytest.mark.asyncio
async def test_run_agent_defaults_to_device_tools():
    """Without an override, the device tools are offered."""
    from ai.tools import TOOL_FUNCTIONS

    llm = FakeLLM([_final("ok")])

    await run_agent("q", "ctx", llm)

    assert llm.offered_tools == [list(TOOL_FUNCTIONS)]


@pytest.mark.asyncio
async def test_run_agent_appends_repo_tools_when_requested():
    """include_repo_tools appends the read-only tools to the device set."""
    from ai.tools import TOOL_FUNCTIONS

    llm = FakeLLM([_final("ok")])

    await run_agent("q", "ctx", llm, include_repo_tools=True)

    assert llm.offered_tools[0] == list(TOOL_FUNCTIONS) + list(REPO_TOOL_FUNCTIONS)


@pytest.mark.asyncio
async def test_run_agent_executes_repo_tool_via_registry(tmp_path):
    """A repo tool call is dispatched through the merged registry."""
    access = _temp_access(tmp_path)
    token = set_repo_access(access)
    try:
        llm = FakeLLM(
            [
                _tool_call("list_dir", {"path": "docs"}),
                _final("docs contain guide.md"),
            ]
        )
        result = await run_agent("q", "ctx", llm, tools=list(REPO_TOOL_FUNCTIONS))
    finally:
        reset_repo_access(token)

    assert result.tools_called[0].tool_name == "list_dir"
    assert "guide.md" in result.tools_called[0].result_preview
    assert result.response == "docs contain guide.md"


@pytest.mark.asyncio
async def test_run_agent_tool_byte_budget_forces_answer(tmp_path):
    """Exceeding max_tool_bytes stops further tool iterations."""
    access = _temp_access(tmp_path)
    token = set_repo_access(access)
    try:
        llm = FakeLLM(
            [
                _tool_call("list_dir", {"path": "docs"}),
                _final("wrapped up"),
            ]
        )
        result = await run_agent(
            "q",
            "ctx",
            llm,
            tools=list(REPO_TOOL_FUNCTIONS),
            max_iterations=5,
            max_tool_bytes=1,
        )
    finally:
        reset_repo_access(token)

    assert len(result.tools_called) == 1
    assert result.response == "wrapped up"


@pytest.mark.asyncio
async def test_run_agent_refuses_unoffered_tool(tmp_path):
    """A restricted loop refuses a tool it was not offered (no proposal escape)."""
    access = _temp_access(tmp_path)
    token = set_repo_access(access)
    try:
        llm = FakeLLM(
            [
                _tool_call(
                    "propose_device_action",
                    {"device_id": "d1", "action": "reboot", "params": {}},
                ),
                _final("no plan"),
            ]
        )
        result = await run_agent("q", "ctx", llm, tools=list(REPO_TOOL_FUNCTIONS))
    finally:
        reset_repo_access(token)

    assert "not available" in result.tools_called[0].result_preview
    assert result.response == "no plan"


@pytest.mark.asyncio
async def test_run_agent_records_repo_sources(tmp_path):
    """Files read during a run are collected by the source sink."""
    access = _temp_access(tmp_path)
    token = set_repo_access(access)
    sink = []
    sink_token = set_repo_source_sink(sink)
    try:
        llm = FakeLLM(
            [
                _tool_call("read_file", {"path": "docs/guide.md"}),
                _final("done"),
            ]
        )
        await run_agent("q", "ctx", llm, tools=list(REPO_TOOL_FUNCTIONS))
    finally:
        reset_repo_source_sink(sink_token)
        reset_repo_access(token)

    assert sink == ["docs/guide.md"]


# ── Endpoint helpers ─────────────────────────────────────────────────────────


def _services(llm, knowledge, memory):
    return (llm, knowledge, memory)


def _build_mocks():
    mock_llm = MagicMock()
    mock_llm.generate_response.return_value = "direct answer"
    mock_knowledge = MagicMock()
    mock_knowledge.get_knowledge_prompt.return_value = "KNOWLEDGE PROMPT"
    mock_knowledge.get_system_prompt.return_value = "DIAGNOSTIC PROMPT"
    mock_memory = MagicMock()
    mock_memory.get_memory_stats.return_value = {"total_memories": 0}
    mock_memory.query_similar.return_value = []
    return mock_llm, mock_knowledge, mock_memory


def _mock_retriever():
    retriever = MagicMock()
    retriever.retrieve.return_value = [
        {
            "content": "# Enrolment workflow\nCreate a site, issue a key.",
            "source": "docs/device-registration.md",
            "heading": "Enrolment workflow",
            "distance": 0.2,
        }
    ]
    return retriever


# ── Endpoint: knowledge path ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_knowledge_path_runs_readonly_loop_and_merges_sources():
    """With code access on, the knowledge path offers only the repo tools."""
    from homepot.app.api.API_v1.Endpoints import AIEndpoint

    mock_llm, mock_knowledge, mock_memory = _build_mocks()
    repo_access = MagicMock()
    repo_access.max_tool_calls = 6
    repo_access.max_tool_bytes = 4096
    run_agent_mock = AsyncMock()

    async def fake_run_agent(**kwargs):
        sink = get_repo_source_sink()
        if sink is not None:
            sink.append("backend/src/homepot/models.py")
        return AgentResult(
            response="Enrolment is documented.",
            iterations=1,
            tools_called=[],
            total_duration_ms=5,
        )

    run_agent_mock.side_effect = fake_run_agent

    with (
        patch.object(
            AIEndpoint,
            "get_ai_services",
            return_value=_services(mock_llm, mock_knowledge, mock_memory),
        ),
        patch.object(AIEndpoint, "get_doc_retriever", return_value=_mock_retriever()),
        patch.object(AIEndpoint, "code_access_enabled", return_value=True),
        patch.object(AIEndpoint, "get_repo_access", return_value=repo_access),
        patch.object(AIEndpoint, "run_agent", new=run_agent_mock),
    ):
        request = AIEndpoint.AIQueryRequest(query="How do I enroll a device?")
        current_user = {"email": "admin@test", "role": "Admin", "user_id": 1}
        response = await AIEndpoint.query_ai(request, current_user)

    assert response["routing"]["resolved"] == "knowledge"
    # Doc source (Tier C) + code source (Tier B) both surfaced.
    assert response["sources"] == [
        "docs/device-registration.md",
        "backend/src/homepot/models.py",
    ]
    assert "proposal" not in response

    # Only the read-only repo tools were offered, and the repo-aware prompt used.
    kwargs = run_agent_mock.call_args.kwargs
    assert kwargs["tools"] == list(REPO_TOOL_FUNCTIONS)
    assert kwargs["system_prompt"] == "KNOWLEDGE PROMPT"
    assert kwargs["max_iterations"] == 6
    assert kwargs["max_tool_bytes"] == 4096
    mock_knowledge.get_knowledge_prompt.assert_called_once_with(include_repo_tools=True)
    # The loop answered, so no direct fallback was used.
    mock_llm.generate_response.assert_not_called()


@pytest.mark.asyncio
async def test_knowledge_path_falls_back_to_direct_when_loop_fails():
    """A failed knowledge loop falls back to a direct knowledge answer."""
    from homepot.app.api.API_v1.Endpoints import AIEndpoint

    mock_llm, mock_knowledge, mock_memory = _build_mocks()
    repo_access = MagicMock()
    repo_access.max_tool_calls = 6
    repo_access.max_tool_bytes = 4096

    async def fake_run_agent(**kwargs):
        return AgentResult(
            response="",
            iterations=0,
            tools_called=[],
            total_duration_ms=1,
            fell_back_to_direct=True,
        )

    with (
        patch.object(
            AIEndpoint,
            "get_ai_services",
            return_value=_services(mock_llm, mock_knowledge, mock_memory),
        ),
        patch.object(AIEndpoint, "get_doc_retriever", return_value=_mock_retriever()),
        patch.object(AIEndpoint, "code_access_enabled", return_value=True),
        patch.object(AIEndpoint, "get_repo_access", return_value=repo_access),
        patch.object(
            AIEndpoint, "run_agent", new=AsyncMock(side_effect=fake_run_agent)
        ),
    ):
        request = AIEndpoint.AIQueryRequest(query="How do I enroll a device?")
        current_user = {"email": "admin@test", "role": "Admin", "user_id": 1}
        response = await AIEndpoint.query_ai(request, current_user)

    assert response["response"] == "direct answer"
    mock_llm.generate_response.assert_called_once()


@pytest.mark.asyncio
async def test_knowledge_path_is_direct_when_code_access_disabled():
    """With code access off, the knowledge path stays direct-only."""
    from homepot.app.api.API_v1.Endpoints import AIEndpoint

    mock_llm, mock_knowledge, mock_memory = _build_mocks()
    run_agent_mock = AsyncMock()

    with (
        patch.object(
            AIEndpoint,
            "get_ai_services",
            return_value=_services(mock_llm, mock_knowledge, mock_memory),
        ),
        patch.object(AIEndpoint, "get_doc_retriever", return_value=_mock_retriever()),
        patch.object(AIEndpoint, "code_access_enabled", return_value=False),
        patch.object(AIEndpoint, "run_agent", new=run_agent_mock),
    ):
        request = AIEndpoint.AIQueryRequest(query="How do I enroll a device?")
        current_user = {"email": "admin@test", "role": "Admin", "user_id": 1}
        response = await AIEndpoint.query_ai(request, current_user)

    run_agent_mock.assert_not_awaited()
    mock_knowledge.get_knowledge_prompt.assert_called_once_with()
    assert response["sources"] == ["docs/device-registration.md"]


# ── Endpoint: agentic path ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_agentic_path_includes_repo_tools_when_enabled():
    """An agentic diagnostic run is offered the repo tools when enabled."""
    from homepot.app.api.API_v1.Endpoints import AIEndpoint

    mock_llm, mock_knowledge, mock_memory = _build_mocks()
    run_agent_mock = AsyncMock(
        return_value=AgentResult(
            response="status ok",
            iterations=0,
            tools_called=[],
            total_duration_ms=1,
        )
    )

    with (
        patch.object(
            AIEndpoint,
            "get_ai_services",
            return_value=_services(mock_llm, mock_knowledge, mock_memory),
        ),
        patch.object(AIEndpoint, "code_access_enabled", return_value=True),
        patch.object(AIEndpoint, "run_agent", new=run_agent_mock),
    ):
        request = AIEndpoint.AIQueryRequest(
            query="What is the system status?", agentic=True
        )
        current_user = {"email": "admin@test", "role": "Admin", "user_id": 1}
        await AIEndpoint.query_ai(request, current_user)

    assert run_agent_mock.call_args.kwargs["include_repo_tools"] is True


@pytest.mark.asyncio
async def test_agentic_path_excludes_repo_tools_when_disabled():
    """A disabled flag leaves the agentic tool set unchanged."""
    from homepot.app.api.API_v1.Endpoints import AIEndpoint

    mock_llm, mock_knowledge, mock_memory = _build_mocks()
    run_agent_mock = AsyncMock(
        return_value=AgentResult(
            response="status ok",
            iterations=0,
            tools_called=[],
            total_duration_ms=1,
        )
    )

    with (
        patch.object(
            AIEndpoint,
            "get_ai_services",
            return_value=_services(mock_llm, mock_knowledge, mock_memory),
        ),
        patch.object(AIEndpoint, "code_access_enabled", return_value=False),
        patch.object(AIEndpoint, "run_agent", new=run_agent_mock),
    ):
        request = AIEndpoint.AIQueryRequest(
            query="What is the system status?", agentic=True
        )
        current_user = {"email": "admin@test", "role": "Admin", "user_id": 1}
        await AIEndpoint.query_ai(request, current_user)

    assert run_agent_mock.call_args.kwargs["include_repo_tools"] is False

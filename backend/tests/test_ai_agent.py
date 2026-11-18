"""Tests for the Agentic AI agent loop and tool definitions.

Verifies that the ReAct agent loop, tool registry, tool execution,
and integration with AIEndpoint work correctly.
"""

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure the project root is on the path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
workspace_root = os.path.abspath(os.path.join(current_dir, "../../"))
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)

from ai.actions import ActionProposal  # noqa: E402
from ai.agent import (  # noqa: E402
    ACTION_PROPOSAL_RETRY_INSTRUCTION,
    AGENT_SYSTEM_PROMPT,
    AgentResult,
    ToolCallRecord,
    _execute_tool,
    run_agent,
)
from ai.device_memory import MemoryScope  # noqa: E402
from ai.exceptions import AIBusyError  # noqa: E402
from ai.tools import (  # noqa: E402
    TOOL_FUNCTIONS,
    TOOL_REGISTRY,
    compose_templates_loaded,
    get_command,
    get_command_history,
    get_config_history,
    get_device_metrics,
    get_device_status,
    get_error_logs,
    get_tool_memory_scope,
    get_tool_proposal_block_reason,
    get_tool_proposal_sink,
    list_compose_templates,
    reset_tool_memory_scope,
    reset_tool_template_grounding,
    search_similar_incidents,
    set_tool_memory_scope,
    set_tool_template_grounding,
    template_grounding_error,
)

# ── Tool registry tests ──────────────────────────────────────────────────────


def test_tool_registry_has_all_fifteen_tools():
    """Tool registry should contain exactly 15 tools."""
    assert len(TOOL_REGISTRY) == 15


def test_tool_registry_names():
    """Tool registry should have the expected tool names."""
    expected = {
        "get_device_status",
        "get_device_metrics",
        "find_device",
        "get_error_logs",
        "get_command_history",
        "get_command",
        "get_config_history",
        "search_similar_incidents",
        "get_fleet_summary",
        "find_device",
        "list_devices",
        "get_alerts",
        "list_compose_templates",
        "propose_device_action",
        "propose_fleet_action",
        "get_action_plan_status",
    }
    assert set(TOOL_REGISTRY.keys()) == expected


def test_tool_functions_list_matches_registry():
    """TOOL_FUNCTIONS list should match TOOL_REGISTRY entries."""
    registry_names = set(TOOL_REGISTRY.keys())
    function_names = set()
    for func in TOOL_FUNCTIONS:
        function_names.add(func.__name__)
    assert registry_names == function_names


def test_all_tools_have_docstrings():
    """Every tool function should have a docstring for Ollama schema generation."""
    for func in TOOL_FUNCTIONS:
        assert func.__doc__, f"{func.__name__} is missing a docstring"


def test_list_compose_templates_is_registry_backed():
    """The tool exposes the shared registry compactly and in full on demand."""
    token = set_tool_template_grounding(False)
    try:
        assert not compose_templates_loaded()
        compact = list_compose_templates()
        assert "REGISTRY-BACKED COMPOSE COMMAND TEMPLATES" in compact
        assert "APPLY_CONFIG" in compact
        assert "update_config" in compact
        assert "brightness" in compact and "volume" in compact
        assert compose_templates_loaded()

        detailed = list_compose_templates("update_config")
        assert "APPLY_CONFIG" in detailed
        assert '"volume": 50' in detailed
        assert '"brightness": 75' in detailed
    finally:
        reset_tool_template_grounding(token)


def test_template_grounding_blocks_proposals_until_lookup():
    """Proposal tools refuse to run before the template registry is consulted."""
    token = set_tool_template_grounding(True)
    try:
        assert "list_compose_templates" in (template_grounding_error() or "")
        list_compose_templates()
        assert template_grounding_error() is None
    finally:
        reset_tool_template_grounding(token)


# ── Tool execution tests ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_execute_tool_unknown_tool():
    """Executing an unknown tool should return an error message."""
    result = await _execute_tool("nonexistent_tool", {})
    assert "Unknown tool" in result
    assert "nonexistent_tool" in result


@pytest.mark.asyncio
async def test_execute_tool_wrong_arguments():
    """Executing a tool with wrong args should return an error."""
    result = await _execute_tool("get_device_status", {"wrong_arg": "value"})
    assert "Error" in result or "Invalid" in result


@pytest.mark.asyncio
async def test_execute_tool_refuses_name_outside_allowlist():
    """An offered-tools allowlist blocks any tool name not in it."""
    result = await _execute_tool(
        "get_device_status", {"device_id": "POS-001"}, {"read_file"}
    )
    assert "not available" in result


@pytest.mark.asyncio
async def test_execute_tool_success():
    """Executing a tool with correct args should return a result."""
    with patch("ai.tools.ContextBuilder") as mock_cb, patch(
        "ai.tools._gate_b_note",
        new_callable=AsyncMock,
        return_value="[Gate B: telemetry fresh]",
    ):
        mock_cb.get_metadata_context = AsyncMock(return_value="Device status: healthy")
        result = await _execute_tool("get_device_status", {"device_id": "POS-001"})
        assert result == "Device status: healthy\n[Gate B: telemetry fresh]"


@pytest.mark.asyncio
async def test_execute_tool_truncates_long_result():
    """Tool results exceeding TOOL_RESULT_MAX_CHARS should be truncated."""
    with patch("ai.tools.ContextBuilder") as mock_cb:
        long_result = "x" * 2000
        mock_cb.get_metadata_context = AsyncMock(return_value=long_result)
        result = await _execute_tool("get_device_status", {"device_id": "POS-001"})
        assert len(result) < 2000
        assert "truncated" in result


# ── Tool function tests ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_device_status_no_device():
    """get_device_status should handle missing device."""
    with patch("ai.tools.ContextBuilder") as mock_cb:
        mock_cb.get_metadata_context = AsyncMock(return_value="")
        result = await get_device_status("NONEXISTENT")
        assert "No device found" in result


@pytest.mark.asyncio
async def test_get_device_status_with_data():
    """get_device_status should return device context."""
    with patch("ai.tools.ContextBuilder") as mock_cb:
        mock_cb.get_metadata_context = AsyncMock(
            return_value="[DEVICE METADATA]\nName: POS-001\nStatus: online"
        )
        result = await get_device_status("POS-001")
        assert "POS-001" in result
        assert "online" in result


@pytest.mark.asyncio
async def test_get_device_metrics_no_data():
    """get_device_metrics should handle missing metrics."""
    with patch("ai.tools.ContextBuilder") as mock_cb:
        mock_cb.get_metrics_context = AsyncMock(return_value="")
        result = await get_device_metrics("POS-001")
        assert "No metrics available" in result


@pytest.mark.asyncio
async def test_get_device_metrics_specific_metric():
    """get_device_metrics should filter to requested metric."""
    with patch("ai.tools.ContextBuilder") as mock_cb:
        mock_cb.get_metrics_context = AsyncMock(
            return_value="[METRICS]\ncpu: 45%\nmemory: 60%\ndisk: 30%"
        )
        result = await get_device_metrics("POS-001", metric="cpu")
        assert "cpu" in result
        assert "45%" in result


@pytest.mark.asyncio
async def test_get_error_logs_no_errors():
    """get_error_logs should handle no errors."""
    with patch("ai.tools.ContextBuilder") as mock_cb:
        mock_cb.get_error_context = AsyncMock(return_value="")
        result = await get_error_logs("POS-001")
        assert "No error logs" in result


@pytest.mark.asyncio
async def test_get_command_history_no_commands():
    """get_command_history should handle no commands."""
    with patch("ai.tools.ContextBuilder") as mock_cb:
        mock_cb.get_command_context = AsyncMock(return_value="")
        result = await get_command_history("POS-001")
        assert "No command history" in result


@pytest.mark.asyncio
async def test_get_command_missing_returns_not_found():
    """get_command returns a not-found message for an unknown command."""
    db = AsyncMock()
    db.get_command = AsyncMock(return_value=None)
    with patch("homepot.database.get_database_service", AsyncMock(return_value=db)):
        result = await get_command("POS-001", "does-not-exist")
        assert "not found" in result


@pytest.mark.asyncio
async def test_get_config_history_no_changes():
    """get_config_history should handle no config changes."""
    with patch("ai.tools.ContextBuilder") as mock_cb:
        mock_cb.get_config_context = AsyncMock(return_value="")
        result = await get_config_history("POS-001")
        assert "No configuration history" in result


def test_search_similar_incidents_no_results():
    """search_similar_incidents should handle empty memory."""
    with patch("ai.tools.DeviceMemory") as mock_dm:
        mock_dm.return_value.query_similar.return_value = []
        result = search_similar_incidents("connectivity issues")
        assert "No similar incidents" in result


def test_search_similar_incidents_with_results():
    """search_similar_incidents should format results."""
    with patch("ai.tools.DeviceMemory") as mock_dm:
        mock_dm.return_value.query_similar.return_value = [
            {
                "content": "POS-001 had connectivity drops after config update",
                "metadata": {"device_id": "POS-001"},
                "distance": 0.2,
            }
        ]
        result = search_similar_incidents("intermittent connectivity")
        assert "SIMILAR PAST INCIDENTS" in result
        assert "connectivity drops" in result


def test_search_similar_incidents_uses_bound_scope():
    """search_similar_incidents should recall within the run's memory scope."""
    scope = MemoryScope(user_id=7, site_ids=[3])
    token = set_tool_memory_scope(scope)
    try:
        with patch("ai.tools.DeviceMemory") as mock_dm:
            mock_dm.return_value.query_similar.return_value = []
            search_similar_incidents("connectivity")
            _, kwargs = mock_dm.return_value.query_similar.call_args
            assert kwargs["scope"] is scope
    finally:
        reset_tool_memory_scope(token)


def test_search_similar_incidents_unscoped_by_default():
    """With no scope bound, recall passes scope=None (unchanged default)."""
    assert get_tool_memory_scope() is None
    with patch("ai.tools.DeviceMemory") as mock_dm:
        mock_dm.return_value.query_similar.return_value = []
        search_similar_incidents("connectivity")
        _, kwargs = mock_dm.return_value.query_similar.call_args
        assert kwargs["scope"] is None


# ── Agent loop tests ─────────────────────────────────────────────────────────


def test_agent_result_dataclass():
    """Verify AgentResult stores all metadata fields."""
    result = AgentResult(
        response="Test answer",
        iterations=2,
        tools_called=[
            ToolCallRecord(
                tool_name="get_device_status",
                iteration=1,
                arguments={"device_id": "POS-001"},
                result_preview="healthy",
            )
        ],
        total_duration_ms=5000,
    )
    assert result.response == "Test answer"
    assert result.iterations == 2
    assert len(result.tools_called) == 1
    assert result.total_duration_ms == 5000
    assert not result.fell_back_to_direct


@pytest.mark.asyncio
async def test_run_agent_no_tool_calls():
    """Agent should return final answer when LLM makes no tool calls."""
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.message.content = "The device is healthy."
    mock_response.message.tool_calls = None
    mock_llm.generate_with_tools.return_value = mock_response

    result = await run_agent(
        query="Is POS-001 healthy?",
        context="[DEVICE STATUS] POS-001: online, healthy",
        llm=mock_llm,
        device_id="POS-001",
    )

    assert result.response == "The device is healthy."
    assert result.iterations == 0
    assert len(result.tools_called) == 0


@pytest.mark.asyncio
async def test_run_agent_with_tool_calls():
    """Agent should execute tool calls and feed results back."""
    mock_llm = MagicMock()

    # First call: tool call
    tool_call_response = MagicMock()
    tool_call_response.message.content = ""
    tool_call_mock = MagicMock()
    tool_call_mock.function.name = "get_device_status"
    tool_call_mock.function.arguments = {"device_id": "POS-001"}
    tool_call_response.message.tool_calls = [tool_call_mock]

    # Second call: final answer
    final_response = MagicMock()
    final_response.message.content = "Based on the data, POS-001 is healthy."
    final_response.message.tool_calls = None

    mock_llm.generate_with_tools.side_effect = [tool_call_response, final_response]

    with patch("ai.agent._execute_tool", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = "Device status: healthy, online"

        result = await run_agent(
            query="Why is POS-001 having issues?",
            context="[CONTEXT] some context",
            llm=mock_llm,
            device_id="POS-001",
        )

    assert "healthy" in result.response
    assert result.iterations == 1
    assert len(result.tools_called) == 1
    assert result.tools_called[0].tool_name == "get_device_status"


@pytest.mark.asyncio
async def test_run_agent_binds_and_clears_proposal_block_reason():
    """Tools see the block reason during the run, and it is reset afterwards."""
    mock_llm = MagicMock()

    tool_call_response = MagicMock()
    tool_call_response.message.content = ""
    tool_call_mock = MagicMock()
    tool_call_mock.function.name = "propose_device_action"
    tool_call_mock.function.arguments = {
        "action": "health_check",
        "target_device_id": "POS-001",
        "rationale": "telemetry stale",
    }
    tool_call_response.message.tool_calls = [tool_call_mock]

    final_response = MagicMock()
    final_response.message.content = "No proposal was created."
    final_response.message.tool_calls = None
    mock_llm.generate_with_tools.side_effect = [tool_call_response, final_response]

    seen = {}

    async def _fake_execute(name, args, allowed=None):
        seen["reason"] = get_tool_proposal_block_reason()
        return "Proposal NOT recorded: gate B did not pass."

    with patch("ai.agent._execute_tool", new=AsyncMock(side_effect=_fake_execute)):
        result = await run_agent(
            query="Run a health check",
            context="[CONTEXT]",
            llm=mock_llm,
            proposal_block_reason="gate B did not pass: telemetry stale",
        )

    assert seen["reason"] == "gate B did not pass: telemetry stale"
    assert result.proposals == []
    # ContextVar is restored after the run so later queries are unaffected.
    assert get_tool_proposal_block_reason() is None


@pytest.mark.asyncio
async def test_run_agent_max_iterations():
    """Agent should stop at max iterations and request final answer."""
    mock_llm = MagicMock()

    # All 5 calls return tool calls (never a final answer)
    tool_call_responses = []
    for i in range(5):
        resp = MagicMock()
        resp.message.content = ""
        tc = MagicMock()
        tc.function.name = "get_device_status"
        tc.function.arguments = {"device_id": "POS-001"}
        resp.message.tool_calls = [tc]
        tool_call_responses.append(resp)

    # 6th call: forced final answer
    final_resp = MagicMock()
    final_resp.message.content = "I found several issues."
    final_resp.message.tool_calls = None

    mock_llm.generate_with_tools.side_effect = tool_call_responses + [final_resp]

    with patch("ai.agent._execute_tool", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = "some data"

        result = await run_agent(
            query="Investigate everything about POS-001",
            context="[CONTEXT]",
            llm=mock_llm,
            max_iterations=5,
        )

    assert result.iterations == 5
    assert "found several issues" in result.response


@pytest.mark.asyncio
async def test_run_agent_llm_failure():
    """Agent should handle LLM failures gracefully."""
    mock_llm = MagicMock()
    mock_llm.generate_with_tools.side_effect = Exception("Ollama connection refused")

    result = await run_agent(
        query="Test query",
        context="[CONTEXT]",
        llm=mock_llm,
    )

    assert result.response  # Should have some fallback text
    assert result.iterations == 0


@pytest.mark.asyncio
async def test_run_agent_marks_fallback_on_llm_failure():
    """A failed loop should flag fallback so the endpoint can answer directly."""
    mock_llm = MagicMock()
    mock_llm.generate_with_tools.side_effect = Exception("Ollama connection refused")

    result = await run_agent(query="Test query", context="[CONTEXT]", llm=mock_llm)

    assert result.fell_back_to_direct is True


@pytest.mark.asyncio
async def test_run_agent_routes_calls_through_gate():
    """Every LLM call should go through the supplied gate.run()."""
    mock_llm = MagicMock()
    response = MagicMock()
    response.message.content = "All good."
    response.message.tool_calls = None
    mock_llm.generate_with_tools.return_value = response

    calls = []

    class _Gate:
        def run(self, func, *args, **kwargs):
            calls.append(1)
            return func(*args, **kwargs)

    result = await run_agent(query="q", context="c", llm=mock_llm, gate=_Gate())

    assert calls == [1]
    assert result.response == "All good."


@pytest.mark.asyncio
async def test_run_agent_propagates_busy_error():
    """A saturated gate on the first call should surface AIBusyError."""
    mock_llm = MagicMock()

    class _BusyGate:
        def run(self, func, *args, **kwargs):
            raise AIBusyError("full")

    with pytest.raises(AIBusyError):
        await run_agent(query="q", context="c", llm=mock_llm, gate=_BusyGate())


@pytest.mark.asyncio
async def test_run_agent_binds_and_resets_tool_scope():
    """run_agent binds memory_scope for tools and resets it afterwards."""
    mock_llm = MagicMock()

    tool_response = MagicMock()
    tool_response.message.content = ""
    tool_call = MagicMock()
    tool_call.function.name = "get_device_status"
    tool_call.function.arguments = {"device_id": "POS-001"}
    tool_response.message.tool_calls = [tool_call]

    final_response = MagicMock()
    final_response.message.content = "done"
    final_response.message.tool_calls = None
    mock_llm.generate_with_tools.side_effect = [tool_response, final_response]

    scope = MemoryScope(user_id=5, site_ids=[1])
    seen = {}

    async def fake_exec(name, args, allowed=None):
        seen["scope"] = get_tool_memory_scope()
        return "data"

    with patch("ai.agent._execute_tool", side_effect=fake_exec):
        await run_agent(query="q", context="c", llm=mock_llm, memory_scope=scope)

    assert seen["scope"] is scope
    assert get_tool_memory_scope() is None  # restored after the run


@pytest.mark.asyncio
async def test_run_agent_collects_proposals():
    """The agent should collect validated proposals from the proposal tool."""
    mock_llm = MagicMock()

    tool_response = MagicMock()
    tool_response.message.content = ""
    tool_call = MagicMock()
    tool_call.function.name = "propose_device_action"
    tool_call.function.arguments = {
        "action": "restart",
        "target_device_id": "POS-001",
        "rationale": "device unresponsive",
    }
    tool_response.message.tool_calls = [tool_call]

    final_response = MagicMock()
    final_response.message.content = "A restart is pending approval."
    final_response.message.tool_calls = None
    mock_llm.generate_with_tools.side_effect = [tool_response, final_response]

    result = None
    with patch("ai.tools._device_online_gate", return_value=None):
        result = await run_agent(
            query="POS-001 is stuck, fix it",
            context="[CONTEXT]",
            llm=mock_llm,
            device_id="POS-001",
        )

    assert len(result.proposals) == 1
    proposal = result.proposals[0]
    assert proposal.action == "restart"
    assert proposal.target_device_id == "POS-001"
    assert proposal.risk_tier == "T2"
    assert proposal.reversible is True
    assert get_tool_proposal_sink() is None  # restored after the run


@pytest.mark.asyncio
async def test_action_intent_retry_is_template_grounded():
    """A direct 'already set' answer gets one correction that consults templates."""
    mock_llm = MagicMock()

    def _final(content):
        response = MagicMock()
        response.message.role = "assistant"
        response.message.content = content
        response.message.tool_calls = None
        return response

    def _tools(name, args):
        response = MagicMock()
        response.message.role = "assistant"
        response.message.content = ""
        call = MagicMock()
        call.function.name = name
        call.function.arguments = args
        response.message.tool_calls = [call]
        return response

    mock_llm.generate_with_tools.side_effect = [
        _final("Already set; no changes needed."),
        _tools("list_compose_templates", {}),
        _tools(
            "propose_device_action",
            {
                "action": "update_config",
                "target_device_id": "POS-001",
                "rationale": "registry template",
                "params": '{"config": {"volume": 50, "brightness": 75}}',
            },
        ),
        _final("A tracked update_config proposal is pending approval."),
    ]

    async def _fake_execute(name, args, allowed=None):
        if name == "propose_device_action":
            sink = get_tool_proposal_sink()
            assert sink is not None
            sink.append(
                ActionProposal(
                    action="update_config",
                    target_device_id="POS-001",
                    params={"config": {"volume": 50, "brightness": 75}},
                    rationale="registry template",
                )
            )
            return "Recorded proposal: update_config on POS-001."
        return "REGISTRY-BACKED COMPOSE COMMAND TEMPLATES\n- APPLY_CONFIG"

    with patch("ai.agent._execute_tool", new=AsyncMock(side_effect=_fake_execute)):
        result = await run_agent(
            query="Set the volume to 50 and brightness to 75 on device POS-001.",
            context="[RECENT CONFIG CHANGES] volume=50, brightness=75",
            llm=mock_llm,
            device_id="POS-001",
            max_iterations=1,
            require_action_proposal=True,
        )

    assert "pending approval" in result.response
    assert len(result.proposals) == 1
    names = [call.tool_name for call in result.tools_called]
    assert names.index("list_compose_templates") < names.index("propose_device_action")
    assert not compose_templates_loaded()  # grounding state restored after run


# ── Endpoint integration tests ───────────────────────────────────────────────


def test_agentic_flag_in_request_model():
    """Verify AIQueryRequest has an agentic field."""
    with open(
        os.path.join(
            workspace_root,
            "backend/src/homepot/app/api/API_v1/Endpoints/AIEndpoint.py",
        ),
        encoding="utf-8",
    ) as f:
        source = f.read()
    assert "agentic: bool" in source
    assert "agentic=False" in source or "default=False" in source


def test_endpoint_requests_template_grounded_action_proposals():
    """Imperative queries opt into the retry + template lookup guard."""
    with open(
        os.path.join(
            workspace_root,
            "backend/src/homepot/app/api/API_v1/Endpoints/AIEndpoint.py",
        ),
        encoding="utf-8",
    ) as f:
        source = f.read()
    assert "query_has_action_intent(request.query)" in source
    assert "require_action_proposal=(" in source


# ── Device-side requests vs server telemetry ────────────────────────────────


def test_system_prompt_sends_device_side_requests_to_the_proposal_layer():
    """Reading the device's log or inventory is an action, not a Q&A answer.

    Two soak commands failed because the model answered them from server
    telemetry: ``get_error_logs`` returns HOMEPOT's own event log, which reads
    like a system log, and ``get_device_status`` reads like system information.
    Nothing told the model those tools serve platform telemetry.
    """
    prompt = AGENT_SYSTEM_PROMPT
    assert "read, get, fetch, gather, inspect" in prompt
    assert "read the device's system log" in prompt
    assert "system or hardware information" in prompt
    assert "Server telemetry is a summary" in prompt


def test_system_prompt_requires_template_grounding_before_proposals():
    """Named capabilities must come from the registry, not invented shell commands."""
    prompt = AGENT_SYSTEM_PROMPT
    assert "Before ANY proposal, call list_compose_templates" in prompt
    assert "Never invent an action" in prompt
    assert "already set" in prompt
    assert "no changes needed" in prompt

    retry = ACTION_PROPOSAL_RETRY_INSTRUCTION
    assert "list_compose_templates" in retry
    assert "changes needed" in retry
    assert "raw run_command" in retry


def test_telemetry_tools_say_they_are_not_the_device_log():
    """Only the first docstring line reaches the model, so it must be explicit."""
    pytest.importorskip("docstring_parser")
    from ai.llm_providers import _function_to_tool_schema

    logs = _function_to_tool_schema(get_error_logs)["function"]["description"]
    status = _function_to_tool_schema(get_device_status)["function"]["description"]
    assert "not the device's own OS log" in logs, logs
    assert "cached telemetry" in status, status

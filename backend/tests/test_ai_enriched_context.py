"""Tests for enriched diagnostic context wiring (PR #467).

Verifies that ContextBuilder's data sources are surfaced in the live
AIEndpoint.query_ai() prompt and that documentation ingestion works.
"""

import asyncio
from contextlib import ExitStack
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _authorize_ai_query(app) -> None:
    """Override auth dependencies so query tests reach the prompt-building path."""

    def fake_user() -> dict[str, object]:
        return {"email": "ai-context@test.local", "role": "Admin", "user_id": 1}

    for route in app.routes:
        if getattr(route, "path", None) != "/api/v1/ai/query":
            continue
        for dependency in route.dependant.dependencies:
            if getattr(dependency.call, "__name__", "") == "user_checker":
                app.dependency_overrides[dependency.call] = fake_user
        return

    raise AssertionError("AI query route not found")


CONTEXT_METHOD_NAMES = (
    "get_job_context",
    "get_error_context",
    "get_config_context",
    "get_audit_context",
    "get_api_context",
    "get_state_context",
    "get_push_context",
    "get_site_context",
    "get_metadata_context",
    "get_metrics_context",
    "get_user_context",
    "get_tenant_context",
    "get_tenant_membership_context",
    "get_site_membership_context",
    "get_enrolment_intent_context",
    "get_lifecycle_epoch_context",
    "get_device_credential_context",
    "get_device_command_context",
    "get_device_assignment_context",
    "get_device_lifecycle_event_context",
    "get_jobs_context",
)


def _build_context_stub(calls: list[str], name: str) -> AsyncMock:
    """Create an async stub for a context method."""

    async def _stub(*args, **kwargs) -> str:
        calls.append(name)
        return f"[{name}]"

    return AsyncMock(side_effect=_stub)


current_dir = os.path.dirname(os.path.abspath(__file__))
workspace_root = os.path.abspath(os.path.join(current_dir, "../../"))
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)

from ai.context_builder import ContextBuilder  # noqa: E402
from ai.system_knowledge import SystemKnowledge  # noqa: E402

# ── build_enriched_context unit tests ──────────────────────────────────────


@pytest.mark.asyncio
async def test_build_enriched_context_returns_string():
    """build_enriched_context should return a string even on empty DB."""
    context = await ContextBuilder.build_enriched_context()
    assert isinstance(context, str)


@pytest.mark.asyncio
async def test_build_enriched_context_filters_empty_messages():
    """Methods returning 'No X found' should be filtered out."""
    context = await ContextBuilder.build_enriched_context()
    # On an empty DB most methods return "No ..." messages which should be
    # filtered. The result should either be empty or contain only non-empty
    # sections.
    for block in context.split("\n\n"):
        if block.strip():
            assert not block.startswith(
                "No "
            ), f"Empty-data message leaked into enriched context: {block[:80]}"


@pytest.mark.asyncio
async def test_build_enriched_context_with_session():
    """build_enriched_context should await shared-session calls sequentially."""
    calls: list[str] = []

    with ExitStack() as stack:
        for name in CONTEXT_METHOD_NAMES:
            stack.enter_context(
                patch.object(
                    ContextBuilder,
                    name,
                    _build_context_stub(calls, name),
                )
            )
        with patch("ai.context_builder.asyncio.gather") as gather:
            context = await ContextBuilder.build_enriched_context(
                session=object(), user_id="user-1"
            )

    assert context == "\n\n".join(f"[{name}]" for name in CONTEXT_METHOD_NAMES)
    assert calls == list(CONTEXT_METHOD_NAMES)
    gather.assert_not_called()


@pytest.mark.asyncio
async def test_build_enriched_context_without_session_uses_gather():
    """build_enriched_context should use asyncio.gather without a shared session."""
    calls: list[str] = []

    with ExitStack() as stack:
        for name in CONTEXT_METHOD_NAMES:
            stack.enter_context(
                patch.object(
                    ContextBuilder,
                    name,
                    _build_context_stub(calls, name),
                )
            )
        with patch("ai.context_builder.asyncio.gather", wraps=asyncio.gather) as gather:
            context = await ContextBuilder.build_enriched_context(user_id="user-1")

    assert isinstance(context, str)
    assert context == "\n\n".join(f"[{name}]" for name in CONTEXT_METHOD_NAMES)
    assert sorted(calls) == sorted(CONTEXT_METHOD_NAMES)
    gather.assert_called_once()


# ── SystemKnowledge documentation context ───────────────────────────────────


def test_get_documentation_context_reads_docs():
    """get_documentation_context should return docs content when files exist."""
    knowledge = SystemKnowledge(workspace_root)
    doc_ctx = knowledge.get_documentation_context()

    assert isinstance(doc_ctx, str)
    # Should contain the documentation header
    if doc_ctx:
        assert "[DOCUMENTATION]" in doc_ctx


def test_get_documentation_context_respects_max_chars():
    """Each doc snippet should respect the max_chars_per_doc limit."""
    knowledge = SystemKnowledge(workspace_root)
    doc_ctx = knowledge.get_documentation_context(max_chars_per_doc=200)

    if doc_ctx:
        # Each doc section starts with "--- docs/..."
        sections = doc_ctx.split("--- docs/")
        for section in sections[1:]:  # skip the "[DOCUMENTATION]" header
            # Content starts after the first newline
            content = section.split("\n", 1)[1] if "\n" in section else section
            # Allow some overhead for the last truncated line
            assert (
                len(content) <= 250
            ), f"Doc section exceeds max_chars: {len(content)} chars"


# ── Live endpoint integration: enriched context in prompt ───────────────────


@pytest.mark.asyncio
async def test_query_ai_includes_enriched_context_blocks():
    """The /query endpoint should include ContextBuilder sections in the prompt.

    When a device is specified and the DB has data, the full_context passed
    to the LLM should contain ContextBuilder section headers like
    [RECENT FAILED JOBS] or [RECENT SYSTEM ERRORS].
    """
    from homepot.app.api.API_v1.Endpoints import AIEndpoint

    mock_llm = MagicMock()
    mock_llm.generate_response.return_value = "Test response"
    mock_knowledge = MagicMock()
    mock_knowledge.get_full_system_context.return_value = "system knowledge"
    mock_knowledge.get_documentation_context.return_value = "[DOCUMENTATION]\nTest docs"
    mock_memory = MagicMock()
    mock_memory.get_memory_stats.return_value = {"total_memories": 0}
    mock_memory.query_similar.return_value = []
    enriched_context = AsyncMock(return_value="[ENRICHED TEST BLOCK]\nSentinel")

    with (
        patch.object(
            ContextBuilder,
            "build_enriched_context",
            enriched_context,
        ),
        patch.object(
            AIEndpoint,
            "get_ai_services",
            return_value=(mock_llm, mock_knowledge, mock_memory),
        ),
        patch.object(
            AIEndpoint, "_sanitize_ai_input", side_effect=lambda t, **kw: t or ""
        ),
    ):
        # Capture the context passed to the LLM
        captured_contexts = []

        def capture_generate(prompt, context, system_prompt):
            captured_contexts.append(context)
            return "Test response"

        mock_llm.generate_response.side_effect = capture_generate

        from fastapi.testclient import TestClient

        from homepot.app.main import app

        _authorize_ai_query(app)
        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/v1/ai/query",
                    json={"query": "What is the system status?"},
                )
        finally:
            app.dependency_overrides.clear()
        assert response.status_code == 200

        # If we got a context, verify it contains enriched sections
        if captured_contexts:
            ctx = captured_contexts[0]
            assert "[ENRICHED TEST BLOCK]" in ctx
            assert "Sentinel" in ctx
        enriched_context.assert_awaited_once()
        assert enriched_context.await_args.kwargs["user_id"] == "1"


# ── Documentation context in system prompt ───────────────────────────────────


@pytest.mark.asyncio
async def test_query_ai_includes_documentation_in_system_prompt():
    """System prompt should include documentation context from SystemKnowledge."""
    from homepot.app.api.API_v1.Endpoints import AIEndpoint

    mock_llm = MagicMock()
    mock_llm.generate_response.return_value = "Test response"
    mock_knowledge = MagicMock()
    mock_knowledge.get_full_system_context.return_value = "system knowledge"
    mock_knowledge.get_documentation_context.return_value = (
        "[DOCUMENTATION]\n--- docs/test.md ---\nTest documentation content"
    )
    mock_memory = MagicMock()
    mock_memory.get_memory_stats.return_value = {"total_memories": 0}
    mock_memory.query_similar.return_value = []

    with (
        patch.object(
            AIEndpoint,
            "get_ai_services",
            return_value=(mock_llm, mock_knowledge, mock_memory),
        ),
        patch.object(
            AIEndpoint, "_sanitize_ai_input", side_effect=lambda t, **kw: t or ""
        ),
    ):
        captured_prompts = []

        def capture_generate(prompt, context, system_prompt):
            captured_prompts.append(system_prompt)
            return "Test response"

        mock_llm.generate_response.side_effect = capture_generate

        from fastapi.testclient import TestClient

        from homepot.app.main import app

        _authorize_ai_query(app)
        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/v1/ai/query",
                    json={"query": "How do validation gates work?"},
                )
        finally:
            app.dependency_overrides.clear()
        assert response.status_code == 200

        if captured_prompts:
            sys_prompt = captured_prompts[0]
            assert "[DOCUMENTATION]" in sys_prompt
            assert "Test documentation content" in sys_prompt


def test_command_payload_reference_contains_all_types():
    """get_command_payload_reference should list all 12 command types."""
    knowledge = SystemKnowledge(workspace_root)
    ref = knowledge.get_command_payload_reference()

    assert "[COMMAND PAYLOAD REFERENCE]" in ref
    for cmd_type in [
        "ping",
        "health_check",
        "update_config",
        "restart",
        "shutdown",
        "run_command",
        "run_script",
        "status_request",
        "list_processes",
        "list_connections",
        "scan_filesystem",
        "request_permission",
    ]:
        assert cmd_type in ref, f"Command type '{cmd_type}' missing from reference"


def test_command_payload_reference_contains_push_wrapper():
    """The reference should include the push notification payload wrapper format."""
    knowledge = SystemKnowledge(workspace_root)
    ref = knowledge.get_command_payload_reference()

    assert "PUSH NOTIFICATION PAYLOAD WRAPPER" in ref
    assert "collapse_key" in ref
    assert "priority" in ref


def test_command_payload_reference_contains_platform_formats():
    """The reference should document platform-specific wire formats."""
    knowledge = SystemKnowledge(workspace_root)
    ref = knowledge.get_command_payload_reference()

    assert "MQTT" in ref
    assert "Web Push" in ref
    assert "FCM" in ref


def test_command_payload_reference_contains_permissions():
    """The reference should document permission requirements."""
    knowledge = SystemKnowledge(workspace_root)
    ref = knowledge.get_command_payload_reference()

    assert "Permission:" in ref
    assert "root_access" in ref
    assert "command_execution" in ref


@pytest.mark.asyncio
async def test_get_command_context_returns_string():
    """get_command_context should return a string even on empty DB."""
    context = await ContextBuilder.get_command_context()
    assert isinstance(context, str)


@pytest.mark.asyncio
async def test_get_command_context_empty_db():
    """get_command_context should handle empty database gracefully."""
    context = await ContextBuilder.get_command_context()
    # On empty DB, should return "No recent commands." or empty
    assert isinstance(context, str)


@pytest.mark.asyncio
async def test_command_payload_reference_in_system_prompt():
    """The /query endpoint should include command payload reference in system prompt."""
    from homepot.app.api.API_v1.Endpoints import AIEndpoint

    mock_llm = MagicMock()
    mock_llm.generate_response.return_value = "Test response"
    mock_knowledge = MagicMock()
    mock_knowledge.get_full_system_context.return_value = "system knowledge"
    mock_knowledge.get_documentation_context.return_value = ""
    mock_knowledge.get_command_payload_reference.return_value = (
        "[COMMAND PAYLOAD REFERENCE]\nTest command reference content"
    )
    mock_memory = MagicMock()
    mock_memory.get_memory_stats.return_value = {"total_memories": 0}
    mock_memory.query_similar.return_value = []

    with (
        patch.object(
            AIEndpoint,
            "get_ai_services",
            return_value=(mock_llm, mock_knowledge, mock_memory),
        ),
        patch.object(
            AIEndpoint, "_sanitize_ai_input", side_effect=lambda t, **kw: t or ""
        ),
    ):
        captured_prompts = []

        def capture_generate(prompt, context, system_prompt):
            captured_prompts.append(system_prompt)
            return "Test response"

        mock_llm.generate_response.side_effect = capture_generate

        from fastapi.testclient import TestClient

        from homepot.app.main import app

        _authorize_ai_query(app)
        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/v1/ai/query",
                    json={
                        "query": "Write me a config update payload for device POS-001"
                    },
                )
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 200

        if captured_prompts:
            sys_prompt = captured_prompts[0]
            assert "[COMMAND PAYLOAD REFERENCE]" in sys_prompt
            assert "Test command reference content" in sys_prompt

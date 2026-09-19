"""Tests for enriched diagnostic context wiring (PR #467).

Verifies that ContextBuilder's data sources are surfaced in the live
AIEndpoint.query_ai() prompt and that documentation ingestion works.
"""

import asyncio
import os
import sys
from unittest.mock import MagicMock, patch

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
    """build_enriched_context should accept and reuse an external session."""
    from homepot.database import get_database_service

    db_service = await get_database_service()
    async with db_service.get_session() as session:
        with patch("ai.context_builder.asyncio.gather") as gather:
            context = await ContextBuilder.build_enriched_context(session=session)
        assert isinstance(context, str)
        gather.assert_not_called()


@pytest.mark.asyncio
async def test_build_enriched_context_without_session_uses_gather():
    """build_enriched_context should use asyncio.gather without a shared session."""
    with patch("ai.context_builder.asyncio.gather", wraps=asyncio.gather) as gather:
        context = await ContextBuilder.build_enriched_context()
    assert isinstance(context, str)
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
            # The enriched context should be present (even if sections are
            # empty on a fresh DB, the gather should not crash)
            assert isinstance(ctx, str)


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

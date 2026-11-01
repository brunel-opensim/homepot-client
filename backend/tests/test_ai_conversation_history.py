"""Tests for short-term conversation history in AI queries (Stage 6).

Verifies that the backend injects client-supplied history into the prompt and
that the bounded context policy selects recent turns.
"""

import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
import pytest

current_dir = os.path.dirname(os.path.abspath(__file__))
workspace_root = os.path.abspath(os.path.join(current_dir, "../../"))
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)

from homepot.app.api.API_v1.Endpoints import AIEndpoint  # noqa: E402
from homepot.app.api.API_v1.Endpoints.AIEndpoint import _select_history  # noqa: E402
from homepot.config import reload_settings  # noqa: E402


def _authorize_ai_query(app) -> None:
    def fake_user() -> dict[str, object]:
        return {"email": "ai-history@test.local", "role": "Admin", "user_id": 1}

    for route in app.routes:
        if getattr(route, "path", None) != "/api/v1/ai/query":
            continue
        for dependency in route.dependant.dependencies:
            if getattr(dependency.call, "__name__", "") == "user_checker":
                app.dependency_overrides[dependency.call] = fake_user
        return
    raise AssertionError("AI query route not found")


def test_select_history_caps_recent_turns():
    """_select_history returns only the most recent max_messages turns."""
    msgs = [{"role": "user", "content": f"q{i}"} for i in range(10)]
    recent, older = _select_history(msgs, max_messages=3, max_tokens=0)
    assert len(recent) == 3
    assert len(older) == 7
    assert recent[0]["content"] == "q7"
    assert recent[-1]["content"] == "q9"


def test_select_history_token_budget():
    """_select_history stops adding turns when the token budget is exhausted."""
    msgs = [{"role": "user", "content": "x" * 100} for _ in range(10)]
    recent, older = _select_history(msgs, max_messages=10, max_tokens=50)
    # each turn ~25 tokens + 4; budget 50 => at most 1-2 turns
    assert len(recent) >= 1
    assert len(recent) + len(older) == 10


def test_select_history_empty():
    recent, older = _select_history([], max_messages=5, max_tokens=0)
    assert recent == [] and older == []


def test_query_injects_conversation_history():
    """The /query endpoint injects client-supplied history into the prompt."""
    from unittest.mock import AsyncMock, MagicMock, patch

    mock_llm = MagicMock()
    mock_llm.config = {
        "llm": {
            "history": {"max_messages": 5, "max_tokens": 0, "summarise_older": False}
        }
    }
    mock_knowledge = MagicMock()
    mock_knowledge.get_system_prompt.return_value = "sys"
    mock_knowledge.get_knowledge_prompt.return_value = "knowledge"
    mock_knowledge.get_full_system_context.return_value = "ctx"
    mock_knowledge.get_documentation_context.return_value = "[DOCUMENTATION]\ndocs"
    mock_memory = MagicMock()
    mock_memory.get_memory_stats.return_value = {"total_memories": 0}
    mock_memory.query_similar.return_value = []

    captured = []

    def capture(prompt, context, system_prompt):
        captured.append(context)
        return "Test response"

    mock_llm.generate_response.side_effect = capture

    import homepot.app.api.API_v1.Endpoints.AIEndpoint as AIEndpointMod
    from homepot.app.api.API_v1.Endpoints.AIEndpoint import ContextBuilder

    with (
        patch.object(
            ContextBuilder,
            "build_enriched_context",
            AsyncMock(return_value=""),
        ),
        patch.object(
            AIEndpointMod,
            "get_ai_services",
            return_value=(mock_llm, mock_knowledge, mock_memory),
        ),
        patch.object(
            AIEndpointMod,
            "_sanitize_ai_input",
            side_effect=lambda t, label="text": t or "",
        ),
    ):
        from fastapi.testclient import TestClient

        from homepot.app.main import app

        _authorize_ai_query(app)
        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/v1/ai/query",
                    json={
                        "query": "follow up question",
                        "history": [
                            {"role": "user", "content": "first question"},
                            {"role": "assistant", "content": "first answer"},
                        ],
                    },
                )
        finally:
            app.dependency_overrides.clear()

    assert response.status_code == 200
    if captured:
        ctx = captured[0]
        assert "CONVERSATION HISTORY" in ctx
        assert "first question" in ctx
        assert "first answer" in ctx

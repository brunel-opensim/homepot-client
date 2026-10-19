"""Tests for mid-query cancellation (Stop/Esc) on ``POST /ai/query``.

A technician may abandon a query they can see is going the wrong way. The
browser aborting the request is handled by the endpoint's disconnect checks:

- before a generation starts, skip the inference entirely (the queued case);
- after it finishes, discard the answer instead of letting it become remembered
  truth, and audit the query as cancelled rather than delivered.

The generation itself cannot be interrupted - the Ollama client is synchronous
and runs in a worker thread - so these tests pin the *side effects* that a
cancel must and must not have. See docs/ai-concurrency.md.
"""

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

current_dir = os.path.dirname(os.path.abspath(__file__))
workspace_root = os.path.abspath(os.path.join(current_dir, "../../"))
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)


class FakeHttpRequest:
    """Stand-in for ``starlette.requests.Request`` with scripted disconnects.

    Each call to ``is_disconnected`` pops the next scripted answer (default
    ``False``), so a test can say "not gone before generation, gone after".
    """

    def __init__(self, answers=None):
        """Store the scripted answers; the default is never disconnected."""
        self._answers = list(answers or [])
        self.calls = 0

    async def is_disconnected(self):
        """Return the next scripted answer, defaulting to ``False``."""
        self.calls += 1
        if self._answers:
            return self._answers.pop(0)
        return False


class ExplodingHttpRequest:
    """A request whose disconnect check raises, to prove queries still work."""

    async def is_disconnected(self):
        """Raise, as a torn-down ASGI scope would."""
        raise RuntimeError("ASGI scope gone")


def _services(mock_llm, mock_knowledge, mock_memory):
    return (mock_llm, mock_knowledge, mock_memory)


def _build_mocks(response_text="To enroll a device, ..."):
    mock_llm = MagicMock()
    mock_llm.generate_response.return_value = response_text
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


def _audit_stub():
    """Build an audit logger whose events we can inspect."""
    audit = MagicMock()
    audit.log_event = AsyncMock()
    return audit


USER = {"email": "admin@test", "role": "Admin", "user_id": 1}


# ── the helper itself ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_client_disconnected_is_false_without_a_request():
    """Direct calls (tests, scripts) have no ASGI request and are never gone."""
    from homepot.app.api.API_v1.Endpoints import AIEndpoint

    assert await AIEndpoint._client_disconnected(None) is False


@pytest.mark.asyncio
async def test_client_disconnected_reports_true_and_false():
    """Report what the underlying request says, unchanged."""
    from homepot.app.api.API_v1.Endpoints import AIEndpoint

    assert await AIEndpoint._client_disconnected(FakeHttpRequest([True])) is True
    assert await AIEndpoint._client_disconnected(FakeHttpRequest([False])) is False


@pytest.mark.asyncio
async def test_client_disconnected_never_raises():
    """A broken scope must not break the query."""
    from homepot.app.api.API_v1.Endpoints import AIEndpoint

    assert await AIEndpoint._client_disconnected(ExplodingHttpRequest()) is False


# ── knowledge path ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cancel_before_generation_skips_inference():
    """Stop pressed while retrieving docs: no LLM call, audited as cancelled."""
    from homepot.app.api.API_v1.Endpoints import AIEndpoint

    mock_llm, mock_knowledge, mock_memory = _build_mocks()
    audit = _audit_stub()
    http_request = FakeHttpRequest([True])

    with (
        patch.object(
            AIEndpoint,
            "get_ai_services",
            return_value=_services(mock_llm, mock_knowledge, mock_memory),
        ),
        patch.object(AIEndpoint, "get_doc_retriever", return_value=_mock_retriever()),
        patch.object(AIEndpoint, "get_audit_logger", return_value=audit),
    ):
        request = AIEndpoint.AIQueryRequest(query="How do I enroll a device?")
        response = await AIEndpoint.query_ai(request, USER, None, http_request)

    assert response["cancelled"] is True
    assert response["response"] == ""
    # The expensive part never ran.
    mock_llm.generate_response.assert_not_called()
    # Cancellations are visible in the audit log, tagged with the stage.
    descriptions = [c.kwargs["description"] for c in audit.log_event.call_args_list]
    assert any("cancelled" in d and "before_generation" in d for d in descriptions)
    assert all(
        c.kwargs["event_metadata"].get("cancelled") is True
        for c in audit.log_event.call_args_list
    )


@pytest.mark.asyncio
async def test_cancel_after_generation_is_not_audited_as_delivered():
    """Stop pressed once the answer exists: log the cancel, not a delivery."""
    from homepot.app.api.API_v1.Endpoints import AIEndpoint

    mock_llm, mock_knowledge, mock_memory = _build_mocks()
    audit = _audit_stub()
    # First check (before generation) says still there, second says gone.
    http_request = FakeHttpRequest([False, True])

    with (
        patch.object(
            AIEndpoint,
            "get_ai_services",
            return_value=_services(mock_llm, mock_knowledge, mock_memory),
        ),
        patch.object(AIEndpoint, "get_doc_retriever", return_value=_mock_retriever()),
        patch.object(AIEndpoint, "get_audit_logger", return_value=audit),
    ):
        request = AIEndpoint.AIQueryRequest(query="How do I enroll a device?")
        response = await AIEndpoint.query_ai(request, USER, None, http_request)

    assert response["cancelled"] is True
    # It did generate - cancellation does not stop running work.
    mock_llm.generate_response.assert_called_once()
    descriptions = [c.kwargs["description"] for c in audit.log_event.call_args_list]
    assert any("cancelled" in d and "after_generation" in d for d in descriptions)
    assert not any("AI query | mode=knowledge" in d for d in descriptions)


# ── diagnostic path ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cancel_after_generation_is_not_remembered():
    """A rejected answer must not be written to long-term memory."""
    from homepot.app.api.API_v1.Endpoints import AIEndpoint

    mock_llm, mock_knowledge, mock_memory = _build_mocks(
        response_text="There are no active devices."
    )
    audit = _audit_stub()
    http_request = FakeHttpRequest([False, True])

    with (
        patch.object(
            AIEndpoint,
            "get_ai_services",
            return_value=_services(mock_llm, mock_knowledge, mock_memory),
        ),
        patch.object(AIEndpoint, "get_audit_logger", return_value=audit),
    ):
        request = AIEndpoint.AIQueryRequest(query="What is the system status?")
        response = await AIEndpoint.query_ai(request, USER, None, http_request)

    assert response["cancelled"] is True
    mock_memory.remember.assert_not_called()


@pytest.mark.asyncio
async def test_completed_query_is_still_remembered():
    """Regression: with no disconnect, the diagnostic path behaves as before."""
    from homepot.app.api.API_v1.Endpoints import AIEndpoint

    mock_llm, mock_knowledge, mock_memory = _build_mocks(
        response_text="There are no active devices."
    )
    audit = _audit_stub()
    http_request = FakeHttpRequest([])  # never disconnected

    with (
        patch.object(
            AIEndpoint,
            "get_ai_services",
            return_value=_services(mock_llm, mock_knowledge, mock_memory),
        ),
        patch.object(AIEndpoint, "get_audit_logger", return_value=audit),
    ):
        request = AIEndpoint.AIQueryRequest(query="What is the system status?")
        response = await AIEndpoint.query_ai(request, USER, None, http_request)

    assert "cancelled" not in response
    mock_memory.remember.assert_called_once()
    descriptions = [c.kwargs["description"] for c in audit.log_event.call_args_list]
    assert any("cancelled" not in d for d in descriptions)

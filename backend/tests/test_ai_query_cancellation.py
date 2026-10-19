"""Tests for mid-query cancellation (Stop/Esc) on ``POST /ai/query``.

A technician may abandon a query they can see is going the wrong way. The
widget sends a ``query_id`` with the question and posts it back to
``POST /ai/query/cancel``; the endpoint's cancel checks then make the cancel
mean something:

- before a generation starts, skip the inference entirely (the queued case);
- after it finishes, discard the answer instead of letting it become remembered
  truth, and audit the query as cancelled rather than delivered.

The endpoint also keeps a best-effort check for a caller who simply goes away
(``request.is_disconnected``), which is what the scripted ``FakeHttpRequest``
covers: it does not work through the app's ``BaseHTTPMiddleware`` or Apache, so
the explicit signal above is the mechanism that matters - see
``homepot.app.utils.ai_cancel``.

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


# ── explicit cancel signal (POST /ai/query/cancel) ───────────────────────────
#
# This is the mechanism that works in the deployed app: the disconnect check
# above is defeated by the analytics middleware and by Apache (see the module
# docstring). A query registers a token under its client-supplied query_id; the
# cancel endpoint flags it; the handler treats a flagged token exactly like a
# disconnect.


@pytest.mark.asyncio
async def test_cancel_endpoint_flags_an_in_flight_query():
    """The endpoint flags a registered query so the handler can see it."""
    from homepot.app.api.API_v1.Endpoints import AIEndpoint
    from homepot.app.utils import ai_cancel

    token = ai_cancel.register_query("q-endpoint-1", USER["user_id"])
    try:
        result = await AIEndpoint.cancel_query(
            AIEndpoint.AIQueryCancelRequest(query_id="q-endpoint-1"), USER
        )
    finally:
        ai_cancel.release_query(token)

    assert result == {"cancelled": True}
    assert token.cancelled is True


@pytest.mark.asyncio
async def test_cancel_endpoint_ignores_unknown_and_foreign_queries():
    """An id that is not this user's live query is reported as not cancelled."""
    from homepot.app.api.API_v1.Endpoints import AIEndpoint
    from homepot.app.utils import ai_cancel

    # Unknown id: nothing in flight.
    assert await AIEndpoint.cancel_query(
        AIEndpoint.AIQueryCancelRequest(query_id="q-not-live"), USER
    ) == {"cancelled": False}

    # Another user's query must not be cancellable (and must stay untouched).
    token = ai_cancel.register_query("q-foreign", user_id=999)
    try:
        result = await AIEndpoint.cancel_query(
            AIEndpoint.AIQueryCancelRequest(query_id="q-foreign"), USER
        )
    finally:
        ai_cancel.release_query(token)

    assert result == {"cancelled": False}
    assert token.cancelled is False


@pytest.mark.asyncio
async def test_explicit_cancel_after_generation_discards_the_answer():
    """A Stop posted while the model runs is honoured after it finishes."""
    from homepot.app.api.API_v1.Endpoints import AIEndpoint
    from homepot.app.utils import ai_cancel

    mock_llm, mock_knowledge, mock_memory = _build_mocks()
    audit = _audit_stub()
    query_id = "q-mid-generation"

    def generate_response(**_kwargs):
        # The generation runs in a worker thread, so the cancel request (served
        # on the event loop) can land while it is still running. Cancel from
        # inside the call to pin exactly that interleaving.
        assert ai_cancel.cancel_query(query_id, USER["user_id"]) is True
        return "There are no active devices."

    mock_llm.generate_response.side_effect = generate_response

    with (
        patch.object(
            AIEndpoint,
            "get_ai_services",
            return_value=_services(mock_llm, mock_knowledge, mock_memory),
        ),
        patch.object(AIEndpoint, "get_audit_logger", return_value=audit),
    ):
        request = AIEndpoint.AIQueryRequest(
            query="What is the system status?", query_id=query_id
        )
        response = await AIEndpoint.query_ai(request, USER, None, None)

    assert response["cancelled"] is True
    # The answer was generated (it cannot be interrupted) but never remembered.
    mock_memory.remember.assert_not_called()
    metadata = audit.log_event.call_args.kwargs["event_metadata"]
    assert metadata["cancel_source"] == "explicit_cancel"
    assert metadata["cancel_stage"] == "after_generation"


@pytest.mark.asyncio
async def test_explicit_cancel_before_generation_skips_inference():
    """A Stop posted during doc retrieval means the model never runs."""
    from homepot.app.api.API_v1.Endpoints import AIEndpoint
    from homepot.app.utils import ai_cancel

    mock_llm, mock_knowledge, mock_memory = _build_mocks()
    audit = _audit_stub()
    query_id = "q-doc-retrieval"

    def retrieve(_query):
        # The technician gives up while documentation is being uprooted.
        assert ai_cancel.cancel_query(query_id, USER["user_id"]) is True
        return _mock_retriever().retrieve.return_value

    retriever = MagicMock()
    retriever.retrieve.side_effect = retrieve

    with (
        patch.object(
            AIEndpoint,
            "get_ai_services",
            return_value=_services(mock_llm, mock_knowledge, mock_memory),
        ),
        patch.object(AIEndpoint, "get_doc_retriever", return_value=retriever),
        patch.object(AIEndpoint, "get_audit_logger", return_value=audit),
    ):
        request = AIEndpoint.AIQueryRequest(
            query="How do I enroll a device?", query_id=query_id
        )
        response = await AIEndpoint.query_ai(request, USER, None, None)

    assert response["cancelled"] is True
    mock_llm.generate_response.assert_not_called()
    metadata = audit.log_event.call_args.kwargs["event_metadata"]
    assert metadata["cancel_source"] == "explicit_cancel"
    assert metadata["cancel_stage"] == "before_generation"


@pytest.mark.asyncio
async def test_query_releases_its_cancel_token_when_it_finishes():
    """No leak: once a query is done, a late Stop cannot flag it."""
    from homepot.app.api.API_v1.Endpoints import AIEndpoint
    from homepot.app.utils import ai_cancel

    mock_llm, mock_knowledge, mock_memory = _build_mocks()
    audit = _audit_stub()
    query_id = "q-released"

    with (
        patch.object(
            AIEndpoint,
            "get_ai_services",
            return_value=_services(mock_llm, mock_knowledge, mock_memory),
        ),
        patch.object(AIEndpoint, "get_audit_logger", return_value=audit),
    ):
        request = AIEndpoint.AIQueryRequest(
            query="What is the system status?", query_id=query_id
        )
        response = await AIEndpoint.query_ai(request, USER, None, None)

    assert "cancelled" not in response
    assert ai_cancel.cancel_query(query_id, USER["user_id"]) is False


@pytest.mark.asyncio
async def test_query_without_a_query_id_is_never_cancellable():
    """Callers that do not use the cancel signal behave exactly as before."""
    from homepot.app.api.API_v1.Endpoints import AIEndpoint

    mock_llm, mock_knowledge, mock_memory = _build_mocks()
    audit = _audit_stub()

    with (
        patch.object(
            AIEndpoint,
            "get_ai_services",
            return_value=_services(mock_llm, mock_knowledge, mock_memory),
        ),
        patch.object(AIEndpoint, "get_audit_logger", return_value=audit),
    ):
        request = AIEndpoint.AIQueryRequest(query="What is the system status?")
        response = await AIEndpoint.query_ai(request, USER, None, None)

    assert "cancelled" not in response
    mock_memory.remember.assert_called_once()


# ── the two-step flow over the real HTTP stack ───────────────────────────────


def test_two_step_cancel_over_http():
    """Query, then cancel: the id survives the body model and the auth layer."""
    from fastapi.testclient import TestClient

    from homepot.app.api.API_v1.Endpoints import AIEndpoint
    from homepot.app.main import app
    from homepot.app.utils import ai_cancel

    mock_llm, mock_knowledge, mock_memory = _build_mocks()
    audit = _audit_stub()
    user = {"email": "cancel@test.local", "role": "Admin", "user_id": 4242}

    def authorize() -> dict:
        """Stand in for the auth dependency on both AI routes."""
        return user

    def install_auth_override() -> None:
        """Route auth through ``authorize`` (same trick as the context tests)."""
        found = False
        for route in app.routes:
            if getattr(route, "path", None) not in (
                "/api/v1/ai/query",
                "/api/v1/ai/query/cancel",
            ):
                continue
            for dependency in route.dependant.dependencies:
                if getattr(dependency.call, "__name__", "") == "user_checker":
                    app.dependency_overrides[dependency.call] = authorize
                    found = True
        assert found, "AI query routes (or their auth) were not found"

    with (
        patch.object(
            AIEndpoint,
            "get_ai_services",
            return_value=_services(mock_llm, mock_knowledge, mock_memory),
        ),
        patch.object(AIEndpoint, "get_doc_retriever", return_value=_mock_retriever()),
        patch.object(AIEndpoint, "get_audit_logger", return_value=audit),
    ):
        install_auth_override()
        # Not a context manager: the query path needs no app startup (no warm-up).
        client = TestClient(app)
        try:
            # Unknown id: nothing in flight to cancel.
            assert client.post(
                "/api/v1/ai/query/cancel", json={"query_id": "q-unknown"}
            ).json() == {"cancelled": False}

            # A live query is flagged through the route the widget calls.
            token = ai_cancel.register_query("q-live", user["user_id"])
            try:
                assert client.post(
                    "/api/v1/ai/query/cancel", json={"query_id": "q-live"}
                ).json() == {"cancelled": True}
            finally:
                ai_cancel.release_query(token)
            assert token.cancelled is True

            # The query itself accepts a query_id (body model + wrapper wiring).
            response = client.post(
                "/api/v1/ai/query",
                json={
                    "query": "How do I enroll a device?",
                    "mode": "knowledge",
                    "query_id": "q-http",
                },
            )
        finally:
            app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "cancelled" not in response.json()
    # Released when the query finished, so a late Stop cannot flag it again.
    assert ai_cancel.cancel_query("q-http", user["user_id"]) is False


# ── the registry itself ──────────────────────────────────────────────────────


def test_registry_is_bounded_and_releases_cleanly():
    """A client that never cancels cannot grow the registry without limit."""
    from homepot.app.utils import ai_cancel

    tokens = [
        ai_cancel.register_query(f"q-bound-{i}", USER["user_id"])
        for i in range(ai_cancel._MAX_TRACKED_QUERIES + 5)
    ]
    try:
        assert len(ai_cancel._tokens) <= ai_cancel._MAX_TRACKED_QUERIES
        # Eviction is oldest-first, so the most recent query is still live.
        newest = tokens[-1]
        assert ai_cancel.cancel_query(newest.query_id, USER["user_id"]) is True
    finally:
        for token in tokens:
            ai_cancel.release_query(token)

    assert ai_cancel._tokens == {}

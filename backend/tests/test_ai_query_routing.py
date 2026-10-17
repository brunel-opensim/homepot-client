"""Tests for AI query intent routing (docs/ai-query-routing.md).

Covers the deterministic, LLM-free router (``ai/query_router.py``) and the two
endpoint paths:

- a ``knowledge`` query answers from documentation without touching the gates,
  insights or device scans, and reports an informational (non-gate) trust;
- a ``diagnostic`` query keeps today's operational, gate-backed behaviour.
"""

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

current_dir = os.path.dirname(os.path.abspath(__file__))
workspace_root = os.path.abspath(os.path.join(current_dir, "../../"))
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)

from ai.context_builder import ContextBuilder  # noqa: E402
from ai.query_router import (  # noqa: E402
    MODE_AUTO,
    MODE_DIAGNOSTIC,
    MODE_KNOWLEDGE,
    resolve_query_mode,
    routing_enabled,
)

# ── Router: classification ───────────────────────────────────────────────────


@pytest.mark.parametrize(
    "query",
    [
        "How do I enroll a device?",
        "What does root_access allow?",
        "Which command restarts an agent?",
        "Explain device credentials and tokens",
        "where can I find the documentation?",
        "meaning of lifecycle epoch",
    ],
)
def test_router_classifies_knowledge(query):
    """How-to / definition phrasings resolve to the knowledge path."""
    assert resolve_query_mode(query, enabled=True).resolved == MODE_KNOWLEDGE


@pytest.mark.parametrize(
    "query",
    [
        "Why is device X offline?",
        "Any anomalies at Site B today?",
        "Show stale devices.",
        "What is the system status?",
        "Is the fleet healthy right now?",
        "hello there",
    ],
)
def test_router_classifies_diagnostic(query):
    """Operational / ambiguous phrasings resolve conservatively to diagnostic."""
    assert resolve_query_mode(query, enabled=True).resolved == MODE_DIAGNOSTIC


def test_router_action_signal_routes_diagnostic():
    """An imperative capability verb follows the operational (agentic) path."""
    decision = resolve_query_mode("restart device C-1 for me", enabled=True)
    assert decision.resolved == MODE_DIAGNOSTIC
    assert "action" in decision.reason


def test_router_device_id_forces_diagnostic():
    """A concrete device scope means the user is asking about that device."""
    decision = resolve_query_mode("How do I use this?", device_id="dev-1", enabled=True)
    assert decision.resolved == MODE_DIAGNOSTIC
    assert "device_id" in decision.reason


def test_router_operational_vocab_beats_knowledge_interrogative():
    """'what is' questions about live state stay diagnostic."""
    decision = resolve_query_mode("What is the status of site B?", enabled=True)
    assert decision.resolved == MODE_DIAGNOSTIC
    assert "operational" in decision.reason


def test_router_override_beats_heuristics():
    """An explicit mode wins regardless of the query text."""
    assert (
        resolve_query_mode(
            "restart device C-1", requested=MODE_KNOWLEDGE, enabled=True
        ).resolved
        == MODE_KNOWLEDGE
    )
    assert (
        resolve_query_mode(
            "how do I enroll a device", requested=MODE_DIAGNOSTIC, enabled=True
        ).resolved
        == MODE_DIAGNOSTIC
    )


def test_router_disabled_falls_back_to_diagnostic():
    """With routing off, even a how-to question takes the diagnostic path."""
    decision = resolve_query_mode("How do I enroll a device?", enabled=False)
    assert decision.resolved == MODE_DIAGNOSTIC
    assert "disabled" in decision.reason


def test_router_invalid_requested_mode_is_treated_as_auto():
    """An unknown mode string is treated as 'auto', not echoed as resolved."""
    decision = resolve_query_mode("How do I enroll a device?", requested="bogus")
    assert decision.requested == MODE_AUTO
    assert decision.resolved == MODE_KNOWLEDGE


# ── Router: flag ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize("raw", ["heuristics", "on", "1", "true", "AUTO", ""])
def test_routing_enabled_for_non_off_values(raw):
    """Any non-off value of AI_QUERY_ROUTING keeps routing enabled."""
    assert routing_enabled(raw) is True


@pytest.mark.parametrize("raw", ["off", "OFF", "0", "false", "no", "disabled", "none"])
def test_routing_disabled_for_off_values(raw):
    """Off-values of AI_QUERY_ROUTING disable heuristic routing."""
    assert routing_enabled(raw) is False


# ── Endpoint: knowledge path ─────────────────────────────────────────────────


def _services(mock_llm, mock_knowledge, mock_memory):
    """Return the singleton tuple in the order expected by get_ai_services."""
    return (mock_llm, mock_knowledge, mock_memory)


def _build_mocks():
    """Build minimal service mocks for routing tests."""
    mock_llm = MagicMock()
    mock_llm.generate_response.return_value = "To enroll a device, ..."
    mock_knowledge = MagicMock()
    mock_knowledge.get_knowledge_prompt.return_value = "KNOWLEDGE PROMPT"
    mock_knowledge.get_system_prompt.return_value = "DIAGNOSTIC PROMPT"
    mock_memory = MagicMock()
    mock_memory.get_memory_stats.return_value = {"total_memories": 0}
    mock_memory.query_similar.return_value = []
    return mock_llm, mock_knowledge, mock_memory


def _mock_retriever(chunks=None):
    """Return a stand-in DocRetriever so tests never index the real corpus."""
    retriever = MagicMock()
    retriever.retrieve.return_value = (
        [
            {
                "content": "# Enrolment workflow\nCreate a site, issue a key.",
                "source": "docs/device-registration.md",
                "heading": "Enrolment workflow",
                "distance": 0.2,
            }
        ]
        if chunks is None
        else chunks
    )
    return retriever


@pytest.mark.asyncio
async def test_knowledge_query_skips_gates_and_returns_informational_trust():
    """A knowledge query must not build/run the gates or device context."""
    from homepot.app.api.API_v1.Endpoints import AIEndpoint

    mock_llm, mock_knowledge, mock_memory = _build_mocks()
    build_envelope = MagicMock()
    enriched = AsyncMock(return_value="[ENRICHED]")

    with (
        patch.object(
            AIEndpoint,
            "get_ai_services",
            return_value=_services(mock_llm, mock_knowledge, mock_memory),
        ),
        patch.object(AIEndpoint, "get_doc_retriever", return_value=_mock_retriever()),
        patch.object(AIEndpoint, "build_envelope_from_config", build_envelope),
        patch.object(ContextBuilder, "build_enriched_context", enriched),
    ):
        request = AIEndpoint.AIQueryRequest(
            query="How do I enroll a device?", role="Admin"
        )
        current_user = {"email": "admin@test", "role": "Admin", "user_id": 1}
        response = await AIEndpoint.query_ai(request, current_user)

    assert response["routing"]["requested"] == MODE_AUTO
    assert response["routing"]["resolved"] == MODE_KNOWLEDGE
    assert response["trust"]["trust_mode"] == "informational"
    assert response["trust"]["actionable"] is False
    assert response["trust"]["trust_score"] is None
    assert response["trust"]["failed_gate"] is None
    assert response["response"] == "To enroll a device, ..."

    # No gates, no enriched diagnostic context, no operational blocks.
    build_envelope.assert_not_called()
    enriched.assert_not_called()

    mock_knowledge.get_knowledge_prompt.assert_called_once()
    mock_knowledge.get_system_prompt.assert_not_called()
    call_kwargs = mock_llm.generate_response.call_args.kwargs
    assert call_kwargs["system_prompt"] == "KNOWLEDGE PROMPT"
    assert "VALIDATION TRUST STATUS" not in call_kwargs["context"]
    assert "[CURRENT SYSTEM STATUS]" not in call_kwargs["context"]

    # Tier C grounding: retrieved docs are injected and surfaced as sources.
    assert "[RELEVANT DOCUMENTATION]" in call_kwargs["context"]
    assert "docs/device-registration.md" in call_kwargs["context"]
    assert response["sources"] == ["docs/device-registration.md"]
    # The fixed five-doc fallback must not run when retrieval hit.
    mock_knowledge.get_documentation_context.assert_not_called()


@pytest.mark.asyncio
async def test_knowledge_query_no_proposal_even_if_agentic_requested():
    """The knowledge path is direct-only, so it can never emit a proposal."""
    from homepot.app.api.API_v1.Endpoints import AIEndpoint

    mock_llm, mock_knowledge, mock_memory = _build_mocks()

    with (
        patch.object(
            AIEndpoint,
            "get_ai_services",
            return_value=_services(mock_llm, mock_knowledge, mock_memory),
        ),
        patch.object(AIEndpoint, "get_doc_retriever", return_value=_mock_retriever()),
        patch.object(AIEndpoint, "run_agent", new=AsyncMock()) as run_agent,
    ):
        request = AIEndpoint.AIQueryRequest(
            query="What does root_access allow?", agentic=True
        )
        current_user = {"email": "admin@test", "role": "Admin", "user_id": 1}
        response = await AIEndpoint.query_ai(request, current_user)

    assert response["routing"]["resolved"] == MODE_KNOWLEDGE
    assert "proposal" not in response
    run_agent.assert_not_awaited()


# ── Endpoint: diagnostic path (unchanged) ────────────────────────────────────


@pytest.mark.asyncio
async def test_forced_diagnostic_query_uses_operational_path():
    """Overriding a how-to query to diagnostic keeps the gate-backed path."""
    from homepot.app.api.API_v1.Endpoints import AIEndpoint

    mock_llm, mock_knowledge, mock_memory = _build_mocks()

    with patch.object(
        AIEndpoint,
        "get_ai_services",
        return_value=_services(mock_llm, mock_knowledge, mock_memory),
    ):
        request = AIEndpoint.AIQueryRequest(
            query="How do I enroll a device?", mode=MODE_DIAGNOSTIC
        )
        current_user = {"email": "admin@test", "role": "Admin", "user_id": 1}
        response = await AIEndpoint.query_ai(request, current_user)

    assert response["routing"]["requested"] == MODE_DIAGNOSTIC
    assert response["routing"]["resolved"] == MODE_DIAGNOSTIC
    # The operational path reports a gate trust mode, never 'informational'.
    assert response["trust"]["trust_mode"] != "informational"
    mock_knowledge.get_system_prompt.assert_called_once()
    mock_knowledge.get_knowledge_prompt.assert_not_called()
    call_kwargs = mock_llm.generate_response.call_args.kwargs
    assert "[VALIDATION TRUST STATUS]" in call_kwargs["context"]


@pytest.mark.asyncio
async def test_operational_query_defaults_to_diagnostic():
    """A live-state question resolves to diagnostic without an override."""
    from homepot.app.api.API_v1.Endpoints import AIEndpoint

    mock_llm, mock_knowledge, mock_memory = _build_mocks()

    with patch.object(
        AIEndpoint,
        "get_ai_services",
        return_value=_services(mock_llm, mock_knowledge, mock_memory),
    ):
        request = AIEndpoint.AIQueryRequest(query="What is the system status?")
        current_user = {"email": "admin@test", "role": "Admin", "user_id": 1}
        response = await AIEndpoint.query_ai(request, current_user)

    assert response["routing"]["requested"] == MODE_AUTO
    assert response["routing"]["resolved"] == MODE_DIAGNOSTIC
    mock_knowledge.get_system_prompt.assert_called_once()
    mock_knowledge.get_knowledge_prompt.assert_not_called()

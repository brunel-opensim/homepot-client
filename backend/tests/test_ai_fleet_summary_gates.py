"""Tests for the reduced gate path used by fleet-summary answers."""

from contextlib import ExitStack
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

current_dir = os.path.dirname(os.path.abspath(__file__))
workspace_root = os.path.abspath(os.path.join(current_dir, "../../"))
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)

from ai.context_builder import ContextBuilder  # noqa: E402
from ai.gates import (  # noqa: E402
    MODE_GROUNDED,
    DataIntegrityGate,
    EnvelopeResult,
    GateResult,
    GateStatus,
    build_default_envelope,
    build_fleet_summary_envelope,
)
from ai.gates.base import GateContext  # noqa: E402
from ai.query_router import MODE_DIAGNOSTIC, MODE_FLEET_SUMMARY  # noqa: E402


def test_connectivity_check_observes_zero_online_when_not_required():
    """Fleet summaries record zero-online as evidence, not a gate failure."""
    gate = DataIntegrityGate(connectivity_required=False)
    result = gate._connectivity_check(None, None, [], 3)

    assert result.passed is True
    assert "0 online device(s)" in result.message
    assert result.evidence[0].extra == {"online_count": 0, "offline_count": 3}


def test_connectivity_check_still_fails_zero_online_by_default():
    """The canonical gate keeps its fail-closed fleet connectivity rule."""
    gate = DataIntegrityGate()
    result = gate._connectivity_check(None, None, [], 3)

    assert result.passed is False
    assert "No online devices" in result.message


@pytest.mark.asyncio
async def test_gate_b_can_skip_all_telemetry_checks():
    """telemetry_checks=False evaluates connectivity only."""
    gate = DataIntegrityGate(telemetry_checks=False, connectivity_required=False)
    context = GateContext(session=MagicMock(), assembled_context="ctx")

    with patch.object(
        gate,
        "_online_scope",
        new=AsyncMock(return_value=([], None, 3)),
    ):
        result = await gate.evaluate(context)

    assert result.status == GateStatus.PASS
    assert [check.check_id for check in result.checks] == ["B.connectivity"]
    assert result.checks[0].passed is True


def test_fleet_summary_envelope_uses_reduced_gate_chain():
    """Only Gate A, connectivity-only Gate B and Gate C are configured."""
    envelope = build_fleet_summary_envelope()

    assert [gate.gate_id for gate in envelope.gates] == ["A", "B", "C"]
    gate_b = envelope.gates[1]
    assert isinstance(gate_b, DataIntegrityGate)
    assert gate_b.telemetry_checks is False
    assert gate_b.connectivity_required is False


def test_default_envelope_still_uses_full_gate_chain():
    """The canonical envelope is unchanged."""
    envelope = build_default_envelope()
    assert [gate.gate_id for gate in envelope.gates] == ["A", "B", "C", "D", "E"]
    gate_b = envelope.gates[1]
    assert isinstance(gate_b, DataIntegrityGate)
    assert gate_b.telemetry_checks is True
    assert gate_b.connectivity_required is True


def _services():
    """Return minimal AI service mocks for endpoint tests."""
    llm = MagicMock()
    llm.generate_response.return_value = "There are 3 active devices, 0 online."
    knowledge = MagicMock()
    knowledge.get_knowledge_prompt.return_value = "KNOWLEDGE PROMPT"
    knowledge.get_system_prompt.return_value = "DIAGNOSTIC PROMPT"
    memory = MagicMock()
    memory.get_memory_stats.return_value = {"total_memories": 0}
    memory.query_similar.return_value = []
    return llm, knowledge, memory


class _FakeSessionContext:
    """Minimal async context manager yielding a fake DB session."""

    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, tb):
        return None


class _FakeDbService:
    """Minimal database service returning the fake session context."""

    def __init__(self, session):
        self.session = session

    def get_session(self):
        return _FakeSessionContext(self.session)


def _nonzero_fleet_patches(AIEndpoint, ContextBuilder):
    """Patch endpoint DB access so the zero-fleet refusal does not trigger."""
    site = MagicMock(id=1, name="Site A", site_id="SITE-A", location="Lab")
    device = MagicMock(
        id=1,
        name="Device 1",
        device_id="DEV-1",
        device_type="sensor",
        health_state="healthy",
        site_id=1,
    )

    def _result(rows):
        result = MagicMock()
        result.scalars.return_value.all.return_value = rows
        return result

    session = MagicMock()
    session.execute = AsyncMock(
        side_effect=[_result([site]), _result([device]), _result([])]
    )
    return [
        patch.object(
            AIEndpoint,
            "get_database_service",
            new=AsyncMock(return_value=_FakeDbService(session)),
        ),
        patch.object(AIEndpoint, "_device_is_online", return_value=True),
        patch.object(AIEndpoint, "_device_mode", return_value="real"),
        patch.object(
            ContextBuilder, "build_enriched_context", new=AsyncMock(return_value="")
        ),
        patch.object(
            ContextBuilder, "get_push_context", new=AsyncMock(return_value="")
        ),
        patch.object(ContextBuilder, "get_job_context", new=AsyncMock(return_value="")),
    ]


def _fake_envelope():
    """Return a reduced-envelope stand-in with a passing post-insight Gate C."""
    gate_c = MagicMock()
    gate_c.gate_id = "C"
    gate_c.run = AsyncMock(
        return_value=GateResult(
            gate_id="C", name="Context Readiness", status=GateStatus.PASS, checks=[]
        )
    )
    envelope = MagicMock()
    envelope.gates = [gate_c]
    envelope.run = AsyncMock(
        return_value=EnvelopeResult(
            gate_results=[],
            trust_mode=MODE_GROUNDED,
            trust_score=1.0,
            failed_gate_id=None,
        )
    )
    return envelope


@pytest.mark.asyncio
async def test_fleet_summary_endpoint_uses_reduced_path_and_no_proposals():
    """Fleet summaries skip telemetry insights and all proposal tools."""
    from homepot.app.api.API_v1.Endpoints import AIEndpoint

    llm, knowledge, memory = _services()
    fleet_envelope = _fake_envelope()
    full_envelope = MagicMock()
    anomalies = AsyncMock(return_value={"anomalies": []})
    predictor = MagicMock()
    run_agent = AsyncMock()

    with ExitStack() as stack:
        for patcher in _nonzero_fleet_patches(AIEndpoint, ContextBuilder):
            stack.enter_context(patcher)
        stack.enter_context(
            patch.object(
                AIEndpoint,
                "get_ai_services",
                return_value=(llm, knowledge, memory),
            )
        )
        build_fleet = stack.enter_context(
            patch.object(
                AIEndpoint,
                "build_fleet_summary_envelope_from_config",
                return_value=fleet_envelope,
            )
        )
        build_full = stack.enter_context(
            patch.object(
                AIEndpoint,
                "build_envelope_from_config",
                return_value=full_envelope,
            )
        )
        stack.enter_context(patch.object(AIEndpoint, "get_system_anomalies", anomalies))
        stack.enter_context(patch.object(AIEndpoint, "FailurePredictor", predictor))
        stack.enter_context(patch.object(AIEndpoint, "run_agent", run_agent))

        request = AIEndpoint.AIQueryRequest(
            query="How many active devices are online?",
            mode=MODE_FLEET_SUMMARY,
            agentic=True,
        )
        response = await AIEndpoint.query_ai(
            request, {"email": "admin@test", "role": "Admin", "user_id": 1}
        )

    assert response["routing"]["resolved"] == MODE_FLEET_SUMMARY
    assert response["trust"]["trust_mode"] == MODE_GROUNDED.id
    build_fleet.assert_called_once()
    build_full.assert_not_called()
    anomalies.assert_not_awaited()
    predictor.assert_not_called()
    run_agent.assert_not_awaited()
    assert "proposal" not in response


@pytest.mark.asyncio
async def test_diagnostic_endpoint_still_uses_full_envelope():
    """Explicit diagnostic queries keep the canonical gate chain."""
    from homepot.app.api.API_v1.Endpoints import AIEndpoint

    llm, knowledge, memory = _services()
    fleet_envelope = _fake_envelope()
    full_envelope = _fake_envelope()

    with ExitStack() as stack:
        for patcher in _nonzero_fleet_patches(AIEndpoint, ContextBuilder):
            stack.enter_context(patcher)
        stack.enter_context(
            patch.object(
                AIEndpoint,
                "get_ai_services",
                return_value=(llm, knowledge, memory),
            )
        )
        build_fleet = stack.enter_context(
            patch.object(
                AIEndpoint,
                "build_fleet_summary_envelope_from_config",
                return_value=fleet_envelope,
            )
        )
        build_full = stack.enter_context(
            patch.object(
                AIEndpoint,
                "build_envelope_from_config",
                return_value=full_envelope,
            )
        )

        request = AIEndpoint.AIQueryRequest(
            query="What is the system status?", mode=MODE_DIAGNOSTIC
        )
        await AIEndpoint.query_ai(
            request, {"email": "admin@test", "role": "Admin", "user_id": 1}
        )

    build_full.assert_called_once()
    build_fleet.assert_not_called()

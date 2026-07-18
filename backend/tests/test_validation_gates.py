"""Tests for the validation-first gate framework (ai/gates).

Covers:
- ``ValidationEnvelope`` sequencing, trust scoring, fail-closed behavior and
  extensibility using lightweight fake gates (no DB needed).
- ``ContractInfrastructureGate`` (Gate A) and ``DataIntegrityGate`` (Gate B)
  against a real (SQLite, in-memory) async session.
- ``ContextReadinessGate`` (Gate C) against assembled-context strings.
- ``build_default_envelope`` wiring.
"""

from datetime import datetime, timedelta
import os
import secrets
import sys

import pytest

# Add the workspace root to sys.path so we can import 'ai' as a package,
# matching the pattern used by the other ai/* test modules in this suite.
current_dir = os.path.dirname(os.path.abspath(__file__))
workspace_root = os.path.abspath(os.path.join(current_dir, "../../"))
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)

from ai.gates import (  # noqa: E402
    MODE_BEST_EFFORT,
    MODE_GROUNDED,
    MODE_STATUS_ONLY,
    CheckResult,
    ContextReadinessGate,
    ContractInfrastructureGate,
    DataIntegrityGate,
    EnvelopeResult,
    Gate,
    GateContext,
    GateResult,
    GateStatus,
    ValidationEnvelope,
    build_default_envelope,
)


class _FakeGate(Gate):
    """Minimal Gate stub for exercising ValidationEnvelope logic in isolation."""

    def __init__(self, gate_id, status, failure_mode, score=None):
        super().__init__(
            gate_id=gate_id, name=f"Fake Gate {gate_id}", failure_mode=failure_mode
        )
        self._status = status
        self._score = score

    async def evaluate(self, context: GateContext) -> GateResult:
        checks = []
        if self._score is not None:
            n_pass = round(self._score * 4)
            checks = [
                CheckResult(f"{self.gate_id}.c{i}", f"check {i}", i < n_pass, "stub")
                for i in range(4)
            ]
        return GateResult(
            gate_id=self.gate_id, name=self.name, status=self._status, checks=checks
        )


class _ExplodingGate(Gate):
    """Gate whose evaluate() always raises, to test fail-closed handling."""

    def __init__(self):
        super().__init__(
            gate_id="X", name="Exploding Gate", failure_mode=MODE_STATUS_ONLY
        )

    async def evaluate(self, context):
        raise RuntimeError("boom")


# --------------------------------------------------------------------------
# ValidationEnvelope: sequencing, trust scoring, extensibility
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_envelope_all_pass_is_grounded():
    """Test that an envelope where every gate passes reports Grounded/actionable."""
    envelope = ValidationEnvelope(
        [
            _FakeGate("A", GateStatus.PASS, MODE_STATUS_ONLY),
            _FakeGate("B", GateStatus.PASS, MODE_BEST_EFFORT),
        ]
    )
    result = await envelope.run(GateContext())

    assert result.trust_mode is MODE_GROUNDED
    assert result.is_actionable
    assert result.trust_score == 1.0
    assert result.passed_gate_ids == ["A", "B"]
    assert result.failed_gate_id is None


@pytest.mark.asyncio
async def test_envelope_stops_at_first_failure():
    """Test that the envelope short-circuits at the first failing gate."""
    envelope = ValidationEnvelope(
        [
            _FakeGate("A", GateStatus.PASS, MODE_STATUS_ONLY),
            _FakeGate("B", GateStatus.FAIL, MODE_BEST_EFFORT, score=0.5),
            _FakeGate("C", GateStatus.PASS, MODE_STATUS_ONLY),  # must not run
        ]
    )
    result = await envelope.run(GateContext())

    assert result.trust_mode is MODE_BEST_EFFORT
    assert not result.is_actionable
    assert result.failed_gate_id == "B"
    assert result.passed_gate_ids == ["A"]
    # Gate C was short-circuited: only A and B were evaluated.
    assert [g.gate_id for g in result.gate_results] == ["A", "B"]
    # Trust score is bounded by Mode 2's ceiling even though partial credit
    # for B's sub-checks would otherwise push it higher.
    assert result.trust_score == MODE_BEST_EFFORT.trust_ceiling


@pytest.mark.asyncio
async def test_envelope_fail_closed_on_exception():
    """Test that a gate raising an exception is treated as a fail-closed failure."""
    envelope = ValidationEnvelope([_ExplodingGate()])
    result = await envelope.run(GateContext())

    assert result.trust_mode is MODE_STATUS_ONLY
    assert not result.is_actionable
    assert result.gate_results[0].status == GateStatus.FAIL
    assert result.gate_results[0].error == "boom"


def test_envelope_is_extensible_with_add_gate():
    """Test that a new gate can be appended to the envelope via add_gate."""
    envelope = ValidationEnvelope([_FakeGate("A", GateStatus.PASS, MODE_STATUS_ONLY)])
    envelope.add_gate(_FakeGate("D", GateStatus.PASS, MODE_BEST_EFFORT))

    assert [g.gate_id for g in envelope.gates] == ["A", "D"]


def test_envelope_result_trace_and_label():
    """Test EnvelopeResult.trace() and .label() produce technician-readable output."""
    gate_result = GateResult(
        gate_id="B",
        name="Data Integrity",
        status=GateStatus.FAIL,
        checks=[CheckResult("B.freshness", "Freshness", False, "stale")],
    )
    env_result = EnvelopeResult(
        gate_results=[gate_result],
        trust_mode=MODE_BEST_EFFORT,
        trust_score=0.4,
        failed_gate_id="B",
    )

    assert "Mode 2" in env_result.label()
    trace = env_result.trace()
    assert trace[0]["gate_id"] == "B"
    assert trace[0]["check_id"] == "B.freshness"
    assert trace[0]["passed"] is False


def test_build_default_envelope_order():
    """Test that build_default_envelope wires Gate A, B, C in order."""
    envelope = build_default_envelope()
    assert [g.gate_id for g in envelope.gates] == ["A", "B", "C"]


# --------------------------------------------------------------------------
# Gate C: pure string/regex checks, no DB required
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gate_c_passes_with_stable_blocks_and_known_ids():
    """Test that Gate C passes when required blocks are present and IDs are known."""
    gate = ContextReadinessGate()
    context = GateContext(
        assembled_context="[CURRENT SYSTEM STATUS]\nAlert ID: #1\n",
        known_alert_ids=[1, 2],
    )
    result = await gate.run(context)

    assert result.status == GateStatus.PASS


@pytest.mark.asyncio
async def test_gate_c_detects_missing_blocks_and_fabricated_ids():
    """Test that Gate C fails on missing content blocks and fabricated alert IDs."""
    gate = ContextReadinessGate()
    context = GateContext(
        assembled_context="No status block here. Alert #99 is critical.",
        known_alert_ids=[1, 2],
    )
    result = await gate.run(context)

    assert result.status == GateStatus.FAIL
    failed_ids = {c.check_id for c in result.checks if not c.passed}
    assert "C.stable_content_blocks" in failed_ids
    assert "C.id_rules" in failed_ids


@pytest.mark.asyncio
async def test_gate_c_bounded_context():
    """Test that Gate C fails when assembled context exceeds the size bound."""
    gate = ContextReadinessGate(max_context_chars=10)
    context = GateContext(assembled_context="[CURRENT SYSTEM STATUS]\n" + "x" * 50)
    result = await gate.run(context)

    assert result.status == GateStatus.FAIL
    assert any(
        c.check_id == "C.bounded_context" and not c.passed for c in result.checks
    )


@pytest.mark.asyncio
async def test_gate_c_fails_without_assembled_context():
    """Test that Gate C fails when no assembled context is supplied."""
    gate = ContextReadinessGate()
    result = await gate.run(GateContext(assembled_context=None))

    assert result.status == GateStatus.FAIL


# --------------------------------------------------------------------------
# Gates A & B: real (SQLite in-memory) async DB session
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gate_a_passes_against_live_schema():
    """Test that Gate A passes against a live, schema-conformant DB session."""
    from homepot.database import get_database_service

    db_service = await get_database_service()
    async with db_service.get_session() as session:
        result = await ContractInfrastructureGate().run(GateContext(session=session))

    assert result.status == GateStatus.PASS, [c.to_dict() for c in result.checks]


@pytest.mark.asyncio
async def test_gate_a_fails_without_session():
    """Test that Gate A fails closed when no DB session is supplied."""
    result = await ContractInfrastructureGate().run(GateContext(session=None))

    assert result.status == GateStatus.FAIL
    assert result.checks[0].check_id == "A.session"


@pytest.mark.asyncio
async def test_gate_b_fails_when_no_telemetry_present():
    """Test that Gate B fails when there is no telemetry in the lookback window."""
    from homepot.database import get_database_service

    db_service = await get_database_service()
    async with db_service.get_session() as session:
        result = await DataIntegrityGate().run(
            GateContext(session=session, window_seconds=3600)
        )

    assert result.status == GateStatus.FAIL
    check_ids = {c.check_id for c in result.checks}
    assert "B.completeness" in check_ids
    assert "B.freshness" in check_ids


@pytest.mark.asyncio
async def test_gate_b_passes_with_fresh_complete_data():
    """Test that Gate B passes when telemetry is fresh, complete, and valid."""
    from homepot.app.auth_utils import hash_password
    from homepot.app.models.AnalyticsModel import DeviceMetrics
    from homepot.database import get_database_service
    from homepot.models import HealthCheck

    db_service = await get_database_service()

    site = await db_service.create_site(
        site_id="gates-test-site",
        name="Gates Test Site",
        description="Test site for Gate B",
        location="Test Location",
        latitude=0.0,
        longitude=0.0,
    )
    device = await db_service.create_device(
        device_id="gates-test-device",
        name="Gates Test Device",
        device_type="POS",
        site_id=site.id,
        ip_address="10.0.0.1",
        api_key_hash=hash_password(secrets.token_urlsafe(16)),
    )

    now = datetime.utcnow()
    async with db_service.get_session() as session:
        for i in range(5):
            ts = now - timedelta(seconds=i * 10)
            session.add(
                DeviceMetrics(
                    timestamp=ts,
                    device_id=device.id,
                    cpu_percent=50.0,
                    memory_percent=40.0,
                    disk_percent=30.0,
                    network_latency_ms=15.0,
                )
            )
            session.add(
                HealthCheck(
                    id=i + 1, timestamp=ts, device_id=device.id, is_healthy=True
                )
            )
        await session.commit()

    async with db_service.get_session() as session:
        result = await DataIntegrityGate().run(
            GateContext(session=session, device_int_id=device.id, window_seconds=3600)
        )

    assert result.status == GateStatus.PASS, [c.to_dict() for c in result.checks]


@pytest.mark.asyncio
async def test_query_ai_always_calls_llm_even_when_not_actionable():
    """The /query endpoint must always call the LLM and return a trust envelope.

    Gates condition the instructions/labelling given to the LLM and
    technician, they no longer short-circuit inference outright.
    """
    from unittest.mock import MagicMock, patch

    from homepot.app.api.API_v1.Endpoints import AIEndpoint

    mock_llm = MagicMock()
    mock_llm.generate_response.return_value = "Some response"
    mock_knowledge = MagicMock()
    mock_knowledge.get_full_system_context.return_value = "system knowledge"
    mock_memory = MagicMock()
    mock_memory.get_memory_stats.return_value = {"total_memories": 0}
    mock_memory.query_similar.return_value = []

    non_actionable_result = EnvelopeResult(
        gate_results=[
            GateResult(
                gate_id="A",
                name="Contract and Infrastructure",
                status=GateStatus.FAIL,
                checks=[],
            )
        ],
        trust_mode=MODE_STATUS_ONLY,
        trust_score=0.0,
        failed_gate_id="A",
    )

    class _StubEnvelope:
        async def run(self, context):
            return non_actionable_result

    with patch.object(
        AIEndpoint,
        "get_ai_services",
        return_value=(mock_llm, mock_knowledge, mock_memory),
    ), patch.object(AIEndpoint, "build_default_envelope", return_value=_StubEnvelope()):
        request = AIEndpoint.AIQueryRequest(query="What is the status?")
        response = await AIEndpoint.query_ai(request)

    assert mock_llm.generate_response.called
    call_kwargs = mock_llm.generate_response.call_args.kwargs
    assert "[VALIDATION TRUST STATUS]" in call_kwargs["context"]
    assert "Actionable: no" in call_kwargs["context"]
    # Gate A failed, so Gate B never ran -- AI insights must be withheld
    # rather than computed from data that hasn't passed integrity checks.
    assert "[AI INSIGHTS]" in call_kwargs["context"]
    assert "Skipped: Gate B (data integrity) did not pass" in call_kwargs["context"]
    assert "[AI INSIGHTS: SYSTEM ANOMALIES]" not in call_kwargs["context"]
    assert response["response"] == "Some response"
    assert response["trust"]["actionable"] is False
    assert response["trust"]["failed_gate"] == "A"


@pytest.mark.asyncio
async def test_query_ai_includes_insights_when_gate_b_passes():
    """AI insights must be included in the LLM context once Gate B passes.

    This is the counterpart to the "withheld on failure" behavior above.
    """
    from unittest.mock import AsyncMock, MagicMock, patch

    from homepot.app.api.API_v1.Endpoints import AIEndpoint

    mock_llm = MagicMock()
    mock_llm.generate_response.return_value = "Some response"
    mock_knowledge = MagicMock()
    mock_knowledge.get_full_system_context.return_value = "system knowledge"
    mock_memory = MagicMock()
    mock_memory.get_memory_stats.return_value = {"total_memories": 0}
    mock_memory.query_similar.return_value = []

    actionable_result = EnvelopeResult(
        gate_results=[
            GateResult(
                gate_id="A",
                name="Contract and Infrastructure",
                status=GateStatus.PASS,
                checks=[],
            ),
            GateResult(
                gate_id="B",
                name="Data Integrity Assurance",
                status=GateStatus.PASS,
                checks=[],
            ),
            GateResult(
                gate_id="C", name="Context Readiness", status=GateStatus.PASS, checks=[]
            ),
        ],
        trust_mode=MODE_GROUNDED,
        trust_score=1.0,
        failed_gate_id=None,
    )

    class _StubEnvelope:
        gates = [ContextReadinessGate()]

        async def run(self, context):
            return actionable_result

    with patch.object(
        AIEndpoint,
        "get_ai_services",
        return_value=(mock_llm, mock_knowledge, mock_memory),
    ), patch.object(
        AIEndpoint, "build_default_envelope", return_value=_StubEnvelope()
    ), patch.object(
        AIEndpoint,
        "get_system_anomalies",
        new=AsyncMock(return_value={"anomalies": []}),
    ):
        request = AIEndpoint.AIQueryRequest(query="What is the status?")
        response = await AIEndpoint.query_ai(request)

    assert mock_llm.generate_response.called
    call_kwargs = mock_llm.generate_response.call_args.kwargs
    assert "[AI INSIGHTS: SYSTEM ANOMALIES]" in call_kwargs["context"]
    assert "No active anomalies detected." in call_kwargs["context"]
    assert "[AI INSIGHTS]\nSkipped" not in call_kwargs["context"]
    assert response["trust"]["actionable"] is True


@pytest.mark.asyncio
async def test_query_ai_downgrades_trust_when_post_insight_gate_c_fails():
    """Post-insight Gate C re-validation must downgrade trust if it fails.

    If appending AI Insights pushes the final context past Gate C's
    bounded-context threshold (or otherwise breaks context readiness), the
    post-insight re-validation must downgrade the trust envelope to
    non-actionable rather than reporting the earlier, pre-insight PASS.
    """
    from unittest.mock import AsyncMock, MagicMock, patch

    from homepot.app.api.API_v1.Endpoints import AIEndpoint

    mock_llm = MagicMock()
    mock_llm.generate_response.return_value = "Some response"
    mock_knowledge = MagicMock()
    mock_knowledge.get_full_system_context.return_value = "system knowledge"
    mock_memory = MagicMock()
    mock_memory.get_memory_stats.return_value = {"total_memories": 0}
    mock_memory.query_similar.return_value = []

    actionable_result = EnvelopeResult(
        gate_results=[
            GateResult(
                gate_id="A",
                name="Contract and Infrastructure",
                status=GateStatus.PASS,
                checks=[],
            ),
            GateResult(
                gate_id="B",
                name="Data Integrity Assurance",
                status=GateStatus.PASS,
                checks=[],
            ),
            GateResult(
                gate_id="C", name="Context Readiness", status=GateStatus.PASS, checks=[]
            ),
        ],
        trust_mode=MODE_GROUNDED,
        trust_score=1.0,
        failed_gate_id=None,
    )

    class _StubEnvelope:
        # An unreasonably small max_context_chars guarantees the final
        # (post-insight) context fails Gate C's bounded_context check.
        gates = [ContextReadinessGate(max_context_chars=10)]

        async def run(self, context):
            return actionable_result

    with patch.object(
        AIEndpoint,
        "get_ai_services",
        return_value=(mock_llm, mock_knowledge, mock_memory),
    ), patch.object(
        AIEndpoint, "build_default_envelope", return_value=_StubEnvelope()
    ), patch.object(
        AIEndpoint,
        "get_system_anomalies",
        new=AsyncMock(return_value={"anomalies": []}),
    ):
        request = AIEndpoint.AIQueryRequest(query="What is the status?")
        response = await AIEndpoint.query_ai(request)

    assert mock_llm.generate_response.called
    call_kwargs = mock_llm.generate_response.call_args.kwargs
    assert "Actionable: no" in call_kwargs["context"]
    assert "Failed gate: C (post-insight)" in call_kwargs["context"]
    assert response["trust"]["actionable"] is False
    assert response["trust"]["failed_gate"] == "C (post-insight)"
    # Original A/B/C results plus the post-insight re-check must all remain traceable.
    assert len(response["trust"]["gates"]) == 4


@pytest.mark.asyncio
async def test_gate_b_fails_on_stale_and_invalid_readings():
    """Test that Gate B fails on stale timestamps and out-of-range readings."""
    from homepot.app.auth_utils import hash_password
    from homepot.app.models.AnalyticsModel import DeviceMetrics
    from homepot.database import get_database_service
    from homepot.models import HealthCheck

    db_service = await get_database_service()

    site = await db_service.create_site(
        site_id="gates-test-site-stale",
        name="Gates Test Site Stale",
        description="Test site for stale Gate B data",
        location="Test Location",
        latitude=0.0,
        longitude=0.0,
    )
    device = await db_service.create_device(
        device_id="gates-test-device-stale",
        name="Gates Test Device Stale",
        device_type="POS",
        site_id=site.id,
        ip_address="10.0.0.2",
        api_key_hash=hash_password(secrets.token_urlsafe(16)),
    )

    # Stale (well past the default 300s freshness threshold) and out-of-range
    # readings so both freshness and validity checks fail.
    stale_ts = datetime.utcnow() - timedelta(hours=2)
    async with db_service.get_session() as session:
        session.add(
            DeviceMetrics(
                timestamp=stale_ts,
                device_id=device.id,
                cpu_percent=150.0,  # invalid: > 100
                memory_percent=40.0,
                disk_percent=30.0,
                network_latency_ms=15.0,
            )
        )
        session.add(
            HealthCheck(id=1, timestamp=stale_ts, device_id=device.id, is_healthy=True)
        )
        await session.commit()

    async with db_service.get_session() as session:
        result = await DataIntegrityGate().run(
            GateContext(
                session=session,
                device_int_id=device.id,
                window_seconds=24 * 3600,
            )
        )

    assert result.status == GateStatus.FAIL
    failed_ids = {c.check_id for c in result.checks if not c.passed}
    assert "B.freshness" in failed_ids
    assert "B.validity" in failed_ids

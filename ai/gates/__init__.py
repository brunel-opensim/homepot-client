"""Validation-first gated architecture for trustworthy AI recommendations.

Implements the gated structure introduced in our ICCS2026 paper
"Trustworthy Data Foundations for AI-Driven Analytics in Distributed IoT: A
Validation-First Methodology" (Fig. 2): telemetry must pass an extensible
chain of quality gates -- starting with Gate A (Contract and Infrastructure),
Gate B (Data Integrity), and Gate C (Context Readiness) -- before AI/LLM
inference is treated as fully trusted (Mode: Grounded LLM Interface).

Failing any gate resolves to a named, non-actionable Mode with a bounded
trust score (Mode 1: Status-only / Mode 2: Best-effort / Mode 3: Cautionary),
and every check carries traceable evidence back to the source table, record,
and threshold that produced it.

Typical usage::

    from ai.gates import build_default_envelope, GateContext

    envelope = build_default_envelope()
    result = await envelope.run(GateContext(session=session, assembled_context=full_context))
    if result.is_actionable:
        ...  # call the LLM normally
    else:
        ...  # fall back to result.trust_mode's constrained behaviour

New gates can be appended without modifying Gate A/B/C::

    envelope.add_gate(MyProvenanceGate())
"""

from .base import (
    MODE_BEST_EFFORT,
    MODE_CAUTIONARY,
    MODE_GROUNDED,
    MODE_STATUS_ONLY,
    CheckResult,
    EvidenceRef,
    Gate,
    GateContext,
    GateResult,
    GateStatus,
    Mode,
)
from .config import build_envelope_from_config
from .envelope import EnvelopeResult, ValidationEnvelope, build_default_envelope
from .gate_a import ContractInfrastructureGate
from .gate_b import DataIntegrityGate
from .gate_c import ContextReadinessGate
from .gate_d import MODE_PERMISSION_GAP, PermissionCapabilityGate
from .gate_e import MODE_LIFECYCLE_HALT, LifecycleIntegrityGate

__all__ = [
    "CheckResult",
    "EvidenceRef",
    "Gate",
    "GateContext",
    "GateResult",
    "GateStatus",
    "Mode",
    "MODE_BEST_EFFORT",
    "MODE_CAUTIONARY",
    "MODE_GROUNDED",
    "MODE_STATUS_ONLY",
    "MODE_PERMISSION_GAP",
    "MODE_LIFECYCLE_HALT",
    "EnvelopeResult",
    "ValidationEnvelope",
    "build_default_envelope",
    "build_envelope_from_config",
    "ContractInfrastructureGate",
    "DataIntegrityGate",
    "ContextReadinessGate",
    "PermissionCapabilityGate",
    "LifecycleIntegrityGate",
]

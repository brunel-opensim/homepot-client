"""Ordered, extensible chain of validation gates (the "validation envelope" of Fig. 2).

``ValidationEnvelope`` runs its gates in sequence and stops at the first
failure, matching the paper's control-flow diagram: the first gate to FAIL
determines the resulting non-actionable Mode, and gates after it are not
evaluated. New gates (e.g. a future cybersecurity/provenance Gate D) can be
appended via ``add_gate`` without touching Gate A/B/C.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .base import MODE_GROUNDED, Gate, GateContext, GateResult, GateStatus, Mode


@dataclass
class EnvelopeResult:
    """Result of running a ValidationEnvelope: gate outcomes + derived trust."""

    gate_results: List[GateResult]
    trust_mode: Mode
    trust_score: float
    failed_gate_id: Optional[str]

    @property
    def is_actionable(self) -> bool:
        """Whether the resulting trust mode permits actionable AI recommendations."""
        return self.trust_mode.actionable

    @property
    def passed_gate_ids(self) -> List[str]:
        """Gate ids that passed, in evaluation order (duplicates possible)."""
        return [g.gate_id for g in self.gate_results if g.status == GateStatus.PASS]

    def label(self) -> str:
        """Human-readable summary suitable for a UI trust badge.

        e.g. "Passed Gate A -- Mode 1: Status-only" or
        "Passed all gates (A, B, C) -- Grounded LLM Interface".
        """
        if self.is_actionable:
            gate_ids = ", ".join(g.gate_id for g in self.gate_results)
            return f"Passed all gates ({gate_ids}) \u2014 {self.trust_mode.label}"
        passed = ", ".join(self.passed_gate_ids) or "none"
        return f"Passed Gate(s) {passed} \u2014 {self.trust_mode.label}"

    def trace(self) -> List[Dict[str, Any]]:
        """Flattened, traceable list of every check + evidence across evaluated gates.

        This is what lets a technician backtrack a trust label/finding to the
        specific table/record/threshold that produced it.
        """
        rows: List[Dict[str, Any]] = []
        for gate in self.gate_results:
            for check in gate.checks:
                base_row = {
                    "gate_id": gate.gate_id,
                    "gate_name": gate.name,
                    "check_id": check.check_id,
                    "check_name": check.name,
                    "passed": check.passed,
                    "message": check.message,
                }
                if not check.evidence:
                    rows.append(base_row)
                    continue
                for ev in check.evidence:
                    rows.append({**base_row, **ev.to_dict()})
        return rows

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the envelope result -- trust mode/score plus every gate's outcome."""
        return {
            "trust_mode": self.trust_mode.id,
            "trust_mode_label": self.trust_mode.label,
            "trust_score": round(self.trust_score, 3),
            "actionable": self.is_actionable,
            "passed_gates": self.passed_gate_ids,
            "failed_gate": self.failed_gate_id,
            "gates": [g.to_dict() for g in self.gate_results],
            "summary": self.label(),
        }


class ValidationEnvelope:
    """Runs an ordered, extensible sequence of gates (Gate A -> B -> C -> ...)."""

    def __init__(self, gates: Optional[List[Gate]] = None):
        """Build an envelope from an optional initial ordered list of gates."""
        self._gates: List[Gate] = list(gates or [])

    def add_gate(self, gate: Gate) -> "ValidationEnvelope":
        """Append a new gate (e.g. a future Gate D) to the end of the chain."""
        self._gates.append(gate)
        return self

    @property
    def gates(self) -> List[Gate]:
        """The current ordered list of gates in this envelope (defensive copy)."""
        return list(self._gates)

    async def run(self, context: GateContext) -> EnvelopeResult:
        """Run all gates in order, stopping at the first failure, and derive overall trust."""
        total_weight = sum(g.weight for g in self._gates) or 1.0
        achieved = 0.0
        gate_results: List[GateResult] = []
        trust_mode: Mode = MODE_GROUNDED
        failed_gate_id: Optional[str] = None

        for gate in self._gates:
            result = await gate.run(context)
            gate_results.append(result)

            if result.status == GateStatus.PASS:
                achieved += gate.weight
                continue

            # Failure: partial credit for the sub-checks that did pass within
            # this gate, then stop -- subsequent gates are not evaluated.
            #
            # TUNABLE: `gate.weight * result.score` is a placeholder scoring
            # model (not yet empirically calibrated -- paper Sec. 6). Two
            # independent knobs are available for later testing/adjustment:
            #   1. Per-gate ``weight`` (see ``Gate.__init__`` in base.py,
            #      default 1.0 for every gate) -- controls how much each
            #      gate contributes to the overall score.
            #   2. Each ``Mode.trust_ceiling`` (see base.py) -- caps the
            #      final score regardless of partial credit.
            achieved += gate.weight * result.score
            trust_mode = gate.failure_mode
            failed_gate_id = gate.gate_id
            break

        raw_score = max(0.0, min(1.0, achieved / total_weight))
        # TUNABLE: see the comment above -- `trust_mode.trust_ceiling` is the
        # hard cap for any non-actionable mode.
        trust_score = (
            raw_score
            if trust_mode.actionable
            else min(raw_score, trust_mode.trust_ceiling)
        )

        return EnvelopeResult(
            gate_results=gate_results,
            trust_mode=trust_mode,
            trust_score=trust_score,
            failed_gate_id=failed_gate_id,
        )


def build_default_envelope(**overrides: Any) -> ValidationEnvelope:
    """Build the paper's canonical Gate A -> B -> C envelope (Fig. 2).

    Additional gates can be appended afterwards via ``envelope.add_gate(...)``,
    e.g. a future cybersecurity/provenance Gate D (see paper Sec. 7).
    """
    from .gate_a import ContractInfrastructureGate
    from .gate_b import DataIntegrityGate
    from .gate_c import ContextReadinessGate

    gate_b_kwargs = {
        k: v
        for k, v in overrides.items()
        if k
        in (
            "freshness_max_age_seconds",
            "continuity_gap_seconds",
            "sustained_gap_seconds",
        )
    }
    gate_c_kwargs = {
        k: v
        for k, v in overrides.items()
        if k in ("required_blocks", "max_context_chars")
    }

    return ValidationEnvelope(
        [
            ContractInfrastructureGate(),
            DataIntegrityGate(**gate_b_kwargs),
            ContextReadinessGate(**gate_c_kwargs),
        ]
    )

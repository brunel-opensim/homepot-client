"""Core types for the validation-first gate framework (ICCS2026 paper, Fig. 2).

Telemetry passes through a sequential chain of quality gates (Gate A -> Gate B
-> Gate C -> ...) before AI/LLM inference is permitted. Each gate evaluates a
set of checks and produces a PASS/FAIL outcome that feeds into the next gate;
failing a gate short-circuits the chain into a named, non-actionable "mode"
with a bounded trust score instead of allowing unrestricted narrative
generation.

The framework is intentionally open-ended: new gates can be appended to a
``ValidationEnvelope`` (see ``envelope.py``) without changing this module, and
each gate defines its own fallback ``Mode`` so a future Gate D can introduce
its own mode without touching Gate A/B/C code. Every ``CheckResult`` carries
``EvidenceRef`` entries so a technician can trace a trust label back to the
specific table/record/threshold that produced it.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from dataclasses import field as dc_field
from datetime import datetime, timezone
from enum import Enum
import time
from typing import Any, Dict, List, Optional, Sequence


class GateStatus(str, Enum):
    """Pass/fail outcome of a gate."""

    PASS = "pass"  # noqa: S105 -- enum value, not a credential
    FAIL = "fail"


@dataclass(frozen=True)
class Mode:
    """A named operating mode a gate falls back to when it fails (Fig. 2).

    ``trust_ceiling`` bounds the reported trust score while operating in this
    mode, so e.g. Mode 1 (failed at the very first gate) can never be
    reported as more trustworthy than Mode 2/3 or a full pass.
    """

    id: str
    label: str
    description: str
    actionable: bool = False
    trust_ceiling: float = 0.0


# ---------------------------------------------------------------------------
# TUNABLE: the ``trust_ceiling`` values below (0.0 / 0.5 / 0.75 / 1.0) are an
# initial, paper-informed default -- they are NOT yet empirically calibrated
# against real deployment/testing data (paper Sec. 6). They are the ONLY
# numbers that bound the reported ``trust_score`` while in a given mode; see
# ``ValidationEnvelope.run()`` in envelope.py for how a ceiling combines with
# each gate's partial-check score to produce the final score. Adjust the
# ``trust_ceiling=`` values on the Mode instances directly below once
# calibration data is available -- no other code needs to change.
# ---------------------------------------------------------------------------

# Canonical modes from the paper (Fig. 2). Gates for future extensions (e.g. a
# cybersecurity/provenance Gate D) may define their own Mode instances instead
# of reusing these.
MODE_STATUS_ONLY = Mode(
    id="mode_1",
    label="Mode 1: Status-only",
    description=(
        "No AI actions. Raw/observed status may be reported, but no "
        "LLM-generated narrative or recommendation is permitted."
    ),
    actionable=False,
    trust_ceiling=0.0,
)
MODE_BEST_EFFORT = Mode(
    id="mode_2",
    label="Mode 2: Best-effort analytics",
    description=(
        "LLM analysis is permitted but explicitly marked as limited-trust / "
        "not audit-ready due to data integrity gaps."
    ),
    actionable=False,
    trust_ceiling=0.5,
)
MODE_CAUTIONARY = Mode(
    id="mode_3",
    label="Mode 3: Cautionary summaries",
    description=(
        "Context could not be assembled deterministically; only "
        "non-actionable, uncertainty-qualified summaries are permitted."
    ),
    actionable=False,
    trust_ceiling=0.75,
)
MODE_GROUNDED = Mode(
    id="grounded",
    label="Grounded LLM Interface",
    description=(
        "All configured gates passed. Full grounded AI inference and "
        "recommendations are permitted."
    ),
    actionable=True,
    trust_ceiling=1.0,
)


@dataclass
class EvidenceRef:
    """A traceable pointer back to the source data behind a check outcome.

    Populated by gate checks so a technician can jump from a trust label or
    finding directly to the underlying record(s) that caused it, rather than
    trusting an opaque pass/fail summary.
    """

    table: Optional[str] = None
    field: Optional[str] = None
    device_id: Optional[str] = None
    record_id: Optional[Any] = None
    observed: Optional[Any] = None
    threshold: Optional[Any] = None
    query_id: Optional[str] = None  # mirrors the paper's reproducibility queries Q1-Q8
    extra: Dict[str, Any] = dc_field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-friendly dict, dropping unset (None) fields."""
        d: Dict[str, Any] = {
            "table": self.table,
            "field": self.field,
            "device_id": self.device_id,
            "record_id": self.record_id,
            "observed": self.observed,
            "threshold": self.threshold,
            "query_id": self.query_id,
        }
        d.update(self.extra)
        return {k: v for k, v in d.items() if v is not None}


@dataclass
class CheckResult:
    """Outcome of a single sub-check within a gate (e.g. Gate B's "freshness")."""

    check_id: str
    name: str
    passed: bool
    message: str
    evidence: List[EvidenceRef] = dc_field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-friendly dict, including nested evidence refs."""
        return {
            "check_id": self.check_id,
            "name": self.name,
            "passed": self.passed,
            "message": self.message,
            "evidence": [e.to_dict() for e in self.evidence],
        }


@dataclass
class GateResult:
    """Outcome of a full gate: PASS/FAIL plus its constituent CheckResults."""

    gate_id: str
    name: str
    status: GateStatus
    checks: List[CheckResult]
    evaluated_at: datetime = dc_field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    duration_ms: float = 0.0
    error: Optional[str] = None

    @property
    def score(self) -> float:
        """Fraction of sub-checks that passed (0.0-1.0); drives partial trust credit."""
        if not self.checks:
            return 1.0 if self.status == GateStatus.PASS else 0.0
        passed = sum(1 for c in self.checks if c.passed)
        return passed / len(self.checks)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-friendly dict, including all constituent checks."""
        return {
            "gate_id": self.gate_id,
            "name": self.name,
            "status": self.status.value,
            "score": round(self.score, 3),
            "checks": [c.to_dict() for c in self.checks],
            "evaluated_at": self.evaluated_at.isoformat(),
            "duration_ms": round(self.duration_ms, 2),
            "error": self.error,
        }


@dataclass
class GateContext:
    """Inputs available to gates during evaluation.

    Gate-specific inputs that don't warrant a first-class field can be passed
    via ``extra`` without changing this class, keeping the framework open for
    new gates.
    """

    session: Optional[Any] = (
        None  # AsyncSession; kept as Any to avoid a heavy import here
    )
    device_id: Optional[str] = None
    device_int_id: Optional[int] = None
    assembled_context: Optional[str] = None
    known_alert_ids: Optional[Sequence[Any]] = None
    window_seconds: int = 24 * 3600
    extra: Dict[str, Any] = dc_field(default_factory=dict)


class Gate(ABC):
    """Base class for a single validation gate in the envelope."""

    def __init__(
        self, gate_id: str, name: str, failure_mode: Mode, weight: float = 1.0
    ):
        """Configure a gate's identity, its failure fallback mode, and scoring weight."""
        self.gate_id = gate_id
        self.name = name
        self.failure_mode = failure_mode
        self.weight = weight

    @abstractmethod
    async def evaluate(self, context: GateContext) -> GateResult:
        """Run all sub-checks for this gate and return a GateResult."""
        raise NotImplementedError

    async def run(self, context: GateContext) -> GateResult:
        """Wrap ``evaluate`` with timing and fail-closed error handling.

        If a gate implementation raises, the gate is treated as FAILED rather
        than silently allowing inference to proceed on an unverified state.
        """
        start = time.monotonic()
        try:
            result = await self.evaluate(context)
        except Exception as exc:  # fail-closed: any evaluation error counts as FAIL
            result = GateResult(
                gate_id=self.gate_id,
                name=self.name,
                status=GateStatus.FAIL,
                checks=[],
                error=str(exc),
            )
        result.duration_ms = (time.monotonic() - start) * 1000
        return result

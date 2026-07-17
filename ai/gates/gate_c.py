"""Gate C: Context Readiness for LLM Ingestion (paper Sec. 4.3, Table 1).

Validates that the assembled prompt context is deterministic, ID-bound, and
bounded before it is handed to the LLM. Even when the underlying telemetry is
fresh and complete (Gates A and B passed), grounding can still fail if the
context is assembled without a stable structure or references non-existent
identifiers. Failing Gate C falls back to Mode 3 (cautionary summaries,
non-actionable) -- see ``base.MODE_CAUTIONARY``.

TUNABLE: ``DEFAULT_REQUIRED_BLOCKS`` and ``DEFAULT_MAX_CONTEXT_CHARS`` below
are initial defaults, not yet validated against real deployment data.
Override per-call via ``ContextReadinessGate(required_blocks=...,
max_context_chars=...)`` / ``build_default_envelope(required_blocks=...,
max_context_chars=...)``.
"""

from __future__ import annotations

import re
from typing import Iterable, List, Optional

from .base import (
    MODE_CAUTIONARY,
    CheckResult,
    EvidenceRef,
    Gate,
    GateContext,
    GateResult,
    GateStatus,
)

DEFAULT_REQUIRED_BLOCKS = ["[CURRENT SYSTEM STATUS]"]
DEFAULT_MAX_CONTEXT_CHARS = 16000  # ~4k tokens at a 4-chars/token heuristic
ALERT_ID_PATTERN = re.compile(r"#(\d+)")


class ContextReadinessGate(Gate):
    """Gate C: stable content blocks, ID rules, bounded context (Fig. 2)."""

    def __init__(
        self,
        required_blocks: Optional[List[str]] = None,
        max_context_chars: int = DEFAULT_MAX_CONTEXT_CHARS,
    ) -> None:
        """Configure Gate C's required content blocks, size bound, and failure fallback."""
        super().__init__(
            gate_id="C", name="Context Readiness", failure_mode=MODE_CAUTIONARY
        )
        self.required_blocks = required_blocks or DEFAULT_REQUIRED_BLOCKS
        self.max_context_chars = max_context_chars

    async def evaluate(self, context: GateContext) -> GateResult:
        """Check stable content blocks, alert ID references, and bounded context size."""
        text = context.assembled_context
        if text is None:
            return GateResult(
                gate_id=self.gate_id,
                name=self.name,
                status=GateStatus.FAIL,
                checks=[
                    CheckResult(
                        check_id="C.context",
                        name="Assembled context available",
                        passed=False,
                        message="No assembled context was supplied to Gate C.",
                    )
                ],
            )

        checks = [
            self._check_stable_blocks(text),
            self._check_id_rules(text, context.known_alert_ids),
            self._check_bounded_context(text),
        ]
        status = GateStatus.PASS if all(c.passed for c in checks) else GateStatus.FAIL
        return GateResult(
            gate_id=self.gate_id, name=self.name, status=status, checks=checks
        )

    def _check_stable_blocks(self, text: str) -> CheckResult:
        missing = [b for b in self.required_blocks if b not in text]
        passed = not missing
        return CheckResult(
            check_id="C.stable_content_blocks",
            name="Stable content blocks",
            passed=passed,
            message=(
                "All required section headers present."
                if passed
                else f"Missing required blocks: {missing}"
            ),
            evidence=(
                []
                if passed
                else [
                    EvidenceRef(
                        query_id="C.stable_content_blocks",
                        extra={"missing_blocks": missing},
                    )
                ]
            ),
        )

    def _check_id_rules(self, text: str, known_ids: Optional[Iterable]) -> CheckResult:
        if known_ids is None:
            return CheckResult(
                check_id="C.id_rules",
                name="ID rules",
                passed=True,
                message="No known-ID allowlist supplied; ID cross-check skipped.",
            )
        known = {str(i) for i in known_ids}
        referenced = set(ALERT_ID_PATTERN.findall(text))
        fabricated = sorted(referenced - known)
        passed = not fabricated
        return CheckResult(
            check_id="C.id_rules",
            name="ID rules",
            passed=passed,
            message=(
                "All referenced alert IDs exist in the current status block."
                if passed
                else f"Unresolvable/fabricated alert IDs referenced: {fabricated}"
            ),
            evidence=(
                []
                if passed
                else [
                    EvidenceRef(
                        query_id="C.id_rules",
                        extra={"fabricated_ids": fabricated},
                    )
                ]
            ),
        )

    def _check_bounded_context(self, text: str) -> CheckResult:
        size = len(text)
        passed = size <= self.max_context_chars
        return CheckResult(
            check_id="C.bounded_context",
            name="Bounded context",
            passed=passed,
            message=f"Assembled context is {size} chars (limit {self.max_context_chars}).",
            evidence=[
                EvidenceRef(
                    observed=size,
                    threshold=self.max_context_chars,
                    query_id="C.bounded_context",
                )
            ],
        )

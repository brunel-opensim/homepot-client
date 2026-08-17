"""Load validation-gate thresholds from ``ai/config.yaml``.

This module is the bridge between the runtime envelope and the single
configuration file ``ai/config.yaml`` (section ``validation_gates``). The
in-code ``DEFAULT_*`` constants in ``gate_b.py`` / ``gate_c.py`` remain as
fallbacks when a key is missing from the file, mirroring how
``anomaly_detection.py`` reads its thresholds. Values in ``config.yaml`` are
authoritative -- change thresholds there, not in code.
"""

from pathlib import Path
from typing import Any, Dict

import yaml

from .gate_b import (
    DEFAULT_COMPLETENESS_MAX_NULL_RATIO,
    DEFAULT_CONTINUITY_GAP_SECONDS,
    DEFAULT_FRESHNESS_MAX_AGE_SECONDS,
    DEFAULT_SUSTAINED_GAP_SECONDS,
)
from .gate_c import DEFAULT_MAX_CONTEXT_CHARS, DEFAULT_REQUIRED_BLOCKS

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"


def _load_gates_section() -> Dict[str, Any]:
    """Return the ``validation_gates`` dict from config.yaml (empty on error)."""
    try:
        with open(CONFIG_PATH, "r") as f:
            data = yaml.safe_load(f) or {}
        return data.get("validation_gates", {}) or {}
    except (OSError, yaml.YAMLError):
        return {}


def gate_b_kwargs() -> Dict[str, Any]:
    """Resolve Gate B thresholds, falling back to the code defaults."""
    section = _load_gates_section().get("gate_b", {}) or {}
    return {
        "freshness_max_age_seconds": section.get(
            "freshness_max_age_seconds", DEFAULT_FRESHNESS_MAX_AGE_SECONDS
        ),
        "continuity_gap_seconds": section.get(
            "continuity_gap_seconds", DEFAULT_CONTINUITY_GAP_SECONDS
        ),
        "sustained_gap_seconds": section.get(
            "sustained_gap_seconds", DEFAULT_SUSTAINED_GAP_SECONDS
        ),
        "completeness_max_null_ratio": section.get(
            "completeness_max_null_ratio", DEFAULT_COMPLETENESS_MAX_NULL_RATIO
        ),
    }


def gate_c_kwargs() -> Dict[str, Any]:
    """Resolve Gate C settings, falling back to the code defaults."""
    section = _load_gates_section().get("gate_c", {}) or {}
    return {
        "required_blocks": section.get("required_blocks", DEFAULT_REQUIRED_BLOCKS),
        "max_context_chars": section.get(
            "max_context_chars", DEFAULT_MAX_CONTEXT_CHARS
        ),
    }


def build_envelope_from_config() -> Any:
    """Build the canonical envelope configured from ``ai/config.yaml``.

    Returns a ``ValidationEnvelope`` with Gate B/C thresholds resolved from the
    config file. Imported lazily to avoid a circular import with ``envelope.py``.
    """
    from .envelope import build_default_envelope

    kwargs = {**gate_b_kwargs(), **gate_c_kwargs()}
    return build_default_envelope(**kwargs)

"""Shared loader for the AI configuration file ``ai/config.yaml``.

Single source for reading ``ai/config.yaml`` across the AI package. Modules
that consume a section of the file (validation gates, anomaly detection, LLM,
memory, ...) call :func:`load_ai_config` and pull their keys from the returned
dict, falling back to their own module-level defaults when a key is missing.
The file is read once per call; on a missing/unreadable/malformed file an
empty dict is returned so callers can degrade gracefully to defaults.
"""

from pathlib import Path
from typing import Any, Dict

import yaml

CONFIG_PATH = Path(__file__).resolve().parent / "config.yaml"


def load_ai_config() -> Dict[str, Any]:
    """Read ``ai/config.yaml`` and return its mapping (``{}`` on any error)."""
    try:
        with open(CONFIG_PATH, "r") as f:
            data = yaml.safe_load(f)
        return data or {}
    except (OSError, yaml.YAMLError):
        return {}

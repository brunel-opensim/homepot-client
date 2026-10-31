"""Runtime LLM provider selection.

Stores the active provider preference in a small JSON file so it can be
changed at runtime without editing config.yaml. Falls back to the config
file's ``llm.provider`` when no preference file exists.

Usage:
    from ai.provider import get_provider, set_provider
    current = get_provider()  # "ollama", "openai", or "anthropic"
    set_provider("openai")    # switch to OpenAI
"""

import json
import logging
import os

logger = logging.getLogger(__name__)

# Where the runtime preference is stored. Relative to the ai/ package.
_PROVIDER_FILE = os.path.join(os.path.dirname(__file__), "provider.json")
_VALID_PROVIDERS = {"ollama", "openai", "anthropic"}


def get_provider() -> str:
    """Return the currently selected LLM provider name."""
    try:
        if os.path.exists(_PROVIDER_FILE):
            with open(_PROVIDER_FILE, "r") as f:
                data = json.load(f)
            provider = str(data.get("provider", "")).lower()
            if provider in _VALID_PROVIDERS:
                return provider
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to read provider preference: %s", e)
    # Fall back to config.yaml
    try:
        import yaml

        config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
        return str(config.get("llm", {}).get("provider", "ollama")).lower()
    except Exception:
        return "ollama"


def set_provider(provider: str) -> bool:
    """Set the active LLM provider. Returns True on success."""
    provider = provider.lower()
    if provider not in _VALID_PROVIDERS:
        return False
    try:
        with open(_PROVIDER_FILE, "w") as f:
            json.dump({"provider": provider}, f)
        logger.info("LLM provider switched to: %s", provider)
        return True
    except OSError as e:
        logger.error("Failed to write provider preference: %s", e)
        return False


def get_provider_info() -> dict:
    """Return provider info including available providers and their status."""
    current = get_provider()
    available = []
    for p in ["ollama", "openai", "anthropic"]:
        available.append({"name": p, "active": p == current})
    return {"current": current, "available": available}

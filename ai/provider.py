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
from typing import Optional

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
        data = {}
        if os.path.exists(_PROVIDER_FILE):
            with open(_PROVIDER_FILE, "r") as f:
                data = json.load(f)
        data["provider"] = provider
        with open(_PROVIDER_FILE, "w") as f:
            json.dump(data, f)
        logger.info("LLM provider switched to: %s", provider)
        return True
    except OSError as e:
        logger.error("Failed to write provider preference: %s", e)
        return False


def get_api_key(provider: str) -> Optional[str]:
    """Get the API key for a provider from env or provider.json."""
    import os

    ext_config = {}
    try:
        config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
        with open(config_path, "r") as f:
            import yaml

            config = yaml.safe_load(f)
            ext_config = config.get("llm", {}).get("external", {}).get(provider, {})
    except Exception:
        pass

    env_var = ext_config.get("api_key_env", "")
    if env_var:
        key = os.environ.get(env_var)
        if key:
            return key

    # Fall back to .env.local file (for dev environments where demouser
    # cannot write to .env)
    try:
        for candidate in [
            ".env.local",
            "backend/.env.local",
            "/var/www/homepot.cabera.com/backend/.env.local",
        ]:
            if os.path.exists(candidate):
                with open(candidate, "r") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            if k.strip() == env_var and v.strip():
                                return v.strip()
    except OSError:
        pass

    # Fall back to provider.json
    try:
        if os.path.exists(_PROVIDER_FILE):
            with open(_PROVIDER_FILE, "r") as f:
                data = json.load(f)
            keys = data.get("api_keys", {})
            if provider in keys:
                return str(keys[provider])
    except (json.JSONDecodeError, OSError):
        pass
    return None


def set_api_key(provider: str, api_key: str) -> bool:
    """Store an API key for a provider in provider.json."""
    try:
        data = {}
        if os.path.exists(_PROVIDER_FILE):
            with open(_PROVIDER_FILE, "r") as f:
                data = json.load(f)
        data.setdefault("api_keys", {})[provider] = api_key
        with open(_PROVIDER_FILE, "w") as f:
            json.dump(data, f)
        return True
    except OSError:
        return False


def get_provider_info() -> dict:
    """Return provider info including available providers and their status."""
    current = get_provider()
    available = []
    for p in ["ollama", "openai", "anthropic"]:
        entry = {"name": p, "active": p == current}
        if p in ("openai", "anthropic"):
            entry["has_api_key"] = bool(get_api_key(p))
        available.append(entry)
    return {"current": current, "available": available}

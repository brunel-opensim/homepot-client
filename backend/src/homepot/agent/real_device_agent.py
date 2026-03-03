"""Real device agent integration logic for Homepot."""

import json
from pathlib import Path
from typing import Any, Dict, cast


def load_agent_config() -> Dict[str, Any]:
    """Load the agent configuration."""
    config_path = Path(__file__).parent / "agent-config.json"

    with config_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    return cast(Dict[str, Any], data)


if __name__ == "__main__":
    config = load_agent_config()
    print("Agent started with config:", config)

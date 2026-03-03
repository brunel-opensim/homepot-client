"""Real device agent integration logic for Homepot."""

import json
from pathlib import Path
from typing import Any, Dict


def load_agent_config() -> Dict[str, Any]:
    """Load the agent configuration from the JSON file."""
    config_path = Path(__file__).parent / "agent-config.json"
    with config_path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    return cast(Dict[str, Any], data)


if __name__ == "__main__":
    config = load_agent_config()
    print("Agent started with config:", config)

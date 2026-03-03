"""Real device agent integration logic for Homepot."""
import json
from pathlib import Path

def load_agent_config():
    """Connect and initialize the real device agent."""
    config_path = Path(__file__).parent / "agent-config.json"
    with open(config_path, "r") as f:
        return json.load(f)


if __name__ == "__main__":
    config = load_agent_config()
    print("Agent started with config:", config)

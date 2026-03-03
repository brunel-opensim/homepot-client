import json
from pathlib import Path


def load_agent_config():
    config_path = Path(__file__).parent / "agent-config.json"
    with open(config_path, "r") as f:
        return json.load(f)


if __name__ == "__main__":
    config = load_agent_config()
    print("Agent started with config:", config)

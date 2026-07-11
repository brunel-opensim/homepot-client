#!/usr/bin/env python3
"""Run a True Lifecycle Emulator for an Android POS Terminal.

This script simulates the complete device lifecycle for an edge device (e.g. an Android POS):
1. Calls the auto-provisioning API (`POST /api/v1/devices/provision`).
2. Generates an `agent-config.json` identity locally based on the response.
3. Spawns the `real_device_agent.py` as a subprocess with `USE_HARDWARE_EMULATOR=true`.

This creates a high-fidelity system-installation bridging test specifically mapped
for the Dealdio User App / POS Tablet deployment flow.
"""

import argparse
import asyncio
import json
import logging
import os
import subprocess
import sys
from pathlib import Path

import httpx
from rich.console import Console

# Setup logging and rich console
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("LifecycleEmulator")
console = Console()

# Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
CONFIG_PATH = Path("agent-config.json")


async def provision_device(
    site_id: str, user_identity: str, device_name: str
) -> dict | None:
    """Fetch provisioning payload and mock an Android device setup wizard."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        # 1. Payload Definition: We strongly type this as an Android POS Terminal
        url = f"{API_BASE_URL}/api/v1/devices/provision"
        payload = {
            "sso_token": "mock_android_sso_token_123",
            "site_id": site_id,
            "user_identity": user_identity,
            "device_name": device_name,
            "device_type": "pos_terminal",
            "os_details": "Android 14 (API 34) Emulated",
        }
        console.print(f"[bold cyan]Provisioning Agent:[/bold cyan] {url}")
        console.print(f"[dim]Payload:[/dim] {payload}")

        try:
            # 2. Make the HTTP POST Request
            response = await client.post(url, json=payload)

            if response.status_code == 200:
                data = response.json()
                # Unpack the standard FastAPI response wrapper if it exists
                if "data" in data:
                    return data["data"]
                return data
            else:
                logger.error(
                    f"Provisioning Failed: HTTP {response.status_code} - {response.text}"
                )
                return None
        except httpx.RequestError as exc:
            logger.error(f"Network Error while requesting API: {exc}")
            return None


def write_agent_config(provision_data: dict) -> None:
    """Take API response credentials and write the local state for the agent script."""
    # Ensure keys map cleanly to what `real_device_agent.py` expects
    device_id = provision_data.get("device_id")
    api_key = provision_data.get("api_key")

    if not device_id or not api_key:
        logger.error("Missing critical 'device_id' or 'api_key' in provision data.")
        sys.exit(1)

    agent_config = {"device_id": device_id, "api_key": api_key}

    # Write to local state config file
    with open(CONFIG_PATH, "w") as config_file:
        json.dump(agent_config, config_file, indent=4)

    console.print(
        f"[bold green]Successfully wrote local identity to:[/bold green] {CONFIG_PATH.absolute()}"
    )


def spawn_real_agent_loop() -> None:
    """Start `real_device_agent.py` as a subprocess passing through emulator flag."""
    console.print(
        "[bold yellow]Spawning the Real Device Agent Telemetry Loop...[/bold yellow]"
    )

    # Use hardware emulator to force mock Zebra scanners / Epson printers
    # instead of doing actual USB polling on this local OS.
    env = os.environ.copy()
    env["USE_HARDWARE_EMULATOR"] = "true"
    env["API_BASE_URL"] = API_BASE_URL
    # Ensure we use python path pointing to our environment
    env["PYTHONPATH"] = str(Path(__file__).parent.parent.parent / "backend/src")

    # Command assumes running in repository root
    agent_script = Path("backend/src/homepot/agent/real_device_agent.py")

    if not agent_script.exists():
        logger.error(f"Could not locate agent script at: {agent_script.absolute()}")
        sys.exit(1)

    # Execute
    try:
        subprocess.run(
            [sys.executable, str(agent_script)],
            env=env,
            check=True,
        )
    except KeyboardInterrupt:
        console.print("[dim]Terminated True Lifecycle Emulator via Keyboard.[/dim]")


async def main():
    parser = argparse.ArgumentParser(
        description="HOMEPOT True Lifecycle Emulator (Android POS mock)"
    )
    parser.add_argument(
        "--site", type=str, default="site-dealdio-01", help="Site ID to register under"
    )
    parser.add_argument(
        "--email",
        type=str,
        default="setup@dealdio.com",
        help="SSO email user performing the tablet setup",
    )
    parser.add_argument(
        "--name",
        type=str,
        default="Emulated Front Register Tablet",
        help="Device display name",
    )
    args = parser.parse_args()

    # Step 1: Provision the device
    provision_data = await provision_device(args.site, args.email, args.name)

    if not provision_data:
        console.print("[bold red]Aborting Lifecycle. Provisioning step failed.[/bold red]")
        sys.exit(1)

    # Step 2: Persist state
    write_agent_config(provision_data)

    # Step 3: Run the real application loop inside fake parameters
    spawn_real_agent_loop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

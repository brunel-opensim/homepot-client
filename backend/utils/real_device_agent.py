"""Real Device Agent for HOMEPOT.

This script runs on a physical device (or WSL2 instance) to collect system metrics
and send them to the HOMEPOT backend. It bridges the gap between simulation and reality.
"""

import asyncio
import logging
import os
import socket
import time
from typing import Optional

import httpx
import psutil

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("RealDeviceAgent")

# Configuration
BASE_URL = "http://localhost:8000/api/v1"
SITE_ID = "site-001"  # Default site for this device
DEVICE_TYPE = "linux_server"
HOSTNAME = socket.gethostname()
DEVICE_ID = f"wsl-device-{HOSTNAME.lower().replace(' ', '-')}"
API_KEY_FILE = ".device_api_key"


async def register_device(client: httpx.AsyncClient) -> Optional[str]:
    """
    Get API Key for this device.

    NOTE: Auto-registration has been disabled to ensure seed_data.py is the single source of truth.
    This agent must be configured with an existing Device ID and API Key.
    """
    # Check environment variable first
    env_key = os.environ.get("HOMEPOT_DEVICE_API_KEY")
    if env_key:
        logger.info("Using API Key from environment variable HOMEPOT_DEVICE_API_KEY")
        return env_key

    # Check if we already have an API key
    if os.path.exists(API_KEY_FILE):
        with open(API_KEY_FILE, "r") as f:
            api_key = f.read().strip()
        if api_key:
            logger.info("Loaded existing API Key.")
            return api_key

    logger.error("No API Key found. Auto-registration is disabled.")
    logger.error(
        "Please configure HOMEPOT_DEVICE_API_KEY or .device_api_key with a valid key for a pre-seeded device."
    )
    return None


async def collect_and_send_metrics(client: httpx.AsyncClient, api_key: str):
    """Collect system metrics and send to backend."""
    headers = {"X-Device-ID": DEVICE_ID, "X-API-Key": api_key}

    while True:
        try:
            # Collect Metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage("/")
            net_io = psutil.net_io_counters()

            # Calculate network latency (simple ping to localhost or gateway)
            # For simplicity, we'll simulate latency or use a placeholder
            latency = 0.5  # Placeholder

            metrics_payload = {
                "device_id": DEVICE_ID,
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "disk_percent": disk.percent,
                "network_latency_ms": latency,
                "transaction_count": 0,  # Not applicable for a generic server
                "transaction_volume": 0.0,
                "error_rate": 0.0,
                "active_connections": len(psutil.net_connections()),
                "extra_metrics": {
                    "boot_time": psutil.boot_time(),
                    "bytes_sent": net_io.bytes_sent,
                    "bytes_recv": net_io.bytes_recv,
                },
            }

            # Send to Backend
            response = await client.post(
                f"{BASE_URL}/analytics/device-metrics",
                json=metrics_payload,
                headers=headers,
            )

            if response.status_code == 201:
                logger.info(f"Sent metrics: CPU={cpu_percent}%, RAM={memory.percent}%")
            elif response.status_code == 401:
                logger.error("Authentication failed. Invalid API Key.")
                break
            else:
                logger.warning(f"Failed to send metrics: {response.status_code}")

        except Exception as e:
            logger.error(f"Error collecting/sending metrics: {e}")

        # Wait before next collection
        await asyncio.sleep(5)


async def poll_commands(client: httpx.AsyncClient, api_key: str):
    """Poll for pending commands and execute them."""
    headers = {"X-Device-ID": DEVICE_ID, "X-API-Key": api_key}

    logger.info("Started command polling...")

    while True:
        try:
            response = await client.get(f"{BASE_URL}/devices/pending", headers=headers)

            if response.status_code == 200:
                commands = response.json()
                for cmd in commands:
                    logger.info(
                        f"Received command: {cmd['command_type']} (ID: {cmd['command_id']})"
                    )

                    # Execute Command
                    status = "completed"
                    result = {"message": "Executed successfully"}

                    if cmd["command_type"] == "ping":
                        result = {"pong": time.time()}
                    elif cmd["command_type"] == "restart":
                        logger.warning(
                            "Restart command received. Simulating restart..."
                        )
                        await asyncio.sleep(2)
                    else:
                        logger.warning(f"Unknown command type: {cmd['command_type']}")
                        status = "failed"
                        result = {"error": "Unknown command type"}

                    # Update Status
                    update_payload = {"status": status, "result": result}
                    await client.put(
                        f"{BASE_URL}/devices/{cmd['command_id']}/status",
                        json=update_payload,
                        headers=headers,
                    )
                    logger.info(f"Command {cmd['command_id']} marked as {status}")
            elif response.status_code == 401:
                logger.error("Auth failed during polling.")
                break

        except Exception as e:
            logger.error(f"Error polling commands: {e}")

        await asyncio.sleep(5)  # Poll every 5 seconds


async def main():
    """Main agent loop."""
    print("\n" + "=" * 60)
    print(f"Real Device Agent for {DEVICE_ID}")
    print("To stop the agent, press Ctrl+C in this terminal.")
    print("If running in background, use: pkill -f real_device_agent.py")
    print("=" * 60 + "\n")

    logger.info(f"Starting Real Device Agent for {DEVICE_ID}")

    async with httpx.AsyncClient() as client:
        # 1. Register Device
        api_key = await register_device(client)
        if not api_key:
            logger.error("Could not obtain API Key. Exiting.")
            return

        # 2. Start Tasks
        await asyncio.gather(
            collect_and_send_metrics(client, api_key), poll_commands(client, api_key)
        )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Agent stopped by user.")

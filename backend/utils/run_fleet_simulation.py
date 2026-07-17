"""Fleet Simulation Runner for HOMEPOT Client.

This script simulates hundreds or thousands of devices sending metrics
and Device DNA (including printer info) to the backend concurrently.
Useful for load testing PostgreSQL and the FastAPI endpoints.
"""

import asyncio
import logging
import random
import sys
from typing import List

import httpx

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Configurable simulation parameters
NUM_DEVICES = 100
API_BASE_URL = "http://localhost:8000"
SIMULATION_DURATION_SECONDS = 60
CONCURRENT_REQUESTS_LIMIT = 50

# Sample printer payload based on R&D specs
SAMPLE_PRINTERS = [
    [],  # No printer
    [
        {
            "name": "EPSON TM-T88VI",
            "manufacturer": "Epson",
            "model": "TM-T88VI",
            "connection_type": "USB",
            "driver_name": "EPSON Receipt Printer",
            "port": "USB001",
            "status": "online",
            "is_default": True,
        }
    ],
    [
        {
            "name": "HP LaserJet Pro",
            "manufacturer": "HP",
            "connection_type": "LAN",
            "status": "idle",
            "is_default": True,
        },
        {
            "name": "Zebra ZD410",
            "manufacturer": "Zebra",
            "connection_type": "USB",
            "status": "online",
            "is_default": False,
        },
    ],
]


async def setup_test_devices(device_ids: List[str], client: httpx.AsyncClient) -> None:
    """Ensure devices exist in the backend before simulating them."""
    logger.info("Registering/ensuring test devices exist...")
    for dev_id in device_ids:
        # We can hit the device provision or register endpoint
        # The exact payload depends on AgentRegisterEndpoint
        # For now, let's call the simplest provision/register if available
        # You may need to adapt this depending on how you create devices dynamically
        register_url = f"{API_BASE_URL}/api/v1/agent/register"
        payload = {
            "device_id": dev_id,
            "mac_address": "00:11:22:33:44:55",
            "os_name": "Linux",
            "os_version": "5.15.0",
        }
        try:
            resp = await client.post(register_url, json=payload, timeout=5.0)
            if resp.status_code not in (200, 201, 409):
                # 409 might mean already exists
                pass
        except Exception:
            pass


async def simulate_device(
    device_id: str, client: httpx.AsyncClient, semaphore: asyncio.Semaphore
) -> int:
    """Simulate a single device sending metrics continuously."""
    end_time = asyncio.get_event_loop().time() + SIMULATION_DURATION_SECONDS
    requests_sent = 0

    while asyncio.get_event_loop().time() < end_time:
        async with semaphore:
            scenarios = [
                "healthy",
                "healthy",
                "healthy",
                "high_cpu",
                "low_memory",
                "high_errors",
            ]
            scenario = random.choice(scenarios)

            # In the future, this endpoint or a new one will receive the printer DNA payload
            # printers = random.choice(SAMPLE_PRINTERS)
            url = f"{API_BASE_URL}/api/v1/testing/simulate/device/{device_id}/metrics?scenario={scenario}"

            try:
                response = await client.post(url, timeout=10.0)
                if response.status_code in (200, 201):
                    requests_sent += 1
                else:
                    logger.warning(
                        f"Device {device_id} got status {response.status_code}: {response.text}"
                    )
            except Exception as e:
                logger.error(f"Device {device_id} connection error: {e}")

        # Sleep randomly between 2 and 5 seconds to simulate real-world scatter
        await asyncio.sleep(random.uniform(2.0, 5.0))

    return requests_sent


async def main() -> None:
    """Run the fleet simulation."""
    # Extract the exact device IDs defined in seed_data.py
    seed_device_ids = [
        "site1-linux-01",
        "site1-windows-02",
        "site1-macos-03",
        "site1-web-04",
        "site1-iot-05",
        "site2-linux-01",
        "site2-windows-02",
        "site2-macos-03",
        "site2-web-04",
        "site2-iot-05",
    ]

    # We will simulate exactly the 10 seed devices
    device_ids = seed_device_ids
    num_active_devices = len(device_ids)

    logger.info(
        f"Starting simulation of {num_active_devices} devices for {SIMULATION_DURATION_SECONDS}s"
    )

    # Use a semaphore to limit the number of strictly concurrent network requests
    # to avoid exhausting local ephemeral ports or instantly overwhelming the local DB
    semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS_LIMIT)
    limits = httpx.Limits(
        max_keepalive_connections=CONCURRENT_REQUESTS_LIMIT,
        max_connections=CONCURRENT_REQUESTS_LIMIT,
    )

    async with httpx.AsyncClient(limits=limits) as client:
        await setup_test_devices(device_ids, client)

        tasks: List[asyncio.Task] = []
        for device_id in device_ids:
            task = asyncio.create_task(simulate_device(device_id, client, semaphore))
            tasks.append(task)

        # Wait for all devices to finish their simulation loops
        results = await asyncio.gather(*tasks, return_exceptions=True)

    total_requests = 0
    errors = 0
    for res in results:
        if isinstance(res, Exception):
            errors += 1
        else:
            total_requests += res

    logger.info("--- Simulation Complete ---")
    logger.info(f"Active Devices: {num_active_devices}")
    logger.info(f"Total Successful Metrics Pushed: {total_requests}")
    logger.info(f"Device Loop Errors: {errors}")
    logger.info(f"Average req/sec: {total_requests / SIMULATION_DURATION_SECONDS:.2f}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Simulation interrupted by user")
        sys.exit(0)

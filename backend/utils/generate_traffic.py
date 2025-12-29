"""Traffic generator for HOMEPOT data collection."""

import asyncio
import logging
import random
from typing import Dict, List, Optional

import httpx

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

BASE_URL = "http://localhost:8000/api/v1"
AUTH_URL = "http://localhost:8000/api/v1/auth"


async def get_auth_token(client: httpx.AsyncClient) -> Optional[str]:
    """Authenticate and return access token."""
    try:
        # Login with homepot_user credentials (matching DB seed)
        login_data = {"email": "admin@homepot.com", "password": "homepot_dev_password"}

        response = await client.post(f"{AUTH_URL}/login", json=login_data)

        if response.status_code == 200:
            data = response.json()
            if data.get("success") and data.get("data"):
                token = data["data"].get("access_token")
                logger.info("Successfully authenticated as homepot_user")
                return token

        logger.error(
            f"Authentication failed. Status: {response.status_code}, Body: {response.text}"
        )
        return None

    except Exception as e:
        logger.error(f"Authentication error: {e}")
        return None


async def fetch_devices(client: httpx.AsyncClient, headers: Dict) -> List[Dict]:
    """Fetch all available devices from the API."""
    try:
        # Endpoint is /devices/device based on DevicesEndpoints.py
        response = await client.get(f"{BASE_URL}/devices/device", headers=headers)

        if response.status_code == 200:
            data = response.json()
            devices = data.get("devices", [])
            logger.info(f"Fetched {len(devices)} devices from API")
            return devices
        else:
            logger.error(f"Failed to fetch devices: {response.status_code}")
            return []
    except Exception as e:
        logger.error(f"Error fetching devices: {e}")
        return []


async def simulate_user_traffic(
    client: Optional[httpx.AsyncClient] = None, max_iterations: Optional[int] = None
):
    """Simulate random user traffic to generate API logs."""

    async def _run_loop(api_client: httpx.AsyncClient):
        # Authenticate first
        token = await get_auth_token(api_client)
        if not token:
            logger.error("Cannot proceed without authentication")
            return

        headers = {"Authorization": f"Bearer {token}"}
        api_client.cookies.set("access_token", token)

        # Fetch real devices
        devices = await fetch_devices(api_client, headers)
        if not devices:
            logger.warning(
                "No devices found! Traffic will be limited to non-device endpoints."
            )

        logger.info("Starting traffic simulation loop...")

        iterations = 0
        while True:
            if max_iterations is not None and iterations >= max_iterations:
                logger.info(f"Reached maximum iterations ({max_iterations}). Stopping.")
                break
            iterations += 1

            try:
                # Pick a random device if available
                device = random.choice(devices) if devices else None
                device_id = device["device_id"] if device else "unknown-device"
                site_id = device["site_id"] if device else "unknown-site"

                # 1. Health Check (Frequent)
                await api_client.get(f"{BASE_URL}/health/health")

                # 2. List Sites (Occasional)
                if random.random() < 0.3:
                    await api_client.get(f"{BASE_URL}/sites/")

                # 3. Get Device Details (Rare)
                if device and random.random() < 0.1:
                    await api_client.get(
                        f"{BASE_URL}/devices/device/{device_id}", headers=headers
                    )

                # 4. Simulate a Push Notification ACK (Device Traffic)
                if device and random.random() < 0.2:
                    await api_client.post(
                        f"{BASE_URL}/push/ack",
                        json={
                            "message_id": f"msg-{random.randint(1000, 9999)}",
                            "device_id": device_id,
                            "status": "delivered",
                        },
                        headers=headers,
                    )

                # 5. Simulate Error Reporting (Frontend/Client Errors)
                if device and random.random() < 0.15:
                    error_types = [
                        ("api", "error", "Connection timeout"),
                        ("validation", "warning", "Invalid input format"),
                        ("device", "critical", "Sensor malfunction"),
                        ("auth", "error", "Token expired"),
                    ]
                    cat, sev, msg = random.choice(error_types)

                    await api_client.post(
                        f"{BASE_URL}/analytics/error",
                        json={
                            "category": cat,
                            "severity": sev,
                            "error_message": msg,
                            "endpoint": "/api/v1/mobile/sync",
                            "device_id": device_id,
                            "context": {"retry_count": random.randint(1, 3)},
                        },
                        headers=headers,
                    )

                # 6. Simulate User Activity (Frontend Analytics)
                if random.random() < 0.25:
                    activity_types = ["page_view", "click", "search", "filter"]
                    pages = ["/dashboard", "/devices", "/sites", "/settings"]

                    # If we have a site, visit site specific pages
                    if site_id != "unknown-site":
                        pages.append(f"/dashboard/sites/{site_id}")

                    await api_client.post(
                        f"{BASE_URL}/analytics/user-activity",
                        json={
                            "activity_type": random.choice(activity_types),
                            "page_url": random.choice(pages),
                            "element_id": f"btn-{random.randint(1, 50)}",
                            "duration_ms": random.randint(500, 5000),
                            "session_id": f"sess-{random.randint(10000, 99999)}",
                        },
                        headers=headers,
                    )

                # 7. Simulate Job Creation
                if device and random.random() < 0.3:
                    try:
                        await api_client.post(
                            f"{BASE_URL}/jobs/sites/{site_id}/jobs",
                            json={
                                "action": "Update POS payment config",
                                "description": "Automated traffic simulation job",
                                "priority": "normal",
                                "config_url": "https://config.example.com/v2.json",
                                "config_version": "2.0.0",
                                "device_id": device_id,  # Target specific device
                            },
                            headers=headers,
                        )
                    except Exception as e:
                        logger.error(f"Job creation failed: {e}")

                # Random delay between 0.5s and 2s
                # Skip sleep if we are running a limited number of iterations (testing)
                if max_iterations is None:
                    await asyncio.sleep(random.uniform(0.5, 2.0))

            except Exception as e:
                logger.error(f"Traffic simulation error: {e}")
                if max_iterations is None:
                    await asyncio.sleep(5)

    if client:
        await _run_loop(client)
    else:
        async with httpx.AsyncClient(timeout=10.0) as new_client:
            await _run_loop(new_client)


if __name__ == "__main__":
    logger.info("Starting traffic simulation...")
    try:
        asyncio.run(simulate_user_traffic())
    except KeyboardInterrupt:
        logger.info("Stopping traffic simulation")

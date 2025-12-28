"""Traffic generator for HOMEPOT data collection."""

import asyncio
import logging
import random

import httpx

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

BASE_URL = "http://localhost:8000/api/v1"
AUTH_URL = "http://localhost:8000/api/v1/auth"


async def get_auth_token(client):
    """Authenticate and return access token."""
    try:
        # Try to login with default admin credentials
        # Note: These should match what's in your database seeding script
        login_data = {"email": "admin@homepot.com", "password": "admin"}

        response = await client.post(f"{AUTH_URL}/login", json=login_data)

        if response.status_code == 200:
            data = response.json()
            if data.get("success") and data.get("data"):
                token = data["data"].get("access_token")
                logger.info("Successfully authenticated as admin")
                return token

        # Try to login as simulation user
        logger.info("Admin login failed, attempting to login as simulation user...")
        sim_login_data = {"email": "simulation@homepot.com", "password": "password123"}
        response = await client.post(f"{AUTH_URL}/login", json=sim_login_data)

        if response.status_code == 200:
            data = response.json()
            if data.get("success") and data.get("data"):
                token = data["data"].get("access_token")
                logger.info("Successfully authenticated as simulation user")
                return token

        # If login fails, try to register a simulation user
        logger.info("Login failed, attempting to register simulation user...")
        signup_data = {
            "email": "simulation@homepot.com",
            "username": "sim_user",
            "password": "password123",
        }

        response = await client.post(f"{AUTH_URL}/signup", json=signup_data)
        if response.status_code == 201:
            data = response.json()
            if data.get("success") and data.get("data"):
                token = data["data"].get("access_token")
                logger.info(
                    "Successfully registered and authenticated as simulation user"
                )
                return token

        logger.error(
            f"Authentication failed. Status: {response.status_code}, Body: {response.text}"
        )
        return None

    except Exception as e:
        logger.error(f"Authentication error: {e}")
        return None


async def simulate_user_traffic():
    """Simulate random user traffic to generate API logs."""
    async with httpx.AsyncClient(timeout=5.0) as client:
        # Authenticate first
        token = await get_auth_token(client)
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
            # Also set cookie as some endpoints might check it
            client.cookies.set("access_token", token)

        while True:
            try:
                # 1. Health Check (Frequent)
                await client.get(f"{BASE_URL}/health/health")

                # 2. List Sites (Occasional)
                if random.random() < 0.3:
                    await client.get(f"{BASE_URL}/sites/")

                # 3. Get Device Details (Rare)
                if random.random() < 0.1:
                    # Use a dummy ID, we just want to generate a log entry (even 404s are logged)
                    await client.get(f"{BASE_URL}/devices/pos-terminal-001")

                # 4. Simulate a Push Notification ACK (Device Traffic)
                if random.random() < 0.2:
                    await client.post(
                        f"{BASE_URL}/push/ack",
                        json={
                            "message_id": f"msg-{random.randint(1000, 9999)}",
                            "device_id": "pos-terminal-001",
                            "status": "delivered",
                        },
                    )

                # 5. Simulate Error Reporting (Frontend/Client Errors)
                if random.random() < 0.15:
                    error_types = [
                        ("api", "error", "Connection timeout"),
                        ("validation", "warning", "Invalid input format"),
                        ("device", "critical", "Sensor malfunction"),
                        ("auth", "error", "Token expired"),
                    ]
                    cat, sev, msg = random.choice(error_types)

                    await client.post(
                        f"{BASE_URL}/analytics/error",
                        json={
                            "category": cat,
                            "severity": sev,
                            "error_message": msg,
                            "endpoint": "/api/v1/mobile/sync",
                            "device_id": "pos-terminal-001",
                            "context": {"retry_count": random.randint(1, 3)},
                        },
                    )

                # 6. Simulate User Activity (Frontend Analytics)
                if random.random() < 0.25:
                    activity_types = ["page_view", "click", "search", "filter"]
                    pages = ["/dashboard", "/devices", "/sites", "/settings"]

                    await client.post(
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

                # 7. Simulate Job Creation (Triggers JobOutcome & ConfigurationHistory)
                if random.random() < 0.3:  # Increased probability (was 0.05)
                    # First get a site
                    try:
                        sites_resp = await client.get(
                            f"{BASE_URL}/sites/", headers=headers
                        )
                        sites = []
                        if sites_resp.status_code == 200:
                            sites = sites_resp.json().get("sites", [])

                        # If no sites, create one
                        if not sites:
                            logger.warning("No sites found for job creation. Skipping.")
                            # site_id = f"site-{random.randint(100, 999)}"
                            # create_site_resp = await client.post(
                            #     f"{BASE_URL}/sites/",
                            #     json={
                            #         "site_id": site_id,
                            #         "name": f"Store {site_id}",
                            #         "location": "New York",
                            #         "description": "Simulated Store",
                            #     },
                            #     headers=headers,
                            # )
                            # if create_site_resp.status_code == 200:
                            #     sites = [{"site_id": site_id}]
                            #     # Also create a device for this site so jobs have a target
                            #     # ... (omitted for brevity)

                        if sites:
                            site_id = random.choice(sites)["site_id"]
                            await client.post(
                                f"{BASE_URL}/jobs/sites/{site_id}/jobs",
                                json={
                                    "action": "Update POS payment config",
                                    "description": "Automated traffic simulation job",
                                    "priority": "normal",
                                    "config_url": "https://config.example.com/v2.json",
                                    "config_version": "2.0.0",
                                },
                                headers=headers,
                            )
                    except Exception as e:
                        logger.error(f"Job creation failed: {e}")

                # Random delay between 0.5s and 2s

                # Random delay between 0.5s and 2s
                await asyncio.sleep(random.uniform(0.5, 2.0))

            except Exception as e:
                logger.error(f"Traffic simulation error: {e}")
                await asyncio.sleep(5)


if __name__ == "__main__":
    logger.info("Starting traffic simulation...")
    try:
        asyncio.run(simulate_user_traffic())
    except KeyboardInterrupt:
        logger.info("Stopping traffic simulation")

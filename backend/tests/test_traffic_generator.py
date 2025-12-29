"""Integration tests for the traffic generator utility."""

import sys
from pathlib import Path

import httpx
import pytest

# Ensure backend is in path
sys.path.append(str(Path(__file__).parent.parent))

from homepot.app.main import app  # noqa: E402

# Now we can import from utils because we added __init__.py
from utils.generate_traffic import simulate_user_traffic  # noqa: E402


@pytest.mark.asyncio
async def test_traffic_generator_integration():
    """Test that the traffic generator runs against the in-memory app."""
    # Create an AsyncClient that talks to our FastAPI app
    # We use base_url="http://localhost:8000/api/v1" because the script uses that BASE_URL
    # But wait, the script hardcodes BASE_URL = "http://localhost:8000/api/v1"
    # and AUTH_URL = "http://localhost:8000/api/v1/auth"

    # When using AsyncClient(app=app), requests to any URL will be routed to the app.
    # However, the app mounts api_v1_router at /api/v1.
    # So http://localhost:8000/api/v1/... should work fine.

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://localhost:8000"
    ) as client:
        # Run the simulation for a few iterations
        # This will:
        # 1. Authenticate (hitting /api/v1/auth/login)
        # 2. Fetch devices (hitting /api/v1/devices/device)
        # 3. Run 2 loops of traffic generation

        await simulate_user_traffic(client=client, max_iterations=2)

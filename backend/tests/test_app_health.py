"""Health endpoint tests for the canonical FastAPI app."""

from fastapi.testclient import TestClient

from homepot.app.main import app


def test_health_endpoint_returns_ok() -> None:
    """The canonical app exposes the liveness endpoint used by Docker."""
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

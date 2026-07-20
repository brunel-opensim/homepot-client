"""Tests for the agent bootstrap flow (claim enrolment intent + DNA registration)."""

from pathlib import Path
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homepot.agent.credential_storage import SimulationStorage


@pytest.fixture
def mock_identity(monkeypatch):
    """Return a fixed device identity without touching the filesystem."""
    monkeypatch.setattr(
        "homepot.agent.identity.get_or_create_device_id",
        lambda: "device-test-bootstrap-identity",
    )


@pytest.fixture
def mock_mac(monkeypatch):
    """Return a fixed MAC address so DNA payload is deterministic."""
    monkeypatch.setattr(
        "homepot.agent.utils.device_dna.get_mac_address",
        lambda: "aa:bb:cc:dd:ee:ff",
    )


@pytest.fixture
def mock_ip(monkeypatch):
    """Return fixed IP addresses so DNA payload is deterministic."""
    monkeypatch.setattr(
        "homepot.agent.utils.device_dna.get_local_ip",
        lambda: "192.168.1.99",
    )
    monkeypatch.setattr(
        "homepot.agent.utils.device_dna.get_wan_ip",
        lambda: "203.0.113.99",
    )


@pytest.fixture
def mock_peripherals(monkeypatch):
    """Return an empty peripherals dict."""
    monkeypatch.setattr(
        "homepot.agent.utils.real_device_discovery.get_connected_peripherals",
        lambda: {},
    )


@pytest.fixture
def cred_storage():
    """Provide a clean SimulationStorage for each test."""
    return SimulationStorage()


@pytest.fixture(autouse=True)
def patch_credential_storage(cred_storage, monkeypatch):
    """Replace the storage factory so bootstrap_agent uses our test storage."""
    monkeypatch.setattr(
        "homepot.agent.real_device_agent.create_credential_storage",
        lambda: cred_storage,
    )


@pytest.fixture
def agent_config_file(monkeypatch):
    """Point load_agent_config at a minimal temp config."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg_path = Path(tmpdir) / "agent-config.json"
        cfg_path.write_text(
            '{"backend_url": "http://localhost:8000", "device_id": "dummy", '
            '"site_id": "s-dummy", "api_key": "dummy", '
            '"device_name": "Test", "device_type": "pos_terminal", '
            '"os_details": "Linux"}',
            encoding="utf-8",
        )
        monkeypatch.setenv("HOMEPOT_AGENT_CONFIG", str(cfg_path))
        yield


async def test_bootstrap_agent_success(
    mock_identity, mock_mac, mock_ip, mock_peripherals, cred_storage, agent_config_file
):
    """Happy path: claim endpoint returns credentials and DNA is registered."""
    claim_response = {
        "status": "success",
        "message": "Device claimed successfully",
        "device_id": "pos-terminal-a1b2c3d4",
        "api_key": "test-api-key-12345",
        "site_id": "site-test-001",
        "epoch_id": "epoch-001",
    }

    dna_response = {
        "status": "success",
        "data": {"device_id": "pos-terminal-a1b2c3d4", "created": True},
    }

    async def _mock_post(url, **kwargs):
        mock_resp = AsyncMock()
        mock_resp.raise_for_status = MagicMock()
        if "/enrolment-intents/" in url and "/claim" in url:
            mock_resp.json.return_value = claim_response
        elif "/device-dna" in url:
            mock_resp.json.return_value = dna_response
        else:
            mock_resp.status_code = 404
        return mock_resp

    with patch("homepot.agent.real_device_agent.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        mock_client.post = _mock_post

        from homepot.agent.real_device_agent import bootstrap_agent

        config = await bootstrap_agent(
            backend_url="http://test-backend:8000",
            intent_id="intent-abc-123",
            claim_token="tok-secret-999",
            device_name="Test POS",
            device_type="pos_terminal",
            os_details="TestOS 1.0",
        )

    assert config["device_id"] == "pos-terminal-a1b2c3d4"
    assert config["site_id"] == "site-test-001"
    assert config["api_key"] == "test-api-key-12345"
    assert config["device_name"] == "Test POS"

    assert cred_storage.get_device_id() == "pos-terminal-a1b2c3d4"
    assert cred_storage.get_api_key() == "test-api-key-12345"
    assert cred_storage.get_backend_url() == "http://test-backend:8000"
    assert cred_storage.get_metadata("site_id") == "site-test-001"
    assert cred_storage.get_metadata("device_name") == "Test POS"
    assert cred_storage.get_metadata("device_type") == "pos_terminal"
    assert cred_storage.get_metadata("os_details") == "TestOS 1.0"


async def test_bootstrap_agent_claim_fails(
    mock_identity, cred_storage, agent_config_file
):
    """When the claim endpoint returns an error, bootstrap_agent should raise."""

    async def _mock_post(url, **kwargs):
        mock_resp = AsyncMock()
        mock_resp.raise_for_status = MagicMock(
            side_effect=Exception("401 Unauthorized")
        )
        mock_resp.status_code = 401
        return mock_resp

    with patch("homepot.agent.real_device_agent.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        mock_client.post = _mock_post

        from homepot.agent.real_device_agent import bootstrap_agent

        with pytest.raises(Exception, match="401 Unauthorized"):
            await bootstrap_agent(
                backend_url="http://test-backend:8000",
                intent_id="intent-bad",
                claim_token="tok-bad",
            )

    assert cred_storage.is_provisioned() is False


async def test_bootstrap_agent_passes_expected_identity(
    mock_identity, mock_mac, mock_ip, mock_peripherals, cred_storage, agent_config_file
):
    """expected_device_identity is forwarded in the claim payload."""
    sent_payload = {}

    async def _mock_post(url, json=None, **kwargs):
        nonlocal sent_payload
        mock_resp = AsyncMock()
        mock_resp.raise_for_status = MagicMock()
        if "/claim" in url:
            sent_payload = json or {}
            mock_resp.json.return_value = {
                "device_id": "d-1234",
                "api_key": "ak-5678",
                "site_id": "s-999",
            }
        elif "/device-dna" in url:
            mock_resp.json.return_value = {"status": "success"}
        return mock_resp

    with patch("homepot.agent.real_device_agent.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        mock_client.post = _mock_post

        from homepot.agent.real_device_agent import bootstrap_agent

        await bootstrap_agent(
            backend_url="http://localhost:8000",
            intent_id="intent-ei-1",
            claim_token="tok-ei-1",
            expected_device_identity="SN-ABCDEF",
        )

    assert sent_payload.get("expected_device_identity") == "SN-ABCDEF"

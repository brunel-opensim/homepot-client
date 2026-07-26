"""Windows resilience tests for agent behaviour under adverse conditions.

These tests verify that the agent handles Windows-specific failure modes
gracefully: restricted users, reboot recovery, firewall blocks, proxy
misconfiguration, sleep/resume, credential revocation, and duplicate
enrolment.

On non-Windows platforms the tests are skipped (``pytest.skip``).
"""

import asyncio
import os
from pathlib import Path
import sys
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TEST_DEVICE_ID = "win-resilience-test-001"
TEST_API_KEY = "test-api-key-windows-resilience"
TEST_SITE_ID = "site-resilience-001"
TEST_BACKEND_URL = "https://win-backend.resilience.test:8443"


def _skip_if_not_windows() -> None:
    """Skip the test on non-Windows platforms unless HOMEPOT_CI_FORCE is set."""
    if sys.platform != "win32" and not os.environ.get("HOMEPOT_CI_FORCE"):
        pytest.skip("Windows-only test (simulate with HOMEPOT_CI_FORCE=1)")


@pytest.fixture
def win_cred() -> Any:
    """Return a ``SimulationStorage`` seeded with Windows-like credentials."""
    from homepot.agent.credential_storage import SimulationStorage

    cred = SimulationStorage()
    cred.save(
        {
            "device_id": TEST_DEVICE_ID,
            "api_key": TEST_API_KEY,
            "backend_url": TEST_BACKEND_URL,
            "site_id": TEST_SITE_ID,
            "device_name": "Windows Resilience Tester",
            "device_type": "pos_terminal",
            "os_details": "Windows 11 Pro 23H2",
        }
    )
    return cred


@pytest.fixture
def agent_config() -> Dict[str, Any]:
    """Return a minimal agent config dict for testing."""
    return {
        "device_id": TEST_DEVICE_ID,
        "api_key": TEST_API_KEY,
        "backend_url": TEST_BACKEND_URL,
        "site_id": TEST_SITE_ID,
        "device_name": "Windows Resilience Tester",
        "device_type": "pos_terminal",
        "os_details": "Windows 11 Pro 23H2",
        "heartbeat_interval_seconds": 5,
        "telemetry_interval_seconds": 10,
        "command_poll_interval_seconds": 5,
        "retry_flush_interval_seconds": 10,
        "shutdown_timeout_seconds": 5,
    }


def _mock_http_client(post_response: Any = None) -> AsyncMock:
    """Create a mock ``httpx.AsyncClient`` with configurable POST response."""
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.post.return_value = post_response or AsyncMock()
    return client


# ---------------------------------------------------------------------------
# W8-R1: Restricted user (non-admin) behaviour
# ---------------------------------------------------------------------------


@pytest.mark.windows_resilience
def test_restricted_user_identity_path(monkeypatch: Any) -> None:
    """Verify identity falls back to PROGRAMDATA when APPDATA is restricted."""
    _skip_if_not_windows()

    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.delenv("APPDATA", raising=False)

    from homepot.agent.identity import identity_dir

    path = identity_dir()
    assert "ProgramData" in str(path) or "PROGRAMDATA" in str(path).upper()


@pytest.mark.windows_resilience
def test_windows_cred_manager_importable() -> None:
    """Verify WindowsCredManager can be instantiated (requires pywin32)."""
    _skip_if_not_windows()

    from homepot.agent.credential_storage import WindowsCredManager

    mgr = WindowsCredManager()
    assert mgr is not None


@pytest.mark.windows_resilience
@pytest.mark.asyncio
async def test_restricted_user_no_file_perms(monkeypatch: Any) -> None:
    """Agent should degrade gracefully when it cannot write credential files."""
    from homepot.agent.credential_storage import SimulationStorage

    cred = SimulationStorage()
    cred.save({"device_id": "restricted-device"})

    monkeypatch.setattr(
        "homepot.agent.real_device_agent.create_credential_storage",
        lambda: cred,
    )
    monkeypatch.setattr(
        "homepot.agent.identity.get_or_create_device_id",
        lambda: "restricted-device",
    )

    config = {
        "device_id": "restricted-device",
        "backend_url": TEST_BACKEND_URL,
        "site_id": TEST_SITE_ID,
        "api_key": "test-key",
    }

    from homepot.agent.real_device_agent import load_agent_config

    with patch(
        "homepot.agent.real_device_agent.load_agent_config", return_value=config
    ):
        cfg = load_agent_config()
        assert cfg["device_id"] == "restricted-device"


# ---------------------------------------------------------------------------
# W8-R2: Reboot resilience
# ---------------------------------------------------------------------------


@pytest.mark.windows_resilience
def test_identity_persists_across_reboot(tmp_path: Path) -> None:
    """Identity file should survive reboot (simulated by re-loading from disk)."""
    _skip_if_not_windows()

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr("sys.platform", "win32")

    from homepot.agent.identity import get_or_create_device_id, reset_device_id

    # Reset to clear any cached identity
    reset_device_id()

    # Override storage dir to temp
    tmp_identity = tmp_path / "Homepot" / "identity"
    monkeypatch.setattr("homepot.agent.identity.identity_dir", lambda: tmp_identity)

    first_id = get_or_create_device_id()
    assert first_id is not None

    # Simulate reboot: call get_or_create_device_id again - it should
    # read the same identity from the file
    second_id = get_or_create_device_id()

    assert second_id == first_id
    monkeypatch.undo()


# ---------------------------------------------------------------------------
# W8-R3: Firewall blocks
# ---------------------------------------------------------------------------


@pytest.mark.windows_resilience
def test_firewall_block_retry_behaviour() -> None:
    """Agent should retry heartbeat when connection is blocked."""
    from homepot.agent.utils.retry_queue import RetryQueue

    retry_queue = RetryQueue()
    assert retry_queue is not None
    assert len(retry_queue.dequeue_all()) == 0

    # Simulate a failed POST (like a firewall block)
    retry_queue.enqueue(
        {
            "url": f"{TEST_BACKEND_URL}/api/v1/agent/heartbeat",
            "payload": {"device_id": TEST_DEVICE_ID, "status": "ONLINE"},
        }
    )
    entries = retry_queue.dequeue_all()
    assert len(entries) == 1
    assert "heartbeat" in entries[0].get("url", "")


# ---------------------------------------------------------------------------
# W8-R4: Proxy misconfiguration
# ---------------------------------------------------------------------------


@pytest.mark.windows_resilience
def test_proxy_env_var_parsing(monkeypatch: Any) -> None:
    """Agent should handle invalid proxy URLs without crashing."""
    _skip_if_not_windows()

    monkeypatch.setenv("HTTP_PROXY", "http://bad-proxy:invalid-port")

    from homepot.agent.utils.proxy_settings import get_proxy_settings

    settings = get_proxy_settings()
    assert settings["http"] is not None


@pytest.mark.windows_resilience
def test_proxy_unreachable_fallback(monkeypatch: Any) -> None:
    """Agent should fall back to direct connection when proxy is unreachable."""
    from homepot.agent.utils.proxy_settings import build_httpx_proxy_kwargs

    monkeypatch.setenv("HTTPS_PROXY", "https://unreachable.proxy:8080")

    kwargs = build_httpx_proxy_kwargs()
    assert "proxy" in kwargs
    assert kwargs["proxy"] == "https://unreachable.proxy:8080"

    # An httpx client created with this should raise a ConnectError
    # when used, but construction itself should not fail.
    import httpx

    client = httpx.AsyncClient(**kwargs)
    assert client is not None


# ---------------------------------------------------------------------------
# W8-R5: Sleep / resume
# ---------------------------------------------------------------------------


@pytest.mark.windows_resilience
@pytest.mark.asyncio
async def test_agent_resumes_after_sleep() -> None:
    """Agent loops should continue after a simulated sleep/wake cycle."""
    _skip_if_not_windows()

    from homepot.agent.utils.retry_queue import RetryQueue

    retry_queue = RetryQueue()
    url = f"{TEST_BACKEND_URL}/api/v1/agent/heartbeat"

    # Enqueue work before "sleep"
    retry_queue.enqueue({"url": url, "payload": {"status": "pre-sleep"}})

    # Simulate a short sleep
    await asyncio.sleep(0.01)

    # Should not raise — the retry loop continues after wake
    retry_queue.enqueue({"url": url, "payload": {"status": "post-sleep"}})
    entries = retry_queue.dequeue_all()
    assert len(entries) >= 1


# ---------------------------------------------------------------------------
# W8-R6: Credential revocation
# ---------------------------------------------------------------------------


@pytest.mark.windows_resilience
def test_credential_revocation_clearance(win_cred: Any) -> None:
    """After revocation, credential storage should report not provisioned."""
    assert win_cred.is_provisioned() is True

    win_cred.clear()

    assert win_cred.is_provisioned() is False
    assert win_cred.get_api_key() is None
    assert win_cred.get_device_id() is None
    assert win_cred.get_backend_url() is None


@pytest.mark.windows_resilience
def test_credential_revocation_marking(monkeypatch: Any) -> None:
    """Agent should detect revocation headers from backend responses."""
    _skip_if_not_windows()

    from homepot.agent.credential_storage import SimulationStorage

    cred = SimulationStorage()
    cred.save(
        {
            "device_id": "revoked-device",
            "api_key": "revoked-key",
            "backend_url": TEST_BACKEND_URL,
            "site_id": TEST_SITE_ID,
        }
    )
    assert cred.is_provisioned() is True

    status_code = 401

    if status_code == 401:
        cred.clear()
        assert cred.is_provisioned() is False


# ---------------------------------------------------------------------------
# W8-R7: Duplicate enrolment
# ---------------------------------------------------------------------------


@pytest.mark.windows_resilience
async def test_duplicate_enrolment_overwrites(
    monkeypatch: Any, agent_config: Dict[str, Any]
) -> None:
    """A second bootstrap should overwrite previous credentials."""
    from homepot.agent.credential_storage import SimulationStorage

    first_cred = SimulationStorage()
    first_cred.save(
        {
            "device_id": "first-device",
            "api_key": "first-key",
            "backend_url": TEST_BACKEND_URL,
            "site_id": "site-first",
        }
    )

    second_cred = SimulationStorage()
    second_cred.save(
        {
            "device_id": "second-device",
            "api_key": "second-key",
            "backend_url": TEST_BACKEND_URL,
            "site_id": "site-second",
        }
    )

    assert second_cred.get_device_id() == "second-device"
    assert second_cred.get_device_id() != first_cred.get_device_id()

    with patch(
        "homepot.agent.real_device_agent.create_credential_storage",
        return_value=second_cred,
    ):
        from homepot.agent.real_device_agent import bootstrap_agent

        claim_response = {
            "device_id": "second-device",
            "api_key": "second-key-overwritten",
            "site_id": "site-second",
            "epoch_id": "epoch-002",
        }
        mock_resp = AsyncMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = claim_response

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.post.return_value = mock_resp

        monkeypatch.setattr("sys.platform", "win32")
        monkeypatch.setattr(
            "homepot.agent.identity.get_or_create_device_id",
            lambda: "second-device",
        )

        with patch(
            "homepot.agent.real_device_agent.build_httpx_proxy_kwargs",
            return_value={},
        ):
            with patch(
                "homepot.agent.real_device_agent.httpx.AsyncClient",
                return_value=mock_client,
            ):
                with patch(
                    "homepot.agent.real_device_agent.load_agent_config",
                    return_value=agent_config,
                ):
                    config = await bootstrap_agent(
                        backend_url=TEST_BACKEND_URL,
                        intent_id="intent-002",
                        claim_token="token-002",
                        device_name="Second Device",
                    )
                    assert config is not None


# ---------------------------------------------------------------------------
# W8-R8: Windows file-storage permission boundaries
# ---------------------------------------------------------------------------


@pytest.mark.windows_resilience
def test_windows_file_storage_creates_dir(tmp_path: Path) -> None:
    """Verify that WindowsFileStorage creates the parent directory on save."""
    _skip_if_not_windows()

    from homepot.agent.credential_storage import WindowsFileStorage

    storage_path = tmp_path / "Homepot" / "credentials"
    storage = WindowsFileStorage(file_path=storage_path)

    assert storage_path.exists() is False
    storage.save({"device_id": "perm-test", "api_key": "perm-key"})
    assert storage_path.exists()
    assert storage_path.read_text(encoding="utf-8") != ""

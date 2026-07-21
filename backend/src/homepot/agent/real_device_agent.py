"""Real device agent runtime for registration, heartbeat, telemetry, and IPC."""

import asyncio
import json
import logging
import os
from pathlib import Path
import signal
import ssl
import threading
from typing import Any, Dict, Optional, cast

from fastapi import FastAPI
import httpx
from uvicorn import Config, Server

from homepot.agent.credential_storage import (
    CredentialStorage,
    create_credential_storage,
)
from homepot.agent.utils.command_poller import (
    build_status_update_payload,
    parse_pending_commands,
    process_command,
)
from homepot.agent.utils.device_dna import get_local_ip, get_mac_address, get_wan_ip
from homepot.agent.utils.heartbeat import build_heartbeat_payload
from homepot.agent.utils.local_ipc import (
    LocalAgentState,
    create_local_ipc_app,
    push_pending_command,
    update_local_agent_state,
)
from homepot.agent.utils.log_setup import (
    configure_agent_logging,
    logging_config_from_config,
)
from homepot.agent.utils.push_listener import create_push_listener
from homepot.agent.utils.real_device_discovery import get_connected_peripherals
from homepot.agent.utils.retry_queue import RetryQueue
from homepot.agent.utils.telemetry import build_telemetry_payload

logger = logging.getLogger(__name__)


def load_agent_config() -> Dict[str, Any]:
    """Load and validate the agent configuration JSON file.

    Reads the default bundled config (or ``$HOMEPOT_AGENT_CONFIG``) and
    overlays values from credential storage (``backend_url``, ``api_key``,
    ``site_id``) so that provisioned settings always win.
    """
    config_path_str = os.environ.get("HOMEPOT_AGENT_CONFIG")
    if config_path_str:
        config_path = Path(config_path_str)
    else:
        config_path = Path(__file__).parent / "agent-config.json"

    with config_path.open("r", encoding="utf-8") as f:
        data = cast(Dict[str, Any], json.load(f))

    # Overlay provisioned values from credential storage
    cred = create_credential_storage()
    if cred.is_provisioned():
        if cred.get_backend_url():
            data["backend_url"] = cred.get_backend_url()
        if cred.get_api_key():
            data["api_key"] = cred.get_api_key()
        if cred.get_device_id():
            data["device_id"] = cred.get_device_id()
        site_id = cred.get_metadata("site_id")
        if site_id:
            data["site_id"] = site_id
        device_name = cred.get_metadata("device_name")
        if device_name:
            data["device_name"] = device_name
        device_type = cred.get_metadata("device_type")
        if device_type:
            data["device_type"] = device_type
        os_details = cred.get_metadata("os_details")
        if os_details:
            data["os_details"] = os_details

    data.setdefault("heartbeat_interval_seconds", 30)
    data.setdefault("telemetry_interval_seconds", 30)
    data.setdefault("retry_flush_interval_seconds", 60)
    data.setdefault("command_poll_interval_seconds", 60)
    data.setdefault("ipc_enabled", True)
    data.setdefault("ipc_host", "127.0.0.1")
    data.setdefault("ipc_port", 8765)
    data.setdefault("log_level", "INFO")
    data.setdefault("log_max_bytes", 10 * 1024 * 1024)
    data.setdefault("log_backup_count", 5)
    data.setdefault("watchdog_enabled", True)
    data.setdefault("watchdog_interval_seconds", 10)
    data.setdefault("shutdown_timeout_seconds", 30)
    return data


def get_auth_headers(config: Dict[str, Any]) -> Dict[str, str]:
    """Build the device credential headers required by agent endpoints."""
    return {
        "X-Device-ID": str(config["device_id"]),
        "X-API-Key": str(config["api_key"]),
    }


async def post_json(
    client: httpx.AsyncClient,
    url: str,
    payload: Dict[str, Any],
    headers: Dict[str, str],
) -> bool:
    """Send JSON payload to backend and return True on HTTP success."""
    try:
        response = await client.post(url, json=payload, headers=headers, timeout=10.0)
        response.raise_for_status()
        return True
    except Exception as e:
        logger.warning("POST failed url=%s error=%s", url, e)
        return False


async def get_json(
    client: httpx.AsyncClient,
    url: str,
    headers: Dict[str, str],
) -> Any:
    """Send GET request to backend and return parsed JSON on success, or ``None``."""
    try:
        response = await client.get(url, headers=headers, timeout=10.0)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.warning("GET failed url=%s error=%s", url, e)
        return None


async def update_command_status(
    client: httpx.AsyncClient,
    config: Dict[str, Any],
    command_id: str,
    status: str,
    result: Optional[Dict[str, Any]] = None,
) -> bool:
    """Report command execution result back to the backend.

    Sends ``PUT /api/v1/devices/{command_id}/status`` with the given status
    and optional result dict.  Returns ``True`` on success.
    """
    url = f"{config['backend_url'].rstrip('/')}/api/v1/devices/{command_id}/status"
    payload = build_status_update_payload(command_id, status, result)
    return await post_json(client, url, payload, get_auth_headers(config))


async def ack_command_backend(
    client: httpx.AsyncClient,
    config: Dict[str, Any],
    device_id: str,
    command_id: str,
) -> bool:
    """Acknowledge a command to the backend, transitioning it from PENDING to SENT.

    Sends ``POST /api/v1/devices/{device_id}/commands/{command_id}/ack``.
    Returns ``True`` on success.
    """
    url = (
        f"{config['backend_url'].rstrip('/')}/api/v1/devices/"
        f"{device_id}/commands/{command_id}/ack"
    )
    try:
        response = await client.post(
            url, headers=get_auth_headers(config), timeout=10.0
        )
        response.raise_for_status()
        return True
    except Exception as e:
        logger.warning("ACK failed url=%s error=%s", url, e)
        return False


async def pending_commands_loop(
    client: httpx.AsyncClient,
    config: Dict[str, Any],
    retry_queue: RetryQueue,
    ipc_server: Server | None,
    wake_event: asyncio.Event,
) -> None:
    """Poll for pending commands, ACK them, and route to IPC or process locally.

    Polls ``GET /api/v1/devices/pending`` at a fixed interval.  Each command
    is acknowledged first (``POST …/ack``), then either exposed via IPC for
    the real device to execute or processed locally by the agent.
    """
    url = f"{config['backend_url'].rstrip('/')}/api/v1/devices/pending"
    interval = int(config["command_poll_interval_seconds"])
    device_id = str(config["device_id"])
    ipc_available = ipc_server is not None
    while True:
        try:
            data = await get_json(client, url, get_auth_headers(config))
            commands = parse_pending_commands(data)
            for command in commands:
                cid = command.get("command_id", "")
                # 1. Ack to backend
                acked = await ack_command_backend(client, config, device_id, cid)
                if not acked:
                    retry_queue.enqueue(
                        {
                            "url": (
                                f"{config['backend_url'].rstrip('/')}"
                                f"/api/v1/devices/{device_id}/commands/{cid}/ack"
                            ),
                            "payload": {},
                        }
                    )
                    continue
                # 2. Route to IPC or process locally
                if ipc_available:
                    app = cast("FastAPI", ipc_server.config.app)  # type: ignore[union-attr]
                    push_pending_command(app, command)
                else:
                    result = process_command(command)
                    ok = await update_command_status(
                        client,
                        config,
                        cid,
                        result["status"],
                        result.get("result"),
                    )
                    if not ok:
                        retry_queue.enqueue(
                            {
                                "url": (
                                    f"{config['backend_url'].rstrip('/')}"
                                    f"/api/v1/devices/{cid}/status"
                                ),
                                "payload": build_status_update_payload(
                                    cid, result["status"], result.get("result")
                                ),
                            }
                        )
        except Exception as e:
            logger.error("Pending commands loop error: %s", e, exc_info=True)
        wake_event.clear()
        await asyncio.sleep(interval)


async def command_result_loop(
    client: httpx.AsyncClient,
    config: Dict[str, Any],
    retry_queue: RetryQueue,
    ipc_server: Server | None,
) -> None:
    """Pick up command results submitted by the real device via IPC and forward to backend.

    Polls the IPC result store at a fixed interval and submits each result
    via ``PUT /api/v1/devices/{command_id}/status``.
    """
    interval = int(config.get("command_poll_interval_seconds", 60))
    while True:
        try:
            if ipc_server is not None:
                app = ipc_server.config.app  # type: ignore[arg-type]
                while True:
                    cid, result = _pop_next_result(app)
                    if cid is None or result is None:
                        break
                    ok = await update_command_status(
                        client,
                        config,
                        cid,
                        result["status"],
                        result.get("result"),
                    )
                    if not ok:
                        retry_queue.enqueue(
                            {
                                "url": (
                                    f"{config['backend_url'].rstrip('/')}"
                                    f"/api/v1/devices/{cid}/status"
                                ),
                                "payload": build_status_update_payload(
                                    cid, result["status"], result.get("result")
                                ),
                            }
                        )
        except Exception as e:
            logger.error("Command result loop error: %s", e, exc_info=True)
        await asyncio.sleep(interval)


async def _watchdog_loop(
    shutdown_event: asyncio.Event,
    interval: int = 10,
    _sd_notify: Any = None,  # injected by tests
) -> None:
    """Periodically notify systemd that the agent is alive (``WATCHDOG=1``).

    When ``systemd`` is not available or the ``systemd`` Python module is not
    installed this loop is a no-op.
    """
    sd_notify: Any = _sd_notify
    if sd_notify is None:
        try:
            import systemd.daemon  # type: ignore[import-untyped, import-not-found]

            sd_notify = systemd.daemon.notify
        except ImportError:
            pass

    if sd_notify is None:
        return

    while not shutdown_event.is_set():
        try:
            sd_notify("WATCHDOG=1")
        except Exception as exc:
            logger.warning("systemd watchdog notification failed: %s", exc)
        await _wait_with_shutdown(interval, shutdown_event)


async def _wait_with_shutdown(interval: int, shutdown_event: asyncio.Event) -> None:
    """Sleep for *interval* seconds or until *shutdown_event* is set."""
    try:
        await asyncio.wait_for(shutdown_event.wait(), timeout=interval)
    except asyncio.TimeoutError:
        pass
    except asyncio.CancelledError:
        shutdown_event.set()


def _pop_next_result(app: Any) -> tuple[Optional[str], Optional[Dict[str, Any]]]:
    """Pop the first available command result from IPC storage."""
    with app.state.state_lock:
        keys = list(app.state.command_results.keys())
        if not keys:
            return (None, None)
        cid = keys[0]
        result = app.state.command_results.pop(cid)
    return (cid, result)


async def send_registration(
    client: httpx.AsyncClient,
    config: Dict[str, Any],
    retry_queue: RetryQueue,
) -> None:
    """Send initial device registration payload with static device DNA."""
    try:
        # Payload sent to POST /api/v1/agent/device-dna
        # {
        #   "device_id": "android-pos-001",
        #   "site_id": "site-1234",
        #   "device_name": "Front POS",
        #   "device_type": "pos_terminal",
        #   "mac_address": "00:11:22:33:44:55",
        #   "os_details": "Android 13",
        #   "local_ip": "192.168.1.20",
        #   "wan_ip": "203.0.113.10"
        # }
        payload = {
            "device_id": config["device_id"],
            "site_id": config["site_id"],
            "device_name": config.get("device_name"),
            "device_type": config.get("device_type", "pos_terminal"),
            "mac_address": get_mac_address(),
            "os_details": config.get("os_details"),
            "local_ip": get_local_ip(),
            "wan_ip": get_wan_ip(),
            "peripherals": get_connected_peripherals(),
        }
        register_url = f"{config['backend_url'].rstrip('/')}/api/v1/agent/device-dna"
        if not await post_json(client, register_url, payload, get_auth_headers(config)):
            retry_queue.enqueue({"url": register_url, "payload": payload})
    except Exception as e:
        logger.error("Registration payload build/send failed: %s", e, exc_info=True)


async def heartbeat_loop(
    client: httpx.AsyncClient,
    config: Dict[str, Any],
    retry_queue: RetryQueue,
    ipc_server: Server | None,
) -> None:
    """Continuously send heartbeats and update local IPC state."""
    url = f"{config['backend_url'].rstrip('/')}/api/v1/agent/heartbeat"
    interval = int(config["heartbeat_interval_seconds"])
    while True:
        try:
            # Payload sent to POST /api/v1/agent/heartbeat
            # {
            #   "device_id": "android-pos-001",
            #   "site_id": "site-1234",
            #   "status": "ONLINE",
            #   "timestamp": "2026-04-13T12:00:00Z"
            # }
            payload = build_heartbeat_payload(
                config["device_id"],
                site_id=config["site_id"],
                status="ONLINE",
            )
            ok = await post_json(client, url, payload, get_auth_headers(config))
            if ok:
                if ipc_server is not None:
                    update_local_agent_state(
                        ipc_server.config.app,  # type: ignore[arg-type]
                        status="ONLINE",
                        last_heartbeat=payload["timestamp"],
                    )
            else:
                retry_queue.enqueue({"url": url, "payload": payload})
                if ipc_server is not None:
                    update_local_agent_state(
                        ipc_server.config.app,  # type: ignore[arg-type]
                        status="OFFLINE",
                    )
        except Exception as e:
            logger.error("Heartbeat loop error: %s", e, exc_info=True)
        await asyncio.sleep(interval)


async def telemetry_loop(
    client: httpx.AsyncClient,
    config: Dict[str, Any],
    retry_queue: RetryQueue,
    ipc_server: Server | None,
) -> None:
    """Continuously send telemetry metrics and update local IPC state."""
    url = f"{config['backend_url'].rstrip('/')}/api/v1/agent/telemetry"
    interval = int(config["telemetry_interval_seconds"])
    while True:
        try:
            # Payload sent to POST /api/v1/agent/telemetry
            # {
            #   "device_id": "android-pos-001",
            #   "site_id": "site-1234",
            #   "cpu_usage": 20.1,
            #   "memory_usage": 55.4,
            #   "disk_usage": 44.8,
            #   "timestamp": "2026-04-13T12:00:30Z"
            # }
            payload = build_telemetry_payload(config["device_id"])
            payload["site_id"] = config["site_id"]
            ok = await post_json(client, url, payload, get_auth_headers(config))
            if ok and ipc_server is not None:
                update_local_agent_state(
                    ipc_server.config.app,  # type: ignore[arg-type]
                    last_telemetry=payload,
                )
            if not ok:
                retry_queue.enqueue({"url": url, "payload": payload})
        except Exception as e:
            logger.error("Telemetry loop error: %s", e, exc_info=True)
        await asyncio.sleep(interval)


async def retry_flush_loop(
    client: httpx.AsyncClient,
    config: Dict[str, Any],
    retry_queue: RetryQueue,
) -> None:
    """Flush queued failed payloads to backend at a fixed interval.

    Uses :meth:`~RetryQueue.dequeue_ready` so that each item respects
    exponential backoff.  Items that still fail are re-enqueued with an
    incremented retry count via :meth:`~RetryQueue.requeue`.
    """
    interval = int(config["retry_flush_interval_seconds"])
    while True:
        try:
            queued_items = retry_queue.dequeue_ready()
            for item in queued_items:
                ok = await post_json(
                    client,
                    item["url"],
                    item["payload"],
                    get_auth_headers(config),
                )
                if not ok:
                    retry_queue.requeue(item)
        except Exception as e:
            logger.error("Retry flush loop error: %s", e, exc_info=True)
        await asyncio.sleep(interval)


def start_local_ipc_server(config: Dict[str, Any]) -> Server | None:
    """Start local IPC server on localhost in a background thread."""
    if not bool(config.get("ipc_enabled", True)):
        return None

    try:
        app = create_local_ipc_app(
            LocalAgentState(device_id=config["device_id"], status="STARTING")
        )
        uv_config = Config(
            app=app,
            host=str(config["ipc_host"]),
            port=int(config["ipc_port"]),
            log_level="warning",
        )
        server = Server(uv_config)

        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        logger.info(
            "Local IPC server started on http://%s:%s",
            config["ipc_host"],
            config["ipc_port"],
        )
        return server
    except Exception as e:
        logger.error("Failed to start local IPC server: %s", e, exc_info=True)
        return None


def _build_tls_config(cred: CredentialStorage) -> Dict[str, Any]:
    """Build an httpx-compatible TLS configuration from credential storage.

    Returns a dict with keys ``verify`` and optionally ``cert`` that can be
    unpacked into ``httpx.AsyncClient(...)``.
    """
    tls_kw: Dict[str, Any] = {"verify": cred.get_tls_verify()}

    ca_cert = cred.get_tls_ca_cert()
    if ca_cert:
        ctx = ssl.create_default_context(cafile=ca_cert)
        tls_kw["verify"] = ctx

    client_cert = cred.get_tls_client_cert()
    client_key = cred.get_tls_client_key()
    if client_cert and client_key:
        tls_kw["cert"] = (client_cert, client_key)
    elif client_cert:
        tls_kw["cert"] = client_cert

    return tls_kw


async def bootstrap_agent(
    backend_url: str,
    intent_id: str,
    claim_token: str,
    device_name: Optional[str] = None,
    device_type: str = "pos_terminal",
    os_details: Optional[str] = None,
    expected_device_identity: Optional[str] = None,
) -> Dict[str, Any]:
    """Provision this device by claiming an enrolment intent.

    Steps
    -----
    1. Ensure a persistent device identity exists.
    2. Call ``POST /api/v1/enrolment-intents/{intent_id}/claim``.
    3. Persist the returned credentials in ``CredentialStorage``.
    4. Register device DNA via ``POST /api/v1/agent/device-dna``.
    5. Return the effective agent configuration.

    Parameters
    ----------
    backend_url:
        Root URL of the Homepot backend (e.g. ``https://api.example.com``).
    intent_id:
        The public ``intent_id`` of a pre-approved enrolment intent.
    claim_token:
        The one-time claim token created with the intent.
    device_name:
        Optional human-friendly display name for this device.
    device_type:
        Device type identifier (default ``"pos_terminal"``).
    os_details:
        Optional OS version string reported by the device.
    expected_device_identity:
        Optional stable hardware identifier for extra validation.
    """
    from homepot.agent.identity import get_or_create_device_id

    device_identity = get_or_create_device_id()
    logger.info("Bootstrapping with device identity: %s", device_identity)

    cred = create_credential_storage()

    claim_payload: Dict[str, Any] = {
        "claim_token": claim_token,
        "device_name": device_name or device_identity,
        "device_type": device_type,
        "os_details": os_details,
    }
    if expected_device_identity:
        claim_payload["expected_device_identity"] = expected_device_identity

    claim_url = f"{backend_url.rstrip('/')}/api/v1/enrolment-intents/{intent_id}/claim"

    async with httpx.AsyncClient() as client:
        response = await client.post(claim_url, json=claim_payload, timeout=30.0)
        response.raise_for_status()
        result = await response.json()

        device_id: str = result["device_id"]
        api_key: str = result["api_key"]
        site_id: str = result["site_id"]

    cred.save(
        {
            "device_id": device_id,
            "api_key": api_key,
            "backend_url": backend_url,
            "site_id": site_id,
            "device_name": device_name or "",
            "device_type": device_type,
            "os_details": os_details or "",
        }
    )

    logger.info("Device provisioned: %s (site: %s)", device_id, site_id)

    config = load_agent_config()
    tls_kw = _build_tls_config(cred)

    try:
        async with httpx.AsyncClient(**tls_kw) as client:
            payload: Dict[str, Any] = {
                "device_id": config["device_id"],
                "site_id": config["site_id"],
                "device_name": config.get("device_name"),
                "device_type": config.get("device_type", "pos_terminal"),
                "mac_address": get_mac_address(),
                "os_details": config.get("os_details"),
                "local_ip": get_local_ip(),
                "wan_ip": get_wan_ip(),
                "peripherals": get_connected_peripherals(),
            }
            dna_url = f"{config['backend_url'].rstrip('/')}/api/v1/agent/device-dna"
            dna_resp = await client.post(
                dna_url, json=payload, headers=get_auth_headers(config), timeout=30.0
            )
            dna_resp.raise_for_status()
            logger.info("Device DNA registered: %s", device_id)
    except Exception as e:
        logger.warning("Device DNA registration failed during bootstrap: %s", e)

    return config


async def run_agent() -> None:
    """Run agent runtime tasks: registration, heartbeat, telemetry, command polling, and retry."""
    config = load_agent_config()

    # Configure logging with optional file rotation
    log_kwargs = logging_config_from_config(config)
    configure_agent_logging(**log_kwargs)

    cred = create_credential_storage()
    retry_queue = RetryQueue()
    ipc_server = start_local_ipc_server(config)

    push_listener = create_push_listener(config)
    await push_listener.start()

    tls_kw = _build_tls_config(cred)

    shutdown_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    # Register signal handlers for graceful shutdown
    shutdown_timeout = int(config.get("shutdown_timeout_seconds", 30))

    def _handle_signal() -> None:
        """Set the shutdown event and log the signal."""
        logger.info("Shutdown signal received, stopping agent…")
        shutdown_event.set()

    try:
        loop.add_signal_handler(signal.SIGTERM, _handle_signal)
        loop.add_signal_handler(signal.SIGINT, _handle_signal)
    except NotImplementedError:
        logger.warning("Signal handlers not supported on this platform")

    async def _shutdown_after_timeout() -> None:
        """Force shutdown if the agent does not stop gracefully within the timeout."""
        await asyncio.sleep(shutdown_timeout)
        if not shutdown_event.is_set():
            logger.warning(
                "Shutdown timeout (%ss) reached, forcing exit", shutdown_timeout
            )
            shutdown_event.set()

    # Start the forced-shutdown timer
    asyncio.ensure_future(_shutdown_after_timeout())

    async def _cancel_on_shutdown(tasks: list) -> None:
        """Cancel all agent tasks when shutdown_event is set."""
        await shutdown_event.wait()
        for t in tasks:
            t.cancel()

    async with httpx.AsyncClient(**tls_kw) as client:
        await send_registration(client, config, retry_queue)

        tasks = [
            asyncio.ensure_future(
                heartbeat_loop(client, config, retry_queue, ipc_server)
            ),
            asyncio.ensure_future(
                telemetry_loop(client, config, retry_queue, ipc_server)
            ),
            asyncio.ensure_future(retry_flush_loop(client, config, retry_queue)),
            asyncio.ensure_future(
                pending_commands_loop(
                    client,
                    config,
                    retry_queue,
                    ipc_server,
                    push_listener.wake_event,
                )
            ),
            asyncio.ensure_future(
                command_result_loop(client, config, retry_queue, ipc_server)
            ),
            asyncio.ensure_future(
                _watchdog_loop(
                    shutdown_event,
                    int(config.get("watchdog_interval_seconds", 10)),
                )
            ),
        ]
        asyncio.ensure_future(_cancel_on_shutdown(tasks))

        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            logger.info("Agent tasks cancelled, shutting down…")
        except Exception as e:
            logger.error("Agent runtime error: %s", e, exc_info=True)

    logger.info("Agent stopped")

    # Cleanup
    await push_listener.stop()
    if ipc_server is not None:
        ipc_server.should_exit = True


if __name__ == "__main__":
    asyncio.run(run_agent())

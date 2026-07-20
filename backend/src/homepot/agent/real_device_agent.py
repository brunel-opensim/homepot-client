"""Real device agent runtime for registration, heartbeat, telemetry, and IPC."""

import asyncio
import json
import logging
import os
from pathlib import Path
import threading
from typing import Any, Dict, Optional, cast

import httpx
from uvicorn import Config, Server

from homepot.agent.credential_storage import create_credential_storage
from homepot.agent.identity import get_or_create_device_id
from homepot.agent.utils.device_dna import get_local_ip, get_mac_address, get_wan_ip
from homepot.agent.utils.heartbeat import build_heartbeat_payload
from homepot.agent.utils.local_ipc import (
    LocalAgentState,
    create_local_ipc_app,
    update_local_agent_state,
)
from homepot.agent.utils.real_device_discovery import get_connected_peripherals
from homepot.agent.utils.retry_queue import RetryQueue
from homepot.agent.utils.telemetry import build_telemetry_payload

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG_PATH = Path(__file__).parent / "agent-config.json"


def _config_path() -> Path:
    override = os.environ.get("HOMEPOT_AGENT_CONFIG")
    if override:
        return Path(override)
    return _DEFAULT_CONFIG_PATH


def load_agent_config() -> Dict[str, Any]:
    """Load and validate the agent configuration.

    Resolution order:
    1. ``HOMEPOT_AGENT_CONFIG`` environment variable.
    2. ``agent-config.json`` shipped with the package.
    """
    config_path = _config_path()
    try:
        with config_path.open("r", encoding="utf-8") as f:
            data = cast(Dict[str, Any], json.load(f))
    except FileNotFoundError:
        logger.warning("Config not found at %s; using defaults", config_path)
        data = {}

    # Fill in device identity from the identity module if not set
    if not data.get("device_id"):
        data["device_id"] = get_or_create_device_id()
        logger.info("Using generated device identity: %s", data["device_id"])

    # Fill in credentials from credential storage if not set
    cred_storage = create_credential_storage()
    if not data.get("api_key") and cred_storage.is_provisioned():
        api_key = cred_storage.get_api_key()
        if api_key:
            data["api_key"] = api_key
            logger.info("Using API key from credential storage")
        site_id = cred_storage.get_metadata("site_id")
        if site_id and not data.get("site_id"):
            data["site_id"] = site_id

    required = ["backend_url", "device_id"]
    missing = [field for field in required if not data.get(field)]
    if missing:
        raise ValueError(
            f"Missing required config fields: {', '.join(missing)}. "
            "Set via config file or environment."
        )

    data.setdefault("api_key", "")
    data.setdefault("site_id", "")
    data.setdefault("heartbeat_interval_seconds", 30)
    data.setdefault("telemetry_interval_seconds", 30)
    data.setdefault("retry_flush_interval_seconds", 60)
    data.setdefault("ipc_enabled", True)
    data.setdefault("ipc_host", "127.0.0.1")
    data.setdefault("ipc_port", 8765)
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


async def send_registration(
    client: httpx.AsyncClient,
    config: Dict[str, Any],
    retry_queue: RetryQueue,
) -> None:
    """Send initial device registration payload with static device DNA."""
    try:
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
            payload = build_heartbeat_payload(
                config["device_id"],
                site_id=config["site_id"],
                status="ONLINE",
            )
            ok = await post_json(client, url, payload, get_auth_headers(config))
            if ok:
                if ipc_server is not None:
                    update_local_agent_state(
                        ipc_server.config.app,
                        status="ONLINE",
                        last_heartbeat=payload["timestamp"],
                    )
            else:
                retry_queue.enqueue({"url": url, "payload": payload})
                if ipc_server is not None:
                    update_local_agent_state(
                        ipc_server.config.app,
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
            payload = build_telemetry_payload(config["device_id"])
            payload["site_id"] = config["site_id"]
            ok = await post_json(client, url, payload, get_auth_headers(config))
            if ok and ipc_server is not None:
                update_local_agent_state(
                    ipc_server.config.app,
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
    """Flush queued failed payloads to backend at a fixed interval."""
    interval = int(config["retry_flush_interval_seconds"])
    while True:
        try:
            queued_items = retry_queue.dequeue_all()
            pending: list[dict] = []
            for item in queued_items:
                ok = await post_json(
                    client,
                    item["url"],
                    item["payload"],
                    get_auth_headers(config),
                )
                if not ok:
                    pending.append(item)
            if pending:
                for item in pending:
                    retry_queue.enqueue(item)
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


async def run_agent() -> None:
    """Run agent runtime tasks for registration, heartbeat, telemetry, and retry."""
    config = load_agent_config()
    retry_queue = RetryQueue()
    ipc_server = start_local_ipc_server(config)

    async with httpx.AsyncClient() as client:
        await send_registration(client, config, retry_queue)

        await asyncio.gather(
            heartbeat_loop(client, config, retry_queue, ipc_server),
            telemetry_loop(client, config, retry_queue, ipc_server),
            retry_flush_loop(client, config, retry_queue),
        )


if __name__ == "__main__":
    asyncio.run(run_agent())

#!/usr/bin/env python3
"""Shared POS device emulator engine.

Simulates a POS terminal device for end-to-end testing of the Dashboard,
User App, and device lifecycle flows without physical hardware.

The engine is OS-agnostic: the operating system only influences the device's
identity (``os_details``, mock MAC/hostname) and the permission capability map
derived from the OS string (see :func:`derive_os_capabilities`). Thin per-OS
wrappers (``linux_pos_emulator.py``, ``android_pos_emulator.py``) supply their
own identity defaults and re-export this engine.

Usage
-----
    python emulators/pos_engine.py --site-id site-it-demo1 --bootstrap-key abc123
    python emulators/pos_engine.py --config my-device.json

The emulator provisions itself via ``POST /devices/bootstrap-provision``,
then runs four concurrent loops:

- **Heartbeat** — ``POST /agent/heartbeat`` at a configurable interval
- **Telemetry** — ``POST /agent/telemetry`` with simulated CPU/memory/disk
  metrics, network latency, plus runtime uptime (``uptime_seconds``)
- **Command polling** — ``GET /devices/pending``, ACK, and respond with mock results;
  a ``status_request`` command returns a live device-status snapshot and posts it
  to the Dashboard's Live Logs tab; composed push commands (``update_pos_payment_config``,
  ``restart_pos_app``, ``health_check``, or custom actions) are applied/acknowledged,
  summarised to Live Logs, and recorded in the Push History page
- **Live logs** — ``POST /agent/logs`` with realistic POS terminal log lines
- **Audit events** — ``POST /agent/audit`` with realistic device audit events
- **Job history** — ``POST /agent/jobs`` + status updates, so the Dashboard's
  Job History tab shows live queued → completed/failed transitions
- **Alert injection** — ``POST /agent/alert`` with occasional network-latency
  spikes, so the Dashboard's Alerts tab is populated
- **Device permissions** — the emulator grants/revokes device permissions
  (``PATCH`` to the permissions endpoint) to model a device owner's consent, and
  it responds to operator-initiated ``request_permission`` push commands with a
  simulated consent decision (grant or deny) recorded to Live Logs and the
  Audit Trail. Behaviour is driven by ``--permission-consent-mode``.

Credentials are persisted to ``~/.homepot/emulators/<device_name>.json``
so the emulator survives restarts without re-provisioning.
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import random
import signal
import sys
import time
from typing import cast

import httpx

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_BACKEND_URL = "http://localhost:8000"
CREDENTIALS_DIR = Path.home() / ".homepot" / "emulators"

API_BASE_PATH = "/api/v1"

# ---------------------------------------------------------------------------
# Device permissions
# ---------------------------------------------------------------------------

ALL_PERMISSION_KEYS = [
    "root_access",
    "command_execution",
    "process_monitoring",
    "filesystem_access",
    "network_monitoring",
]

PERMISSION_CONSENT_MODES = ("auto", "fixed", "deny", "external")

COMMAND_PERMISSIONS = {
    "health_check": "command_execution",
    "restart": "root_access",
    "restart_pos_app": "command_execution",
    "run_command": "command_execution",
    "run_script": "command_execution",
    "shutdown": "root_access",
    "update_config": "filesystem_access",
    "update_pos_payment_config": "filesystem_access",
    "list_processes": "process_monitoring",
    "list_connections": "network_monitoring",
    "scan_filesystem": "filesystem_access",
}


def derive_os_capabilities(os_details: str) -> dict[str, bool]:
    """Mirror the backend's OS→capability mapping (``schemas.permissions``).

    Determines which permission keys the simulated OS can support, so the
    emulator only grants permissions the backend would accept.
    """
    keys = ALL_PERMISSION_KEYS
    if not os_details:
        return {k: False for k in keys}

    os_lower = os_details.lower()
    if any(
        kw in os_lower
        for kw in (
            "linux",
            "ubuntu",
            "debian",
            "fedora",
            "centos",
            "raspberry pi",
            "macos",
            "mac os",
            "darwin",
            "os x",
        )
    ):
        return {k: True for k in keys}
    if "android" in os_lower:
        return {
            "root_access": False,
            "process_monitoring": True,
            "filesystem_access": True,
            "network_monitoring": True,
        }
    if any(kw in os_lower for kw in ("windows", "win32", "win64")):
        return {
            "root_access": False,
            "process_monitoring": True,
            "filesystem_access": True,
            "network_monitoring": True,
        }
    if any(kw in os_lower for kw in ("ios", "ipados", "iphone os", "ipad")):
        return {
            "root_access": False,
            "process_monitoring": False,
            "filesystem_access": False,
            "network_monitoring": True,
        }
    return {k: False for k in keys}


def derive_push_channel(os_details: str) -> str | None:
    """Derive the push-notification channel the simulated OS would use.

    Mobile and push-capable OSes receive commands over a push transport
    (FCM on Android, WNS on Windows, APNs on iOS); desktop / POS runtimes
    fall back to plain HTTP polling (``None``). Mirrors how the real agent
    registers a ``device_token`` with the backend.
    """
    if not os_details:
        return None
    os_lower = os_details.lower()
    if "android" in os_lower:
        return "fcm"
    if any(kw in os_lower for kw in ("windows", "win32", "win64")):
        return "wns"
    if any(kw in os_lower for kw in ("ios", "ipados", "iphone os", "ipad")):
        return "apns"
    return None


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


@dataclass
class EmulatorConfig:
    backend_url: str = DEFAULT_BACKEND_URL
    site_id: str = ""
    bootstrap_key: str = ""
    device_name: str = "linux-pos-emulator-1"
    device_type: str = "pos_terminal"
    os_details: str = "Linux 6.8.0 (Debian 12)"
    mock_mac: str = "02:42:ac:11:00:02"
    mock_ip: str = "192.168.1.100"
    mock_hostname: str = "linux-pos-001"
    mock_firmware: str = "2.4.1"
    heartbeat_interval: float = 10.0
    telemetry_interval: float = 15.0
    command_poll_interval: float = 15.0
    push_poll_interval: float = 15.0
    logs_interval: float = 15.0
    audit_interval: float = 60.0
    jobs_interval: float = 30.0
    alerts_interval: float = 90.0
    command_failure_rate: float = 0.1
    permission_consent_mode: str = "auto"
    permission_sync_interval: float = 20.0

    @classmethod
    def from_dict(cls, d: dict) -> EmulatorConfig:
        return cls(
            backend_url=d.get("backend_url", DEFAULT_BACKEND_URL),
            site_id=d.get("site_id", ""),
            bootstrap_key=d.get("bootstrap_key", ""),
            device_name=d.get("device_name", "linux-pos-emulator-1").strip(),
            device_type=d.get("device_type", "pos_terminal"),
            os_details=d.get("os_details", "Linux 6.8.0 (Debian 12)"),
            mock_mac=d.get("mock_mac", "02:42:ac:11:00:02"),
            mock_ip=d.get("mock_ip", "192.168.1.100"),
            mock_hostname=d.get("mock_hostname", "linux-pos-001"),
            mock_firmware=d.get("mock_firmware", "2.4.1"),
            heartbeat_interval=float(d.get("heartbeat_interval_seconds", 10)),
            telemetry_interval=float(d.get("telemetry_interval_seconds", 15)),
            command_poll_interval=float(d.get("command_poll_interval_seconds", 15)),
            push_poll_interval=float(d.get("push_poll_interval_seconds", 15)),
            logs_interval=float(d.get("logs_interval_seconds", 15)),
            audit_interval=float(d.get("audit_interval_seconds", 60)),
            jobs_interval=float(d.get("jobs_interval_seconds", 30)),
            alerts_interval=float(d.get("alerts_interval_seconds", 90)),
            command_failure_rate=float(d.get("command_failure_rate", 0.1)),
            permission_consent_mode=d.get("permission_consent_mode", "auto"),
            permission_sync_interval=float(
                d.get("permission_sync_interval_seconds", 20)
            ),
        )

    def to_credentials(self, device_id: str, api_key: str) -> dict:
        return {
            "device_id": device_id,
            "api_key": api_key,
            "site_id": self.site_id,
            "device_name": self.device_name,
            "device_type": self.device_type,
            "os_details": self.os_details,
            "mock_mac": self.mock_mac,
            "mock_ip": self.mock_ip,
            "mock_hostname": self.mock_hostname,
            "mock_firmware": self.mock_firmware,
        }


# ---------------------------------------------------------------------------
# Simulated metrics
# ---------------------------------------------------------------------------


class SimulatedMetrics:
    """Generates realistic-looking system metrics that vary over time."""

    def __init__(self) -> None:
        self._cpu_baseline = random.uniform(15, 35)
        self._mem_baseline = random.uniform(40, 55)
        self._disk_baseline = random.uniform(30, 45)
        self._latency_baseline = random.uniform(3, 12)
        self._tick = 0

    def sample(self) -> dict[str, float]:
        self._tick += 1

        cpu = self._cpu_baseline + random.gauss(0, 8)
        if self._tick % random.randint(15, 30) == 0:
            cpu += random.uniform(30, 55)
        cpu = max(0, min(100, cpu))

        mem = self._mem_baseline + random.gauss(0, 3)
        mem = max(0, min(100, mem))

        disk = self._disk_baseline + random.gauss(0, 1.5)
        disk = max(0, min(100, disk))

        latency = self._latency_baseline + random.gauss(0, 2.5)
        if self._tick % random.randint(30, 60) == 0:
            latency += random.uniform(20, 80)
        latency = max(1, latency)

        return {
            "cpu_usage": round(cpu, 1),
            "memory_usage": round(mem, 1),
            "disk_usage": round(disk, 1),
            "network_latency_ms": round(latency, 1),
        }


# ---------------------------------------------------------------------------
# Credential persistence
# ---------------------------------------------------------------------------


def _credentials_path(name: str) -> Path:
    return CREDENTIALS_DIR / f"{name}.json"


def load_credentials(device_name: str) -> dict | None:
    path = _credentials_path(device_name)
    if path.exists():
        try:
            return cast(dict, json.loads(path.read_text()))
        except (json.JSONDecodeError, OSError):
            return None
    return None


def save_credentials(device_name: str, data: dict) -> None:
    CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
    path = _credentials_path(device_name)
    path.write_text(json.dumps(data, indent=2))
    path.chmod(0o600)


# ---------------------------------------------------------------------------
# Emulator
# ---------------------------------------------------------------------------


class POSEmulator:
    """Runs a simulated POS device lifecycle against the backend."""

    def __init__(
        self,
        config: EmulatorConfig,
        banner: str = "HOMEPOT POS Emulator",
    ) -> None:
        self.config = config
        self._banner = banner
        self._device_id: str | None = None
        self._api_key: str | None = None
        self._shutdown_event = asyncio.Event()
        self._metrics = SimulatedMetrics()
        self._started = time.monotonic()
        self._config_version: str = "1.0.1"
        self._applied_config: dict[str, object] = {}
        self._app_restarts: int = 0
        self._capabilities: dict[str, bool] = derive_os_capabilities(config.os_details)
        self._push_channel: str | None = derive_push_channel(config.os_details)
        self._push_token: str | None = (
            self._new_push_token() if self._push_channel else None
        )
        self._granted: dict[str, bool] = {k: False for k in ALL_PERMISSION_KEYS}
        self._http: httpx.AsyncClient

    @property
    def device_id(self) -> str:
        assert self._device_id is not None
        return self._device_id

    @property
    def api_key(self) -> str:
        assert self._api_key is not None
        return self._api_key

    @property
    def _backend(self) -> str:
        return self.config.backend_url.rstrip("/") + API_BASE_PATH

    def _headers(self) -> dict[str, str]:
        return {"X-Device-ID": self.device_id, "X-API-Key": self.api_key}

    # --
    # OS-specific behavior hooks
    # --

    @property
    def push_channel(self) -> str | None:
        """Name of the push transport this OS uses (``fcm``/``wns``/``apns``)."""
        return self._push_channel

    @property
    def push_token(self) -> str | None:
        """Synthetic push registration token (only for push-capable OSes)."""
        return self._push_token

    def _new_push_token(self) -> str:
        """Generate a fake push registration token for the used channel."""
        channel = self._push_channel or "push"
        prefix = {
            "fcm": "fcm:emulator",
            "wns": "https://wns.notify.windows.com/?token=emulator",
            "apns": "apns://emulator",
        }.get(channel, "push:emulator")
        suffix = hex(random.getrandbits(64))[2:]
        return f"{prefix}:{suffix}"

    def _push_delivery_note(self, command_type: str) -> str | None:
        """OS-specific push behavior: how a command was delivered.

        Returns a short human-readable delivery note, or ``None`` when the
        device has no push channel (plain HTTP polling).
        """
        if not self._push_channel:
            return None
        channel = {
            "fcm": "pushed via FCM",
            "wns": "pushed via WNS",
            "apns": "pushed via APNs",
        }.get(self._push_channel, "pushed")
        return f"{command_type} {channel}"

    # --
    # Device permissions
    # --

    def _default_permission_grants(self) -> dict[str, bool]:
        """Consent granted at boot for the current mode and OS."""
        if self.config.permission_consent_mode == "deny":
            return {k: False for k in ALL_PERMISSION_KEYS}
        # ``auto`` and ``fixed`` start by granting every supported permission.
        return {k: bool(self._capabilities.get(k, False)) for k in ALL_PERMISSION_KEYS}

    async def _refresh_device_permissions(self) -> bool:
        try:
            resp = await self._http.get(
                f"{self._backend}/devices/device/{self.device_id}/permissions",
                headers=self._headers(),
            )
            if resp.status_code >= 400:
                print(f"  [permissions] refresh error: {resp.status_code}")
                return False
            data = resp.json().get("data", {})
            permissions = data.get("permissions", {})
            if not isinstance(permissions, dict):
                return False
            self._granted = {
                key: bool(permissions.get(key, False)) for key in ALL_PERMISSION_KEYS
            }
            return True
        except httpx.RequestError as exc:
            print(f"  [permissions] refresh connection error: {exc}")
            return False

    def _permission_denial(self, command_type: str, payload: object) -> str | None:
        required: list[str] = []
        base_permission = COMMAND_PERMISSIONS.get(command_type)
        if base_permission:
            required.append(base_permission)
        payload_dict = payload if isinstance(payload, dict) else {}
        data = payload_dict.get("data")
        command_data = data if isinstance(data, dict) else payload_dict
        if command_type in ("run_command", "run_script") and command_data.get(
            "run_as_root", False
        ):
            required.append("root_access")
        missing = [key for key in required if not self._granted.get(key, False)]
        if missing:
            return f"Permission denied: {', '.join(missing)} not granted"
        return None

    def _consent_for_request(self) -> bool:
        """Whether the simulated owner consents to an operator permission request."""
        if self.config.permission_consent_mode == "deny":
            return False
        if self.config.permission_consent_mode == "fixed":
            return True
        # ``auto``: mostly consent, occasionally deny to exercise the prompt path.
        return random.random() < 0.8

    async def _update_device_permissions(self, changes: dict[str, bool]) -> None:
        """PATCH the device's permission grants to the backend (device-cred auth)."""
        try:
            resp = await self._http.patch(
                f"{self._backend}/devices/device/{self.device_id}/permissions",
                json={"permissions": changes},
                headers=self._headers(),
            )
            if resp.status_code >= 400:
                print(
                    f"  [permissions] update error: {resp.status_code} {resp.text[:120]}"
                )
            else:
                print(f"  [permissions] synced: {changes}")
        except httpx.RequestError as exc:
            print(f"  [permissions] update connection error: {exc}")

    async def _report_permission_audit(
        self, permission: str, granted: bool, actor: str, action: str
    ) -> None:
        """Post a permission-related event to the Dashboard Audit Trail."""
        verb = "granted" if granted else "denied"
        description = f"Permission '{permission}' {verb} ({action}) by {actor}"
        try:
            resp = await self._http.post(
                f"{self._backend}/agent/audit",
                json={
                    "device_id": self.device_id,
                    "event_type": "permission_change",
                    "description": description,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                headers=self._headers(),
            )
            if resp.status_code >= 400:
                print(
                    f"  [permissions] audit error: {resp.status_code} {resp.text[:120]}"
                )
            else:
                print(f"  [permissions] {description}")
        except httpx.RequestError as exc:
            print(f"  [permissions] audit connection error: {exc}")

    async def _apply_permission_result(
        self, result: dict, payload: dict | None
    ) -> None:
        """Persist an operator-initiated permission request outcome on the device."""
        res = result.get("result")
        if not isinstance(res, dict):
            return
        permission = res.get("permission")
        if not permission or permission not in ALL_PERMISSION_KEYS:
            return
        action = res.get("action", "grant")
        granted = bool(res.get("granted"))
        data = payload.get("data") if payload else None
        data = data if isinstance(data, dict) else {}
        requested_by = data.get("requested_by") or "HOMEPOT operator"

        self._granted[permission] = granted
        await self._update_device_permissions({permission: granted})
        await self._report_permission_audit(permission, granted, requested_by, action)

    async def _apply_default_consent(self) -> None:
        if self.config.permission_consent_mode == "external":
            await self._refresh_device_permissions()
            print("  [permissions] consent managed by User App")
            return
        self._granted = self._default_permission_grants()
        await self._update_device_permissions(dict(self._granted))
        print(
            "  [permissions] consent: "
            + " ".join(f"{k}={v}" for k, v in self._granted.items())
        )

    async def _consent_loop(self) -> None:
        """Device-initiated consent: the device owner toggles grants over time."""
        while not self._shutdown_event.is_set():
            try:
                if self.config.permission_consent_mode == "auto":
                    supported = [
                        k for k in ALL_PERMISSION_KEYS if self._capabilities.get(k)
                    ]
                    if supported and random.random() < 0.6:
                        key = random.choice(supported)
                        grant = random.random() < 0.6
                        if self._granted.get(key, False) != grant:
                            self._granted[key] = grant
                            await self._update_device_permissions({key: grant})
                            verb = "granted" if grant else "revoked"
                            print(f"  [permissions] device {verb} {key}")
            except httpx.RequestError as exc:
                print(f"  [permissions] connection error: {exc}")

            await self._wait_or_shutdown(self.config.permission_sync_interval)

    # --
    # Provisioning
    # --

    def _try_restore(self) -> bool:
        creds = load_credentials(self.config.device_name)
        if creds and creds.get("device_id") and creds.get("api_key"):
            self._device_id = creds["device_id"]
            self._api_key = creds["api_key"]
            self.config.site_id = creds.get("site_id", self.config.site_id)
            print(f"  Restored credentials for device {self._device_id}")
            return True
        return False

    async def _provision(self) -> None:
        print("  Provisioning via bootstrap-provision ...")
        payload = {
            "site_id": self.config.site_id,
            "bootstrap_key": self.config.bootstrap_key,
            "device_name": self.config.device_name,
            "device_type": self.config.device_type,
            "os_details": self.config.os_details,
            "provisioning_source": "emulator",
        }
        resp = await self._http.post(
            f"{self._backend}/devices/bootstrap-provision", json=payload
        )
        if resp.status_code >= 400:
            body = resp.json()
            detail = body.get("detail", resp.text)
            raise RuntimeError(f"Provisioning failed ({resp.status_code}): {detail}")

        data = resp.json()["data"]
        self._device_id = data["device_id"]
        self._api_key = data["api_key"]
        self.config.site_id = data["site_id"]

        save_credentials(
            self.config.device_name,
            self.config.to_credentials(self._device_id, self._api_key),
        )
        print(f"  Provisioned device {self._device_id}")

        await self._register_dna()

    async def _register_dna(self) -> None:
        print("  Registering device DNA ...")
        payload = {
            "device_id": self.device_id,
            "mac_address": self.config.mock_mac,
            "local_ip": self.config.mock_ip,
            "os_details": self.config.os_details,
            "firmware_version": self.config.mock_firmware,
            "site_id": self.config.site_id,
            "device_name": self.config.device_name,
            "device_type": self.config.device_type,
            "device_source": "emulator",
            "device_token": self._push_token,
        }
        resp = await self._http.post(
            f"{self._backend}/agent/device-dna", json=payload, headers=self._headers()
        )
        if resp.status_code >= 400:
            print(
                f"  [dna] warning: registration returned {resp.status_code}: {resp.text[:120]}"
            )
        else:
            print(
                "  Registered DNA:"
                f" hostname={self.config.mock_hostname}"
                f", MAC={self.config.mock_mac}, IP={self.config.mock_ip}"
            )

    # --
    # Loops
    # --

    async def _heartbeat_loop(self) -> None:
        while not self._shutdown_event.is_set():
            try:
                payload = {
                    "device_id": self.device_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                resp = await self._http.post(
                    f"{self._backend}/agent/heartbeat",
                    json=payload,
                    headers=self._headers(),
                )
                if resp.status_code >= 400:
                    print(f"  [heartbeat] error: {resp.status_code} {resp.text[:120]}")
                else:
                    print(
                        f"  [heartbeat] OK  ({datetime.now(timezone.utc).strftime('%H:%M:%S')})"
                    )
            except httpx.RequestError as exc:
                print(f"  [heartbeat] connection error: {exc}")

            await self._wait_or_shutdown(self.config.heartbeat_interval)

    async def _telemetry_loop(self) -> None:
        while not self._shutdown_event.is_set():
            try:
                metrics = self._metrics.sample()
                uptime_seconds = int(time.monotonic() - self._started)
                payload = {
                    "device_id": self.device_id,
                    **metrics,
                    "uptime_seconds": uptime_seconds,
                    "collection_interval_seconds": int(self.config.telemetry_interval),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                resp = await self._http.post(
                    f"{self._backend}/agent/telemetry",
                    json=payload,
                    headers=self._headers(),
                )
                if resp.status_code >= 400:
                    print(f"  [telemetry] error: {resp.status_code} {resp.text[:120]}")
                else:
                    print(
                        "  [telemetry] OK"
                        f" cpu={metrics['cpu_usage']}%"
                        f" mem={metrics['memory_usage']}%"
                        f" disk={metrics['disk_usage']}%"
                        f" net={metrics['network_latency_ms']}ms"
                        f" uptime={uptime_seconds}s"
                    )
            except httpx.RequestError as exc:
                print(f"  [telemetry] connection error: {exc}")

            await self._wait_or_shutdown(self.config.telemetry_interval)

    def _next_log_entry(self, tick: int) -> tuple[str, str, str]:
        m = self._metrics.sample()
        info_entries = [
            ("info", "device", "Heartbeat acknowledged by HOMEPOT backend"),
            (
                "info",
                "telemetry",
                "Telemetry report sent"
                f" (cpu={m['cpu_usage']:.1f}%, mem={m['memory_usage']:.1f}%,"
                f" disk={m['disk_usage']:.1f}%)",
            ),
            ("info", "payment", "Payment gateway connection healthy"),
            ("info", "printer", "Receipt printer queue OK - 0 pending jobs"),
            ("info", "network", f"Network link up (eth0, {self.config.mock_ip})"),
            (
                "info",
                "device",
                f"Device DNA verified: hostname={self.config.mock_hostname}",
            ),
        ]
        warning_entries = [
            ("warning", "payment", "Payment gateway latency elevated (1.2s)"),
            ("warning", "printer", "Receipt printer paper low"),
            ("warning", "network", "WAN link flapping detected"),
            ("warning", "device", "Clock skew detected, resyncing NTP"),
        ]
        error_entries = [
            ("error", "payment", "Payment gateway timeout while authorising card"),
            ("error", "network", "Connection to backend lost, retrying"),
            ("error", "device", "Unhandled exception in checkout service"),
        ]

        if tick > 0 and tick % random.randint(10, 20) == 0:
            return random.choice(error_entries)
        if tick % random.randint(4, 8) == 0:
            return random.choice(warning_entries)
        return random.choice(info_entries)

    async def _logs_loop(self) -> None:
        tick = 0
        while not self._shutdown_event.is_set():
            try:
                level, category, message = self._next_log_entry(tick)
                payload = {
                    "device_id": self.device_id,
                    "level": level,
                    "category": category,
                    "message": message,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                resp = await self._http.post(
                    f"{self._backend}/agent/logs",
                    json=payload,
                    headers=self._headers(),
                )
                if resp.status_code >= 400:
                    print(f"  [logs] error: {resp.status_code} {resp.text[:120]}")
                else:
                    print(f"  [logs] {level}: {message[:60]}")
            except httpx.RequestError as exc:
                print(f"  [logs] connection error: {exc}")

            tick += 1
            await self._wait_or_shutdown(self.config.logs_interval)

    def _next_audit_entry(self, tick: int) -> tuple[str, str]:
        if tick == 0:
            return (
                "agent_started",
                f"HOMEPOT agent started on {self.config.mock_hostname}",
            )
        routine = [
            (
                "health_check_performed",
                "Routine health check completed (cpu, memory, disk, network)",
            ),
            ("config_update_applied", "Config updated: heartbeat interval set to 10s"),
            ("device_status_changed", "Device status changed from offline to online"),
            (
                "push_notification_sent",
                "Push notification delivered to employee device",
            ),
            ("api_access", "Authenticated agent API request completed successfully"),
        ]
        anomalies = [
            ("error_occurred", "Payment gateway timeout during card authorisation"),
            ("error_occurred", "Connection to backend lost and recovered"),
        ]
        if tick % random.randint(8, 15) == 0:
            return random.choice(anomalies)
        return random.choice(routine)

    async def _audit_loop(self) -> None:
        tick = 0
        while not self._shutdown_event.is_set():
            try:
                event_type, description = self._next_audit_entry(tick)
                payload = {
                    "device_id": self.device_id,
                    "event_type": event_type,
                    "description": description,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                resp = await self._http.post(
                    f"{self._backend}/agent/audit",
                    json=payload,
                    headers=self._headers(),
                )
                if resp.status_code >= 400:
                    print(f"  [audit] error: {resp.status_code} {resp.text[:120]}")
                else:
                    print(f"  [audit] {event_type}: {description[:60]}")
            except httpx.RequestError as exc:
                print(f"  [audit] connection error: {exc}")

            tick += 1
            await self._wait_or_shutdown(self.config.audit_interval)

    def _next_job_action(self) -> str:
        return random.choice(
            [
                "Update POS payment config",
                "Rotate API credentials",
                "Sync device time (NTP)",
                "Run diagnostic suite",
                "Update firmware",
                "Clear application cache",
                "Restart payment service",
                "Backup transaction log",
            ]
        )

    def _next_job_outcome(self) -> tuple[str, dict | None, str | None]:
        if random.random() < 0.8:
            return (
                "completed",
                {"message": "Job executed successfully", "exit_code": 0},
                None,
            )
        return (
            "failed",
            None,
            "Timeout waiting for payment gateway",
        )

    async def _create_job(self) -> str | None:
        action = self._next_job_action()
        payload = {
            "device_id": self.device_id,
            "action": action,
            "description": f"Automated background task: {action}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        resp = await self._http.post(
            f"{self._backend}/agent/jobs",
            json=payload,
            headers=self._headers(),
        )
        if resp.status_code >= 400:
            print(f"  [jobs] create error: {resp.status_code} {resp.text[:120]}")
            return None
        data = resp.json().get("data", {})
        job_id = data.get("job_id")
        print(f"  [jobs] queued '{action}' ({str(job_id)[:8]}...)")
        return str(job_id) if job_id is not None else None

    async def _update_job(
        self,
        job_id: str,
        status: str,
        result: dict | None,
        error_message: str | None,
    ) -> None:
        payload = {
            "device_id": self.device_id,
            "status": status,
            "result": result,
            "error_message": error_message,
        }
        resp = await self._http.put(
            f"{self._backend}/agent/jobs/{job_id}",
            json=payload,
            headers=self._headers(),
        )
        if resp.status_code >= 400:
            print(f"  [jobs] update error: {resp.status_code} {resp.text[:120]}")
        else:
            print(f"  [jobs] {str(job_id)[:8]} -> {status}")

    async def _jobs_loop(self) -> None:
        current_job: str | None = None
        while not self._shutdown_event.is_set():
            try:
                if current_job:
                    status, result, error = self._next_job_outcome()
                    await self._update_job(current_job, status, result, error)
                current_job = await self._create_job()
            except httpx.RequestError as exc:
                print(f"  [jobs] connection error: {exc}")

            await self._wait_or_shutdown(self.config.jobs_interval)

    async def _alerts_loop(self) -> None:
        while not self._shutdown_event.is_set():
            try:
                if random.random() < 0.4:
                    latency = round(random.uniform(250, 900), 1)
                    severity = "critical" if latency > 500 else "warning"
                    payload = {
                        "device_id": self.device_id,
                        "title": f"High Latency: {latency:.0f}ms",
                        "description": (
                            f"Network latency exceeded threshold: {latency:.0f}ms "
                            "observed on primary interface"
                        ),
                        "severity": severity,
                        "category": "network",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                    resp = await self._http.post(
                        f"{self._backend}/agent/alert",
                        json=payload,
                        headers=self._headers(),
                    )
                    if resp.status_code >= 400:
                        print(f"  [alerts] error: {resp.status_code} {resp.text[:120]}")
                    else:
                        print(
                            f"  [alerts] injected '{payload['title']}'" f" ({severity})"
                        )
                else:
                    print("  [alerts] no anomaly this cycle")
            except httpx.RequestError as exc:
                print(f"  [alerts] connection error: {exc}")

            await self._wait_or_shutdown(self.config.alerts_interval)

    async def _command_poll_loop(self) -> None:
        while not self._shutdown_event.is_set():
            try:
                resp = await self._http.get(
                    f"{self._backend}/devices/pending", headers=self._headers()
                )
                if resp.status_code >= 400:
                    print(
                        f"  [commands] poll error: {resp.status_code} {resp.text[:120]}"
                    )
                    await self._wait_or_shutdown(self.config.command_poll_interval)
                    continue

                commands = resp.json()
                if not commands:
                    print(
                        f"  [commands] none pending ({datetime.now(timezone.utc).strftime('%H:%M:%S')})"
                    )
                else:
                    print(f"  [commands] {len(commands)} pending")
                    for cmd in commands:
                        await self._handle_command(cmd)
            except httpx.RequestError as exc:
                print(f"  [commands] connection error: {exc}")

            await self._wait_or_shutdown(self.config.command_poll_interval)

    async def _push_loop(self) -> None:
        """Poll undelivered push notifications and model the delivery lifecycle.

        The dashboard sends non-executable notifications via the backend, which
        persists them as ``sent``. This loop picks them up and acks them so the
        lifecycle advances to ``delivered`` (with latency) exactly like a real
        push-capable agent.
        """
        while not self._shutdown_event.is_set():
            try:
                resp = await self._http.get(
                    f"{self._backend}/push/pending", headers=self._headers()
                )
                if resp.status_code >= 400:
                    print(f"  [push] poll error: {resp.status_code} {resp.text[:120]}")
                    await self._wait_or_shutdown(self.config.push_poll_interval)
                    continue

                body = resp.json()
                pushes = body.get("pushes", []) if isinstance(body, dict) else []
                if not pushes:
                    print(
                        f"  [push] none pending ({datetime.now(timezone.utc).strftime('%H:%M:%S')})"
                    )
                else:
                    print(f"  [push] {len(pushes)} pending")
                    for push in pushes:
                        await self._deliver_push(push)
            except httpx.RequestError as exc:
                print(f"  [push] connection error: {exc}")

            await self._wait_or_shutdown(self.config.push_poll_interval)

    async def _deliver_push(self, push: dict) -> None:
        message_id = push.get("message_id", "")
        payload = push.get("payload")
        payload = payload if isinstance(payload, dict) else {}
        title = payload.get("title") or "Push notification"
        body = payload.get("body") or ""
        channel = self._push_delivery_note("push")

        await asyncio.sleep(random.uniform(0.2, 1.5))
        failed = self._command_should_fail()
        received_at = datetime.now(timezone.utc).isoformat()
        ack = {
            "message_id": message_id,
            "device_id": self.device_id,
            "status": "failed" if failed else "delivered",
        }
        if not failed:
            ack["received_at"] = received_at
        else:
            ack["error_message"] = random.choice(
                [
                    "Client connection lost before delivery",
                    "Message dropped by push service",
                ]
            )

        resp = await self._http.post(
            f"{self._backend}/push/ack",
            json=ack,
            headers=self._headers(),
        )
        if resp.status_code >= 400:
            print(
                f"  [push] ack failed for {message_id}: {resp.status_code} {resp.text[:120]}"
            )
            return

        note = f" [{channel}]" if channel else ""
        if failed:
            print(
                f"  [push] delivery FAILED for {message_id}{note}: {ack['error_message']}"
            )
        else:
            print(f"  [push] delivered {title!r}{note} ({message_id[:8]})")

        await self._report_push_log(payload, title, body, failed)

    async def _report_push_log(
        self, payload: dict, title: str, body: str, failed: bool
    ) -> None:
        extra = ""
        if body:
            extra = f" | {body[:120]}"
        if payload.get("action") and payload.get("action") != "notification":
            extra += f" | action={payload['action']}"
        message = (
            f"Push notification delivered: {title}{extra}"
            if not failed
            else f"Push notification delivery failed: {title}"
        )
        log_payload = {
            "device_id": self.device_id,
            "level": "error" if failed else "info",
            "category": "push",
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        resp = await self._http.post(
            f"{self._backend}/agent/logs",
            json=log_payload,
            headers=self._headers(),
        )
        if resp.status_code >= 400:
            print(f"  [push] log failed: {resp.status_code} {resp.text[:120]}")
        else:
            print("  [push] delivery logged to Live Logs")

    async def _handle_command(self, cmd: dict) -> None:
        cid = cmd["command_id"]
        ctype = cmd["command_type"]
        note = self._push_delivery_note(ctype)
        print(
            f"  [commands] processing {ctype} ({cid})" + (f" [{note}]" if note else "")
        )

        try:
            if (
                ctype == "request_permission"
                and self.config.permission_consent_mode == "external"
            ):
                return

            payload = cmd.get("payload")
            denial: str | None
            if not await self._refresh_device_permissions():
                denial = "Permission state unavailable"
            else:
                denial = self._permission_denial(ctype, payload)
            if denial:
                status_resp = await self._http.put(
                    f"{self._backend}/devices/{cid}/status",
                    json={"status": "failed", "result": {"error": denial}},
                    headers=self._headers(),
                )
                print(f"  [commands] rejected {ctype}: {denial}")
                if status_resp.status_code >= 400:
                    print(
                        f"  [commands] rejection update failed: {status_resp.status_code}"
                    )
                return

            ack_resp = await self._http.post(
                f"{self._backend}/devices/{self.device_id}/commands/{cid}/ack",
                headers=self._headers(),
            )
            if ack_resp.status_code >= 400:
                print(f"  [commands] ack failed for {cid}: {ack_resp.status_code}")
                return

            status_report = None
            if ctype == "status_request":
                status_report = self._status_report()

            simulated_result = self._simulate_command_result(
                ctype, status_report, payload
            )
            if ctype == "status_request":
                await self._report_status_log(
                    status_report if status_report is not None else {}
                )
            elif ctype == "request_permission":
                payload_dict = payload if isinstance(payload, dict) else {}
                await self._apply_permission_result(simulated_result, payload_dict)
                await self._report_command_log(ctype, payload_dict, simulated_result)
            elif payload:
                await self._report_command_log(ctype, payload, simulated_result)
                await self._record_push_history(ctype, payload, simulated_result)
            await asyncio.sleep(2)

            status_resp = await self._http.put(
                f"{self._backend}/devices/{cid}/status",
                json=simulated_result,
                headers=self._headers(),
            )
            if status_resp.status_code >= 400:
                print(
                    "  [commands] status update failed"
                    f" for {cid}: {status_resp.status_code} {status_resp.text[:120]}"
                )
            else:
                status = simulated_result.get("status", "completed")
                print(f"  [commands] {ctype} -> {status} ({cid})")
        except httpx.RequestError as exc:
            print(f"  [commands] error processing {cid}: {exc}")

    def _format_uptime(self, seconds: float) -> str:
        total = int(seconds)
        parts: list[str] = []
        for label, divisor in (("d", 86400), ("h", 3600), ("m", 60), ("s", 1)):
            value, total = divmod(total, divisor)
            if parts or value or label == "s":
                parts.append(f"{value}{label}")
        return " ".join(parts)

    def _status_report(self) -> dict[str, object]:
        """Build a live status snapshot from the emulator's current state."""
        metrics = self._metrics.sample()
        return {
            "device_id": self.device_id,
            "device_name": self.config.device_name,
            "device_type": self.config.device_type,
            "status": "online",
            "connectivity_state": "online",
            "hostname": self.config.mock_hostname,
            "os_details": self.config.os_details,
            "push_channel": self._push_channel,
            "push_token": self._push_token,
            "local_ip": self.config.mock_ip,
            "mac_address": self.config.mock_mac,
            "firmware_version": self.config.mock_firmware,
            "uptime_seconds": round(time.monotonic() - self._started, 1),
            "cpu_usage": metrics["cpu_usage"],
            "memory_usage": metrics["memory_usage"],
            "disk_usage": metrics["disk_usage"],
            "network_latency_ms": metrics["network_latency_ms"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def _report_status_log(self, report: dict[str, object]) -> None:
        payload = {
            "device_id": self.device_id,
            "level": "info",
            "category": "status",
            "message": (
                "Status report: ONLINE | uptime "
                f"{self._format_uptime(cast(float, report['uptime_seconds']))} | "
                f"cpu {report['cpu_usage']}% | mem {report['memory_usage']}% | "
                f"disk {report['disk_usage']}% | "
                f"net {report['network_latency_ms']}ms | "
                f"fw {report['firmware_version']} | {report['local_ip']}"
            ),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        resp = await self._http.post(
            f"{self._backend}/agent/logs",
            json=payload,
            headers=self._headers(),
        )
        if resp.status_code >= 400:
            print(
                f"  [commands] status log failed: {resp.status_code} {resp.text[:120]}"
            )
        else:
            print("  [commands] status report sent to Live Logs")

    async def _report_command_log(
        self, command_type: str, payload: dict[str, object], result: dict
    ) -> None:
        data = payload.get("data")
        data = data if isinstance(data, dict) else {}
        label = data.get("command") or command_type
        params = [
            f"{k}={v}"
            for k, v in data.items()
            if k not in ("command", "timestamp", "config_url", "config_version")
        ]
        res = result.get("result")
        outcome = (
            res.get("message")
            if isinstance(res, dict) and res.get("message")
            else result.get("status", "completed")
        )
        failed = result.get("status") != "completed"
        message = f"Command received: {label} ({command_type})"
        if params:
            message += " | " + " ".join(params)
        if outcome:
            message += f" | {outcome}"
        payload_log = {
            "device_id": self.device_id,
            "level": "error" if failed else "info",
            "category": "command",
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        resp = await self._http.post(
            f"{self._backend}/agent/logs",
            json=payload_log,
            headers=self._headers(),
        )
        if resp.status_code >= 400:
            print(
                f"  [commands] command log failed: {resp.status_code} {resp.text[:120]}"
            )
        else:
            print("  [commands] command log sent to Live Logs")

    async def _record_push_history(
        self, command_type: str, payload: dict[str, object], result: dict
    ) -> None:
        data = payload.get("data")
        data = data if isinstance(data, dict) else {}
        label = data.get("command") or command_type
        failed = result.get("status") != "completed"
        if failed:
            change_reason = f"Push command {label} ({command_type}) failed"
        else:
            change_reason = f"Push command {label} ({command_type}) executed"
        record = {
            "device_id": self.device_id,
            "action": command_type,
            "parameter_name": f"push_command:{label}",
            "old_value": None,
            "new_value": {
                "command": label,
                "action": command_type,
                "version": data.get("config_version") or data.get("version") or "v1",
                "result": result.get("result"),
            },
            "success": not failed,
            "change_reason": change_reason,
        }
        resp = await self._http.post(
            f"{self._backend}/agent/config-history",
            json=record,
            headers=self._headers(),
        )
        if resp.status_code >= 400:
            print(
                "  [commands] push history record failed:"
                f" {resp.status_code} {resp.text[:120]}"
            )
        else:
            print("  [commands] push history recorded")

    def _simulate_command_result(
        self,
        command_type: str,
        status_report: dict[str, object] | None = None,
        payload: dict[str, object] | None = None,
    ) -> dict:
        if command_type == "status_request":
            return {
                "status": "completed",
                "result": (
                    status_report
                    if status_report is not None
                    else self._status_report()
                ),
            }

        data = payload.get("data") if payload else None
        data = data if isinstance(data, dict) else {}

        if command_type == "request_permission":
            permission = data.get("permission")
            if not permission or permission not in ALL_PERMISSION_KEYS:
                return self._fail_result(
                    "Permission request failed",
                    f"Unknown permission: {permission!r}",
                )
            if not self._capabilities.get(permission, False):
                return self._fail_result(
                    "Permission request failed",
                    f"Permission '{permission}' is not supported by this OS",
                )

            action = data.get("action", "grant")
            if action == "revoke":
                granted = False
                message = f"Permission '{permission}' revoked by request"
            elif action == "deny":
                granted = False
                self._granted[permission] = False
                message = f"Consent refused for '{permission}'"
            else:
                granted = self._consent_for_request()
                self._granted[permission] = granted
                message = (
                    f"Permission '{permission}' "
                    f"{'granted' if granted else 'denied by user'}"
                )
            return {
                "status": "completed",
                "result": {
                    "permission": permission,
                    "action": action,
                    "granted": granted,
                    "message": message,
                },
            }

        if command_type == "update_pos_payment_config":
            if self._command_should_fail():
                return self._fail_result(
                    "Configuration update failed",
                    random.choice(
                        [
                            "Configuration download failed: Connection timeout",
                            "Configuration validation failed: "
                            "Invalid payment gateway settings",
                        ]
                    ),
                )
            params = {
                k: v
                for k, v in data.items()
                if k not in ("command", "timestamp", "config_url", "config_version")
            }
            self._config_version = str(
                data.get("config_version") or self._config_version
            )
            self._applied_config = dict(params)
            return {
                "status": "completed",
                "result": {
                    "message": "Configuration applied successfully",
                    "config_url": data.get("config_url", ""),
                    "config_version": self._config_version,
                    "applied_settings": self._applied_config,
                },
            }

        if command_type == "restart_pos_app":
            if self._command_should_fail():
                return self._fail_result(
                    "POS application restart failed",
                    "Service dependency error: pos-svc on localhost:9100 unreachable",
                )
            self._app_restarts += 1
            return {
                "status": "completed",
                "result": {
                    "message": f"POS application restarted (restart #{self._app_restarts})",
                    "delay_seconds": data.get("delay_seconds", 10),
                },
            }

        if command_type == "health_check":
            tests = data.get("tests") or ["network", "storage", "memory"]
            test_results: dict[str, object] = {}
            for test in tests if isinstance(tests, list) else [tests]:
                name = str(test)
                passed = random.random() < 0.9
                test_results[name] = (
                    "pass"
                    if passed
                    else f"fail: {random.choice(['timeout', 'resource exhausted', 'io error'])}"
                )
            healthy = all(v == "pass" for v in test_results.values())
            if not healthy:
                return self._fail_result(
                    "Diagnostics failed",
                    "; ".join(
                        f"{k}={v}" for k, v in test_results.items() if v != "pass"
                    ),
                    details={"tests": test_results, "healthy": False},
                )
            return {
                "status": "completed",
                "result": {
                    "message": "Diagnostics completed",
                    "tests": test_results,
                    "healthy": healthy,
                },
            }

        if command_type == "list_processes":
            if self._command_should_fail():
                return self._fail_result(
                    "Process listing failed", "Unable to read process table"
                )
            processes = [
                {"pid": 1, "name": "launchd", "cpu": 0.2, "mem": 1.1},
                {"pid": 118, "name": "pos-svc", "cpu": 2.4, "mem": 12.8},
                {"pid": 320, "name": "WindowServer", "cpu": 1.8, "mem": 9.3},
            ]
            max_results = int(data.get("max_results") or 50)
            processes = processes[: max(1, min(max_results, len(processes)))]
            return {
                "status": "completed",
                "result": {
                    "message": f"Listed {len(processes)} processes",
                    "processes": processes,
                },
            }

        if command_type == "list_connections":
            if self._command_should_fail():
                return self._fail_result(
                    "Connection listing failed", "Unable to read network table"
                )
            connections = [
                {
                    "proto": "tcp",
                    "local": "192.168.1.100:8000",
                    "peer": "192.168.1.176:51123",
                    "state": "ESTABLISHED",
                },
                {
                    "proto": "tcp",
                    "local": "192.168.1.100:53",
                    "peer": "8.8.8.8:53",
                    "state": "ESTABLISHED",
                },
            ]
            state_filter = data.get("filter_state")
            if state_filter:
                connections = [c for c in connections if c["state"] == state_filter]
            limit = int(data.get("limit") or 100)
            connections = connections[: max(0, limit)]
            return {
                "status": "completed",
                "result": {
                    "message": f"Listed {len(connections)} network connections",
                    "connections": connections,
                },
            }

        if command_type == "scan_filesystem":
            if self._command_should_fail():
                return self._fail_result(
                    "Filesystem scan failed", "Permission denied on /var"
                )
            scan_path = data.get("path") or "/var/homepot"
            files = [
                {"path": f"{scan_path}/config.json", "size": 2048},
                {"path": f"{scan_path}/logs/app.log", "size": 65536},
            ]
            return {
                "status": "completed",
                "result": {
                    "message": f"Scanned {len(files)} files",
                    "files": files,
                },
            }

        if payload is not None:
            if self._command_should_fail():
                return self._fail_result(
                    f"Command '{command_type}' execution failed",
                    "Agent reported an internal error while processing the command",
                )
            return {
                "status": "completed",
                "result": {
                    "message": f"Command '{command_type}' received and acknowledged",
                },
            }

        outcomes = {
            "restart": {
                "status": "completed",
                "result": {
                    "message": "Device restart initiated",
                    "reboot_time_seconds": 45,
                },
            },
            "shutdown": {
                "status": "completed",
                "result": {"message": "Device shutdown initiated"},
            },
            "update_config": {
                "status": "completed",
                "result": {
                    "message": "Configuration updated successfully",
                    "applied_settings": {"log_level": "INFO"},
                },
            },
            "ping": {
                "status": "completed",
                "result": {
                    "message": "pong",
                    "latency_ms": round(random.uniform(5, 50), 1),
                },
            },
        }
        return outcomes.get(
            command_type,
            {
                "status": "completed",
                "result": {
                    "message": f"Unknown command '{command_type}' executed as no-op"
                },
            },
        )

    def _command_should_fail(self) -> bool:
        return random.random() < self.config.command_failure_rate

    def _fail_result(
        self, summary: str, reason: str, details: dict[str, object] | None = None
    ) -> dict:
        result: dict[str, object] = {"message": reason}
        if details:
            result.update(details)
        return {"status": "failed", "result": {"summary": summary, **result}}

    async def _wait_or_shutdown(self, seconds: float) -> None:
        try:
            await asyncio.wait_for(self._shutdown_event.wait(), timeout=seconds)
        except asyncio.TimeoutError:
            pass

    # --
    # Lifecycle
    # --

    async def start(self) -> None:
        print(f"\n{'=' * 60}")
        print(f"  {self._banner}")
        print(f"  Device:  {self.config.device_name}")
        print(f"  Backend: {self.config.backend_url}")
        print(
            f"  Mock DNA: hostname={self.config.mock_hostname}"
            f", MAC={self.config.mock_mac}, IP={self.config.mock_ip}"
        )
        print(f"{'=' * 60}\n")

        self._http = httpx.AsyncClient(timeout=30.0)
        try:
            if not self._try_restore():
                await self._provision()
            else:
                await self._register_dna()

            await self._apply_default_consent()

            print(f"\n  Device ID: {self.device_id}")
            print(f"  Site ID:   {self.config.site_id}")
            if self._push_channel:
                print(
                    f"  Push:      channel={self._push_channel}"
                    f", token={self._push_token}"
                )
            print(
                "\n  Starting loops"
                f" (heartbeat={self.config.heartbeat_interval}s"
                f", telemetry={self.config.telemetry_interval}s"
                f", commands={self.config.command_poll_interval}s"
                f", pushes={self.config.push_poll_interval}s"
                f", logs={self.config.logs_interval}s"
                f", audits={self.config.audit_interval}s"
                f", jobs={self.config.jobs_interval}s"
                f", alerts={self.config.alerts_interval}s"
                f", permissions={self.config.permission_sync_interval}s)"
            )
            print("  Press Ctrl+C to stop.\n")

            await asyncio.gather(
                self._heartbeat_loop(),
                self._telemetry_loop(),
                self._command_poll_loop(),
                self._push_loop(),
                self._logs_loop(),
                self._audit_loop(),
                self._jobs_loop(),
                self._alerts_loop(),
                self._consent_loop(),
            )
        finally:
            await self._http.aclose()

    def stop(self) -> None:
        self._shutdown_event.set()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(
    argv: list[str] | None = None, defaults: dict | None = None
) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="HOMEPOT POS Device Emulator")
    d = defaults or {}
    parser.add_argument("--config", "-c", type=str, help="Path to JSON config file")
    parser.add_argument("--backend-url", type=str, default=None, help="Backend URL")
    parser.add_argument(
        "--site-id", type=str, default="", help="Site ID to provision under"
    )
    parser.add_argument(
        "--bootstrap-key", type=str, default="", help="Bootstrap key for provisioning"
    )
    parser.add_argument(
        "--device-name",
        type=str,
        default=d.get("device_name", "linux-pos-emulator-1"),
        help="Device name",
    )
    parser.add_argument(
        "--os-details",
        type=str,
        default=None,
        help="Operating system label (e.g. 'Linux 6.8.0 (Debian 12)', 'Android 14')",
    )
    parser.add_argument(
        "--device-type",
        type=str,
        default=None,
        help="Device type/category (e.g. 'pos_terminal', 'tablet')",
    )
    parser.add_argument(
        "--mock-mac",
        type=str,
        default=d.get("mock_mac", "02:42:ac:11:00:02"),
        help="Mock MAC address",
    )
    parser.add_argument(
        "--mock-ip",
        type=str,
        default=d.get("mock_ip", "192.168.1.100"),
        help="Mock local IP",
    )
    parser.add_argument(
        "--mock-hostname",
        type=str,
        default=d.get("mock_hostname", "linux-pos-001"),
        help="Mock hostname",
    )
    parser.add_argument(
        "--mock-firmware",
        type=str,
        default=d.get("mock_firmware", "2.4.1"),
        help="Mock firmware version",
    )
    parser.add_argument(
        "--heartbeat-interval",
        type=float,
        default=10.0,
        help="Heartbeat interval (seconds)",
    )
    parser.add_argument(
        "--telemetry-interval",
        type=float,
        default=15.0,
        help="Telemetry interval (seconds)",
    )
    parser.add_argument(
        "--command-poll-interval",
        type=float,
        default=15.0,
        help="Command poll interval (seconds)",
    )
    parser.add_argument(
        "--push-poll-interval",
        type=float,
        default=15.0,
        help="Push notification poll interval (seconds)",
    )
    parser.add_argument(
        "--logs-interval",
        type=float,
        default=15.0,
        help="Live-log report interval (seconds)",
    )
    parser.add_argument(
        "--audit-interval",
        type=float,
        default=60.0,
        help="Audit event report interval (seconds)",
    )
    parser.add_argument(
        "--jobs-interval",
        type=float,
        default=30.0,
        help="Job history report interval (seconds)",
    )
    parser.add_argument(
        "--alerts-interval",
        type=float,
        default=90.0,
        help="Alert injection report interval (seconds)",
    )
    parser.add_argument(
        "--command-failure-rate",
        type=float,
        default=0.1,
        help="Probability (0..1) a pushed command fails on the device",
    )
    parser.add_argument(
        "--permission-consent-mode",
        type=str,
        default=None,
        choices=PERMISSION_CONSENT_MODES,
        help=(
            "How the device's owner consents to permissions: auto (mostly grant, "
            "occasionally deny, and toggles over time), fixed (grant all supported "
            "at boot and keep), or deny (refuse everything)"
        ),
    )
    parser.add_argument(
        "--permission-sync-interval",
        type=float,
        default=None,
        help="Seconds between device-initiated consent syncs",
    )
    return parser.parse_args(argv)


def build_config(
    args: argparse.Namespace, defaults: dict | None = None
) -> EmulatorConfig:
    d = defaults or {}
    if args.config:
        path = Path(args.config)
        if not path.exists():
            print(f"Config file not found: {path}", file=sys.stderr)
            sys.exit(1)
        with open(path) as f:
            cfg = json.load(f)
        config = EmulatorConfig.from_dict({**d, **cfg})
        if args.backend_url:
            config.backend_url = args.backend_url
        if args.os_details:
            config.os_details = args.os_details
        if args.device_type:
            config.device_type = args.device_type
        if args.site_id:
            config.site_id = args.site_id
        if args.bootstrap_key:
            config.bootstrap_key = args.bootstrap_key
        if args.permission_consent_mode:
            config.permission_consent_mode = args.permission_consent_mode
        if args.permission_sync_interval:
            config.permission_sync_interval = args.permission_sync_interval
        return config

    return EmulatorConfig(
        backend_url=args.backend_url or DEFAULT_BACKEND_URL,
        site_id=args.site_id,
        bootstrap_key=args.bootstrap_key,
        device_name=args.device_name.strip(),
        os_details=args.os_details or d.get("os_details", "Linux 6.8.0 (Debian 12)"),
        device_type=args.device_type or d.get("device_type", "pos_terminal"),
        mock_mac=args.mock_mac,
        mock_ip=args.mock_ip,
        mock_hostname=args.mock_hostname,
        mock_firmware=args.mock_firmware,
        heartbeat_interval=args.heartbeat_interval,
        telemetry_interval=args.telemetry_interval,
        command_poll_interval=args.command_poll_interval,
        push_poll_interval=args.push_poll_interval,
        logs_interval=args.logs_interval,
        audit_interval=args.audit_interval,
        jobs_interval=args.jobs_interval,
        alerts_interval=args.alerts_interval,
        command_failure_rate=args.command_failure_rate,
        permission_consent_mode=args.permission_consent_mode or "auto",
        permission_sync_interval=args.permission_sync_interval or 20.0,
    )


def main(
    argv: list[str] | None = None,
    defaults: dict | None = None,
    emulator_class: type[POSEmulator] = POSEmulator,
    banner: str = "HOMEPOT POS Emulator",
) -> None:
    args = parse_args(argv, defaults)
    config = build_config(args, defaults)

    if not config.site_id or not config.bootstrap_key:
        print("Error: --site-id and --bootstrap-key are required", file=sys.stderr)
        print(
            "  Either pass them on the CLI or provide a --config file.", file=sys.stderr
        )
        sys.exit(1)

    emulator = emulator_class(config, banner=banner)

    def _signal_handler() -> None:
        print("\n  Shutting down ...")
        emulator.stop()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _signal_handler)

    print(
        f"\n  Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        f" (PID {os.getpid()})"
    )

    try:
        loop.run_until_complete(emulator.start())
    except KeyboardInterrupt:
        pass
    finally:
        print(
            f"  Emulator stopped at "
            f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (PID {os.getpid()})"
        )
        loop.close()


if __name__ == "__main__":
    main()

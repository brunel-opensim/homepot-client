#!/usr/bin/env python3
"""Linux POS device emulator.

Simulates a Linux POS terminal device for end-to-end testing of the
Dashboard, User App, and device lifecycle flows without physical hardware.

Usage
-----
    python emulators/linux_pos_emulator.py
    python emulators/linux_pos_emulator.py --config my-device.json
    python emulators/linux_pos_emulator.py --device-id my-device --bootstrap-key abc123

The emulator provisions itself via ``POST /devices/bootstrap-provision``,
then runs four concurrent loops:

- **Heartbeat** — ``POST /agent/heartbeat`` at a configurable interval
- **Telemetry** — ``POST /agent/telemetry`` with simulated CPU/memory/disk
  metrics, network latency, plus runtime uptime (``uptime_seconds``)
- **Command polling** — ``GET /devices/pending``, ACK, and respond with mock results
- **Live logs** — ``POST /agent/logs`` with realistic POS terminal log lines
- **Audit events** — ``POST /agent/audit`` with realistic device audit events
- **Job history** — ``POST /agent/jobs`` + status updates, so the Dashboard's
  Job History tab shows live queued → completed/failed transitions

Credentials are persisted to ``~/.homepot/emulators/<device_name>.json``
so the emulator survives restarts without re-provisioning.
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import json
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
    heartbeat_interval: float = 10.0
    telemetry_interval: float = 15.0
    command_poll_interval: float = 15.0
    logs_interval: float = 15.0
    audit_interval: float = 60.0
    jobs_interval: float = 30.0

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
            heartbeat_interval=float(d.get("heartbeat_interval_seconds", 10)),
            telemetry_interval=float(d.get("telemetry_interval_seconds", 15)),
            command_poll_interval=float(d.get("command_poll_interval_seconds", 15)),
            logs_interval=float(d.get("logs_interval_seconds", 15)),
            audit_interval=float(d.get("audit_interval_seconds", 60)),
            jobs_interval=float(d.get("jobs_interval_seconds", 30)),
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


class LinuxPOSEmulator:
    """Runs a simulated Linux POS device lifecycle against the backend."""

    def __init__(self, config: EmulatorConfig) -> None:
        self.config = config
        self._device_id: str | None = None
        self._api_key: str | None = None
        self._shutdown_event = asyncio.Event()
        self._metrics = SimulatedMetrics()
        self._started = time.monotonic()
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
            "site_id": self.config.site_id,
            "device_name": self.config.device_name,
            "device_type": self.config.device_type,
            "device_source": "emulator",
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
            ("push_notification_sent", "Push notification delivered to employee device"),
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
        return job_id

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

    async def _handle_command(self, cmd: dict) -> None:
        cid = cmd["command_id"]
        ctype = cmd["command_type"]
        print(f"  [commands] processing {ctype} ({cid})")

        try:
            ack_resp = await self._http.post(
                f"{self._backend}/devices/{self.device_id}/commands/{cid}/ack",
                headers=self._headers(),
            )
            if ack_resp.status_code >= 400:
                print(f"  [commands] ack failed for {cid}: {ack_resp.status_code}")
                return

            simulated_result = self._simulate_command_result(ctype)
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
                print(f"  [commands] {ctype} completed ({cid})")
        except httpx.RequestError as exc:
            print(f"  [commands] error processing {cid}: {exc}")

    def _simulate_command_result(self, command_type: str) -> dict:
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
        print("  HOMEPOT Linux POS Emulator")
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

            print(f"\n  Device ID: {self.device_id}")
            print(f"  API Key:   {self.api_key[:16]}...")
            print(f"  Site ID:   {self.config.site_id}")
            print(
                "\n  Starting loops"
                f" (heartbeat={self.config.heartbeat_interval}s"
                f", telemetry={self.config.telemetry_interval}s"
                f", commands={self.config.command_poll_interval}s"
                f", logs={self.config.logs_interval}s"
                f", audits={self.config.audit_interval}s"
                f", jobs={self.config.jobs_interval}s)"
            )
            print("  Press Ctrl+C to stop.\n")

            await asyncio.gather(
                self._heartbeat_loop(),
                self._telemetry_loop(),
                self._command_poll_loop(),
                self._logs_loop(),
                self._audit_loop(),
                self._jobs_loop(),
            )
        finally:
            await self._http.aclose()

    def stop(self) -> None:
        self._shutdown_event.set()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="HOMEPOT Linux POS Device Emulator")
    parser.add_argument("--config", "-c", type=str, help="Path to JSON config file")
    parser.add_argument(
        "--backend-url", type=str, default=DEFAULT_BACKEND_URL, help="Backend URL"
    )
    parser.add_argument(
        "--site-id", type=str, default="", help="Site ID to provision under"
    )
    parser.add_argument(
        "--bootstrap-key", type=str, default="", help="Bootstrap key for provisioning"
    )
    parser.add_argument(
        "--device-name", type=str, default="linux-pos-emulator-1", help="Device name"
    )
    parser.add_argument(
        "--mock-mac", type=str, default="02:42:ac:11:00:02", help="Mock MAC address"
    )
    parser.add_argument(
        "--mock-ip", type=str, default="192.168.1.100", help="Mock local IP"
    )
    parser.add_argument(
        "--mock-hostname", type=str, default="linux-pos-001", help="Mock hostname"
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
    return parser.parse_args(argv)


def build_config(args: argparse.Namespace) -> EmulatorConfig:
    if args.config:
        path = Path(args.config)
        if not path.exists():
            print(f"Config file not found: {path}", file=sys.stderr)
            sys.exit(1)
        with open(path) as f:
            cfg = json.load(f)
        config = EmulatorConfig.from_dict(cfg)
        config.backend_url = args.backend_url
        if args.site_id:
            config.site_id = args.site_id
        if args.bootstrap_key:
            config.bootstrap_key = args.bootstrap_key
        return config

    return EmulatorConfig(
        backend_url=args.backend_url,
        site_id=args.site_id,
        bootstrap_key=args.bootstrap_key,
        device_name=args.device_name.strip(),
        mock_mac=args.mock_mac,
        mock_ip=args.mock_ip,
        mock_hostname=args.mock_hostname,
        heartbeat_interval=args.heartbeat_interval,
        telemetry_interval=args.telemetry_interval,
        command_poll_interval=args.command_poll_interval,
        logs_interval=args.logs_interval,
        audit_interval=args.audit_interval,
        jobs_interval=args.jobs_interval,
    )


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    config = build_config(args)

    if not config.site_id or not config.bootstrap_key:
        print("Error: --site-id and --bootstrap-key are required", file=sys.stderr)
        print(
            "  Either pass them on the CLI or provide a --config file.", file=sys.stderr
        )
        sys.exit(1)

    emulator = LinuxPOSEmulator(config)

    def _signal_handler() -> None:
        print("\n  Shutting down ...")
        emulator.stop()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _signal_handler)

    try:
        loop.run_until_complete(emulator.start())
    except KeyboardInterrupt:
        pass
    finally:
        print("  Emulator stopped.")
        loop.close()


if __name__ == "__main__":
    main()

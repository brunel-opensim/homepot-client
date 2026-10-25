"""Real device and peripheral discovery utility for the HomePot Agent.

This module discovers connected physical peripherals (printers, scanners,
card readers, etc.) via OS-level commands. It also includes an emulator
toggle to generate realistic mock payloads for fleet load testing.
"""

import json
import os
import platform
import subprocess  # noqa: S404
from typing import Any, Dict, List, Tuple

# A flag we can set during simulated runs to bypass actual OS checks
# and instead generate massive randomized loads for testing API/DB throughput.
USE_HARDWARE_EMULATOR = os.getenv("USE_HARDWARE_EMULATOR", "False").lower() == "true"


def get_connected_peripherals() -> Dict[str, List[Dict[str, Any]]]:
    """Retrieve all connected peripherals, either real or emulated.

    Returns:
        A dictionary containing lists of detected hardware categories.
    """
    if USE_HARDWARE_EMULATOR:
        return _get_emulated_peripherals()

    peripherals: Dict[str, List[Dict[str, Any]]] = {
        "printers": _discover_printers(),
        "scanners": [],
        "card_readers": [],
    }

    # Windows exposes scanners and smart-card readers through PnP device
    # classes; Linux/macOS discovery is not implemented yet.
    if platform.system().lower() == "windows":
        peripherals["scanners"] = _get_windows_pnp_devices(
            "Image", "scanner", exclude_keywords=("camera", "webcam")
        )
        peripherals["card_readers"] = _get_windows_pnp_devices(
            "SmartCardReader", "card_reader"
        )

    return peripherals


def _discover_printers() -> List[Dict[str, Any]]:
    """Discover real physical printers connected to the local OS."""
    os_name = platform.system().lower()

    if os_name == "windows":
        return _get_windows_printers()

    if os_name in ("linux", "darwin"):
        return _get_cups_printers()

    return []


def _printer_status(code: Any) -> str:
    """Map PowerShell's ``PrinterStatus`` enum to a simple online/offline string.

    ``PrinterStatus``: 0 Other, 1 Unknown, 2 Idle, 3 Printing, 4 WarmingUp,
    5 StoppedPrinting, 6 Offline, 7 Paused, 8 Error, 9 Busy.
    """
    return "online" if code in (0, 2, 3, 9) else "offline"


def _get_windows_printers() -> List[Dict[str, Any]]:
    """Collect printers from Windows using PowerShell Get-Printer."""
    try:
        result = subprocess.run(  # noqa: S603, S607
            [
                "powershell",
                "-Command",
                "Get-Printer | Select-Object Name,DriverName,PortName,PrinterStatus | ConvertTo-Json",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return []

        data = json.loads(result.stdout)
        printers = data if isinstance(data, list) else [data]
        return [
            {
                "name": item.get("Name") or "Unknown printer",
                "driver_name": item.get("DriverName"),
                "port": item.get("PortName"),
                "type": "printer",
                "connection_type": "Windows",
                "status": _printer_status(item.get("PrinterStatus")),
                "source": "windows_powershell",
            }
            for item in printers
            if isinstance(item, dict)
        ]
    except json.JSONDecodeError:
        return [{"error": "could not parse Windows printer list"}]
    except Exception as exc:
        return [{"error": str(exc)}]


def _pnp_connection_type(instance_id: str) -> str:
    """Best-effort bus type from a Windows PnP instance id prefix."""
    prefix = instance_id.split("\\", 1)[0].upper()
    return {
        "USB": "USB",
        "PCI": "PCIe",
        "HDAUDIO": "Audio",
        "BTHENUM": "Bluetooth",
        "ROOT": "System",
        "SWD": "Software",
    }.get(prefix, "Windows")


def _get_windows_pnp_devices(
    device_class: str,
    device_type: str,
    exclude_keywords: Tuple[str, ...] = (),
) -> List[Dict[str, Any]]:
    """Enumerate Windows PnP devices in ``device_class`` (e.g. ``Image``).

    Used for scanners (``Image``) and smart-card readers
    (``SmartCardReader``). Devices whose friendly name contains one of
    ``exclude_keywords`` are skipped, because the ``Image`` class also
    contains webcams.
    """
    script = (
        f"Get-PnpDevice -Class {device_class} -ErrorAction SilentlyContinue | "
        "Where-Object { $_.Status -eq 'OK' } | "
        "Select-Object FriendlyName,Manufacturer,InstanceId | ConvertTo-Json"
    )
    try:
        result = subprocess.run(  # noqa: S603, S607
            ["powershell", "-Command", script],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return []

        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return []
    except Exception:  # noqa: BLE001 - best-effort hardware discovery
        return []

    devices = data if isinstance(data, list) else [data]
    discovered: List[Dict[str, Any]] = []
    for item in devices:
        if not isinstance(item, dict):
            continue
        name = item.get("FriendlyName") or item.get("InstanceId")
        if not name:
            continue
        if any(keyword in name.lower() for keyword in exclude_keywords):
            continue
        discovered.append(
            {
                "name": name,
                "manufacturer": item.get("Manufacturer"),
                "type": device_type,
                "connection_type": _pnp_connection_type(item.get("InstanceId") or ""),
                "status": "online",
                "source": "windows_pnp",
            }
        )
    return discovered


def _get_cups_printers() -> List[Dict[str, Any]]:
    """Collect printers from Linux/macOS using CUPS lpstat."""
    try:
        result = subprocess.run(  # noqa: S603, S607
            ["lpstat", "-p"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return []

        printers = []
        for line in result.stdout.splitlines():
            if line.startswith("printer "):
                parts = line.split()
                if len(parts) > 1:
                    name = parts[1]
                    status = "disabled" if "disabled" in line.lower() else "online"
                    printers.append(
                        {
                            "name": name,
                            "type": "printer",
                            "status": status,
                            "connection_type": "CUPS",
                            "is_default": False,
                            "source": "cups_lpstat",
                        }
                    )
        return printers
    except Exception as exc:
        return [{"error": str(exc)}]


def _get_emulated_peripherals() -> Dict[str, List[Dict[str, Any]]]:
    """Return realistic mocked peripheral data for fleet simulation loads."""
    return {
        "printers": [
            {
                "name": "EPSON TM-T88VI (EMULATED)",
                "manufacturer": "Epson",
                "model": "TM-T88VI",
                "connection_type": "USB",
                "driver_name": "EPSON Receipt Printer",
                "port": "USB001",
                "status": "online",
                "is_default": True,
            }
        ],
        "scanners": [
            {
                "name": "Zebra DS2200 (EMULATED)",
                "type": "barcode_scanner",
                "connection_type": "USB",
                "status": "online",
            }
        ],
        "card_readers": [],
    }

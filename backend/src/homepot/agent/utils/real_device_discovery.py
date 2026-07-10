"""Real device and peripheral discovery utility for the HomePot Agent.

This module discovers connected physical peripherals (printers, scanners, 
card readers, etc.) via OS-level commands. It also includes an emulator 
toggle to generate realistic mock payloads for fleet load testing.
"""

import os
import platform
import subprocess
from typing import Any, Dict, List

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

    return {
        "printers": _discover_printers(),
        "scanners": [],  # Placeholder for future scanner integration
        "card_readers": [],  # Placeholder for future card reader integration
    }


def _discover_printers() -> List[Dict[str, Any]]:
    """Discover real physical printers connected to the local OS."""
    os_name = platform.system().lower()

    if os_name == "windows":
        return _get_windows_printers()

    if os_name in ("linux", "darwin"):
        return _get_cups_printers()

    return []


def _get_windows_printers() -> List[Dict[str, Any]]:
    """Collect printers from Windows using PowerShell Get-Printer."""
    try:
        result = subprocess.run(
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

        # MVP: For now we just return the raw JSON string wrapper. 
        # In a production iteration, we would `json.loads(result.stdout)` 
        # and normalize the keys to match the expected schema.
        return [{"raw_output": result.stdout.strip(), "source": "windows_powershell"}]
    except Exception as exc:
        return [{"error": str(exc)}]


def _get_cups_printers() -> List[Dict[str, Any]]:
    """Collect printers from Linux/macOS using CUPS lpstat."""
    try:
        result = subprocess.run(
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

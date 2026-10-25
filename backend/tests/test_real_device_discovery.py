"""Unit tests for the agent's peripheral discovery helpers."""

import json
import subprocess  # noqa: S404
from typing import Any
from unittest.mock import patch

import pytest

from homepot.agent.utils import real_device_discovery as rdd


def _completed(stdout: str, returncode: int = 0) -> subprocess.CompletedProcess:
    """Build a ``CompletedProcess`` with the given stdout."""
    return subprocess.CompletedProcess(
        args=[], returncode=returncode, stdout=stdout, stderr=""
    )


def test_printer_status_mapping() -> None:
    """Ready/printing/busy states map to online; errors and paused to offline."""
    for code in (0, 2, 3, 9):
        assert rdd._printer_status(code) == "online"
    for code in (1, 4, 5, 6, 7, 8):
        assert rdd._printer_status(code) == "offline"


@patch("homepot.agent.utils.real_device_discovery.subprocess.run")
def test_windows_printers_are_normalised(mock_run: Any) -> None:
    """Windows printer JSON is parsed into the normalised peripheral schema."""
    mock_run.return_value = _completed(
        json.dumps(
            [
                {
                    "Name": "Microsoft Print to PDF",
                    "DriverName": "Microsoft Print To PDF",
                    "PortName": "PORTPROMPT:",
                    "PrinterStatus": 0,
                },
                {
                    "Name": "Offline Printer",
                    "DriverName": "Generic Driver",
                    "PortName": "USB001",
                    "PrinterStatus": 6,
                },
            ]
        )
    )

    printers = rdd._get_windows_printers()

    assert [p["name"] for p in printers] == [
        "Microsoft Print to PDF",
        "Offline Printer",
    ]
    assert printers[0]["port"] == "PORTPROMPT:"
    assert printers[0]["driver_name"] == "Microsoft Print To PDF"
    assert printers[0]["status"] == "online"
    assert printers[1]["status"] == "offline"
    assert all(p["source"] == "windows_powershell" for p in printers)
    assert "raw_output" not in printers[0]


@patch("homepot.agent.utils.real_device_discovery.subprocess.run")
def test_windows_printers_single_object(mock_run: Any) -> None:
    """``ConvertTo-Json`` emits a bare object when only one printer exists."""
    mock_run.return_value = _completed(
        json.dumps(
            {
                "Name": "Solo Printer",
                "DriverName": "Solo Driver",
                "PortName": "USB002",
                "PrinterStatus": 2,
            }
        )
    )

    printers = rdd._get_windows_printers()

    assert len(printers) == 1
    assert printers[0]["name"] == "Solo Printer"
    assert printers[0]["status"] == "online"


@patch("homepot.agent.utils.real_device_discovery.subprocess.run")
def test_windows_printers_invalid_json(mock_run: Any) -> None:
    """Unparseable output is reported as an error entry, not a crash."""
    mock_run.return_value = _completed("not json")

    assert rdd._get_windows_printers() == [
        {"error": "could not parse Windows printer list"}
    ]


@patch("homepot.agent.utils.real_device_discovery.subprocess.run")
def test_windows_printers_empty_output(mock_run: Any) -> None:
    """No printers yields an empty list."""
    mock_run.return_value = _completed("")

    assert rdd._get_windows_printers() == []


@patch("homepot.agent.utils.real_device_discovery.subprocess.run")
def test_windows_printers_command_failure(mock_run: Any) -> None:
    """A failing PowerShell invocation yields an empty list."""
    mock_run.return_value = _completed("boom", returncode=1)

    assert rdd._get_windows_printers() == []


@patch("homepot.agent.utils.real_device_discovery.subprocess.run")
def test_windows_pnp_devices_normalise_and_filter(mock_run: Any) -> None:
    """Plug-and-play devices are normalised and webcams are excluded."""
    mock_run.return_value = _completed(
        json.dumps(
            [
                {
                    "FriendlyName": "Integrated Webcam",
                    "Manufacturer": "Dell",
                    "InstanceId": "USB\\VID_0BDA&PID_5652",
                },
                {
                    "FriendlyName": "Epson Perfection V39",
                    "Manufacturer": "Epson",
                    "InstanceId": "USB\\VID_04B8&PID_013D",
                },
            ]
        )
    )

    scanners = rdd._get_windows_pnp_devices(
        "Image", "scanner", exclude_keywords=("camera", "webcam")
    )

    assert [s["name"] for s in scanners] == ["Epson Perfection V39"]
    assert scanners[0]["manufacturer"] == "Epson"
    assert scanners[0]["connection_type"] == "USB"
    assert scanners[0]["type"] == "scanner"
    assert scanners[0]["status"] == "online"


@pytest.mark.parametrize(
    ("instance_id", "expected"),
    [
        ("USB\\VID_04B8", "USB"),
        ("PCI\\VEN_8086", "PCIe"),
        ("BTHENUM\\{0000}", "Bluetooth"),
        ("ROOT\\WPD", "System"),
        ("HDAUDIO\\FUNC_01", "Audio"),
        ("UNKNOWN\\DEVICE", "Windows"),
    ],
)
def test_pnp_connection_type(instance_id: str, expected: str) -> None:
    """The bus type is derived from the PnP instance-id prefix."""
    assert rdd._pnp_connection_type(instance_id) == expected


def test_get_connected_peripherals_windows() -> None:
    """Windows discovery wires printers, scanners and card readers together."""
    with (
        patch.object(rdd, "USE_HARDWARE_EMULATOR", False),
        patch.object(rdd.platform, "system", return_value="Windows"),
        patch.object(rdd, "_discover_printers", return_value=[{"name": "P1"}]),
        patch.object(
            rdd,
            "_get_windows_pnp_devices",
            side_effect=[[{"name": "S1"}], [{"name": "C1"}]],
        ) as pnp,
    ):
        peripherals = rdd.get_connected_peripherals()

    assert peripherals == {
        "printers": [{"name": "P1"}],
        "scanners": [{"name": "S1"}],
        "card_readers": [{"name": "C1"}],
    }
    assert [call.args[0] for call in pnp.call_args_list] == [
        "Image",
        "SmartCardReader",
    ]


def test_get_connected_peripherals_non_windows() -> None:
    """Non-Windows hosts return printers only (scanners/card readers empty)."""
    with (
        patch.object(rdd, "USE_HARDWARE_EMULATOR", False),
        patch.object(rdd.platform, "system", return_value="Linux"),
        patch.object(rdd, "_discover_printers", return_value=[{"name": "P1"}]),
    ):
        peripherals = rdd.get_connected_peripherals()

    assert peripherals == {
        "printers": [{"name": "P1"}],
        "scanners": [],
        "card_readers": [],
    }


def test_get_connected_peripherals_emulator() -> None:
    """The emulator toggle yields the seeded mock fleet payload."""
    with patch.object(rdd, "USE_HARDWARE_EMULATOR", True):
        peripherals = rdd.get_connected_peripherals()

    assert peripherals["printers"][0]["name"].endswith("(EMULATED)")
    assert peripherals["scanners"][0]["name"].endswith("(EMULATED)")

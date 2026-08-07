#!/usr/bin/env python3
"""Windows POS device emulator.

Simulates a Windows POS terminal device for end-to-end testing of the
Dashboard, User App, and device lifecycle flows without physical hardware.

Thin wrapper around the shared emulator engine (:mod:`pos_engine`) configured
with Windows identity defaults (OS details, mock MAC/hostname). The engine is
OS-agnostic; Windows only overrides the device identity and thereby inherits a
Windows-specific permission capability map (no root access, but process /
filesystem / network monitoring).

Usage
-----
    python emulators/windows_pos_emulator.py --site-id site-it-demo1 --bootstrap-key abc123
    python emulators/windows_pos_emulator.py --config my-device.json
"""

from __future__ import annotations

from typing import Any

from pos_engine import POSEmulator, main

LinuxPOSEmulator = POSEmulator

WINDOWS_DEFAULTS: dict[str, Any] = {
    "device_name": "windows-pos-emulator-1",
    "os_details": "Windows 11",
    "mock_mac": "02:42:ac:11:00:04",
    "mock_hostname": "windows-pos-001",
}


def windows_main(argv: list[str] | None = None) -> None:
    main(
        argv,
        defaults=WINDOWS_DEFAULTS,
        emulator_class=POSEmulator,
        banner="HOMEPOT Windows POS Emulator",
    )


if __name__ == "__main__":
    windows_main()

#!/usr/bin/env python3
"""macOS POS device emulator.

Simulates a macOS POS terminal device for end-to-end testing of the
Dashboard, User App, and device lifecycle flows without physical hardware.

Thin wrapper around the shared emulator engine (:mod:`pos_engine`) configured
with macOS identity defaults (OS details, mock MAC/hostname). macOS inherits
the engine's *nix-style permission capability map (root access + process /
filesystem / network monitoring), matching the backend's OS model for macOS.

Usage
-----
    python emulators/macos_pos_emulator.py --site-id site-it-demo --bootstrap-key abc123
    python emulators/macos_pos_emulator.py --config my-device.json
"""

from __future__ import annotations

from typing import Any

from pos_engine import (
    POSEmulator,
    main,
    derive_os_capabilities,
    parse_args,
    build_config,
    EmulatorConfig,
)

LinuxPOSEmulator = POSEmulator

MACOS_DEFAULTS: dict[str, Any] = {
    "device_name": "macos-pos-emulator-1",
    "device_type": "pos_terminal",
    "os_details": "macOS 14",
    "mock_mac": "02:42:ac:11:00:05",
    "mock_hostname": "macos-pos-001",
}


def macos_main(argv: list[str] | None = None) -> None:
    main(
        argv,
        defaults=MACOS_DEFAULTS,
        emulator_class=POSEmulator,
        banner="HOMEPOT macOS POS Emulator",
    )


if __name__ == "__main__":
    macos_main()
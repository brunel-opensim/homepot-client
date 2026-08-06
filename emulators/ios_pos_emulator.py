#!/usr/bin/env python3
"""iOS POS device emulator.

Simulates an iOS POS terminal device for end-to-end testing of the
Dashboard, User App, and device lifecycle flows without physical hardware.

Thin wrapper around the shared emulator engine (:mod:`pos_engine`) configured
with iOS identity defaults (device type ``tablet``, OS details, mock
MAC/hostname). iOS inherits a restricted permission capability map (network
monitoring only, no root / process / filesystem access), matching the
backend's capability model for iOS.

Usage
----
    python emulators/ios_pos_emulator.py --site-id site-it-demo --bootstrap-key abc123
    python emulators/ios_pos_emulator.py --config my-device.json
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

IOS_DEFAULTS: dict[str, Any] = {
    "device_name": "ios-pos-emulator-1",
    "device_type": "tablet",
    "os_details": "iOS 17",
    "mock_mac": "02:42:ac:11:00:06",
    "mock_hostname": "ios-pos-001",
}


def ios_main(argv: list[str] | None = None) -> None:
    main(
        argv,
        defaults=IOS_DEFAULTS,
        emulator_class=POSEmulator,
        banner="HOMEPOT iOS POS Emulator",
    )


if __name__ == "__main__":
    ios_main()
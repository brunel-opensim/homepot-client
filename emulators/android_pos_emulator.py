#!/usr/bin/env python3
"""Android POS device emulator.

Simulates an Android POS terminal device for end-to-end testing of the
Dashboard, User App, and device lifecycle flows without physical hardware.

Thin wrapper around the shared emulator engine (:mod:`pos_engine`) configured
with Android identity defaults (OS details, mock MAC/hostname). The engine is
OS-agnostic; Android only overrides the device identity and thereby inherits an
Android-specific permission capability map (no root access, but process /
filesystem / network monitoring).

Usage
-----
    python emulators/android_pos_emulator.py --site-id site-it-demo1 --bootstrap-key abc123
    python emulators/android_pos_emulator.py --config my-device.json

When launched by the User App Electron shell, ``electron/main.ts`` writes the
Android ``os_details``/``mock_mac`` into the temp config JSON, so the
config-file path picks up the Android identity automatically.
"""

from __future__ import annotations

from typing import Any

from pos_engine import POSEmulator, main

LinuxPOSEmulator = POSEmulator

ANDROID_DEFAULTS: dict[str, Any] = {
    "device_name": "android-pos-emulator-1",
    "os_details": "Android 14",
    "mock_mac": "02:42:ac:11:00:03",
    "mock_hostname": "android-pos-001",
}


def android_main(argv: list[str] | None = None) -> None:
    main(
        argv,
        defaults=ANDROID_DEFAULTS,
        emulator_class=POSEmulator,
        banner="HOMEPOT Android POS Emulator",
    )


if __name__ == "__main__":
    android_main()

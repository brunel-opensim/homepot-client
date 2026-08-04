#!/usr/bin/env python3
"""Android POS device emulator.

Simulates an Android POS terminal device for end-to-end testing of the
Dashboard, User App, and device lifecycle flows without physical hardware.

Reuses the parameterized emulator engine from ``linux_pos_emulator.py`` with
Android-specific device identity defaults (OS details, mock MAC/hostname).

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

try:
    from linux_pos_emulator import LinuxPOSEmulator, main  # type: ignore[import-not-found]
except ModuleNotFoundError:
    from .linux_pos_emulator import LinuxPOSEmulator, main

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
        emulator_class=LinuxPOSEmulator,
        banner="HOMEPOT Android POS Emulator",
    )


if __name__ == "__main__":
    android_main()

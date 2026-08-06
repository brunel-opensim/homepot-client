#!/usr/bin/env python3
"""Linux POS device emulator.

Thin wrapper around the shared emulator engine (:mod:`pos_engine`) configured
with Linux identity defaults. All behaviour lives in ``pos_engine.py``; this
module only supplies the OS-specific identity and re-exports the engine's
public API so existing entrypoints keep working unchanged.

Usage
-----
    python emulators/linux_pos_emulator.py --site-id site-it-demo1 --bootstrap-key abc123
    python emulators/linux_pos_emulator.py --config my-device.json
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

LINUX_DEFAULTS: dict[str, Any] = {
    "device_name": "linux-pos-emulator-1",
    "os_details": "Linux 6.8.0 (Debian 12)",
    "mock_mac": "02:42:ac:11:00:02",
    "mock_hostname": "linux-pos-001",
    "mock_firmware": "2.4.1",
}


def linux_main(argv: list[str] | None = None) -> None:
    main(
        argv,
        defaults=LINUX_DEFAULTS,
        emulator_class=POSEmulator,
        banner="HOMEPOT Linux POS Emulator",
    )


if __name__ == "__main__":
    linux_main()
#!/usr/bin/env python3
"""PyInstaller entry point for the HOMEPOT device emulators.

The User App spawns the emulator as ``emulators/<os>_pos_emulator.py --config
<file>``. In a packaged app there is no checked-out repo or Python runtime, so
electron-builder ships this frozen binary instead. It reads ``--config``, maps
the JSON ``emulator_type`` to the matching per-OS wrapper
(``linux_pos`` → ``linux_pos_emulator.linux_main``), adds the bundled
``emulators/`` source directory to ``sys.path`` (PyInstaller extracts it to
``sys._MEIPASS``), and hands argv straight through to that wrapper.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
from pathlib import Path

EMULATOR_TYPE_TO_MODULE = {
    "linux_pos": "linux_pos_emulator",
    "android_pos": "android_pos_emulator",
    "windows_pos": "windows_pos_emulator",
    "macos_pos": "macos_pos_emulator",
    "ios_pos": "ios_pos_emulator",
}

EMULATOR_MODULE_TO_MAIN = {
    "linux_pos_emulator": "linux_main",
    "android_pos_emulator": "android_main",
    "windows_pos_emulator": "windows_main",
    "macos_pos_emulator": "macos_main",
    "ios_pos_emulator": "ios_main",
}


def _bundled_emulators_dir() -> Path:
    # PyInstaller onedir/onefile extracts bundled data to sys._MEIPASS; when
    # running from source this falls back to the checked-out emulators/ dir.
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / "emulators"


def _resolve_emulator_type(config_path: str) -> str:
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    emulator_type = config.get("emulator_type", "linux_pos")
    if emulator_type not in EMULATOR_TYPE_TO_MODULE:
        raise SystemExit(f"Unknown emulator_type: {emulator_type}")
    return emulator_type


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="HOMEPOT POS emulator (packaged)")
    parser.add_argument("--config", required=True, help="Path to the emulator config JSON")
    args, remaining = parser.parse_known_args(argv)

    emulator_type = _resolve_emulator_type(args.config)
    module_name = EMULATOR_TYPE_TO_MODULE[emulator_type]
    main_name = EMULATOR_MODULE_TO_MAIN[module_name]

    emulators_dir = _bundled_emulators_dir()
    if str(emulators_dir) not in sys.path:
        sys.path.insert(0, str(emulators_dir))

    wrapper = importlib.import_module(module_name)
    entry = getattr(wrapper, main_name)
    entry(["--config", args.config, *remaining])


if __name__ == "__main__":
    main()

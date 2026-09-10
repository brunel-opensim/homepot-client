# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the HOMEPOT device emulators (packaged User App).

Builds a single ``homepot-emulator`` binary from `emulator_entry.py`. The
entry reads ``--config``, maps the JSON ``emulator_type`` to the matching
per-OS wrapper, and dispatches to it. The whole ``emulators/`` source
directory is bundled (``emulators/<os>_pos_emulator.py`` + ``pos_engine.py``)
and extracted to ``sys._MEIPASS`` at run time.

Usage:
    python -m PyInstaller packaging/emulator.spec \
        --distpath user_app/pyinstaller-dist --workpath /tmp/pyinstaller-emulator

Note: the distpath is *outside* `user_app/dist`, because the frontend `vite
build` empties `dist/` on every run and would otherwise wipe the packaged
binaries before electron-builder copies them into the app
(``extraResources`` -> ``resources/bin``).
"""

from pathlib import Path

block_cipher = None

SPEC_DIR = Path(SPECPATH).resolve()
REPO_ROOT = SPEC_DIR.parent
EMULATORS_DIR = REPO_ROOT / "emulators"
# Canonical OS capability/push-channel logic lives in the backend package but
# must stay importable from the frozen emulator, which only bundles the
# ``emulators/`` tree. We add the backend's stdlib-only ``os_capabilities.py``
# module alongside it; ``pos_engine.py`` falls back to ``import os_capabilities``
# when the backend is not importable.
PACKAGED_SCHEMAS = REPO_ROOT / "backend" / "src" / "homepot" / "app" / "schemas"

a = Analysis(
    [str(SPEC_DIR / "emulator_entry.py")],
    pathex=[str(EMULATORS_DIR), str(PACKAGED_SCHEMAS)],
    binaries=[],
    datas=[
        (str(EMULATORS_DIR), "emulators"),
        (str(PACKAGED_SCHEMAS / "os_capabilities.py"), "emulators"),
    ],
    hiddenimports=[
        "pos_engine",
        "linux_pos_emulator",
        "android_pos_emulator",
        "windows_pos_emulator",
        "macos_pos_emulator",
        "ios_pos_emulator",
        "os_capabilities",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "pytest"],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="homepot-emulator",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="homepot-emulator",
)

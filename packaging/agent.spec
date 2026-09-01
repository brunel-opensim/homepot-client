# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the HOMEPOT on-device agent.

Builds a standalone ``homepot-agent`` binary that the packaged Electron User
App spawns instead of ``python -m homepot.agent.real_device_agent`` (which
would require a checked-out repo and Python environment on the target device).

The agent's minimal runtime is fastapi + uvicorn + httpx + psutil +
platformdirs, all discovered via the import graph. SQLAlchemy is *not*
excluded even though the agent never touches the DB directly: importing any
``homepot.agent`` submodule runs ``homepot/agent/__init__``, which eagerly
exports ``agent_api.router`` (mounted by the backend API) and that router
imports ``sqlalchemy.orm``. Excluding it crashes the frozen binary at startup,
so it is bundled for fidelity with the repo runtime. The bundled
``agent-config.json`` is the fallback default; the Electron shell always writes
a config and passes it through $HOMEPOT_AGENT_CONFIG.

Usage:
    PYTHONPATH=backend/src python -m PyInstaller packaging/agent.spec \
        --distpath user_app/pyinstaller-dist --workpath /tmp/pyinstaller-agent

Note: the distpath is *outside* `user_app/dist`, because the frontend `vite
build` empties `dist/` on every run and would otherwise wipe the packaged
binaries before electron-builder copies them into the app
(``extraResources`` -> ``resources/bin``).
"""

from pathlib import Path

block_cipher = None

# Paths are resolved relative to the spec file's directory (packaging/).
SPEC_DIR = Path(SPECPATH).resolve()
REPO_ROOT = SPEC_DIR.parent
AGENT_PKG = REPO_ROOT / "backend" / "src" / "homepot" / "agent"

a = Analysis(
    [str(REPO_ROOT / "backend" / "src" / "homepot" / "agent" / "real_device_agent.py")],
    pathex=[str(REPO_ROOT / "backend" / "src")],
    binaries=[],
    datas=[
        (str(AGENT_PKG / "agent-config.json"), "homepot/agent"),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "pytest",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="homepot-agent",
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
    name="homepot-agent",
)

# HOMEPOT User App — Packaging

Build scripts for turning the **User App** (Electron) into a distributable
application that works on a real device with **no runtime prerequisites** on
the target machine (no Python install, virtualenv, or checked-out repo).

This directory is deliberately **top-level, alongside `scripts/` and
`deploy/`**, so the User App build stays independent of the Dashboard and its
backend dependencies. `deploy/` (systemd services for the backend dev server)
is a separate story and should not be mixed in here.

## What it builds

PyInstaller freezes two Python runtimes into standalone **onedir** binaries
(always onedir — FastAPI/uvicorn are unreliable as onefile):

| Binary | Source | Contents |
| --- | --- | --- |
| `homepot-agent` | `backend/src/homepot/agent/real_device_agent.py` | The on-device agent (fastapi, uvicorn, httpx, psutil, platformdirs) + bundled `agent-config.json` |
| `homepot-emulator` | `packaging/emulator_entry.py` | Thin dispatcher + the whole `emulators/` package (per-OS wrappers + `pos_engine`) |

The Electron shell spawns these at runtime instead of `python -m
homepot.agent.real_device_agent` / the `emulators/*.py` scripts. Files:

| File | Purpose |
| --- | --- |
| `agent.spec` | PyInstaller spec → `homepot-agent` |
| `emulator.spec` | PyInstaller spec → `homepot-emulator` |
| `emulator_entry.py` | Dispatcher: reads `--config`, maps JSON `emulator_type` → `<os>_pos_emulator.<os>_main`, adds bundled `emulators/` to `sys.path` |

## Build locally

```bash
# 1. Freeze the binaries (outputs land in user_app/pyinstaller-dist/)
PYTHONPATH=backend/src python -m PyInstaller packaging/agent.spec \
    --distpath user_app/pyinstaller-dist --workpath /tmp/pyinstaller-agent
python -m PyInstaller packaging/emulator.spec \
    --distpath user_app/pyinstaller-dist --workpath /tmp/pyinstaller-emulator

# 2. Package the app (electron-builder)
cd user_app
npx electron-builder --mac    # or --win / --linux
```

> **Build order matters.** `pyinstaller-dist/` is intentionally *outside*
> `user_app/dist`, because the frontend `vite build` empties `dist/` on every
> run and would otherwise wipe the frozen binaries before electron-builder
> copies them — the `.app` would silently ship without them.

`pyinstaller-dist/` is gitignored (build artifact); the binaries are **not**
committed. Only the specs/entry here and the icon assets are versioned.

## How the binaries reach the packaged app

`user_app/package.json` → `build.extraResources`:

```json
{ "from": "pyinstaller-dist", "to": "bin" }
```

copies `pyinstaller-dist/{homepot-agent,homepot-emulator}` into
`<resources>/bin/<name>/<name>` (`.exe` on Windows). `user_app/electron/main.ts`
resolves them with `packagedBinary()` (`electron/main.ts`) and:

- `startAgentProcess()` spawns `homepot-agent` with `HOMEPOT_AGENT_CONFIG`
  pointing at a config the shell writes at runtime (fallback: the bundled
  `agent-config.json`).
- `startEmulatorProcess()` spawns `homepot-emulator --config <cfg>`.
- In dev / unpackaged runs both fall back to launching Python from the repo.

`bin/` lands under the app's `resources` directory (e.g.
`HOMEPOT Agent.app/Contents/Resources/bin/` on macOS), alongside the asar
rather than inside it. electron-builder preserves the executable bit on POSIX
(verified on macOS; same copy path in Linux CI).

## CI / release flow

`.github/workflows/user-app-build.yml`:

- `quality` — lint/test/build on every trigger.
- `package` — mac/win/linux matrix; each job installs
  `pyinstaller fastapi uvicorn httpx==0.27.0 psutil platformdirs`, builds both
  specs into `pyinstaller-dist`, then runs `electron-builder`.
- `publish` — manual (`workflow_dispatch` with `publish=true`); collects all
  artifacts and uploads to a **draft GitHub release**. Drafts are held back so
  a technician promotes them deliberately; `electron-updater`
  (`latest-mac.yml` / `latest.yml`) drives auto-update on real devices.

## Gotchas learned (read before changing anything)

- **Do not exclude `sqlalchemy` from `agent.spec`.** The agent never touches
  the DB, but importing any `homepot.agent` submodule runs
  `homepot/agent/__init__.py`, which eagerly exports `agent_api.router`
  (mounted by the backend API) — and that router imports `sqlalchemy.orm`.
  Excluding it crashes the frozen binary at startup (ModuleNotFoundError), so
  it is bundled for fidelity with the repo runtime.
- Onedir output is required; the `codesign_identity=None` / `target_arch=None`
  in each spec's `EXE(...)` block keep PyInstaller from attempting local code
  signing during the build.
- Each OS must be built on its native runner/OS (PyInstaller is not
  cross-compiling — no mac binary from a Linux box).
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

## Changing the app icon

The icon assets are versioned, and the platform build configs point at
three separate files (see `user_app/package.json` → `build`):

| Platform | Icon file |
| --- | --- |
| Linux | `user_app/resources/icon.png` |
| macOS | `user_app/build/icon.icns` |
| Windows | `user_app/build/icon.ico` |

The **master artwork is `user_app/resources/icon.png`**. It is *not* read
directly by the mac/win builds, so after you change it you must regenerate
`build/icon.png`, `build/icon.icns`, and `build/icon.ico` from it, then
repackage — icons are baked in at build time, not read at runtime.

### Regenerate + repackage (manual)

Requires Python 3 with Pillow (macOS `iconutil` also used on mac):

```bash
# from the repo root
python3 - <<'PY'
from PIL import Image

src = Image.open("user_app/resources/icon.png").convert("RGBA")

# 1024px PNG + Windows ICO (multi-size; PIL resizes internally per `sizes`)
src.resize((1024, 1024), Image.LANCZOS).save("user_app/build/icon.png", format="PNG")
src.save("user_app/build/icon.ico", format="ICO",
         sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
PY
```

Generate the macOS `.icns` from an iconset (the dir name *must* end in
`.iconset` or `iconutil` rejects it):

```bash
mkdir -p /tmp/homepot.iconset
python3 - <<'PY'
from PIL import Image
import json

src = Image.open("user_app/resources/icon.png").convert("RGBA")
sizes = [
    ("icon_16x16.png", 16, "1x"), ("icon_16x16@2x.png", 32, "2x"),
    ("icon_32x32.png", 32, "1x"), ("icon_32x32@2x.png", 64, "2x"),
    ("icon_128x128.png", 128, "1x"), ("icon_128x128@2x.png", 256, "2x"),
    ("icon_256x256.png", 256, "1x"), ("icon_256x256@2x.png", 512, "2x"),
    ("icon_512x512.png", 512, "1x"), ("icon_512x512@2x.png", 1024, "2x"),
]
images = []
for name, px, scale in sizes:
    src.resize((px, px), Image.LANCZOS).save(f"/tmp/homepot.iconset/{name}", format="PNG")
    logical = px // 2 if scale == "2x" else px
    images.append({"filename": name, "idiom": "mac", "scale": scale, "size": f"{logical}x{logical}"})
with open("/tmp/homepot.iconset/Contents.json", "w") as f:
    json.dump({"images": images, "info": {"author": "xcode", "version": 1}}, f)
PY
iconutil -c icns /tmp/homepot.iconset -o user_app/build/icon.icns
rm -rf /tmp/homepot.iconset
```

Then repackage (see "How to package & run" below):

```bash
# quick sanity check that the freshly built app carries the new icon
md5 user_app/build/icon.icns
md5 "user_app/release/mac-arm64/HOMEPOT Agent.app/Contents/Resources/icon.icns"  # must match
```

> If you only edit a UI-facing asset shipped inside the bundle, freeze/
> repackage every time — the `.app` is a snapshot of `dist/`,
> `dist-electron/`, `pyinstaller-dist/`, and the build icons.

## How to package & run (without the assistant)

Full end-to-end recipe for turning source edits into a running app:

```bash
# 0. (one-time / after changed backend or emulator code) rebuild frozen binaries
cd <repo-root>
PYTHONPATH=backend/src python -m PyInstaller packaging/agent.spec \
    --distpath user_app/pyinstaller-dist --workpath /tmp/pyinstaller-agent
python -m PyInstaller packaging/emulator.spec \
    --distpath user_app/pyinstaller-dist --workpath /tmp/pyinstaller-emulator

# 1. build the frontend + package the app in one shot
cd user_app
npm install            # one-time; package-lock.json is source of truth
npm run electron:build # VITE_ELECTRON=true vite build && electron-builder
                       #   → builds dist/ + dist-electron/ AND packages the app
```

If you already built the bundle (step 1's `vite build` succeeded and only the
icons/package.json changed), you can skip straight to packaging alone:

```bash
cd user_app
npx electron-builder --mac      # or --win / --linux (each runs on its host OS)
```

> Never point electron-builder at a `dist/` that misses `pyinstaller-dist/`
> — see "Build order matters" above.

To run the packaged result without installing (macOS):

```bash
open "user_app/release/mac-arm64/HOMEPOT Agent.app"
# or, with console output so you can watch the agent:
"user_app/release/mac-arm64/HOMEPOT Agent.app/Contents/MacOS/<binary>"
```

If you want to test with a *different* backend than the packaged default,
edit `~/.homepot/agent/agent-config.json` first (see `deploy/README` or the
agent docs for the schema) — the frozen agent reads its config from there.

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
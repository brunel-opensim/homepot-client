# User App ↔ Host OS: Testing Runbook

How to exercise the end-to-end command loop (Dashboard → backend queue →
device → real execution → result) against the User App running on a real
host (a Mac today). Two paths:

1. **Emulator path** — quick UI sanity check; commands are *simulated* on the
   device and never touch the host OS.
2. **Real-agent path** — the bundled Python agent executes the nine command
   types *for real* against the host (diagnostics, process/connection listing,
   filesystem scan, brightness/config, reboot, shutdown).

Both assume the backend, Dashboard, and User App are running locally.

## Prerequisites

- Repo venv installed (`backend` + `emulators` deps).
- `frontend` and `user_app` node_modules installed.
- A Dashboard admin account and a site.

## Start the stack

```bash
# Backend (port 8000 by default)
cd backend
../.venv/bin/python -m uvicorn homepot.app.main:app --reload

# Dashboard (separate terminal)
./scripts/start-dashboard.sh

# User App — Electron shell (separate terminal)
cd user_app
npm run electron:dev
```

If the backend is not on `http://localhost:8000`, export it before launching
the User App (the agent config resolves `HOMEPOT_BACKEND_URL` → stored
`backend_url` → default):

```bash
export HOMEPOT_BACKEND_URL=http://<host>:<port>/api/v1
```

## Path 1 — Emulator (quick sanity)

1. User App → Setup → enter the site ID + bootstrap key from the Dashboard.
2. Pick **macOS POS emulator** in the device-type picker.
3. Dashboard → the device → **Compose Command** → **Run Diagnostics** → Queue.
4. Watch the emulator log; the command is polled, executed (simulated), and
   appears **completed** in the device's Push History.

This exercises Dashboard → backend queue → permission gate → delivery →
ack → result reporting, with the emulator standing in for the OS.

## Path 2 — Real agent (the new code)

In Setup, **do not** pick an emulator — choose **"Set up a real device"**
(self-enrolled). The wizard auto-detects the host: on a Mac it fills the OS
(macOS) and defaults the **Device Type to Desktop** (Laptop / POS Terminal etc.
are available if you override). The app writes
`enrollment_method: 'self-enrolled'`, so the Electron main process spawns the
**real Python agent** (`python -m homepot.agent.real_device_agent`) instead of
an emulator.

### Verify each link

| Check | How |
|---|---|
| Agent process running | `ps aux \| grep real_device_agent` |
| Agent config written | `cat ~/.homepot/agent/agent-config.json` (your `backend_url`, `device_id`, `api_key`) |
| Registration + heartbeat | Dashboard device shows **online / active**; backend log shows registration + heartbeats |
| Permissions synced | User App → Permissions → toggle **Monitor** on; the device page **CAPABILITIES** shows Monitor granted |
| Monitor-tier command | Compose **Run Diagnostics** → Queue → polls ≤15 s → real `health_check` → Push History shows **completed** with real CPU/mem/disk |
| Real process list | Compose **List Processes** → result has real pids/names from the host |
| Real filesystem scan | Compose **Scan Filesystem** (path e.g. `/var/homepot`) → real `os.walk` entries |
| Real config action | Compose **Apply Configuration** with `brightness` → host brightness actually changes |
| Permission gating | With Monitor only, **Run Command** shows **Request Access**; grant **Manage** on the User App → **Queue Command** appears |
| Command wake-up | Only for push-capable OSes (Android FCM / Windows WNS); on macOS it is a no-op and delivery relies on polling |

### Testing the wake-up with the emulator

Set up an **Android** (or Windows) emulator — those register `push_channel`/`push_token`,
so queueing a command makes the backend persist a `command_wakeup` push that the emulator
picks up from `/push/pending` and reacts to by polling `/devices/pending` **immediately**
(instead of waiting out the poll interval). Watch the emulator log for:

```
[push] command wake-up received — polling pending commands now
[commands] N pending
```

On macOS (polling-only) there is no wake-up, so the command arrives on the next poll
interval — that is expected.

### Real-device readiness checklist

The code path for a real device is built, but "moving to real devices" has four
gates before the emulator stops being the primary validation target:

1. **Real-agent path proven on the Mac.** Run Path 2 above end-to-end once on the
   target Mac and confirm every link in the verify table — registration, heartbeat,
   permission sync, a Monitor-tier command, and a Manage-tier command.
2. **Electron packaging.** Today `main.ts` spawns the agent using the **repo's**
   `.venv` and walks up to find `emulators/` (`getProjectRoot()`). A self-contained
   installed app must **bundle the Python agent + its venv + `backend/src`** inside
   the app (e.g. `resources/`). Until that is done, the real device only works from a
   dev checkout, not as an installed app.
3. **Host setup on the target Mac.** Manage-tier execution needs **passwordless sudo**
   for the agent user (`sudo -n`), and `brightness`/`volume` config needs its CLI
   tools installed. These are ops notes, not code.
4. **APNs push (Phase 2).** macOS delivery works by polling; near-instant wake-up
   needs an Apple Developer ID + push entitlement + certificate.

Until gates 1–3 are green, treat the emulator as the reliable baseline and the
real-agent path as the thing to validate each change against.

### Granting Manage (root) — sudo caveat

Manage-tier execution runs through `sudo -n`:

- `run_command` / `run_script` → `sudo -n -- <argv>` (needs passwordless sudo)
- `restart` / `shutdown` → `sudo -n shutdown -r/-h now` (needs passwordless sudo)
- `scan_filesystem` → pure `os.walk`, no sudo
- `update_config` brightness → `brightness` CLI (`brew install brightness`), no sudo

Without a NOPASSWD sudo rule for the agent user, `run_command`/`run_script`
and `restart`/`shutdown` report `failed` — expected. The Monitor-tier and
`scan_filesystem`/`brightness` paths work without elevation.

## What to expect at each command

| Command | Tier | Real host result |
|---|---|---|
| Run Diagnostics (`health_check`) | Monitor | per-test pass/fail + CPU/memory/disk values |
| List Processes | Monitor | sorted process snapshot |
| List Network Connections | Monitor | connections filtered by state |
| Run Command / Run Script | Manage | sudo execution, stdout/stderr/exit code |
| Scan Filesystem | Manage | bounded `os.walk` entries with sizes |
| Apply Configuration | Manage | brightness/volume OS action; unknown keys acknowledged |
| Reboot System / Shut Down System | Manage | `sudo shutdown` (actually reboots/shuts down!) |

## Troubleshooting

- **Device output on the Mac** — the emulator/agent stdout+stderr is appended to
  per-device files **`logs/emulator-<device>.log`** / **`logs/agent-<device>.log`**
  (timestamps + source tag), matching the standalone launcher convention, so you can
  `tail -f logs/emulator-demo-mac-1.log` for live telemetry, commands, and wake-ups.
  This is separate from `logs/userapp.log` (the app launcher log).

- **Agent exits immediately** — check the User App console / app log
  (`~/Library/Application Support/.../app-events.json`) and run the spawn
  manually:
  ```bash
  HOMEPOT_AGENT_CONFIG=~/.homepot/agent/agent-config.json \
  PYTHONPATH=backend/src .venv/bin/python -m homepot.agent.real_device_agent
  ```
- **Command stays queued** — confirm the device is online (heartbeat), the
  permission tier is granted, and the agent's poll interval elapsed.
- **`Permission denied` on a Manage command** — the owner has not granted
  Manage in the User App, or passwordless sudo is not configured.
- **Wake-up not firing** — macOS is polling-only; wake-ups only apply to
  push-capable OSes (FCM/WNS).
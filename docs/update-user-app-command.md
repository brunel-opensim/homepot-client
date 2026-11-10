# Update the User App (One-shot) — Design

Status: In progress — the one-shot update, the `generic` provider switch, and
the `update_app` command (agent handler, Electron stdout marker, AI registry,
and compose template) are implemented; rollback ("previous" channel) and the
Electron → agent terminal channel are follow-ons.

> Decision: Updating the User App is a **single one-shot action** — check,
> download, and restart-to-install happen in one step, both in the on-device UI
> and (later) as a single `update_app` command from the Dashboard. The
> **stable** source of truth is the Dashboard **Downloads page** (`/downloads`),
> not the GitHub release. The User App is installed **per device** (one install
> per device), and a broken release must be **rollback-able to the previous
> version**.

## Problem

Today a device owner updates the User App manually, on the device, in three
steps:

1. **Check** — `app:checkForUpdates` → `performUpdateCheck()`.
2. **Download** — `app:downloadUpdate` → `autoUpdater.downloadUpdate()` (packaged)
   or `applySourceUpdate()` (git source).
3. **Restart to install** — `app:restartToInstall` → `autoUpdater.quitAndInstall()`
   or `restartToApplySourceUpdate()`.

This is split across three buttons and only reachable from the device window, so
a technician or the AI cannot drive it from the Dashboard.

There is also a **split-brain in the update source**:

| Reader | Source |
|---|---|
| Downloads page (`Downloads.jsx` + `updateFeed.js`) | `https://…/downloads/latest.yml` — the **server** (`dist/downloads`) |
| Auto-updater (`electron-updater`) | `publish.provider: "github"` — the **GitHub release** |

`scripts/mirror-downloads.sh` already downloads the GitHub release, verifies it
against `sha256`/`checksums.json`, and atomically swaps it into `dist/downloads`.
So the server is already the curated, verified "stable" location — the
auto-updater just is not reading from it yet.

## Goal

1. Make the **server-hosted Downloads page the single source of truth** for
   updates, by switching `electron-updater` from the GitHub provider to a
   `generic` provider pointing at `/downloads`.
2. Collapse the three-step flow into a **single one-shot "Update" action** in the
   on-device UI.
3. Provide **rollback to the previous version** when a release misbehaves.
4. Add an `update_app` command so the Dashboard (or the AI) can trigger the same
   one-shot remotely.

## Design

### 1. Update source: `generic` provider → `/downloads`

In `user_app/package.json`, change the publish block from GitHub to a static
server URL:

```jsonc
"publish": {
  "provider": "generic",
  "url": "https://homepot.cabera.com/downloads"
}
```

The feed format (`latest.yml` / `latest-mac.yml` / `latest-linux.yml` plus
`*.blockmap`) is identical either way — electron-builder generates it; only the
host changes. The Downloads page already parses that exact feed, so "stable" now
means **mirrored + verified + atomically staged into `/downloads`**.

**Install mode.** The User App is installed **per device** (one install per
device — the NSIS per-user default, no `--all-users`). This keeps
`quitAndInstall()` silent: the installer runs in the user's context with no UAC
prompt. A per-machine install would re-run elevated and require a UAC click,
which one-shot cannot provide — that mode is out of scope, but it is why the
per-device model matters.

### 2. One-shot update flow

The explicit update action chains check → download → restart automatically. The
**background auto-check** (30s after launch + every 4h) stays **check-only** —
it notifies "update available" but never auto-restarts without an explicit
action.

| Mode | Check | Download | Restart |
|---|---|---|---|
| Packaged (`generic`) | `latest.yml` on `/downloads` | `autoUpdater.downloadUpdate()` (blockmap diff) | `autoUpdater.quitAndInstall()` |
| Source (git) | `git fetch` behind-count | `applySourceUpdate()` (pull + npm + vite build) | `restartToApplySourceUpdate()` |

### 3. Electron changes (`user_app/electron/main.ts`)

- Add a module-level flag `let installOnDownload = false`.
- **`update-available`** — when the flag is set, skip the notification and call
  `autoUpdater.downloadUpdate()` immediately.
- **`update-downloaded`** — when the flag is set, call
  `autoUpdater.quitAndInstall()` (no "restart to finish" prompt).
- **`update-not-available`** and **`error`** — reset the flag (a later check-only
  run must not auto-install).
- Add a new **`app:updateNow`** handler:
  - source mode → `applySourceUpdate()`; if it returns `downloaded`, call
    `restartToApplySourceUpdate()`.
  - packaged mode → set `installOnDownload = true`, then `performUpdateCheck()`
    (the event handlers drive download + install).
- Remove `app:downloadUpdate` and `app:restartToInstall` (subsumed by
  `app:updateNow`). Keep `app:checkForUpdates` and `app:getUpdateState`.

### 4. Preload (`user_app/electron/preload.ts`)

Expose `app.updateNow`; drop `downloadUpdate` and `restartToInstall`.

### 5. Renderer (`user_app/src/views/DeviceInfo.tsx`)

- Replace `handleCheckUpdate` / `handleDownloadUpdate` / `handleRestartToInstall`
  with a single `handleUpdateNow`.
- **Remove the 5s auto-fast-path** (it would otherwise trigger a full update at
  launch); rely on the main process's 30s auto-check for the "up to date"
  display.
- Collapse the render states:
  - `idle` / `not-available` → one **"Update app"** button.
  - `checking` / `updating` → spinner.
  - `downloading` → progress bar.
  - `error` / `disabled` → message + "Retry".
  - `available` / `downloaded` → transient (render as progress, no button).

### 6. Type definitions (`user_app/src/services/credentialStorage.ts`)

Add `updateNow()` to the `electronAPI.app` interface; drop the removed methods.
Keep `available`/`downloaded` in `UpdateState` (they still occur transiently).

## Rollback to the previous version

A broken release must not strand a device. Rollback is the same operation as
update, pointed at an older version: download the previous installer and silent-
install it.

### Approach: "previous" channel

The mirror script's atomic swap already keeps the previous version's full feed
and installers in its backup. Serve that as a `previous` channel alongside
`latest.yml`, and roll back by reusing the update pipeline:

```ts
autoUpdater.allowDowngrade = true   // permit a lower version
autoUpdater.channel = 'previous'    // fetch previous.yml instead of latest.yml
// → checkForUpdates() → downloadUpdate() → quitAndInstall()
```

- Reuses the blockmap differential and checksum verification.
- One step back only (the immediately-previous version).

### Fallback: manual reinstall

The Downloads page serves installers and GitHub retains every release, so a
device can always be rolled back by downloading and running the previous
installer by hand. This is the zero-code safety net.

**Deferred:** an explicit version downgrade (`rollback_app` /
`update_app --target=<version>`) to go back to any release, not just the
immediately-previous one.

## `update_app` command (implemented)

The `update_app` command lets the Dashboard or AI trigger the same one-shot
remotely:

- **Command** — `update_app` (T3, `root_access`), added to `COMMAND_TYPES`,
  `REQUIRED_PERMISSION`, the AI `ACTION_REGISTRY`, the AI command titles, and
  the compose-command templates in `PushReview.jsx`.
- **Agent → Electron** — after the agent posts the "update initiated" result it
  prints the reserved `UPDATE_APP_MARKER` (`__HOMEPOT_UPDATE_APP__`) to stdout.
  Because the agent must stay alive through the download (unlike `restart_agent`,
  which exits), this uses a **stdout marker** rather than a reserved exit code.
  The Electron supervisor detects the marker and runs the one-shot update.
- **Result confirmation** — success is confirmed by the device's `agent_version`
  bump on the next heartbeat (it already reports `app_version` in the device
  DNA). The command reports "update initiated", not the final outcome.

**Deferred:**

- **Electron → agent terminal signal** — the Electron shell does not yet report
  the outcome (downloaded / no-update / error) back to the agent, because the
  agent cannot see electron-updater's lifecycle. The current stdin is `'ignore'`;
  this needs a minimal channel (piped stdin line or a status file), so failures
  are not silently invisible.
- **`rollback_app`** — reuses the same machinery with `channel: 'previous'` +
  `allowDowngrade`.

## Edge cases

1. **Auto-check must not auto-install** — only the explicit `app:updateNow` (and
   the future command) sets `installOnDownload`.
2. **No update available** — one-shot must return a clean "already up to date",
   not a hung "initiated".
3. **Download error** — must surface to the caller (on-device UI, and later the
   Dashboard), not silently do nothing.
4. **Restart kills the agent** — `quitAndInstall()` restarts the whole app
   (Electron + agent), so the device briefly drops its heartbeat; the version
   bump on restart confirms success.
5. **Rollback** — a `previous` channel must always point at the last-known-good
   version, and `allowDowngrade` must be set only for the rollback path (not for
   the normal `latest` update, which must never silently downgrade).

## Scope of change

| Layer | Change | Effort |
|---|---|---|
| Electron (`main.ts`, `preload.ts`) | one-shot flag + `app:updateNow` + handler changes | Small |
| Renderer (`DeviceInfo.tsx`) | collapse buttons + remove fast-path | Small |
| Types (`credentialStorage.ts`) | interface + `UpdateState` | Small |
| Packaging (`package.json`) | `publish.provider` → `generic` | Small |
| Tests (`views.test.tsx`) | one-shot API + UI assertions | Moderate |
| Rollback (`main.ts`, mirror script) | `previous` channel + `allowDowngrade` | Deferred (follow-on) |
| `update_app` command | agent handler + stdout marker + AI registry + compose template | Implemented |
| Terminal channel (`main.ts`, agent) | Electron → agent outcome report | Deferred (follow-on) |

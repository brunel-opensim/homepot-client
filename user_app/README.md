# HOMEPOT Agent — User App

Desktop client for the HOMEPOT device management platform. Runs as a
browser-based SPA during development and as a native Electron shell in
production.

## Quick start

```bash
npm install
npm run dev              # browser-only SPA at http://localhost:5174
VITE_ELECTRON=true npm run dev   # launch Electron with HMR
```

## Scripts

| Command | Description |
|---|---|
| `npm run dev` | Vite dev server (browser only) |
| `npm run electron:dev` | Electron + Vite HMR |
| `npm run build` | TypeScript check + production build |
| `npm run electron:build` | Build + package with electron-builder |
| `npm run preview` | Preview production build |

## Routes

| Path | View | Description |
|---|---|---|
| `/` | redirect | → `/home` if provisioned, → `/setup` if not |
| `/setup` | Step 1 | Device details (Site ID, hostname, type, OS) |
| `/signin` | Step 2 | Bootstrap key entry — site-level enrolment token |
| `/setup/review` | Step 3 | Review details and complete setup |
| `/home` | Dashboard | Status, gauges, heartbeat (post-provisioning) |
| `/claim` | Claim device | Enter intent ID + claim token |
| `/permissions` | Permissions | Toggle data collection access |
| `/settings` | Device Info | Identity DNA table, unpair |

## Architecture

### Technology stack

- **React 19** + **TypeScript** with Vite
- **react-router-dom** for URL-based routing
- **Electron** (optional, via `VITE_ELECTRON=true`) for native desktop
- **electron-builder** for packaging

### Credential storage

Credentials are stored through a `CredentialStorage` abstraction:

| Environment | Implementation | Storage location |
|---|---|---|
| Browser | `SessionStorage` (fallback) | `window.sessionStorage` |
| Electron | `ElectronStorage` (IPC bridge) | `~/.homepot/credentials` (mode 0600) |

Detection order: `window.electronAPI` → `SessionStorage`.

### Electron features (VITE_ELECTRON=true)

| Feature | Implementation |
|---|---|
| Window | 420×740, non-resizable, centred |
| System tray | Emerald icon, context menu (Show / Quit) |
| Hide on close | Minimises to tray instead of quitting |
| Credential storage | IPC to main process, filesystem-backed |
| Device identity | `os.hostname()`, `os.networkInterfaces()`, `os.cpus()` via IPC |
| App version | `app.getVersion()` via IPC |
| Dev-mode bypass | In-app skip buttons for testing without backend |

### Development mode

When `VITE_ELECTRON` is not set, the app runs as a normal browser SPA.
All Electron-specific code is hidden behind `window.electronAPI` detection,
so the same codebase works in both modes.

In dev mode, each flow provides a bypass:
- **/signin**: "⚡ Dev: Skip Bootstrap Key" fills in a key and advances
- **/setup/review**: "⚡ Dev: Complete Setup" generates a fake API key and
  device ID without calling the backend

## Building for distribution

```bash
npm run electron:build
```

Output goes to `release/`:

| Platform | Format |
|---|---|
| Linux | `.deb`, `.rpm`, `.AppImage` |
| macOS | `.dmg`, `.zip` |
| Windows | `.nsis` (installer), `.msi` |

## Roadmap

| PR | Focus |
|---|---|---|
| **U1** ✅ | Standalone Electron desktop shell with routing, sign-in, and native storage |
| **U2** ✅ | Device-credential auth — bootstrap key replaces SSO cookie login |
| **U3** ✅ | Device permissions DB model + API (capabilities, admin-override) |
| **U4** ✅ | Wire Permissions UI to backend (fetch, debounced PATCH, loading/error states, capability-aware) |
| **U5** ✅ | Agent-side permission enforcement (fetch perms on poll, gate privileged commands, capability-aware DNA registration) |
| **U6** ✅ | Real device DNA — fetch MAC, local IP, OS via device-credential auth, fall back to Electron IPC or credential storage |
| **U7** ✅ | Error boundaries, API service layer, unit tests (credentialStorage, API, views), integration tests |

See [`docs/device-lifecycle-and-ownership.md`](../docs/device-lifecycle-and-ownership.md#user-app-prs) for details.

## Trust model

The User App governs **what** the backend is allowed to do on this device
via the Permissions page.  Every push notification command is checked
against the stored permissions before it is dispatched — see
[`docs/agent-permissions-trust-model.md`](../docs/agent-permissions-trust-model.md).

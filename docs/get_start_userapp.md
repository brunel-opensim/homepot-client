# Getting Started — HOMEPOT User App

**Team:** GetFudo
**Stack:** React 19 + TypeScript + Vite + Tailwind CSS

---

## Prerequisites

| Tool | Version | Check |
|---|---|---|
| Node.js | 20.19+ | `node -v` |
| npm | 10+ | `npm -v` |
| nvm | Any | `nvm --version` |

> Node v16 or v18 will **not** work. Vite 8 requires Node 20.19+.

---

## One-Time Setup

```bash
# Step 1 — Switch to correct Node version
nvm use 20.19.6

# Step 2 — Go to the user app directory
cd user_app

# Step 3 — Install dependencies
npm install
```

### Make Node 20 your default (recommended)

```bash
nvm alias default 20.19.6
```

Avoids running `nvm use` every time you open a new terminal.

---

## Run Commands

| Command | What it does |
|---|---|
| `./scripts/start-userapp.sh` | Automatically check requirements and start the App via `nohup` |
| `./scripts/stop-userapp.sh` | Kill the `nohup` server processes running the user app |
| `npm run dev` | Start local dev server at http://localhost:5174 |
| `npm run build` | Production build → output to `dist/` |
| `npm run preview` | Serve the production `dist/` build locally |
| `npm run lint` | Run ESLint checks across all source files |

---

## Start the Dev Server

### Option 1: Using the provided Startup Script (Recommended)
This method automates Node version checking, port validation, and background logging.

```bash
# From the repo root
./scripts/start-userapp.sh
```

**Note:** Logs go to `logs/userapp.log`. To stop it, run `./scripts/stop-userapp.sh`.

### Option 2: Manual Start

```bash
# From the repo root
cd user_app
nvm use 20.19.6
npm run dev
```

Open **http://localhost:5174/** in your browser.

Press `Ctrl+C` in the terminal to stop manual runs.

---

### Concurrent Testing with Dashboard

By default, the Dashboard runs on port `5173`. The User App explicitly runs on port **`5174`**.
You can run both at the same time to test the provisioning workflow by executing both `./scripts/start-dashboard.sh` and `./scripts/start-userapp.sh`.

---

## If nvm is not loaded in your terminal

Run this first, then retry:

```bash
export NVM_DIR="$HOME/.nvm" && . "$NVM_DIR/nvm.sh"
nvm use 20.19.6
npm run dev
```

---

## First Run — Setup Wizard

When you open the app for the first time you will see the **Setup Wizard (Page 1)**:

1. Enter your **Site ID** (required — provided by IT admin)
2. Enter a **Device Name** (optional, e.g. `Kasi-Laptop`)
3. Click **Login with SSO** to authenticate
4. Click **Complete Setup** — app moves to the Home Dashboard

### Reset the wizard (for testing)

Open browser DevTools → **Application** → **Local Storage** → delete `homepot_token` → refresh.

---

## Project Structure

```
user_app/
  src/
    views/
      SetupWizard.tsx     ← Page 1 (first run)
      HomeDashboard.tsx   ← Page 2 (default)
      Permissions.tsx     ← Page 3
      DeviceInfo.tsx      ← Page 4
    components/           ← shared UI components
    context/
      AppContext.tsx       ← global state, view routing
    hooks/                ← API and IPC hooks
    App.tsx               ← view switcher
    main.tsx              ← entry point
    index.css             ← Tailwind directives
  index.html
  package.json
  vite.config.ts
  tailwind.config.js
```

---

## Common Issues

| Problem | Cause | Fix |
|---|---|---|
| `Vite requires Node.js 20.19+` error | Running Node v16/v18 | `nvm use 20.19.6` |
| `nvm: command not found` | nvm not loaded in shell | Run the export command above |
| UI renders unstyled (plain text) | Tailwind `content` was empty | Already fixed in `tailwind.config.js` |
| Stuck on Setup Wizard after completing | `homepot_token` not saved | Check Local Storage in DevTools |
| Port 5173 already in use | Another Vite instance running | Kill it: `lsof -ti:5173 \| xargs kill` |

---

## Related Docs

- [User App Frontend Guide](user-app-frontend-guide.md) — full tech stack, page flow, API reference
- [UI Wireframes](../ui-designs/user-app-wireframes.md) — 4-page layout sketches
- [User App Implementation](user-app-implementation.md) — architecture and phase roadmap

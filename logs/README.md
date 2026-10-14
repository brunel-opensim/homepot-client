# HOMEPOT Runtime Logs

This directory holds realtime runtime logs produced by the development scripts
and the backend/AI services. The contents are **ephemeral** and the directory is
listed in `.gitignore` (only this `README.md` is tracked).

## Typical files

| File | Producer | Notes |
|------|----------|-------|
| `backend.log` | Backend app (root logger, rotating) | `backend.out` / `backend.pid` come from the launcher scripts |
| `ai.log` | Backend `ai` logger (`ai/log_config.py`) | AI/LLM **application** logs (in-process, rotating) |
| `ollama.log` | `scripts/setup-ollama.sh` | Ollama **server** stdout — only when the script starts its own instance (dev) |
| `ollama.pid` | `scripts/setup-ollama.sh` | PID of the Ollama server it started; **not** written when reusing a systemd instance |
| `frontend.log`, `frontend.pid` | `scripts/start-dashboard.sh` | Vite dev server — **development only** |
| `emulator-<name>.log`, `emulator-<name>.pid` | `scripts/start-emulator.sh` | |
| `userapp.log`, `userapp.pid` | `scripts/start-userapp.sh` | |

## Where logs live (development vs production)

- **Development** (scripts in this repo): backend → `logs/backend.log`, AI app →
  `logs/ai.log`, Ollama server → `logs/ollama.log`, Vite dev server →
  `logs/frontend.log`.
- **Production** (`homepot-api` systemd unit + Apache):
  - Backend API → **journald** (`journalctl -u homepot-api`) *and* `logs/backend.log`.
  - AI app logs → `logs/ai.log` (and forwarded to journald via the backend).
  - Ollama runs under its own systemd unit → `journalctl -u ollama`.
- **There is no `frontend.log` in production.** The frontend is a static build
  served by Apache, so it has no server-side process. Frontend runtime errors
  appear in the **browser console**; request-level logs are in Apache's
  `access.log` / `error.log` (typically `/var/log/apache2/`).

## Purpose

- Route application output away from the terminal (e.g. `setsid ... > logs/backend.log 2>&1 &`).
- Record service PIDs (`backend.pid`, `frontend.pid`, `emulator.pid`, `ollama.pid`, `userapp.pid`)
  so the `stop-*` sibling scripts can terminate them cleanly.

> The emulator and dashboard scripts create these files automatically; you do not
> normally need to write to this directory by hand.

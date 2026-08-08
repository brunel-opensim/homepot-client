# HOMEPOT Runtime Logs

This directory holds realtime runtime logs produced by the development scripts
and emulators. The contents are **ephemeral** and the directory is listed in
`.gitignore` (only this `README.md` is tracked).

## Typical files

| File | Producer |
|------|----------|
| `backend.log`, `backend.out`, `backend.pid` | Dashboard/backend launcher scripts |
| `frontend.log`, `frontend.pid` | `scripts/start-dashboard.sh` |
| `emulator.log`, `emulator.pid` | `scripts/start-emulator.sh` |
| `ai.log`, `ai.pid` | AI/LLM service (`scripts/setup-ollama.sh`) |
| `userapp.log`, `userapp.pid` | `scripts/start-userapp.sh` |

## Purpose

- Route application output away from the terminal (e.g. `setsid ... > logs/backend.log 2>&1 &`).
- Record service PIDs (`backend.pid`, `frontend.pid`, `emulator.pid`, `ai.pid`, `userapp.pid`)
  so the `stop-*` sibling scripts can terminate them cleanly.

> The emulator and dashboard scripts create these files automatically; you do not
> normally need to write to this directory by hand.
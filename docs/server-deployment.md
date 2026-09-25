# HOMEPOT Server Deployment

## Overview

This document covers deploying HOMEPOT on a Ubuntu 24.04 server for
development and staging. The stack includes:

- **Backend**: FastAPI (uvicorn) on port 8000
- **Frontend**: Built React app served via Apache on port 80/443
- **Database**: PostgreSQL 16 (local, passwordless for development)
- **LLM**: Ollama with llama3.2 (3B model, ~2GB)
- **Domain**: homepot.cabera.com (SSL via Let's Encrypt)

## Server Requirements

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| OS | Ubuntu 24.04 LTS | Ubuntu 24.04 LTS |
| CPU | 2 cores | 4 cores |
| RAM | 4 GB | 8 GB |
| Disk | 20 GB | 50 GB |
| Python | 3.12+ | 3.12 |
| Node.js | 22+ | 22 |
| PostgreSQL | 16 | 16 |
| Ollama | Latest | Latest |

## Pre-Deployment (Server Team Tasks)

These tasks require sudo access. Ask the server team to complete them
before proceeding with deployment.

### 1. Install PostgreSQL 16

```bash
sudo apt update
sudo apt install -y postgresql postgresql-contrib
sudo systemctl enable --now postgresql
```

### 2. Configure Passwordless Local Access

Edit `/etc/postgresql/16/main/pg_hba.conf` and replace the
`host` lines with:

```
# TYPE  DATABASE  USER      ADDRESS       METHOD
local   all       postgres                peer
host    all       all       127.0.0.1/32  trust
host    all       all       ::1/128       trust
```

Then restart PostgreSQL:

```bash
sudo systemctl restart postgresql
```

> **Security note**: `trust` auth means any local process can connect
> without a password. This is acceptable for development. Revert to
> `md5` or `scram-sha-256` before production hardening.

### 3. Add demouser to postgres Group

```bash
sudo usermod -aG postgres demouser
```

This allows demouser to manage PostgreSQL without sudo.

### 4. Install Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sudo sh
```

This installs the Ollama binary to `/usr/local/bin/ollama`.

### 5. Stop Existing HOMEPOT Services

```bash
sudo systemctl stop homepot-api homepot-agent homepot-frontend 2>/dev/null
sudo systemctl disable homepot-api homepot-agent homepot-frontend 2>/dev/null
```

## Deployment (demouser Tasks)

All steps below are performed as `demouser` **without sudo**.

### 1. Clone Repository

```bash
cd /var/www
git clone https://github.com/brunel-opensim/homepot-client.git homepot.cabera.com
cd homepot.cabera.com
```

If the repo already exists:

```bash
cd /var/www/homepot.cabera.com
git pull origin main
```

### 2. Set Up Python Environment

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 3. Initialize Database

Under `trust` the demouser connects passwordless and needs **no sudo at all** —
this is the recommended mode once the server team finishes Section 1. Run:

```bash
HOMEPOT_DB_AUTH=trust ./scripts/init-postgresql.sh
```

The script is auth-mode aware and adapts automatically:
- `HOMEPOT_DB_AUTH=trust` — connects as `postgres` over localhost with no
  password, never asks for sudo, does **not** create `.pgpass`/`.pgpass`-style
  helpers (there is nothing to store), and writes a `DATABASE__URL` into
  `backend/.env` **without** a password.
- Default/`peer` — the existing sudo+password flow for developer machines.

Default (no env var, equivalent to `HOMEPOT_DB_AUTH=peer`):

```bash
./scripts/init-postgresql.sh
```

This script (both modes):
- Creates the `homepot_user` database user
- Creates the `homepot_db` database
- Grants privileges
- Enables TimescaleDB extension (if available)
- Runs Alembic migrations

### 4. Configure Environment

Edit `deploy/env-override.sh`:

```bash
export DATABASE__URL="postgresql://homepot_user@localhost:5432/homepot_db"
export SECRET_KEY="your-production-secret-key-here"
export CORS_ORIGINS="https://homepot.cabera.com"
export ENABLE_AGENT_SIMULATION="false"
export HOST="127.0.0.1"
export PORT="8000"
export LOG_LEVEL="INFO"
```

Also update `backend/.env` with the same `DATABASE__URL` (no password).

### 5. Set Up Ollama and Pull Model

```bash
./scripts/setup-ollama.sh
```

This script:
- Reads the model name from `ai/config.yaml` (default: `llama3.2`)
- Starts the Ollama server on port 11434
- Pulls the llama3.2 model (~2GB download)

### 6. Build Frontend

```bash
cd frontend
npm install
npm run build
cd ..
```

### 7. Start Dashboard

```bash
./scripts/start-dashboard.sh
```

This starts:
- Backend API on port 8000
- Frontend dev server on port 5173

### 8. Verify Deployment

```bash
./scripts/status.sh
```

Or manually:

```bash
curl -s http://localhost:8000/health | python3 -m json.tool
curl -s http://localhost:11434/api/tags | python3 -m json.tool
```

## Database Management

### Reset Database (Development)

During development, drop and recreate the database:

```bash
./scripts/reset-db.sh
```

Or manually:

```bash
psql -h localhost -U postgres -c "DROP DATABASE IF EXISTS homepot_db;"
psql -h localhost -U postgres -c "CREATE DATABASE homepot_db OWNER homepot_user;"
psql -h localhost -U postgres -d homepot_db \
  -c "GRANT ALL ON SCHEMA public TO homepot_user;"
./scripts/upgrade-db.sh
```

### Run Migrations

```bash
./scripts/upgrade-db.sh
```

### Query Database

```bash
./scripts/query-db.sh tables
./scripts/query-db.sh devices
./scripts/query-db.sh "SELECT * FROM devices LIMIT 5;"
```

## LLM Management

### Start Ollama

```bash
./scripts/setup-ollama.sh
```

### Check Model Status

```bash
ollama list
```

### Model Sizing Guide

| Model | Parameters | File Size | Speed (CPU) | Use Case |
|-------|-----------|-----------|-------------|----------|
| **llama3.2** (Default) | 3B | ~2.0 GB | ~40 tok/s | General queries, analysis |
| mistral | 7B | ~4.1 GB | ~20 tok/s | Complex analysis |
| phi3.5 | 3.8B | ~2.2 GB | ~50 tok/s | Quick status checks |

### LLM Configuration

Edit `ai/config.yaml`:

```yaml
llm:
  model: "llama3.2"
  base_url: "http://localhost:11434"
  temperature: 0.7
  context_window: 4096
```

## Device Connection

### 1. Register Device via API

```bash
curl -X POST https://homepot.cabera.com/api/v1/devices/sites/{site_id}/devices \
  -H "Content-Type: application/json" \
  -d '{"device_name": "POS-001", "device_type": "pos_terminal"}'
```

### 2. Install User App on Device

On the Windows device:

```powershell
# Run as Administrator
.\scripts\install-agent.ps1
```

### 3. User App Handles Elevation

The User App (Electron) automatically handles `homepot-ctl` installation:
- On Windows: triggers UAC elevation, installs `homepot-ctl.ps1`
- On macOS: triggers admin password prompt, installs `homepot-ctl`
- On Linux: triggers PolicyKit dialog, installs `homepot-ctl`

No server-side configuration is needed for elevation.

## Scripts Reference

| Script | Purpose | Requires sudo? |
|--------|---------|----------------|
| `init-postgresql.sh` | Full database setup | No |
| `setup-ollama.sh` | Install/start Ollama, pull model | No |
| `start-dashboard.sh` | Start backend + frontend | No |
| `stop-dashboard.sh` | Stop both services | No |
| `reset-db.sh` | Drop and recreate database | No |
| `status.sh` | Check all service statuses | No |
| `upgrade-db.sh` | Run Alembic migrations | No |
| `query-db.sh` | Query database | No |
| `seed-demo-data.sh` | Seed demo data | No |

## Troubleshooting

### PostgreSQL Connection Refused

```bash
# Check if PostgreSQL is running
pg_isready -h localhost -p 5432

# If not running, ask server team to start it
sudo systemctl start postgresql
```

### Ollama Not Responding

```bash
# Check if Ollama is running
curl -s http://localhost:11434/api/tags

# Restart Ollama
./scripts/setup-ollama.sh
```

### API Returns 500 Errors

```bash
# Check API logs
tail -f logs/api.log

# Verify database connection
./scripts/query-db.sh tables
```

### Port Already in Use

```bash
# Check what's using the port
ss -tlnp | grep :8000
ss -tlnp | grep :11434
```

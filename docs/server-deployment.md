# HOMEPOT Server Deployment

## Overview

This document covers deploying HOMEPOT on a Ubuntu 24.04 server for
development and staging. The stack includes:

- **Backend**: FastAPI (uvicorn) on port 8000
- **Frontend**: Built React app served via Apache on port 80/443
- **Database**: PostgreSQL 16 (local, passwordless for development)
- **LLM**: Ollama with llama3.2 (3B model, ~2GB)
- **Domain**: homepot.cabera.com (SSL via Let's Encrypt)

## Production as-built (homepot.cabera.com)

Current state of the live production server, for technicians applying changes.
Last verified: 2026-10-13, after the first successful production reset (current
`main`).

### Topology

- **Split-host**: application/web host `51.161.114.192` and database host
  `51.161.114.195:5432`. Apache serves `https://homepot.cabera.com` and
  reverse-proxies to the API on loopback only.
- **Checkout**: `/var/www/homepot.cabera.com`, files owned `ubuntu:homepot`,
  operator account `demouser`. Never run `git` via sudo.

### Python environment

- The venv lives at the **checkout root**: `/var/www/homepot.cabera.com/.venv`
  (canonical location — do not use `backend/.venv`). Rebuild it with:

  ```bash
  cd /var/www/homepot.cabera.com
  python3 -m venv .venv
  .venv/bin/pip install -e backend/
  .venv/bin/pip install -r backend/requirements.txt
  .venv/bin/python -c "import homepot, passlib, sqlalchemy, bcrypt, psycopg2"
  .venv/bin/alembic --version
  ```

  Run **both** installs — the same sequence `install-backend.sh` performs. The
  editable step alone pulls the latest SQLAlchemy, and ≥ 2.1 resolves a bare
  `postgresql://` URL to the psycopg 3 dialect, which is not installed; the
  pinned `requirements.txt` (`sqlalchemy==2.0.45`, `psycopg2-binary`) keeps the
  sync driver on psycopg2. Missing that second step is what broke `alembic
  stamp` on the 2026-10-13 reset (`No module named 'psycopg'`), fixed by #490.

- Verified: `alembic 1.20.0`; schema stamped at head
  `20260929_add_command_issued_by`. The retired `backend/.venv` was backed up
  to `/root/homepot-venv-backup-*`.

### Service

- Unit: `/etc/systemd/system/homepot-api.service` (no drop-ins as last known).
- `WorkingDirectory=/var/www/homepot.cabera.com/backend`
- `ExecStart=/var/www/homepot.cabera.com/.venv/bin/uvicorn homepot.app.main:app --host 127.0.0.1 --port 8000 --log-level info`
- `homepot.app.main:app` is the canonical entrypoint; the legacy
  `homepot.main:app` must never be started.

### Database

- Database `homepot`, role `homepot_user` (owner, has `CREATEDB`), on
  `51.161.114.195`, password auth (scram). The two `pg_hba.conf` rules for the
  web host and the maintenance-URL technique are recorded in
  `docs/server-admin-option-b.md` (§ As-built).

### Credentials (gitignored, deploy-only)

- `backend/.env` → `DATABASE__URL` used by the app and the reset scripts.
- `scripts/seed-users.env` → account set applied by
  `scripts/seed-users.sh` after a reset (3 dev accounts: `maziar` Admin,
  `gowtham` Technician, `robin` Technician, shared dev password). Google SSO
  env vars are not configured.

### LLM (Ollama)

- `ollama` **0.40.4** installed and running as a systemd unit
  (`ollama.service`), **enabled at boot**, listening on `127.0.0.1:11434`.
  The `llama3.2` model (~2 GB) is pulled.
- The app reads the model/host from `ai/config.yaml` (`llm.model`,
  `llm.base_url`). The dashboard AI calls Ollama **in-process** from the backend
  (`ai/llm.py` → `localhost:11434`); the standalone `ai/api.py` service on
  `:8001` is **not** required.
- `demouser` has a scoped NOPASSWD rule for `systemctl start|stop|restart ollama`
  (`/etc/sudoers.d/homepot-ollama`).
- A **2 GB swapfile** is configured (the host has no other swap) to absorb the
  model-load memory spike.

### Status (post-reset, 2026-10-13)

- **Reset executed successfully** with `scripts/reset-prod-db.sh`: DB dropped
  and recreated as `homepot_user`, service restarted onto the root `.venv`,
  alembic stamped at head (`20260929_add_command_issued_by`, 16 tables), and
  three accounts provisioned — `maziar` (Admin), `gowtham` (Technician),
  `robin` (Technician), shared dev password.
- Verified live: `/api/v1/health` → 200; password login as `maziar` returns a
  JWT with `is_admin: true`.
- `demouser` has scoped passwordless sudo for **exactly** `/usr/bin/systemctl
  stop homepot-api` and `/usr/bin/systemctl start homepot-api` (file
  `/etc/sudoers.d/homepot-api-reset`) — required by `reset-prod-db.sh`;
  nothing broader was granted.
- Pre-reset devices were wiped by design — re-register devices after a reset.

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

> **Before starting:** run the read-only readiness check. It tells you whether
> the app and the database share a host or not, and it verifies the live API:
>
> ```bash
> ./scripts/preflight-server.sh                        # single-box (default)
> HOMEPOT_DB_HOST=<db server IP> ./scripts/preflight-server.sh   # split-host
> ```
>
> If the database lives on a **different machine**, do not enable `trust` and do
> not run `init-postgresql.sh` / `reset-db.sh` there — those drop and create
> databases. See `docs/server-admin-option-b.md` for the two modes and check 5,
> which flags a database-name mismatch before anything destructive can run.

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
sudo systemctl enable --now ollama
```

This installs the Ollama binary to `/usr/local/bin/ollama` and registers a
systemd unit (`ollama.service`) that listens on `127.0.0.1:11434`. Enable it so
it starts at boot.

To let `demouser` manage Ollama without broad sudo, add a scoped rule at
`/etc/sudoers.d/homepot-ollama` (`chmod 0440`; validate with `visudo -c`):

```
demouser ALL=(ALL) NOPASSWD: /usr/bin/systemctl start ollama, /usr/bin/systemctl stop ollama, /usr/bin/systemctl restart ollama
```

For low-RAM hosts, add a **2 GB swapfile** so the model load does not OOM
(the production host has one).

### 5. Stop Existing HOMEPOT Services

```bash
sudo systemctl stop homepot-api homepot-agent homepot-frontend 2>/dev/null
sudo systemctl disable homepot-api homepot-agent homepot-frontend 2>/dev/null
```

### 6. Reverse Proxy Timeout (Apache)

The dashboard AI answers with local CPU inference and can take **60-120 s**
(longer on the first, cold request). Apache's default `Timeout`/`ProxyTimeout`
is 60 s, so it will cut the response off with a **504** before the backend
finishes. In the API vhost, raise both to match the app:

```apache
ProxyTimeout 180
Timeout 180
```

Then reload Apache:

```bash
sudo systemctl reload apache2
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

The venv lives at the **checkout root** (`.venv/`), not under `backend/` —
this matches `install-backend.sh` and the systemd unit's ExecStart. Run from
the repo root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e backend/
pip install -r backend/requirements.txt
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

The server team installs and enables Ollama (§ Pre-Deployment → Install
Ollama). As `demouser`, just pull the model:

```bash
./scripts/setup-ollama.sh
```

This script:
- Reads the model name from `ai/config.yaml` (default: `llama3.2`)
- Detects and **reuses** the existing systemd Ollama instance on `:11434`
  (it does not start a second server, and writes no PID file in this case)
- Pulls `llama3.2` (~2 GB) if it is missing
- Writes server stdout to `logs/ollama.log` only when it starts its own
  instance (development)

Verify:

```bash
ollama list                                   # -> llama3.2:latest
curl -s http://127.0.0.1:11434/api/version    # -> {"version":"0.40.4"}
```

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

### 9. Publishing User App installers (optional)

Technicians install the packaged **User App** (`user_app/`) on their own machines;
the API and dashboard stay on this server. Because the vhost `DocumentRoot` is
`frontend/dist`, any file placed in a subdirectory there is served publicly as
static content — so a download link needs **no Apache change and no root**:

```bash
# demouser is in the `homepot` group, which has write access to dist/
mkdir -p /var/www/homepot.cabera.com/frontend/dist/downloads

# From a machine with the release downloaded (see the GitHub release), copy
# every platform's installers, the update feeds and the checksum manifest.
# checksums.json is produced by the packaging job and MUST ship alongside the
# files it describes, or the Downloads page shows no checksums.
scp homepot-agent-setup-<version>.exe homepot-agent-<version>.msi \
    homepot-agent-<version>-arm64.dmg homepot-agent-<version>-arm64.zip \
    homepot-agent-<version>-x86_64.AppImage homepot-agent-<version>-amd64.deb \
    homepot-agent-<version>-x86_64.rpm \
    latest.yml latest-mac.yml latest-linux.yml checksums.json \
    demouser:/var/www/homepot.cabera.com/frontend/dist/downloads/
```

Technicians then fetch them over HTTPS, e.g.:

```
https://homepot.cabera.com/downloads/homepot-agent-setup-0.3.0.exe
```

#### checksums.json

`checksums.json` lists every published artifact with its `sha256` (hex), its
`sha512` (base64) and its size:

```json
{
  "files": {
    "homepot-agent-setup-0.3.0.exe": {
      "sha256": "749d4bdb…",
      "sha512": "wawin3Y2…==",
      "size": 128115209
    }
  }
}
```

It is **generated by the packaging job** in
`.github/workflows/user-app-build.yml` from the exact bytes in `release/`, not
written by hand — so it cannot describe a file other than the one that was
built. The same step is a **gate**: it fails the build if any file the update
feeds reference is missing from the manifest, or if its `sha512` differs from
the feed's. That is what keeps the checksum page and the auto-updater telling
technicians the same story; run it locally to reproduce a failure:

```bash
cd /path/to/artifacts   # the dir containing release/ and latest*.yml
python3 - <<'PY'
import base64, hashlib, json, pathlib, re, sys
release = pathlib.Path('release'); manifest = {}
for path in sorted(release.iterdir()):
    if not path.is_file() or path.name.endswith('.blockmap'): continue
    if not path.name.endswith(('.exe','.msi','.dmg','.zip','.AppImage','.deb','.rpm')): continue
    data = path.read_bytes()
    manifest[path.name] = {'size': len(data),
        'sha256': hashlib.sha256(data).hexdigest(),
        'sha512': base64.b64encode(hashlib.sha512(data).digest()).decode()}
for feed in sorted(release.glob('latest*.yml')):
    for url, sha512 in re.findall(r'url:\s*(\S+).*?sha512:\s*(\S+)', feed.read_text(), re.DOTALL):
        url, sha512 = url.strip('\'"'), sha512.strip('\'"')
        entry = manifest.get(url)
        if entry is None: print(f'ERROR: {feed.name} references {url} with no entry'); sys.exit(1)
        if entry['sha512'] != sha512: print(f'ERROR: {feed.name} sha512 mismatch for {url}'); sys.exit(1)
print('feeds agree with the manifest')
PY
```

The page shows the **SHA-256** (what `certutil`, `shasum` and `sha256sum` print
by default). The feed's SHA-512 is retained for the updater. Because SHA-256
cannot be derived from SHA-512, the manifest is the only source of the SHA-256 —
which is exactly why it is CI-generated rather than reconstructed later.

#### Downloads page in the dashboard

Directory listing is disabled (`Options -Indexes`), so browsing to
`/downloads/` returns **403** and the files are only discoverable by their exact
names. The dashboard's **Downloads** page (`/downloads`, in the sidebar under
*Actions*) is the discoverable entry point.

It does not hardcode the version. At load it reads the update feeds
(`latest.yml`, `latest-mac.yml`, `latest-linux.yml`) plus `checksums.json` and
shows the version, filenames, sizes and SHA-256 digests actually staged, so it
cannot disagree with the server. A missing `checksums.json` is not an error: the
page simply omits the checksum blocks.

Two traps worth knowing when debugging it:

1. **A missing feed does not 404 here.** The SPA fallback rewrites unknown paths
   to `index.html` and returns **200 with an HTML body**, so a naive `resp.ok`
   check would treat an absent feed as present. The page rejects a body that
   does not start like YAML, which is why an unpublished platform shows "No
   build published" rather than a broken link.

2. **The page route and the installer directory share the path `/downloads`.**
   Because a *real* directory of that name exists, Apache's `DirectorySlash`
   redirected `/downloads` to `/downloads/`, which then hit
   `Options -Indexes` and returned **403** — the page was unreachable. The
   `.htaccess` therefore disables `DirectorySlash` and rewrites the bare
   `/downloads` path to the SPA, matching real **files** before directories so
   the installers still serve.

   This only shows up behind Apache. Serving `dist/` with a plain static server
   (or a test stub) does not reproduce `DirectorySlash`, so **the page must be
   checked over HTTPS on the server**, not only against a local dev server:

   ```bash
   for u in /downloads /downloads/latest.yml /downloads/homepot-agent-setup-<version>.exe; do
     curl -s -o /dev/null -w "%{http_code}  $u\n" "https://homepot.cabera.com$u"
   done   # all must be 200
   ```

Notes:

- **Verify the transfer.** These files are ~130 MB each and a dropped connection
  silently leaves a truncated file at a valid-looking URL, which fails only when
  a technician runs it. Always compare sizes/hashes after copying:

  ```bash
  # Sizes on the server ...
  ssh demouser 'stat -c "%s %n" /var/www/homepot.cabera.com/frontend/dist/downloads/*'

  # ... against the manifest, which the Downloads page also serves.
  # Any mismatch means a bad transfer: delete the file and re-copy.
  curl -s https://homepot.cabera.com/downloads/checksums.json | python3 -m json.tool
  ssh demouser 'cd /var/www/homepot.cabera.com/frontend/dist/downloads && sha256sum *.exe *.msi *.dmg *.zip *.AppImage *.deb *.rpm'
  ```

  `checksums.json` must be copied in the **same** upload as the files it
  describes. Copying a new installer but leaving an old manifest behind would
  make the page display a stale SHA-256 — worse than showing none. If the
  manifest is missing entirely the page degrades to no checksums, which the
  technician guide covers.

  A truncated upload is worse than a missing one — remove it and retry rather
  than leaving it in place.
- **`rsync` from macOS is unreliable here.** macOS ships `openrsync`
  (`protocol version 29`, advertised as rsync 2.6.9-compatible), which rejects
  common flags such as `--append-verify`. Plain `scp` works; run large copies in
  the background so a network hiccup does not abort them.
- For Windows auto-update to function, the installer `.exe` and `latest.yml` must
  be **replaced together** whenever a new version is published; a stale
  `latest.yml` points the updater at a missing file. The `url:` inside
  `latest.yml` must exactly match the asset filename — this is asserted at
  package time in CI (see `.github/workflows/user-app-build.yml`).
- `npm run build` (frontend) recreates `frontend/dist` and will remove
  `downloads/`. Re-copy the installers **and `checksums.json`** after rebuilding
  the dashboard, or keep a separate directory outside `dist` and reference it
  with an `Alias` (requires root).

  **Deploying the dashboard therefore silently removes the installers.** The
  Downloads page (below) will then report "No build published" until they are
  re-staged — including `checksums.json`, without which the page shows no
  checksums. After any frontend deploy, confirm they are still present:

  ```bash
  ssh demouser 'ls -l /var/www/homepot.cabera.com/frontend/dist/downloads/'
  ```
- **Apache config lives in `frontend/public/.htaccess`, not `dist/`.** Vite
  copies `public/` into `dist/` on every build, so `dist/.htaccess` is a build
  artifact. Edit the **`public/`** copy, or the change is lost on the next
  deploy. Rule changes there need no root (`demouser` owns both files) and take
  effect immediately — no Apache restart.
- A published GitHub release is the other delivery route and is what the app's
  built-in updater is configured against
  (`provider: github`, in `user_app/package.json`). The release also carries
  `checksums.json`, so the same digests are available from either route.

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

### Reset Database (Production)

Use `scripts/reset-prod-db.sh` — it reads `backend/.env` for the real database,
connects via the maintenance URL to perform the DROP/CREATE, refuses to touch
system databases, and re-runs migrations plus the user seed on success.
Prerequisites: both `pg_hba.conf` rules, `CREATEDB` on `homepot_user`, the root
`.venv`, and a populated `scripts/seed-users.env`. Run `--dry-run` first, then
the real run (it types the database name to confirm):

```bash
./scripts/reset-prod-db.sh --dry-run
./scripts/reset-prod-db.sh
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

### Start / Restart Ollama

On production Ollama runs as a systemd service — restart it directly:

```bash
sudo systemctl restart ollama        # scoped NOPASSWD rule for demouser
journalctl -u ollama -n 50 --no-pager
```

`./scripts/setup-ollama.sh` is mainly for pulling models and development; it
reuses (and never restarts) an existing systemd instance.

### Check Model Status

```bash
ollama list
```

### AI Query Latency & Timeouts

`llama3.2` on CPU generates at ~4 tok/s and evaluates *new* prompt tokens at
~22 tok/s (the cached system-prompt prefix is effectively free). The static
prompt plus the live context and an uncapped answer can take **60-120 s**; the
tunings below bring a warm answer down to roughly **40-60 s**.

- **Output cap**: `num_predict` (`ai/config.yaml`, default `160`) bounds the
  generated tokens; without it the model can emit 1k+ tokens, adding tens of
  seconds of pure generation.
- **Prompt trim** (static): `SystemKnowledge` caps the README overview and
  DB-schema blocks and moves all invariant text (e.g. role definitions) into
  the cached system prompt (`ai/system_knowledge.py`).
- **Live-context trim**: every dynamic token is re-evaluated by the CPU each
  turn, so `ContextBuilder` injects only a few recent audit/API rows and
  excludes the assistant's OWN audit events (`ai_*`) — otherwise each answer
  feeds its previous turns back into its own prompt. Sizes are logged as
  `AI context parts | full=... site=... enriched=...`.
- **Warm-up / KV cache**: on startup the backend primes Ollama with the *real*
  system prompt (`SystemKnowledge.get_system_prompt()`), and `keep_alive`
  (`ai/config.yaml`, default `30m`) keeps the model and cached prefix resident,
  so sparse queries skip both the reload and the prompt-eval cost. The same
  startup hook also rebuilds the **docs vector index** when `docs/*.md` changed
  (~100 s for ~3,220 chunks — see `docs/ai-doc-retrieval.md`), so an edit made in
  a deploy is never billed to the first technician's question afterwards. Both
  run in the background and neither blocks startup or holds a generation slot;
  a restart logs `Docs index warm-up: rebuilt|already current (…s)`.
- **Frontend**: `/api/v1/ai/query` uses `VITE_AI_QUERY_TIMEOUT` ms (default
  `180000`) — see `frontend/src/services/api.js`.
- **Proxy**: Apache must allow at least as long (`ProxyTimeout 180` /
  `Timeout 180`; see Pre-Deployment → Reverse Proxy Timeout).
- The LLM call runs in a worker thread (`asyncio.to_thread`), so a slow answer
  no longer blocks other API requests.
- Per-request timings (`prompt_eval_ms`, `eval_ms`, `num_predict`) are logged
  as `LLM generate | ...` lines — useful to confirm the mitigations above.

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
  context_window: 8192  # fits the ~3.8k-token system prompt + live context
  num_predict: 160      # cap generated tokens (bounds answer latency)
  keep_alive: "30m"     # keep the model + KV-cache prefix resident
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
| `reset-db.sh` | Drop and recreate database (dev) | No |
| `reset-prod-db.sh` | Deployment-safe reset (DROP/CREATE via maintenance URL) | Yes (systemctl) |
| `seed-users.sh` | Seed/rotate user accounts | No |
| `add-user.sh` | Add a single user | No |
| `status.sh` | Check all service statuses | No |
| `upgrade-db.sh` | Run Alembic migrations | No |
| `query-db.sh` | Query database | No |
| `seed-demo-data.sh` | Seed demo data | No |

## Logging & Observability

Where each component logs on production, and how to read it:

| Component | Production | Development |
|-----------|-----------|-------------|
| Backend API | `journalctl -u homepot-api` **and** `logs/backend.log` | `logs/backend.log` |
| AI / LLM app | `logs/ai.log` (also in journald via the backend) | `logs/ai.log` |
| Ollama server | `journalctl -u ollama` | `logs/ollama.log` |
| Frontend | **none** — static build served by Apache; errors in the browser console, requests in `/var/log/apache2/{access,error}.log` | `logs/frontend.log` (Vite dev server) |

```bash
journalctl -u homepot-api -n 100 --no-pager    # backend (production)
journalctl -u ollama -n 50 --no-pager          # LLM server
tail -f logs/ai.log                            # AI app logs
tail -f logs/backend.log                       # backend file log
```

> `logs/` is ephemeral and gitignored. `frontend.log` is created **only** by the
> development launcher (`scripts/start-dashboard.sh`) — there is no frontend log
> on production because the frontend has no server-side process.

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
curl -s http://127.0.0.1:11434/api/tags

# Production: restart the systemd service (scoped NOPASSWD for demouser)
sudo systemctl restart ollama
journalctl -u ollama -n 50 --no-pager

# Pull/re-check the model
./scripts/setup-ollama.sh
```

### API Returns 500 Errors

```bash
# Check API logs (production: journald; also logs/backend.log)
journalctl -u homepot-api -n 100 --no-pager
tail -f logs/backend.log

# Verify database connection
./scripts/query-db.sh tables
```

### Port Already in Use

```bash
# Check what's using the port
ss -tlnp | grep :8000
ss -tlnp | grep :11434
```

### Dashboard Unreachable From One Machine (ISP Content Filter)

Symptom: `https://homepot.cabera.com` works on some devices/networks but fails on
another, with client errors such as:

- Safari — "Can't Open the Page"
- Firefox — "SSL received a record that exceeded the maximum permissible length"
- `curl` — "wrong version number" or "tlsv1 alert protocol version"

These mean a network-level content filter is intercepting TLS and returning a block
page, not a HOMEPOT or browser problem. Seen in the field with **EE broadband**,
whose "WiFi Security (Advanced Web Protect)" / "Web Safe" setting blocks
`homepot.cabera.com` and redirects to `block.ee.co.uk`. Every browser on the
affected machine fails identically; other machines (including phones on cellular)
are unaffected.

Diagnose from the affected machine — a block page appears as a `302` to the filter:

```bash
curl -vI http://homepot.cabera.com/ 2>&1 | grep -iE 'HTTP/|Location'
```

Fix (any one):
- Disable the ISP/router web filter or parental controls for that connection.
- Ask the ISP to whitelist/recategorise `homepot.cabera.com`.
- Use a VPN or a different network (e.g. mobile hotspot) on the affected machine.

No specific browser is required; any modern browser works once the network stops
intercepting the connection.

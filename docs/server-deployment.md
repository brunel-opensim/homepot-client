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

### Database connection pool

The API holds two connection pools: the async engine (the request path and
`DatabaseService`) and a smaller synchronous engine (Alembic, the reconcile
loop, and a few sync endpoints). Both read their bounds from the same settings
and — since #572 — actually honour them (previously the async engine ignored
the pool settings entirely and ran on defaults with no recycle).

| Setting | Default | Meaning |
|---|---|---|
| `DATABASE__POOL_SIZE` | `5` | Steady-state connections per engine |
| `DATABASE__MAX_OVERFLOW` | `10` | Extra connections allowed above `POOL_SIZE` under load |
| `DATABASE__POOL_TIMEOUT` | `30` | Seconds a request waits for a connection before failing |
| `DATABASE__POOL_RECYCLE` | `300` | Seconds before a pooled connection is recycled (defends against silently dropped / SSL-closed connections) |

The async engine also enables `pool_pre_ping`, so a connection closed by
PostgreSQL or an intermediate proxy is detected before use instead of being
handed out stale.

### Database pool tuning

Defaults (5 steady + 10 overflow) fit a single uvicorn worker. If you run
multiple `--workers`, or see connection-timeout errors in the logs, raise
`DATABASE__POOL_SIZE` / `DATABASE__MAX_OVERFLOW` and confirm Postgres has
headroom: `SELECT count(*) FROM pg_stat_activity;` must stay well under
`SHOW max_connections;` (see *Database connection pool exhaustion* under
Troubleshooting).

### API request log retention

The analytics middleware writes one `api_request_logs` row per request, and
that table (with several indexes) grew unbounded — a slow-burn load source.
Since #573 a background task trims rows older than
`DATABASE__API_REQUEST_LOG_RETENTION_DAYS` (default `30`; set `0` to disable)
on startup and every 6 hours, in bounded batches so it never blocks request
traffic.

The trim is logged as `Trimmed N stale api_request_logs row(s)`. Confirm the
task is running by looking for `API request log retention task started` in
`journalctl -u homepot-api`.

### Credentials (gitignored, deploy-only)

- `backend/.env` → `DATABASE__URL` used by the app and the reset scripts.
  Owned by `homepot:homepot` with `640` permissions (read-only for `demouser`).
- `backend/.env.local` → Developer overrides (API keys, etc.). Owned by
  `demouser:homepot` with `664` permissions. `demouser` can write, `homepot`
  can read. Loaded by pydantic-settings **after** `.env`, so values here
  override `.env`. Both files are gitignored.
- `scripts/seed-users.env` → account set applied by
  `scripts/seed-users.sh` after a reset (3 dev accounts: `maziar` Admin,
  `gowtham` Technician, `robin` Technician, shared dev password). Google SSO
  env vars are not configured.

### Hybrid .env approach (dev vs production)

For environments where the deploy user (`demouser`) needs to modify secrets
(e.g. API keys for external LLM providers) without sudo access:

1. **Production secrets** go in `backend/.env` (managed by server admin).
   - Permissions: `640` (`homepot:homepot`)
   - Only the `homepot` service user and `homepot` group can read.

2. **Developer overrides** go in `backend/.env.local` (managed by `demouser`).
   - Permissions: `664` (`demouser:homepot`)
   - `demouser` can write, `homepot` can read.
   - Values here override `.env` (loaded second by pydantic-settings).

**Setup for demouser:**
```bash
# Create the file (one-time)
touch /var/www/homepot.cabera.com/backend/.env.local
chgrp homepot /var/www/homepot.cabera.com/backend/.env.local
chmod 664 /var/www/homepot.cabera.com/backend/.env.local

# Add API keys (no sudo needed)
echo 'OPENAI_API_KEY=sk-proj-...' >> /var/www/homepot.cabera.com/backend/.env.local
echo 'ANTHROPIC_API_KEY=sk-ant-...' >> /var/www/homepot.cabera.com/backend/.env.local

# Restart the backend to pick up the new env vars
sudo /usr/bin/systemctl stop homepot-api
sudo /usr/bin/systemctl start homepot-api
```

**Production considerations:**
- `.env.local` is gitignored and should never be committed.
- In production, prefer storing secrets in `.env` managed by the server admin.
- The hybrid approach is for development/demo environments where the deploy
  user needs self-service secret management.
- The AI provider module also reads from `.env.local` as a fallback, so
  keys are available even if pydantic-settings hasn't loaded them yet.

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

# Database connection pool (see "Database connection pool" above). The async
# engine now honours these; tune them if you change uvicorn workers or see
# connection-timeout errors.
export DATABASE__POOL_SIZE="5"
export DATABASE__MAX_OVERFLOW="10"
export DATABASE__POOL_TIMEOUT="30"
export DATABASE__POOL_RECYCLE="300"

# api_request_logs retention (see "API request log retention" above).
export DATABASE__API_REQUEST_LOG_RETENTION_DAYS="30"
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

#### Is the deployed dashboard current?

`frontend/dist` is git-ignored and assembled on the server, so a deployment
records nothing about its own source by default. The build therefore writes a
`build-info.json` alongside `index.html`, recording the commit it was built
from. Checking a deployment is one fetch, no login and no `ls -l` timestamps:

```bash
curl -s https://homepot.cabera.com/build-info.json
```

```json
{
  "commit": "450f9be551dec9b39c8f28e27e914026a006daa7",
  "commitShort": "450f9be",
  "branch": "main",
  "dirty": true,
  "runId": null,
  "repository": null,
  "builtAt": "2026-10-21T17:04:02.183Z"
}
```

Compare `commit` against the commit the docs and code claim, rather than
trusting a file timestamp:

```bash
curl -s https://homepot.cabera.com/build-info.json | python3 -c \
  "import json,sys; print(json.load(sys.stdin)['commitShort'])"
git -C /var/www/homepot.cabera.com log --oneline -1
```

Two fields are easy to misread:

- **`dirty`** describes the *whole checkout*, not `frontend/`. A local edit to
  an unrelated deploy-only file (e.g. `ai/config.yaml`) sets it to `true` even
  when the frontend tree is exactly at `commit`. To narrow it:
  `git status --porcelain -- frontend`. It is also `null`, not `false`, when
  git was unavailable at build time — "unknown" is not "clean".
- **`runId`/`repository`** are only set when the build ran in CI. A server-side
  build leaves them `null`, which is expected, not a fault.

The file is served with `no-store`, so a cached copy can never report an
outdated commit. If the response is **404**, the deployment predates this
feature and `frontend/dist` was not rebuilt after the plugin landed.

### 9. Publishing User App installers (optional)

Technicians install the packaged **User App** (`user_app/`) on their own machines;
the API and dashboard stay on this server. Because the vhost `DocumentRoot` is
`frontend/dist`, any file placed in a subdirectory there is served publicly as
static content — so a download link needs **no Apache change and no root**.

#### The rule: one version number, one set of bytes

The GitHub release is the **single source of truth**. The server mirrors it; it
is never assembled by hand.

This matters because a version number is a promise to two different consumers:

- the **auto-updater**, which decides whether to download by comparing versions,
  then verifies the download against the `sha512` in the feed;
- a **technician**, who reads the SHA-256 off the Downloads page and checks the
  file they actually received.

If two different builds both call themselves `0.3.0`, a device that already has
one of them can be shown a feed for the same version with a different digest.
The updater has no way to interpret that: it may conclude the release is not
newer and never update, or download it and fail verification. And no one can
tell the two apart by looking at the filename.

That is not hypothetical — it already happened with `v0.3.0`:

| | GitHub `v0.3.0` | server `/downloads` (was) |
|---|---|---|
| `latest.yml` `sha512` | `E/duYD7G…` | `wawin3Y2…` |
| `.exe` size | 128,108,327 | 128,115,209 |
| `checksums.json` | absent (predates the manifest) | present |

Two builds, one version, different bytes. `v0.3.1` exists to resolve this: it is
the first release carrying `checksums.json`, and it gives every device a
genuinely newer version to converge on.

**So: never re-upload a different build under an existing version, and never
edit a published release's assets in place.** If a build is wrong, bump the
version. The mirror below enforces the one-way nature of this by refusing
anything that does not match the published release.

#### Mirroring the release (preferred)

`scripts/mirror-downloads.sh` pulls the assets from the published release and
verifies each one before anything goes live. The repository is public, so it
needs **no token and no `gh`** — only `curl` and `python3`:

```bash
# On the server. The script is installed durably at ~/bin/mirror-downloads.sh
# (~/bin is on PATH via .profile), so it survives reboots and does not have to
# be copied over by hand. Keep it in step with the repo:
#
#   # from a workstation, after a change to the script on main:
#   git show main:scripts/mirror-downloads.sh \
#     | ssh demouser 'cat > ~/bin/mirror-downloads.sh && chmod +x ~/bin/mirror-downloads.sh'

# Verify without installing: downloads everything, checks every digest,
# leaves the live directory untouched.
DRY_RUN=1 ~/bin/mirror-downloads.sh

# Latest published release:
~/bin/mirror-downloads.sh

# A specific version:
~/bin/mirror-downloads.sh v0.3.2

# Override the destination (default: the live dist/downloads):
TARGET_DIR=/var/www/homepot.cabera.com/frontend/dist/downloads \
  ~/bin/mirror-downloads.sh
```

For each asset it checks the bytes against **GitHub's own per-asset `sha256`
digest** from the release API, then cross-checks the release's `checksums.json`
against those same bytes. Files are staged next to the target and swapped in by
rename, so the live directory is never empty and a partial download changes
nothing. The previous set is kept as `downloads.old.<timestamp>` for rollback.

It **refuses** to mirror a release that has no `checksums.json`, because doing so
would silently strip the digests from the Downloads page — worse than not
mirroring. It also refuses draft releases, whose bytes can still change.

Technicians then fetch them over HTTPS, e.g.:

```
https://homepot.cabera.com/downloads/homepot-agent-setup-0.3.1.exe
```

#### Copying by hand (fallback only)

If the mirror cannot run, copying with `scp` still works, but you own the
verification:

```bash
# demouser is in the `homepot` group, which has write access to dist/
mkdir -p /var/www/homepot.cabera.com/frontend/dist/downloads

# Take the files from the published release, not from a local build directory,
# so what is served is what was actually released.
scp homepot-agent-setup-<version>.exe homepot-agent-<version>.msi \
    homepot-agent-<version>-arm64.dmg homepot-agent-<version>-arm64.zip \
    homepot-agent-<version>-x86_64.AppImage homepot-agent-<version>-amd64.deb \
    homepot-agent-<version>-x86_64.rpm \
    latest.yml latest-mac.yml latest-linux.yml checksums.json \
    demouser:/var/www/homepot.cabera.com/frontend/dist/downloads/
```

`checksums.json` MUST ship in the **same** upload as the files it describes.
Then verify every file against the release's digests before walking away:

```bash
# For each asset, compare the local hash with what GitHub recorded:
curl -s https://api.github.com/repos/brunel-opensim/homepot-client/releases/latest \
  | python3 -c 'import json,sys; [print(a["digest"], a["name"]) for a in json.load(sys.stdin)["assets"]]'
ssh demouser 'cd /var/www/homepot.cabera.com/frontend/dist/downloads && sha256sum *.exe *.msi *.dmg *.zip *.AppImage *.deb *.rpm'
```

Any mismatch means a bad transfer. Delete the file and re-copy it — a truncated
installer fails only when a technician runs it.

#### Keeping a local copy (server-down resilience)

`homepot.cabera.com/downloads/` is a *mirror*, not the source of truth — the
GitHub release is. Because the repository is public, the installers stay
downloadable even when the server is unreachable, so a workstation can keep its
own local copy as a fallback distribution path.

A local download reads from GitHub directly and never touches the server, so it
cannot interfere with the live mirror. The copy is byte-identical to what the
server serves, because both mirror the same release.

```bash
# From a workstation. release-artifacts/ is gitignored.
mkdir -p release-artifacts/v0.3.9

# Option A — gh CLI (simplest; needs gh and its auth):
gh release download v0.3.9 --dir release-artifacts/v0.3.9 --clobber

# Option B — the mirror script against a local directory (no gh; only curl and
# python3, and it verifies every digest before finishing):
TARGET_DIR="$PWD/release-artifacts/v0.3.9" ./scripts/mirror-downloads.sh v0.3.9
```

Verify the bytes against `checksums.json` before relying on the copy: the mirror
script does this itself, while after `gh release download` you compare
`sha256sum` over the installers with the manifest's `sha256` entries. A single
machine can also be pointed straight at GitHub as a last resort:

```
https://github.com/brunel-opensim/homepot-client/releases/download/v0.3.9/homepot-agent-setup-0.3.9.exe
```

Refresh the copy on each release — it is a snapshot, not a live mirror.

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

1. **A missing feed used to not 404 here.** The SPA fallback rewrote unknown
   paths to `index.html` and returned **200 with an HTML body**, so a naive
   `resp.ok` check would treat an absent feed as present. That is fixed for
   `downloads/`: a path under it that is not a real file now returns **404**.
   The page still rejects a body that does not start like YAML, because that is
   cheap and covers any other origin serving an error page with a 200, and
   because it is what makes an unpublished platform show "No build published"
   rather than a broken link.

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
  a technician runs it. The mirror script does this for you; if you copy by hand,
  compare sizes/hashes afterwards:

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

  To avoid the gap entirely, build into a staging directory and swap, carrying
  `downloads/` across in the same operation:

  ```bash
  ssh demouser
  cd /var/www/homepot.cabera.com/frontend

  # Build elsewhere so the live dist is untouched while npm runs.
  npm run build -- --outDir /tmp/homepot-dist-new

  # Swap atomically, moving downloads/ from the old dist into the new one.
  mv dist "dist.old-$(date -u +%Y%m%dT%H%M%SZ)"
  cp -a /tmp/homepot-dist-new dist
  mv dist.old-*/downloads dist/downloads

  # Verify, then keep or move the rollback out of the repo tree:
  #   mv dist.old-* ~/frontend-dist-rollback-<date>
  # (dist/ is git-ignored, but dist.old-* is not, so it would show in
  #  `git status` if left in place.)
  ```

  Then confirm `/downloads`, `/downloads/checksums.json` and one installer URL
  all return **200**.
- **Apache config lives in `frontend/public/.htaccess`, not `dist/`.** Vite
  copies `public/` into `dist/` on every build, so `dist/.htaccess` is a build
  artifact. Edit the **`public/`** copy, or the change is lost on the next
  deploy. Rule changes there need no root (`demouser` owns both files) and take
  effect immediately — no Apache restart.
- A published GitHub release is the other delivery route and is what the app's
  built-in updater is configured against (`provider: github`, in
  `user_app/package.json`). Since `v0.3.1` the release carries
  `checksums.json`, so the same digests are available from either route. For
  `v0.3.0` they are **not** the same — that release predates the manifest and
  its bytes differ from what the server served; see "one version number, one set
  of bytes" above.

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

> **Important:** Always run migrations *before* restarting the backend after a
> sync. The app bootstraps its base schema via SQLAlchemy `create_all()` at
> startup, but additive migrations (new columns, tables) must be applied
> explicitly. Skipping this step causes `ProgrammingError: column X does not
> exist` and makes all device/site queries fail.

### Deploy sync process (after merging PRs)

When new code is merged to `main`, follow this sequence on the server:

1. **Stash server-only config drift** (e.g. `ai/config.yaml` with
   `keep_alive: "24h"`):
   ```bash
   cd /var/www/homepot.cabera.com
   git stash
   ```

2. **Pull latest code**:
   ```bash
   git pull origin main
   ```

3. **Restore server-only config**:
   ```bash
   git stash pop
   ```

4. **Run database migrations** (required when new columns/tables are added):
   ```bash
   bash scripts/upgrade-db.sh
   ```
   This script resolves the database URL from `backend/.env` (including
   remote/split-host setups) and applies any pending Alembic migrations.
   It handles fresh `create_all`-bootstrapped databases and already-migrated
   databases gracefully.

5. **Rebuild the frontend** (when frontend files changed):
   ```bash
   cd frontend && npm run build && cd ..
   ```

   > **Important:** `npm run build` empties the `dist/` directory, which deletes
   > the `downloads/` folder. After every frontend rebuild, re-run the mirror:
   > ```bash
   > mkdir -p frontend/dist/downloads
   > ~/bin/mirror-downloads.sh v0.3.24   # use the current release version
   > ```

6. **Restart the backend** (demouser has passwordless sudo for this):
   ```bash
   sudo /usr/bin/systemctl stop homepot-api
   sudo /usr/bin/systemctl start homepot-api
   ```

7. **Verify**:
   ```bash
   curl -s http://localhost:8000/health
   # Should return {"status":"ok"}
   ```

> **Note:** `sudo systemctl restart homepot-api` is NOT in the passwordless
> sudoers list. Use `stop` + `start` instead. The `restart` command requires
> a password.

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
| `mirror-downloads.sh` | Mirror the published GitHub release into `dist/downloads/`, verifying every asset | No |

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

### API Returns 500 Errors with "column X does not exist"

This happens when the code references new database columns that haven't been
migrated yet (e.g. after syncing new code that adds model fields).

```bash
# Run pending migrations
cd /var/www/homepot.cabera.com
bash scripts/upgrade-db.sh

# Restart the backend
sudo /usr/bin/systemctl stop homepot-api
sudo /usr/bin/systemctl start homepot-api
```

Verify the migration applied:
```bash
cd /var/www/homepot.cabera.com/backend
source .env
export PYTHONPATH=/var/www/homepot.cabera.com/backend/src
alembic current
# Should show the latest revision (head)
```

### API Returns 500 Errors

```bash
# Check API logs (production: journald; also logs/backend.log)
journalctl -u homepot-api -n 100 --no-pager
tail -f logs/backend.log

# Verify database connection
./scripts/query-db.sh tables
```

### Database connection pool exhaustion

Symptom: `/api/v1/*` endpoints time out or return 500s while `/api/v1/health`
still responds and the database port is reachable from the web host. This is
the failure mode behind the two production outages: the analytics middleware
performed a synchronous DB write inside the async event loop on every request
(blocking the loop and saturating the small sync pool), and the async engine
ignored its pool settings and had no defence against dropped connections —
both fixed in #572.

Diagnose on the database host (`51.161.114.195`):

```bash
psql -h localhost -U postgres -c "SELECT count(*) FROM pg_stat_activity;"
psql -h localhost -U postgres -c "SHOW max_connections;"
```

If the count is pinned at or near `max_connections`, connections are leaking or
the pool bounds are too small. Restart `homepot-api` to clear the pools:

```bash
sudo systemctl restart homepot-api && sleep 10
curl -s http://127.0.0.1:8000/api/v1/health
```

Then review `DATABASE__POOL_*` and confirm the non-blocking analytics
middleware from #572 is deployed.

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

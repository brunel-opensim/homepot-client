# Server Admin — Option B (passwordless trust): Step-by-Step

> **About this document.** This is the **server-team one-time checklist** for
> letting `demouser` drop/recreate the HOMEPOT demo database **passwordless and
> sudo-free** (Option B — the option the server team approved). After these
> steps, everything runs automatically; the demouser needs **no sudo, no
> password, no `.pgpass`**.
>
> Who this is for: the **server admin** on `homepot.cabera.com` (this section can
> be run with sudo). Everything `demouser` does afterwards is in
> `docs/server-deployment.md` §3.
>
> Time required: **≈20 minutes, one-time**. We'll ask for a quiet slot to run
> the real drop/recreate once it's in place.

---

## Prerequisite check (2 min)

Confirm PostgreSQL 16 is installed and running:

```bash
systemctl is-active postgresql && /usr/lib/postgresql/16/bin/postgres --version
```

```text
active
postgres (PostgreSQL) 16.x
```

If it is not already installed, install once (as admin, sudo):

```bash
sudo apt-get update && sudo apt-get install -y postgresql-16 postgresql-client-16
sudo systemctl enable --now postgresql
```

---

## Step 1 — Enable passwordless `trust` for the admin role over loopback (5 min)

Edit the host-based auth file:

```bash
sudoedit /etc/postgresql/16/main/pg_hba.conf
```

Add these **two lines** *above* the existing `scram-sha-256` entries (the
`host ... 127.0.0.1/32` block):

```
host  all  postgres  127.0.0.1/32  trust
host  all  postgres  ::1/128       trust
```

> **REVERT WHEN PRODUCTION READY (trust -> password).** The two lines above are
> the *only* security change for Option B. To reverse later: delete them and
> `sudo systemctl reload postgresql`. The client scripts carry matching
> `REVERT` markers — `grep -rn 'REVERT' scripts/ deploy/ docs/` finds every
> spot on both sides.

Apply without a full restart (`reload` re-reads `pg_hba.conf`):

```bash
sudo systemctl reload postgresql
```

---

## Step 2 — Ensure the `postgres` superuser role exists (1 min)

On a stock Debian/Ubuntu install the `postgres` role already exists as the
superuser (`initdb` creates it during package install). Verify, and only
create if missing:

```bash
sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='postgres' AND rolsuper"
```

- returns **`1`** -> role exists, nothing to do.
- returns **nothing** -> create it once:

```bash
sudo -u postgres createuser -s postgres
```

---

## Step 3 — Prove the trust path works, passwordless (2 min)

The following must succeed with **no password and no sudo** (run it as the
admin directly — the `trust` lines make it passwordless from this point on):

```bash
psql -h localhost -U postgres -d postgres -c "SELECT 'option-B trust OK';"
```

```text
      ?column?
-----------------
 option-B trust OK
(1 row)
```

If `psql` is not on the admin's `PATH`, use its full path:
`/usr/lib/postgresql/16/bin/psql -h localhost -U postgres -d postgres ...`

---

## Step 4 — Add `demouser` to the `postgres` group (2 min, once)

So `demouser` can reach the socket-backed admin path if it is ever needed
(read-only, not for drop/recreate under trust):

```bash
sudo usermod -aG postgres demouser
```

---

## Step 5 — Hand back to us (5 min)

We need two things once Steps 1-4 are done:

1. Confirm option B is in place on the box (reply to issue #474 or the PR #473
   thread — a `yes, Steps 1-4 done` is enough).
2. A quiet **~20-minute slot** when we can run the real proof:
   `HOMEPOT_DB_AUTH=trust ./scripts/reset-db.sh` as `demouser` (passwordless,
   no sudo) — the drop-and-recreate we must confirm before launch.

Nothing merges or launches until those two are true.

---

## Preflight: which mode are we in?

`scripts/preflight-server.sh` is a read-only readiness check. It picks its mode
from `HOMEPOT_DB_HOST` — this matters, because the two topologies need different
checks.

| Mode | When | Trust checks (2)(3)(4) |
|---|---|---|
| **single-box** | `HOMEPOT_DB_HOST` unset or `localhost` (default) | run normally |
| **split-host** | `HOMEPOT_DB_HOST=<db server IP>` | reported **SKIP**, never FAIL |

In **split-host** mode the app server and the database are different machines, so
`trust` in `pg_hba.conf` cannot apply: it only authenticates local socket and
loopback connections, never a connection arriving from another host. Those
deployments authenticate with a password plus a `pg_hba.conf` rule for the app
server's source IP. The create/drop probe in check 3 is disabled in this mode on
purpose, so the script can never touch a production database server.

```bash
# single-box (app and database on the same machine)
./scripts/preflight-server.sh

# split-host (database on a separate server)
HOMEPOT_DB_HOST=10.0.0.9 \
HOMEPOT_API_URL=http://127.0.0.1:8000 \
./scripts/preflight-server.sh
```

**Check 7 is the real launch gate.** It probes the live API: `/api/v1/health`
should return `200`, and `/api/v1/sites/` should return `200`/`401`/`403` — a
`401` means the request reached FastAPI and authentication is being enforced,
which is the healthy result. A `5xx` there points at the database. Note that
`/api/v1/health` reports the *client* connection only, so a `200` from it does
**not** prove the database is reachable.

### ⚠️ Check 5 exists to stop you dropping the wrong database

`init-postgresql.sh` and `reset-db.sh` **DROP and CREATE** a database, and both
default to `DB_NAME=homepot_db`. If the deployment uses a different name, a
"helpful" edit could point them at the production database. Check 5 reads the
app's own `DATABASE__URL` and warns when the script's target disagrees with what
the app is actually configured for.

If it warns, do not run those scripts on that host. The deployment-safe
alternative is `scripts/reset-prod-db.sh`, which reads the app's own
`backend/.env` for the database (so it always targets the real database, by
name and by host), connects to a maintenance database to perform the drop, and
refuses to touch any system database. Run it with `--dry-run` first. If you do
need to use the dev scripts, always name the database explicitly:

```bash
HOMEPOT_DB_NAME=<the name in the app's DATABASE__URL> ./scripts/preflight-server.sh
```

The check reads only the database name out of the URL; the password is never
printed. If `backend/.env` is owned by a service account, re-run as that user so
the check can read it:

```bash
sudo -u homepot ./scripts/preflight-server.sh
```

Other overrides: `HOMEPOT_DB_PORT`, `HOMEPOT_DB_USER`, `HOMEPOT_SITE_DIR`,
`HOMEPOT_API_URL`, `HOMEPOT_PUBLIC_URL`.

## Reverting later (the full reverse, for the record)

When production-ready, every trust spot on BOTH sides is grep-able:

```bash
grep -rn 'REVERT' scripts/ deploy/ docs/
```

Reverse = delete the two `trust` lines in Step 1 + `reload`, then follow the
password path in `docs/server-deployment.md` §1.

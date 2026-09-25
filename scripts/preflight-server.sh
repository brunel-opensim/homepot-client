#!/bin/bash
# HOMEPOT server preflight.
# Read-mostly verification that the server is ready for a centralized
# HOMEPOT Client deploy under /var/www. Passwordless-safe: it only uses
# pg_isready + psql over TCP trust (no sudo, no password, no .pgpass) and
# filesystem checks. It NEVER touches homepot_db; the create/drop capability
# is proven with a disposable scratch database that it always cleans up.
#
# Run as the demouser on the server:  ./scripts/preflight-server.sh
# Exit 0 = all checks passed (safe to proceed to deploy). Exit 1 = a check
# failed; do NOT deploy yet. See docs/server-admin-option-b.md to fix.

set -u

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

DB_NAME="${HOMEPOT_DB_NAME:-homepot_db}"
DB_USER="${HOMEPOT_DB_USER:-homepot_user}"
DB_HOST="${HOMEPOT_DB_HOST:-localhost}"
DB_PORT="${HOMEPOT_DB_PORT:-5432}"
SITE_DIR="${HOMEPOT_SITE_DIR:-/var/www/homepot.cabera.com}"
PROBE_DB="_homepot_preflight_probe"

FAILURES=0
pass() { echo -e "${GREEN}[PASS]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
fail() { echo -e "${RED}[FAIL]${NC} $*"; FAILURES=$((FAILURES + 1)); }
head_() { echo; echo "━━ $* ━━"; }

# OS-aware trust admin: Homebrew superuser is the login user; the Ubuntu
# server team created the `postgres` superuser over localhost trust.
if [[ "$OSTYPE" == "darwin"* ]]; then
  ADMIN_USER="$(whoami)"
else
  ADMIN_USER="postgres"
fi
PSQL_ADMIN="psql -h $DB_HOST -p $DB_PORT -U $ADMIN_USER -d postgres"

echo -e "${BLUE}HOMEPOT Server Preflight${NC} (as $(whoami)@$(hostname))"
echo "  target db : $DB_NAME   app user: $DB_USER"
echo "  admin role: $ADMIN_USER   (passwordless trust over $DB_HOST)"

# --- 1. PostgreSQL is up -----------------------------------------------------
head_ "1. PostgreSQL reachability (no sudo, no password)"
if command -v psql >/dev/null 2>&1; then
  pass "psql client present: $(psql --version)"
else
  fail "psql not on PATH — is postgresql-client installed for $(whoami)?"
fi
if command -v pg_isready >/dev/null 2>&1; then
  if pg_isready -h "$DB_HOST" -p "$DB_PORT" >/dev/null 2>&1; then
    pass "pg_isready: server accepting connections on $DB_HOST:$DB_PORT"
  else
    fail "pg_isready: nothing listening on $DB_HOST:$DB_PORT"
    # "Connection refused" means the server is down or not bound to TCP.
    # It is NOT a trust/auth problem (that would say "authentication failed").
    echo "       -> 'Connection refused' = PostgreSQL is NOT running or not on TCP."
    echo "          Ask the server team to run these (they have sudo):"
    echo "            pg_lsclusters                         # is the 16/main cluster running, on which port?"
    echo "            systemctl status postgresql --no-pager"
    echo "            sudo systemctl start postgresql        # if it is installed but stopped"
    echo "          If it is running but still refused, the cluster may not be on TCP; check:"
    echo "            sudo -u postgres psql -c 'show listen_addresses'   # want 'localhost' (or 127.0.0.1)"
    echo "          and 'port' (must be 5432 to match this check)."
  fi
fi

# --- 2. Passwordless trust as the admin role ---------------------------------
head_ "2. Passwordless admin access (the Option B trust check)"
if ADMPW=$($PSQL_ADMIN -tAc "SELECT current_user" 2>&1); then
  pass "connected as '$ADMIN_USER' over TCP trust with NO password (no sudo)"
else
  fail "cannot connect as '$ADMIN_USER' passwordlessly: $ADMPW"
  echo "       -> see docs/server-admin-option-b.md Step 3"
fi
if [ "${FAILURES:-0}" -eq 0 ]; then
  SUPER=$($PSQL_ADMIN -tAc "SELECT rolsuper FROM pg_roles WHERE rolname='$ADMIN_USER'" 2>/dev/null)
  if [ "$SUPER" = "t" ]; then
    pass "role '$ADMIN_USER' is a SUPERUSER (can create/drop databases)"
  else
    fail "role '$ADMIN_USER' is not a superuser — create/drop would fail"
  fi
fi

# --- 3. Capability probe: create+drop a SCRATCH database ----------------------
head_ "3. Create/drop capability (scratch DB, homepot_db untouched)"
if [ "${FAILURES:-0}" -eq 0 ]; then
  $PSQL_ADMIN -c "DROP DATABASE IF EXISTS $PROBE_DB;" >/dev/null 2>&1
  if $PSQL_ADMIN -c "CREATE DATABASE $PROBE_DB;" >/dev/null 2>&1; then
    pass "created scratch DB '$PROBE_DB' passwordless"
    if $PSQL_ADMIN -c "DROP DATABASE $PROBE_DB;" >/dev/null 2>&1; then
      pass "dropped scratch DB '$PROBE_DB' — full drop/recreate cycle works"
    else
      warn "could not drop scratch DB '$PROBE_DB' — clean it up manually"
    fi
  else
    fail "could not CREATE scratch DB — admin role lacks rights (or pg_hba not trust yet)"
  fi
else
  warn "skipped (admin access failed above)"
fi

# --- 4. Target database state -----------------------------------------------
head_ "4. Target database '$DB_NAME'"
if [ "${FAILURES:-0}" -eq 0 ]; then
  EXISTS=$($PSQL_ADMIN -tAc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" 2>/dev/null)
  if [ "$EXISTS" = "1" ]; then
    pass "'$DB_NAME' already exists (init-postgresql.sh will reuse/configure it)"
  else
    pass "'$DB_NAME' does not exist yet — normal before first deploy"
  fi
  APPROLE=$($PSQL_ADMIN -tAc "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'" 2>/dev/null)
  if [ "$APPROLE" = "1" ]; then
    pass "app role '$DB_USER' exists"
  else
    pass "app role '$DB_USER' not created yet — init-postgresql.sh will create it"
  fi
fi

# --- 5. Deploy target directory ---------------------------------------------
head_ "5. Deploy location ($SITE_DIR)"
if [ -d "$SITE_DIR" ]; then
  if [ -w "$SITE_DIR" ]; then
    pass "'$SITE_DIR' exists and is writable by $(whoami)"
  else
    fail "'$SITE_DIR' exists but is NOT writable by $(whoami) — ask the server team to chown it"
  fi
else
  if [ -d "$(dirname "$SITE_DIR")" ]; then
    if [ -w "$(dirname "$SITE_DIR")" ]; then
      pass "parent '$(dirname "$SITE_DIR")' is writable — deploy script will create the site dir"
    else
      warn "parent '$(dirname "$SITE_DIR")' is not writable by $(whoami)"
    fi
  else
    warn "'$(dirname "$SITE_DIR")' does not exist — server team must create /var/www first"
  fi
fi

# --- 6. Pre-existing HOMEPOT installs (single-clone check) --------------------
head_ "6. Pre-existing HOMEPOT installs / conflicting services"
echo "  (single-clone check: we want exactly ONE HOMEPOT, under $SITE_DIR)"

# 6a. find any homepot clone in common locations (sudo-free; unreadable dirs skipped)
SITE_REAL=$(cd "$SITE_DIR" 2>/dev/null && pwd -P)
CLONE_LIST=""
for base in /var/www /srv /opt /home /usr/local; do
  [ -d "$base" ] || continue
  found=$(find "$base" -maxdepth 4 \( -name 'homepot' -o -name 'homepot-client' -o -name 'Homepot' \) -type d 2>/dev/null || true)
  if [ -n "$found" ]; then
    while IFS= read -r d; do
      [ -n "$d" ] || continue
      real=$(cd "$d" 2>/dev/null && pwd -P)
      # skip the deploy dir itself and anything resolving to the same realpath
      [ "$real" = "$SITE_REAL" ] && continue
      [ "$d" = "$SITE_DIR" ] && continue
      CLONE_LIST="$CLONE_LIST$d"$'\n'
    done <<< "$found"
  fi
done
if [ -n "$CLONE_LIST" ]; then
  n=$(printf "%s" "$CLONE_LIST" | grep -c .)
  printf "%s" "$CLONE_LIST" | sed 's/^/      /'
  if [ -d "$SITE_DIR" ]; then
    fail "$n other homepot directory/ies found — we want exactly ONE clone at $SITE_DIR; review & remove the rest"
  else
    fail "$n homepot directory/ies found OUTSIDE the (not-yet-created) $SITE_DIR — decide which is the ONE live copy"
  fi
else
  pass "no other homepot clone in /var/www,/srv,/opt,/home,/usr/local (single-clone clean)"
fi

# 6b. git state of the deploy clone (uncommitted changes = unknown version)
if [ -d "$SITE_DIR/.git" ]; then
  BR=$(git -C "$SITE_DIR" rev-parse --abbrev-ref HEAD 2>/dev/null)
  SHA=$(git -C "$SITE_DIR" rev-parse --short HEAD 2>/dev/null)
  DIRTY=$(git -C "$SITE_DIR" status --porcelain 2>/dev/null | head -5)
  pass "deploy clone git: branch=$BR commit=$SHA"
  if [ -n "$DIRTY" ]; then
    warn "deploy clone has uncommitted changes (version is not reproducible):"
    printf "$DIRTY" | sed 's/^/        /'
  fi
else
  warn "no .git in $SITE_DIR (not a git clone, or not deployed yet)"
fi

# 6c. running HOMEPOT processes
if command -v ps >/dev/null 2>&1; then
  PROCS=$(ps -eo pid,args 2>/dev/null | grep -E 'uvicorn|vite|homepot' | grep -v -e grep -e 'ps -eo' | head -5)
  if [ -n "$PROCS" ]; then
    warn "HOMEPOT-looking processes already running (an old instance?):"
    printf "%s\n" "$PROCS" | sed 's/^/      /'
  else
    pass "no running uvicorn/vite/homepot processes"
  fi
fi

# 6d. systemd units that would conflict on restart
if command -v systemctl >/dev/null 2>&1; then
  UNITS=$(systemctl list-units --type=service --all 2>/dev/null | grep -i homepot | head -5)
  if [ -n "$UNITS" ]; then
    warn "systemd unit(s) named homepot exist (confirm only one is enabled):"
    printf "$UNITS" | sed 's/^/      /'
  else
    pass "no systemd service named *homepot* (good: no duplicate auto-start)"
  fi
fi

# 6e. ports the centralized dashboard needs (conflict = something else is there)
if command -v ss >/dev/null 2>&1; then
  for port in 8000 5173 11434; do
    who=$(ss -ltnp 2>/dev/null | grep ":$port " | head -1)
    if [ -n "$who" ]; then
      warn "port $port already in use (will conflict with HOMEPOT): $who"
    else
      pass "port $port free"
    fi
  done
else
  warn "ss not available — could not check port conflicts"
fi

# --- summary -----------------------------------------------------------------
echo
if [ "$FAILURES" -eq 0 ]; then
  echo -e "${GREEN}PREFLIGHT PASSED — passwordless PostgreSQL is confirmed on this host.${NC}"
  echo "  Next: HOMEPOT_DB_AUTH=trust ./scripts/init-postgresql.sh   (from $SITE_DIR)"
  echo "        then HOMEPOT_DB_AUTH=trust ./scripts/reset-db.sh     (real drop/recreate)"
  exit 0
else
  echo -e "${RED}PREFLIGHT FAILED ($FAILURES check(s)) — do NOT deploy yet.${NC}"
  echo "  Fix the failing items above, or see docs/server-admin-option-b.md."
  exit 1
fi

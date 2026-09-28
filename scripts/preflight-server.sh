#!/bin/bash
# HOMEPOT server preflight.
# Read-mostly verification that a HOMEPOT deployment is healthy and ready.
# Passwordless-safe: psql over TCP, filesystem and HTTP checks only. No sudo,
# no password, no .pgpass. It NEVER touches the application database; in
# single-box mode the create/drop capability is proven with a disposable
# scratch database that it always cleans up.
#
# TOPOLOGY AWARENESS
#   single-box : PostgreSQL runs on this same host. The passwordless 'trust'
#                checks (2), (3) and (4) apply.
#   split-host : PostgreSQL runs on a REMOTE host. 'trust' in pg_hba.conf only
#                ever authenticates local socket / loopback connections, so it
#                can NEVER authenticate a connection arriving from another
#                host. Those checks are therefore reported SKIP, never FAIL,
#                and the create/drop probe is deliberately NOT run so this
#                script can never touch a production database server.
#                Set HOMEPOT_DB_HOST to the DB host to select this mode.
#
# Run as the demouser on the server:  ./scripts/preflight-server.sh
# Exit 0 = ready. Exit 1 = a check failed; do NOT proceed.
# See docs/server-admin-option-b.md to fix failures.
#
# Overrides: HOMEPOT_DB_HOST HOMEPOT_DB_PORT HOMEPOT_DB_NAME HOMEPOT_DB_USER
#            HOMEPOT_SITE_DIR HOMEPOT_API_URL HOMEPOT_PUBLIC_URL

set -u

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

DB_NAME="${HOMEPOT_DB_NAME:-homepot_db}"
DB_USER="${HOMEPOT_DB_USER:-homepot_user}"
DB_HOST="${HOMEPOT_DB_HOST:-localhost}"
DB_PORT="${HOMEPOT_DB_PORT:-5432}"
SITE_DIR="${HOMEPOT_SITE_DIR:-/var/www/homepot.cabera.com}"
API_URL="${HOMEPOT_API_URL:-http://127.0.0.1:8000}"
PUBLIC_URL="${HOMEPOT_PUBLIC_URL:-}"
PROBE_DB="_homepot_preflight_probe"

# Where this script lives, so the drop-safety check can also read the
# checkout it was run from (useful when run from the repo, not the server).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd -P)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"

# --- topology detection -------------------------------------------------------
case "$DB_HOST" in
  localhost|127.0.0.1|::1|"") IS_LOCAL=1 ;;
  *) IS_LOCAL=0 ;;
esac

FAILURES=0
SKIPS=0
pass() { echo -e "${GREEN}[PASS]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
fail() { echo -e "${RED}[FAIL]${NC} $*"; FAILURES=$((FAILURES + 1)); }
skip() { echo -e "${CYAN}[SKIP]${NC} $*"; SKIPS=$((SKIPS + 1)); }
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
if [ "$IS_LOCAL" -eq 1 ]; then
  echo -e "  mode      : ${CYAN}single-box${NC}  PostgreSQL on this host; trust checks apply"
  echo "  admin role: $ADMIN_USER  (passwordless trust over $DB_HOST)"
else
  echo -e "  mode      : ${CYAN}split-host${NC}  PostgreSQL on $DB_HOST (remote)"
  echo "  admin role: n/a  'trust' cannot authenticate a remote TCP hop"
fi

# --- 1. PostgreSQL is up ------------------------------------------------------
head_ "1. PostgreSQL reachability (no sudo, no password)"
if command -v psql >/dev/null 2>&1; then
  pass "psql client present: $(psql --version)"
else
  fail "psql not on PATH - is postgresql-client installed for $(whoami)?"
fi
if command -v pg_isready >/dev/null 2>&1; then
  if pg_isready -h "$DB_HOST" -p "$DB_PORT" >/dev/null 2>&1; then
    pass "pg_isready: accepting connections on $DB_HOST:$DB_PORT"
  else
    fail "pg_isready: nothing listening on $DB_HOST:$DB_PORT"
    if [ "$IS_LOCAL" -eq 1 ]; then
      echo "       -> 'Connection refused' = PostgreSQL is NOT running or not on TCP."
      echo "          Ask the server team to run these (they have sudo):"
      echo "            pg_lsclusters                         # is the 16/main cluster running, on which port?"
      echo "            systemctl status postgresql --no-pager"
      echo "            sudo systemctl start postgresql        # if it is installed but stopped"
      echo "          If it is running but still refused, the cluster may not be on TCP; check:"
      echo "            sudo -u postgres psql -c 'show listen_addresses'   # want 'localhost' (or 127.0.0.1)"
      echo "          and 'port' (must be 5432 to match this check)."
    else
      echo "       -> PostgreSQL is expected on the SEPARATE DB host $DB_HOST."
      echo "          Do NOT start a second PostgreSQL on this app host: the deployment"
      echo "          is designed to use the remote DB, and a rogue local cluster would"
      echo "          quietly serve an empty database."
      echo "          Ask the DB/server team to confirm ON $DB_HOST:"
      echo "            systemctl status postgresql --no-pager"
      echo "            pg_isready -h $DB_HOST -p $DB_PORT"
      echo "            sudo -u postgres psql -c 'show listen_addresses'   # must include this host"
      echo "          and that pg_hba.conf allows THIS host's source IP."
    fi
  fi
fi

# --- 2. Passwordless trust as the admin role ---------------------------------
head_ "2. Passwordless admin access (the Option B trust check)"
if [ "$IS_LOCAL" -eq 0 ]; then
  skip "not applicable: 'trust' only authenticates local socket/loopback connections"
  echo "       -> a split-host deployment authenticates with a password plus a"
  echo "          pg_hba.conf rule for this host's source IP. Nothing to verify here."
else
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
      fail "role '$ADMIN_USER' is not a superuser - create/drop would fail"
    fi
  fi
fi

# --- 3. Capability probe: create+drop a SCRATCH database ----------------------
head_ "3. Create/drop capability (scratch DB '$PROBE_DB', app database untouched)"
if [ "$IS_LOCAL" -eq 0 ]; then
  skip "deliberately not run: $DB_HOST is a remote host (likely the production DB server)"
  echo "       -> this probe CREATEs and DROPs a database. It must never run against"
  echo "          a shared or production database server, so it is disabled in"
  echo "          split-host mode by design."
else
  if [ "${FAILURES:-0}" -eq 0 ]; then
    $PSQL_ADMIN -c "DROP DATABASE IF EXISTS $PROBE_DB;" >/dev/null 2>&1
    if $PSQL_ADMIN -c "CREATE DATABASE $PROBE_DB;" >/dev/null 2>&1; then
      pass "created scratch DB '$PROBE_DB' passwordless"
      if $PSQL_ADMIN -c "DROP DATABASE $PROBE_DB;" >/dev/null 2>&1; then
        pass "dropped scratch DB '$PROBE_DB' - full drop/recreate cycle works"
      else
        warn "could not drop scratch DB '$PROBE_DB' - clean it up manually"
      fi
    else
      fail "could not CREATE scratch DB - admin role lacks rights (or pg_hba not trust yet)"
    fi
  else
    warn "skipped (admin access failed above)"
  fi
fi

# --- 4. Target database state -----------------------------------------------
head_ "4. Target database '$DB_NAME'"
if [ "$IS_LOCAL" -eq 0 ]; then
  skip "cannot enumerate databases without a superuser login (no password allowed)"
else
  if [ "${FAILURES:-0}" -eq 0 ]; then
    EXISTS=$($PSQL_ADMIN -tAc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" 2>/dev/null)
    if [ "$EXISTS" = "1" ]; then
      pass "'$DB_NAME' already exists (init-postgresql.sh will reuse/configure it)"
    else
      pass "'$DB_NAME' does not exist yet - normal before first deploy"
    fi
    APPROLE=$($PSQL_ADMIN -tAc "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'" 2>/dev/null)
    if [ "$APPROLE" = "1" ]; then
      pass "app role '$DB_USER' exists"
    else
      pass "app role '$DB_USER' not created yet - init-postgresql.sh will create it"
    fi
  fi
fi

# --- 5. Which database is the app actually configured for? (drop safety) -----
head_ "5. Which database is the app actually configured for? (drop safety)"
APP_DB=""
APP_SRC=""
for f in "$SITE_DIR/backend/.env" "$SITE_DIR/deploy/env-override.sh" "$REPO_DIR/backend/.env"; do
  [ -r "$f" ] || continue
  # Extract ONLY the database name. The full URL holds a password and is
  # never echoed.
  cand=$(grep -h -m1 -E '^[[:space:]]*(export[[:space:]]+)?DATABASE__URL=' "$f" 2>/dev/null \
         | sed -nE 's#.*postgresql(\+[a-z0-9]+)?://[^/]*/([^/?[:space:]"]+).*#\2#p')
  if [ -n "$cand" ]; then APP_DB="$cand"; APP_SRC="$f"; break; fi
done
if [ -n "$APP_DB" ]; then
  pass "app is configured for database '$APP_DB' (from $APP_SRC)"
  if [ "$APP_DB" = "$DB_NAME" ]; then
    pass "matches this script's target - no drop-safety conflict"
  else
    warn "MISMATCH: this script targets '$DB_NAME' but the app uses '$APP_DB'"
    echo "       -> DO NOT run init-postgresql.sh or reset-db.sh against this host."
    echo "          Both scripts DROP and CREATE a database named '$DB_NAME'."
    echo "          Point the scripts at the real name if you must, e.g.:"
    echo "            HOMEPOT_DB_NAME='$APP_DB' ./scripts/preflight-server.sh"
  fi
else
  warn "could not read the app's DATABASE__URL (unreadable file, or not deployed yet)"
  echo "       -> confirm manually which database the app uses BEFORE running any"
  echo "          script that drops a database. To let this check read a root- or"
  echo "          service-owned .env, re-run this script as that user, e.g.:"
  echo "            sudo -u homepot ./scripts/preflight-server.sh"
fi

# --- 6. Deploy target directory ---------------------------------------------
head_ "6. Deploy location ($SITE_DIR)"
if [ -d "$SITE_DIR" ]; then
  DIRPERMS=$(ls -ld "$SITE_DIR" 2>/dev/null | awk '{print $1}')
  DIROWNER=$(ls -ld "$SITE_DIR" 2>/dev/null | awk '{print $3":"$4}')
  pass "exists: owner=$DIROWNER mode=$DIRPERMS"
  case "$DIRPERMS" in
    ????????w?)
      fail "deploy root is WORLD-WRITABLE - any local account can replace files the service runs"
      echo "       -> the app executes from this tree, so world-write is an escalation path."
      echo "          Ask the server team (sudo):"
      echo "            sudo chown <deploy-user>:<group> $SITE_DIR"
      echo "            sudo chmod 755 $SITE_DIR"
      ;;
  esac
  if touch "$SITE_DIR/.homepot_write_test" 2>/dev/null; then
    rm -f "$SITE_DIR/.homepot_write_test"
    pass "top level is writable by $(whoami)"
  else
    fail "'$SITE_DIR' exists but is NOT writable by $(whoami)"
    echo "       -> Ask the server team (sudo) to run ONE of:"
    echo "            sudo chown -R $(whoami):$(whoami) $SITE_DIR"
    echo "            sudo mkdir -p $SITE_DIR && sudo chown $(whoami):$(whoami) $SITE_DIR"
    echo "          Note: demouser does NOT need write access to /var/www itself -"
    echo "          only to the '$SITE_DIR' subdirectory. git clones INTO that subdir,"
    echo "          so parent-directory write is never required."
  fi

  # A real deploy writes INSIDE subdirectories and updates .git, so being able
  # to write the top level is not the same as being able to deploy here.
  DEEP_OK=1
  for sub in scripts frontend .git; do
    [ -d "$SITE_DIR/$sub" ] || continue
    if touch "$SITE_DIR/$sub/.homepot_write_test" 2>/dev/null; then
      rm -f "$SITE_DIR/$sub/.homepot_write_test"
    else
      DEEP_OK=0
      warn "'$sub/' is NOT writable by $(whoami)"
    fi
  done
  if [ "$DEEP_OK" -eq 1 ]; then
    pass "subdirectories writable by $(whoami) (git pull / build can happen here)"
  else
    fail "cannot write into subdirectories - you can READ this deploy but not update it"
    echo "       -> top-level write access alone is not a real deploy capability."
    echo "          Pick ONE deploy account and let it own the tree (sudo):"
    echo "            sudo chown -R <deploy-user>:<group> $SITE_DIR"
    echo "          The service account (e.g. 'homepot') needs only READ on the code and"
    echo "          WRITE on backend/ and logs/ - it does not need to own the tree."
  fi
else
  if [ -d "$(dirname "$SITE_DIR")" ]; then
    if [ -w "$(dirname "$SITE_DIR")" ]; then
      pass "parent '$(dirname "$SITE_DIR")' is writable - deploy script will create the site dir"
    else
      warn "parent '$(dirname "$SITE_DIR")' is not writable by $(whoami)"
    fi
  else
    warn "'$(dirname "$SITE_DIR")' does not exist - server team must create /var/www first"
  fi
fi

# --- 7. Live API (app-level reality check) ----------------------------------
head_ "7. Live API (app-level check - the real launch gate)"
if command -v curl >/dev/null 2>&1; then
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "$API_URL/api/v1/health" 2>/dev/null)
  case "$code" in
    200) pass "GET $API_URL/api/v1/health -> 200" ;;
    404) warn "GET $API_URL/api/v1/health -> 404 (not present in the deployed build)" ;;
    000) fail "GET $API_URL/api/v1/health -> no response (is the app running?)" ;;
    *)   warn "GET $API_URL/api/v1/health -> HTTP $code" ;;
  esac
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "$API_URL/api/v1/sites/" 2>/dev/null)
  case "$code" in
    200|401|403) pass "GET $API_URL/api/v1/sites/ -> HTTP $code (app reachable, auth enforced)" ;;
    000) fail "GET $API_URL/api/v1/sites/ -> no response" ;;
    5*)  fail "GET $API_URL/api/v1/sites/ -> HTTP $code (server error - check the database)" ;;
    *)   warn "GET $API_URL/api/v1/sites/ -> HTTP $code" ;;
  esac
  echo "       -> note: /api/v1/health reports the client connection, NOT the"
  echo "          database. A 200 there does not prove the DB is reachable."
  if [ -n "$PUBLIC_URL" ]; then
    code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 "$PUBLIC_URL" 2>/dev/null)
    case "$code" in
      200|301|302) pass "GET $PUBLIC_URL -> HTTP $code" ;;
      000) warn "GET $PUBLIC_URL -> no response from this host (may be firewalled)" ;;
      *)   warn "GET $PUBLIC_URL -> HTTP $code" ;;
    esac
  fi
else
  warn "curl not available - could not run the app-level checks"
fi

# --- 8. Pre-existing HOMEPOT installs (single-clone check) --------------------
head_ "8. Pre-existing HOMEPOT installs / conflicting services"
echo "  (single-clone check: we want exactly ONE HOMEPOT, under $SITE_DIR)"

SITE_REAL=$(cd "$SITE_DIR" 2>/dev/null && pwd -P)
CLONE_LIST=""
for base in /var/www /srv /opt /home /usr/local; do
  [ -d "$base" ] || continue
  found=$(find "$base" -maxdepth 4 \( -name 'homepot' -o -name 'homepot-client' -o -name 'Homepot' \) -type d 2>/dev/null || true)
  if [ -n "$found" ]; then
    while IFS= read -r d; do
      [ -n "$d" ] || continue
      real=$(cd "$d" 2>/dev/null && pwd -P)
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
    fail "$n other homepot directory/ies found - we want exactly ONE clone at $SITE_DIR; review & remove the rest"
  else
    fail "$n homepot directory/ies found OUTSIDE the (not-yet-created) $SITE_DIR - decide which is the ONE live copy"
  fi
else
  pass "no other homepot clone in /var/www,/srv,/opt,/home,/usr/local (single-clone clean)"
fi

if [ -d "$SITE_DIR/.git" ]; then
  BR=$(git -C "$SITE_DIR" rev-parse --abbrev-ref HEAD 2>/dev/null)
  SHA=$(git -C "$SITE_DIR" rev-parse --short HEAD 2>/dev/null)
  DIRTY=$(git -C "$SITE_DIR" status --porcelain 2>/dev/null | head -5)
  pass "deploy clone git: branch=$BR commit=$SHA"
  if [ -n "$DIRTY" ]; then
    warn "deploy clone has uncommitted changes (version is not reproducible):"
    printf '%s\n' "$DIRTY" | sed 's/^/        /'
  fi
  if [ -n "$SHA" ]; then
    IGNORED=$([ -f "$SITE_DIR/.gitignore" ] && echo yes || echo no)
    if [ "$IGNORED" = "no" ]; then
      warn ".gitignore is MISSING in the deploy clone - backend/.env (db password)"
      echo "       -> is NO LONGER ignored. Do NOT run 'git add -A' here: it would"
      echo "          stage the database password. Restore .gitignore from main first."
    fi
  fi
else
  warn "no .git in $SITE_DIR (not a git clone, or not deployed yet)"
fi

if command -v ps >/dev/null 2>&1; then
  # Match HOMEPOT processes specifically. A bare 'homepot' would also match
  # postgres backend rows ("postgres: homepot_user homepot_db ... idle") and
  # this script's own command line, both false positives.
  PROCS=$(ps -eo pid,args 2>/dev/null \
          | grep -E 'uvicorn|vite|homepot-api|homepot\.app|homepot/main' \
          | grep -v -e grep -e 'ps -eo' -e 'preflight-server' | head -5)
  if [ -n "$PROCS" ]; then
    warn "HOMEPOT-looking processes already running (an old instance?):"
    printf "%s\n" "$PROCS" | sed 's/^/      /'
  else
    pass "no running uvicorn/vite/homepot processes"
  fi
fi

if command -v systemctl >/dev/null 2>&1; then
  UNITS=$(systemctl list-units --type=service --all 2>/dev/null | grep -i homepot | head -5)
  if [ -n "$UNITS" ]; then
    warn "systemd unit(s) named homepot exist (confirm only one is enabled):"
    printf "%s\n" "$UNITS" | sed 's/^/      /'
  else
    pass "no systemd service named *homepot* (good: no duplicate auto-start)"
  fi
fi

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
  warn "ss not available - could not check port conflicts"
fi

# --- summary -----------------------------------------------------------------
echo
if [ "$FAILURES" -eq 0 ]; then
  if [ "$IS_LOCAL" -eq 1 ]; then
    echo -e "${GREEN}PREFLIGHT PASSED - passwordless PostgreSQL is confirmed on this host.${NC}"
    echo "  Next: HOMEPOT_DB_AUTH=trust ./scripts/init-postgresql.sh   (from $SITE_DIR)"
    echo "        then HOMEPOT_DB_AUTH=trust ./scripts/reset-db.sh     (real drop/recreate)"
  else
    echo -e "${GREEN}PREFLIGHT PASSED - split-host deployment looks healthy.${NC}"
    echo "  Trust checks (2)(3)(4) do not apply across a TCP hop - that is expected,"
    echo "  not a problem. Verify the database the way the app does (section 7), and"
    echo "  do NOT run init-postgresql.sh / reset-db.sh against $DB_HOST."
  fi
  [ "$SKIPS" -gt 0 ] && echo "  ($SKIPS check(s) skipped as not applicable to this topology)"
  exit 0
else
  if [ "$IS_LOCAL" -eq 0 ]; then
    echo -e "${RED}PREFLIGHT FAILED ($FAILURES check(s)).${NC}"
    echo "  These are real failures in split-host mode (trust checks were skipped, so"
    echo "  they are NOT the cause). Fix the failing items above, or see"
    echo "  docs/server-admin-option-b.md."
  else
    echo -e "${RED}PREFLIGHT FAILED ($FAILURES check(s)) - do NOT deploy yet.${NC}"
    echo "  Fix the failing items above, or see docs/server-admin-option-b.md."
  fi
  exit 1
fi

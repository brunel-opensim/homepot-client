#!/bin/bash
# reset-prod-db.sh — drop and recreate the HOMEPOT database, repeatably.
#
# Unlike scripts/reset-db.sh (development), this one runs against a real
# deployment: it does not assume localhost, does not assume a passwordless
# superuser, and does not re-run the dev bootstrap. It connects to a separate
# maintenance database, drops the target, recreates it with the configured
# owner, restarts the service so the app rebuilds the schema, then stamps
# alembic and re-provisions accounts.
#
# Prerequisites — both are one-time grants on the DATABASE host:
#   ALTER ROLE homepot_user CREATEDB;
#   # pg_hba.conf: allow the app role into the maintenance database
#   host    homepot_user    postgres    <web-host>/32    <auth>
# The script reports exactly which one is missing rather than failing mid-drop.
#
# Usage:
#   ./scripts/reset-prod-db.sh [options]
#
# Options:
#   --url URL               Target database URL. Otherwise DATABASE__URL /
#                           DATABASE_URL / backend/.env, in that order.
#   --maintenance-db NAME   Database to connect to for the drop (default:
#                           postgres). Must be reachable from this host.
#   --service NAME          systemd unit to stop/start (default: homepot-api).
#   --no-stop               Do not stop or start the service. Use when you will
#                           manage it yourself. Connections are still killed.
#   --no-seed               Stop after migrations; do not run seed-users.sh.
#   --yes                   Skip the confirmation prompt (for automation).
#   --dry-run               Print what would happen, then exit. Changes nothing.
#   -h, --help              Show this help.
#
# Examples:
#   ./scripts/reset-prod-db.sh
#   ./scripts/reset-prod-db.sh --dry-run
#   ./scripts/reset-prod-db.sh --no-stop --no-seed
#
# WARNING: this destroys every row in the target database. It is intended for
# deployments where the schema can be rebuilt and accounts re-seeded. Take a
# pg_dump first if there is anything in it you would miss.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
HOMEPOT_REPO_ROOT="$REPO_ROOT"
# shellcheck source=scripts/lib/db.sh
. "$SCRIPT_DIR/lib/db.sh"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

URL_ARG=""
MAINT_DB="postgres"
SERVICE="homepot-api"
STOP_SERVICE=1
SKIP_SEED=0
ASSUME_YES=0
DRY_RUN=0

usage() {
  sed -n '/^# Usage:/,/^set -euo pipefail$/p' "$0" | sed 's/^# \{0,1\}//' | sed '$d'
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --url)
      URL_ARG="${2:-}"
      [ -n "$URL_ARG" ] || { echo -e "${RED}Error: --url requires a value${NC}" >&2; exit 1; }
      shift 2
      ;;
    --maintenance-db)
      MAINT_DB="${2:-}"
      [ -n "$MAINT_DB" ] || { echo -e "${RED}Error: --maintenance-db requires a value${NC}" >&2; exit 1; }
      shift 2
      ;;
    --service)
      SERVICE="${2:-}"
      [ -n "$SERVICE" ] || { echo -e "${RED}Error: --service requires a value${NC}" >&2; exit 1; }
      shift 2
      ;;
    --no-stop) STOP_SERVICE=0; shift ;;
    --no-seed) SKIP_SEED=1; shift ;;
    --yes)     ASSUME_YES=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *)
      echo -e "${RED}Unknown option: $1${NC}" >&2
      usage >&2
      exit 1
      ;;
  esac
done

command -v psql >/dev/null 2>&1 || {
  echo -e "${RED}Error: psql not found on PATH.${NC}" >&2
  exit 1
}

# ----- Resolve the connection -------------------------------------------------
if [ -n "$URL_ARG" ]; then
  HOMEPOT_DB_URL="$URL_ARG"
fi
homepot_db_resolve

MAINT_URL="$(homepot_db_url_for "$MAINT_DB")" || {
  echo -e "${RED}Error: could not derive a maintenance URL.${NC}" >&2
  exit 1
}
TARGET_DESC="$(homepot_db_describe)"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "HOMEPOT Database Reset"
[ "$DRY_RUN" -eq 1 ] && echo "  *** DRY RUN — nothing will be changed ***"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  target:     $TARGET_DESC"
echo "  maintenance: database '$MAINT_DB' on the same host"
echo "  service:    $([ "$STOP_SERVICE" -eq 1 ] && echo "$SERVICE (stopped and restarted)" || echo "not managed (--no-stop)")"
echo "  accounts:   $([ "$SKIP_SEED" -eq 1 ] && echo "not seeded (--no-seed)" || echo "seed-users.sh after migration")"
echo ""

# ----- Preflight --------------------------------------------------------------
# Every failure mode here is a permission or connection problem on the database
# host, reported with the exact command that fixes it — better than discovering
# it half way through a drop. Problems are gathered into PREFLIGHT_PROBLEM so
# that --dry-run can report them while still printing the plan, without having
# already touched anything.
PREFLIGHT_PROBLEM=""

if ! MAINT_ERR="$(psql "$MAINT_URL" -v ON_ERROR_STOP=1 -tAc "SELECT 1" 2>&1 >/dev/null)"; then
  case "$MAINT_ERR" in
    *"no pg_hba.conf entry"*)
      PREFLIGHT_PROBLEM="pg_hba.conf does not allow $HOMEPOT_DB_USER into '$MAINT_DB'.
  DROP DATABASE cannot run while connected to the database being dropped, so a
  maintenance database is required. On the database host, add a line matching
  the existing $HOMEPOT_DB_USER entry, e.g.:

    host    $HOMEPOT_DB_USER    $MAINT_DB    <this-host>/32    <auth-as-existing>

  then run: sudo -u postgres psql -d postgres -c 'SELECT pg_reload_conf();'"
      ;;
    *"password authentication failed"*|*"no password supplied"*)
      PREFLIGHT_PROBLEM="Authentication to '$MAINT_DB' failed. The URL in
  backend/.env may be stale (role or password)."
      ;;
    *"could not connect"*|*"Connection refused"*)
      PREFLIGHT_PROBLEM="The database host is unreachable from here. Check the
  host and port in backend/.env."
      ;;
    *)
      PREFLIGHT_PROBLEM="Cannot connect to the maintenance database '$MAINT_DB':
  $MAINT_ERR"
      ;;
  esac
else
  ROLE_PRIV="$(psql "$MAINT_URL" -tAc "SELECT rolsuper || ',' || rolcreatedb FROM pg_roles WHERE rolname = current_user" | tr -d '[:space:]')"
  ROLE_SUPER="${ROLE_PRIV%,*}"
  ROLE_CREATEDB="${ROLE_PRIV#*,}"

  if [ "$ROLE_SUPER" = "t" ]; then
    echo -e "${YELLOW}note: connected as a superuser, not $HOMEPOT_DB_USER.${NC}" >&2
  fi
  if [ "$ROLE_CREATEDB" != "t" ]; then
    PREFLIGHT_PROBLEM="$HOMEPOT_DB_USER lacks CREATEDB. It owns the database but
  cannot drop or recreate it. On the database host, run once:

    sudo -u postgres psql -d postgres -c \"ALTER ROLE $HOMEPOT_DB_USER CREATEDB;\"

  This does not confer superuser."
  fi
fi

# Refuse to touch a system database no matter what was passed in.
case "$HOMEPOT_DB_NAME" in
  postgres|template0|template1)
    echo -e "${RED}Error: refusing to drop a system database ('$HOMEPOT_DB_NAME').${NC}" >&2
    exit 1
    ;;
esac

if [ "$DRY_RUN" -eq 1 ]; then
  if [ -n "$PREFLIGHT_PROBLEM" ]; then
    echo -e "${RED}Preflight would halt this reset:${NC}"
    echo "$PREFLIGHT_PROBLEM"
  else
    echo -e "${GREEN}Preflight OK:${NC} connected to '$MAINT_DB' as a role with CREATEDB."
  fi
  echo ""
  echo -e "${CYAN}Would:${NC}"
  [ "$STOP_SERVICE" -eq 1 ] && echo "  1. sudo systemctl stop $SERVICE"
  echo "  2. terminate open connections to '$HOMEPOT_DB_NAME'"
  echo "  3. DROP DATABASE $HOMEPOT_DB_NAME"
  echo "  4. CREATE DATABASE $HOMEPOT_DB_NAME OWNER $HOMEPOT_DB_USER"
  [ "$STOP_SERVICE" -eq 1 ] && echo "  5. sudo systemctl start $SERVICE"
  echo "  6. scripts/upgrade-db.sh   (stamp alembic head)"
  [ "$SKIP_SEED" -eq 0 ] && echo "  7. scripts/seed-users.sh    (if scripts/seed-users.env exists)"
  echo ""
  echo -e "${YELLOW}Dry run — nothing was changed.${NC}"
  exit 0
fi

if [ -n "$PREFLIGHT_PROBLEM" ]; then
  echo -e "${RED}Error: preflight failed.${NC}" >&2
  echo "$PREFLIGHT_PROBLEM" >&2
  exit 1
fi

# ----- Confirm ----------------------------------------------------------------
if [ "$ASSUME_YES" -eq 0 ]; then
  echo -e "${RED}This destroys every row in $TARGET_DESC.${NC}"
  if [ -t 0 ]; then
    printf "Type the database name ('%s') to continue: " "$HOMEPOT_DB_NAME"
    read -r REPLY
    if [ "$REPLY" != "$HOMEPOT_DB_NAME" ]; then
      echo -e "${YELLOW}Aborted. Nothing was changed.${NC}"
      exit 1
    fi
  else
    echo -e "${RED}Error: refusing to run unattended without --yes.${NC}" >&2
    exit 1
  fi
fi
echo ""

# ----- Reset ------------------------------------------------------------------
# The trap guarantees a stopped service gets started again, including when a
# later step fails under `set -e`.
SERVICE_STOPPED=0
restart_if_stopped() {
  if [ "$STOP_SERVICE" -eq 1 ] && [ "$SERVICE_STOPPED" -eq 1 ]; then
    echo -e "${YELLOW}Restarting $SERVICE after failure...${NC}" >&2
    sudo systemctl start "$SERVICE" >/dev/null 2>&1 || true
    SERVICE_STOPPED=0
  fi
}
trap restart_if_stopped EXIT

if [ "$STOP_SERVICE" -eq 1 ]; then
  echo "Stopping $SERVICE..."
  sudo systemctl stop "$SERVICE"
  SERVICE_STOPPED=1
  echo -e "${GREEN}stopped${NC}"
fi

echo "Terminating open connections to '$HOMEPOT_DB_NAME'..."
psql "$MAINT_URL" -v ON_ERROR_STOP=1 -q \
  -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$HOMEPOT_DB_NAME' AND pid <> pg_backend_pid();"

# DROP/CREATE cannot run inside a transaction, so each statement is its own
# psql invocation — never a combined -c with both.
echo "Dropping '$HOMEPOT_DB_NAME'..."
psql "$MAINT_URL" -v ON_ERROR_STOP=1 -q \
  -c "DROP DATABASE IF EXISTS \"$HOMEPOT_DB_NAME\";"

echo "Creating '$HOMEPOT_DB_NAME' owned by $HOMEPOT_DB_USER..."
psql "$MAINT_URL" -v ON_ERROR_STOP=1 -q \
  -c "CREATE DATABASE \"$HOMEPOT_DB_NAME\" OWNER \"$HOMEPOT_DB_USER\";"
echo -e "${GREEN}recreated${NC}"

# Export the target URL so the steps below resolve to the database just created.
export DATABASE__URL="$HOMEPOT_DB_URL"

if [ "$STOP_SERVICE" -eq 1 ]; then
  echo "Starting $SERVICE..."
  sudo systemctl start "$SERVICE"
  SERVICE_STOPPED=0

  # The app bootstraps the schema through create_all() on startup, so a service
  # that fails here means the schema was never built. Report it before moving on
  # to migrations that would fail for the same reason.
  sleep 2
  if ! systemctl is-active --quiet "$SERVICE"; then
    echo -e "${RED}Error: $SERVICE did not come up after the reset.${NC}" >&2
    echo "The database is empty and the service is down. Inspect it with:" >&2
    echo "  sudo journalctl -u $SERVICE -n 50 --no-pager" >&2
    exit 1
  fi
  echo -e "${GREEN}active${NC}"
else
  echo -e "${YELLOW}--no-stop: the service is still running against a recreated database.${NC}"
  echo "Its pooled connections may need a restart to recover."
fi

echo ""
echo "Stamping alembic..."
"$REPO_ROOT/scripts/upgrade-db.sh"

if [ "$SKIP_SEED" -eq 1 ]; then
  echo ""
  echo -e "${YELLOW}--no-seed: skipping account provisioning.${NC}"
elif [ -f "$SCRIPT_DIR/seed-users.env" ]; then
  echo ""
  echo "Provisioning accounts..."
  "$REPO_ROOT/scripts/seed-users.sh" --dry-run
  "$REPO_ROOT/scripts/seed-users.sh"
else
  echo ""
  echo -e "${YELLOW}No scripts/seed-users.env — skipping account provisioning.${NC}"
  echo "Create one and seed accounts with:"
  echo "  cp scripts/seed-users.env.example scripts/seed-users.env"
  echo "  \$EDITOR scripts/seed-users.env"
  echo "  ./scripts/seed-users.sh"
fi

echo ""
echo -e "${GREEN}Reset complete.${NC}"
echo "  $TARGET_DESC — empty schema, alembic at head"
echo ""
echo "Sanity check:"
echo "  ./scripts/query-db.sh count"

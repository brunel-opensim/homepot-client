#!/bin/bash
# lib/db.sh — one place where HOMEPOT shell scripts resolve the database URL.
#
# Source this, then call homepot_db_resolve:
#
#   . "$(dirname "${BASH_SOURCE[0]}")/lib/db.sh"
#   homepot_db_resolve
#   psql "$HOMEPOT_DB_URL" ...
#
# Why this exists: scripts used to fall straight back to a hard-coded local dev
# default (localhost:5432/homepot_db). On a split-host deployment that default
# is wrong — the database lives on another host and is named `homepot` — so the
# scripts failed in ways that looked like a missing pg_hba entry or a missing
# database, when in fact they were simply pointing at the wrong server. The
# deployment's own backend/.env is the authoritative source and is read here.
#
# Precedence, highest first:
#   1. HOMEPOT_DB_URL            an explicit full URL
#   2. DATABASE__URL             already in the environment
#   3. DATABASE_URL              already in the environment
#   4. HOMEPOT_DB_HOST / _PORT / _USER / _NAME / _PASSWORD
#                                explicit connection parts (an unset part keeps
#                                its local dev default)
#   5. DATABASE__URL / DATABASE_URL read from backend/.env
#   6. local dev default         localhost:5432/homepot_db
#
# On success exports: HOMEPOT_DB_URL, HOMEPOT_DB_NAME, HOMEPOT_DB_USER,
# HOMEPOT_DB_HOST, HOMEPOT_DB_PORT. Never prints the URL or the password.

# shellcheck shell=bash

if [ -z "${BASH_VERSION:-}" ]; then
  printf 'error: scripts/lib/db.sh is a bash library and must be sourced by\na bash script (use #!/bin/bash and call . scripts/lib/db.sh).\n' >&2
  return 1 2>/dev/null || exit 1
fi

HOMEPOT_DB_DEFAULT_HOST="localhost"
HOMEPOT_DB_DEFAULT_PORT="5432"
HOMEPOT_DB_DEFAULT_USER="homepot_user"
HOMEPOT_DB_DEFAULT_NAME="homepot_db"
HOMEPOT_DB_DEFAULT_PASSWORD="homepot_dev_password"

# Split a postgresql:// URL into its parts. Sets HOMEPOT_DB_USER, _HOST, _PORT
# and _NAME; leaves them untouched on failure so the caller can report why.
homepot_db_parse_url() {
  local url="${1%%\?*}" rest auth hostport
  case "$url" in
    *://*) ;;
    *) return 1 ;;
  esac

  rest="${url#*://}"
  case "$rest" in
    *@*) ;;
    *) return 1 ;;
  esac
  auth="${rest%%@*}"
  hostport="${rest##*@}"

  case "$hostport" in
    */*) ;;
    *) return 1 ;;
  esac

  HOMEPOT_DB_USER="${auth%%:*}"
  HOMEPOT_DB_NAME="${hostport##*/}"
  hostport="${hostport%/*}"

  # A URL of the form postgresql://user:password@... carries the password;
  # postgresql://user@... does not, so this stays empty and the caller falls
  # back to its own default (peer/trust auth needs no password).
  case "$auth" in
    *:*) HOMEPOT_DB_PASSWORD="${auth#*:}" ;;
    *)   HOMEPOT_DB_PASSWORD="" ;;
  esac
  export HOMEPOT_DB_PASSWORD

  case "$hostport" in
    *:*) HOMEPOT_DB_PORT="${hostport##*:}" ;;
    *)   HOMEPOT_DB_PORT="$HOMEPOT_DB_DEFAULT_PORT" ;;
  esac
  HOMEPOT_DB_HOST="${hostport%:*}"

  [ -n "$HOMEPOT_DB_USER" ] && [ -n "$HOMEPOT_DB_NAME" ] && [ -n "$HOMEPOT_DB_HOST" ]
}

# Print DATABASE__URL (or DATABASE_URL) from backend/.env, if present.
homepot_db_env_file_url() {
  local root="${HOMEPOT_REPO_ROOT:-}" file line
  if [ -z "$root" ]; then
    root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
  fi
  file="$root/backend/.env"
  [ -f "$file" ] || return 1

  # Only accept an uncommented assignment of a postgres URL. Quotes are
  # stripped; anything else is left alone so the value fails later rather
  # than being silently mangled.
  line="$(grep -E '^[[:space:]]*(DATABASE__URL|DATABASE_URL)[[:space:]]*=' "$file" | tail -1)"
  [ -n "$line" ] || return 1
  line="${line#*=}"
  line="${line%$'\r'}"
  case "$line" in
    \"*\") line="${line#\"}"; line="${line%\"}" ;;
    \'*\') line="${line#\'}"; line="${line%\'}" ;;
  esac
  [ -n "$line" ] && printf '%s' "$line"
}

homepot_db_resolve() {
  local url="" host port user name password
  local explicit_parts=0

  if [ -n "${HOMEPOT_DB_URL:-}" ]; then
    url="$HOMEPOT_DB_URL"
  elif [ -n "${DATABASE__URL:-}" ]; then
    url="$DATABASE__URL"
  elif [ -n "${DATABASE_URL:-}" ]; then
    url="$DATABASE_URL"
  fi

  # Explicit HOMEPOT_DB_* parts win over backend/.env: a value typed into the
  # environment is a deliberate override. Test with +x, because these scripts
  # also supply dev defaults and must not mistake those for explicit intent.
  for var in HOMEPOT_DB_HOST HOMEPOT_DB_PORT HOMEPOT_DB_USER HOMEPOT_DB_NAME HOMEPOT_DB_PASSWORD; do
    if [ -n "${!var+x}" ]; then
      explicit_parts=1
      break
    fi
  done

  if [ -z "$url" ] && [ "$explicit_parts" -eq 1 ]; then
    host="${HOMEPOT_DB_HOST:-$HOMEPOT_DB_DEFAULT_HOST}"
    port="${HOMEPOT_DB_PORT:-$HOMEPOT_DB_DEFAULT_PORT}"
    user="${HOMEPOT_DB_USER:-$HOMEPOT_DB_DEFAULT_USER}"
    name="${HOMEPOT_DB_NAME:-$HOMEPOT_DB_DEFAULT_NAME}"
    password="${HOMEPOT_DB_PASSWORD:-$HOMEPOT_DB_DEFAULT_PASSWORD}"
    url="postgresql://${user}:${password}@${host}:${port}/${name}"
  fi

  if [ -z "$url" ]; then
    if url="$(homepot_db_env_file_url)"; then
      printf 'note: using DATABASE__URL from backend/.env\n' >&2
    else
      url="postgresql://${HOMEPOT_DB_DEFAULT_USER}:${HOMEPOT_DB_DEFAULT_PASSWORD}@${HOMEPOT_DB_DEFAULT_HOST}:${HOMEPOT_DB_DEFAULT_PORT}/${HOMEPOT_DB_DEFAULT_NAME}"
    fi
  fi

  if ! homepot_db_parse_url "$url"; then
    printf 'error: could not parse the database URL.\n' >&2
    printf 'Expected postgresql://user:password@host:port/database\n' >&2
    return 1
  fi

  HOMEPOT_DB_URL="$url"
  export HOMEPOT_DB_URL HOMEPOT_DB_NAME HOMEPOT_DB_USER HOMEPOT_DB_HOST HOMEPOT_DB_PORT
}

# Print the URL for a different database on the same server. PostgreSQL refuses
# to drop a database you are connected to, so a reset needs somewhere else to
# stand — `postgres` by default, never `template0` (datallowconn = false) and
# not `template1` either: CREATE DATABASE copies template1, so anything written
# there would be inherited by every database created afterwards.
homepot_db_url_for() {
  local name="$1"
  case "$HOMEPOT_DB_URL" in
    */*) printf '%s' "${HOMEPOT_DB_URL%/*}/${name}" ;;
    *) return 1 ;;
  esac
}

# Human-readable summary that never includes the password.
homepot_db_describe() {
  printf '%s@%s:%s/%s' "$HOMEPOT_DB_USER" "$HOMEPOT_DB_HOST" "$HOMEPOT_DB_PORT" "$HOMEPOT_DB_NAME"
}

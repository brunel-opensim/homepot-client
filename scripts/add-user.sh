#!/bin/bash
# add-user.sh — create a single HOMEPOT user interactively.
#
# For provisioning several accounts, or for rebuilding after a database reset,
# prefer scripts/seed-users.sh — it is re-runnable and reads credentials from a
# gitignored file instead of the command line.
#
# Usage:
#   ./scripts/add-user.sh <username> <email> <password> [role]
#
#   role: Admin | Technician (case-insensitive; legacy aliases such as
#         "engineer" or "viewer" are normalised). Defaults to Technician.
#         Use a literal 'true' or 'false' for is_admin to stay backward
#         compatible with older call sites.
#
# Examples:
#   ./scripts/add-user.sh john_doe john@example.com 'a-long-passphrase'
#   ./scripts/add-user.sh jane_ops jane@example.com 'a-long-passphrase' Admin
#   ./scripts/add-user.sh john_doe john@example.com 'a-long-passphrase' true
#
# The database URL is resolved the same way as scripts/upgrade-db.sh,
# scripts/query-db.sh and scripts/reset-prod-db.sh — see scripts/lib/db.sh:
#   --url 'postgresql://user:pw@host:5432/homepot_db'   (highest precedence)
#   DATABASE__URL
#   DATABASE_URL
#   HOMEPOT_DB_HOST / _PORT / _USER / _NAME / _PASSWORD
#   DATABASE__URL from backend/.env
#   local dev default (localhost:5432/homepot_db)
# Reading backend/.env is what matters on split-host deployments, where the
# database is not on localhost and is not named homepot_db.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=scripts/lib/db.sh
. "$SCRIPT_DIR/lib/db.sh"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

usage() { sed -n '2,30p' "$0" | sed 's/^# \{0,1\}//'; }

if [ "$#" -lt 3 ]; then
  echo -e "${RED}Error: too few arguments${NC}" >&2
  usage >&2
  exit 1
fi

# Pull --url out of the argument list before the positional count is checked,
# so its presence does not trip the "too many arguments" guard.
URL=""
if [ "${1:-}" = "--url" ]; then
  URL="${2:-}"
  if [ -z "$URL" ]; then
    echo -e "${RED}Error: --url requires a value${NC}" >&2
    exit 1
  fi
  shift 2
fi

if [ "$#" -gt 4 ]; then
  echo -e "${RED}Error: too many arguments${NC}" >&2
  usage >&2
  exit 1
fi

USERNAME="$1"
EMAIL="$2"
PASSWORD="$3"
ROLE_RAW="${4:-Technician}"

# Backward compatibility: older call sites passed is_admin as true/false.
case "$ROLE_RAW" in
  true)  ROLE_RAW="Admin" ;;
  false) ROLE_RAW="Technician" ;;
esac

if [ "${#PASSWORD}" -lt 12 ]; then
  echo -e "${RED}Error: password must be at least 12 characters.${NC}" >&2
  exit 1
fi

# ----- Resolve the database URL ---------------------------------------------
# CLI --url > DATABASE__URL > DATABASE_URL > HOMEPOT_DB_* > backend/.env >
# local dev default. Exporting the result keeps the Python block below, which
# reads DATABASE__URL, in step with whatever was resolved here.
if [ -n "$URL" ]; then
  HOMEPOT_DB_URL="$URL"
fi
homepot_db_resolve
export DATABASE__URL="$HOMEPOT_DB_URL"

# ----- Locate the interpreter ------------------------------------------------
# The repo venv lives at the checkout root (.venv/), matching every other
# script. No fallback to backend/.venv (non-canonical location).
if [ -x "$REPO_ROOT/.venv/bin/python" ]; then
  PYTHON="$REPO_ROOT/.venv/bin/python"
else
  PYTHON="python3"
fi

if ! "$PYTHON" -c "import passlib, sqlalchemy" >/dev/null 2>&1; then
  echo -e "${RED}Error: passlib/sqlalchemy not importable by $PYTHON${NC}" >&2
  echo "Create the repo venv at the checkout root first:" >&2
  echo "  python3 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt" >&2
  exit 1
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "HOMEPOT Add User"
echo "  username: $USERNAME"
echo "  email:    $EMAIL"
echo "  role:     $ROLE_RAW"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Password hashing and the dialect fix both need Python, so the work happens
# there rather than in a temp file written to the repo root.
REPO_ROOT="$REPO_ROOT" PYTHON="$PYTHON" \
  HOMEPOT_NEW_USERNAME="$USERNAME" \
  HOMEPOT_NEW_EMAIL="$EMAIL" \
  HOMEPOT_NEW_PASSWORD="$PASSWORD" \
  HOMEPOT_NEW_ROLE="$ROLE_RAW" \
  "$PYTHON" - <<'PYEOF'
import os
import sys

REPO_ROOT = os.environ["REPO_ROOT"]
sys.path.insert(0, os.path.join(REPO_ROOT, "backend", "src"))

import bcrypt  # noqa: E402

# passlib 1.7.x reads bcrypt.__about__, removed in bcrypt 4.0+.
if not hasattr(bcrypt, "__about__"):
    class _About:
        __version__ = bcrypt.__version__

    bcrypt.__about__ = _About()

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from homepot.app.auth_utils import hash_password  # noqa: E402
from homepot.app.roles import (  # noqa: E402
    ADMIN,
    LEGACY_ROLE_ALIASES,
    normalize_role,
)
from homepot.database import to_sync_db_url  # noqa: E402
from homepot.models import User  # noqa: E402

RED = "\033[0;31m"
YELLOW = "\033[1;33m"
GREEN = "\033[0;32m"
NC = "\033[0m"

username = os.environ["HOMEPOT_NEW_USERNAME"].strip()
email = os.environ["HOMEPOT_NEW_EMAIL"].strip()
password = os.environ["HOMEPOT_NEW_PASSWORD"]
role_raw = os.environ["HOMEPOT_NEW_ROLE"].strip()

role = normalize_role(role_raw)
if role_raw.lower() not in LEGACY_ROLE_ALIASES:
    print(f"{RED}Error: unrecognised role {role_raw!r}.{NC}", file=sys.stderr)
    print(f"Valid roles: {ADMIN}, Technician (aliases accepted).", file=sys.stderr)
    sys.exit(1)

# Derive the legacy boolean from the canonical role, NOT from
# roles.is_privileged(): that returns True for every role while
# HOMEPOT_DEV_UNIFIED_ACCESS is on, which would make a Technician an admin.
is_admin = role == ADMIN

# #479: a bare postgresql:// URL must be normalised for the sync engine or
# SQLAlchemy 2.1 picks psycopg 3 and fails with "No module named 'psycopg'".
url = to_sync_db_url(os.environ["DATABASE__URL"])
engine = create_engine(url)
Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = Session()

try:
    clash = db.query(User).filter(User.username == username).first()
    if clash is None:
        clash = db.query(User).filter(User.email == email).first()
    if clash is not None:
        print(
            f"{RED}Error:{NC} a user with that username or email already exists "
            f"({clash.username}). Use scripts/seed-users.sh to update in place.",
            file=sys.stderr,
        )
        db.rollback()
        sys.exit(1)

    db.add(
        User(
            username=username,
            email=email,
            hashed_password=hash_password(password),
            role=role,
            is_admin=is_admin,
            is_active=True,
        )
    )
    db.commit()
    print(f"{GREEN}Created user {username} ({email}) with role {role}.{NC}")
except Exception as exc:
    db.rollback()
    print(f"{RED}Failed to create user: {exc}{NC}", file=sys.stderr)
    sys.exit(1)
finally:
    db.close()
    engine.dispose()
PYEOF

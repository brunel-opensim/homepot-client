#!/bin/bash
# seed-users.sh — idempotently provision HOMEPOT admin/technician accounts.
#
# Intended for rebuilding the `users` table after a database reset (development),
# or for adding the initial accounts to a fresh deployment. It is safe to re-run:
# existing usernames are updated in place rather than rejected.
#
# Credentials are NEVER committed. Copy the template, fill it in, and run:
#   cp scripts/seed-users.env.example scripts/seed-users.env   # gitignored
#   $EDITOR scripts/seed-users.env
#   ./scripts/seed-users.sh
#
# Usage:
#   ./scripts/seed-users.sh [options]
#
# Options:
#   --url URL        Target database URL. Overrides DATABASE__URL / DATABASE_URL.
#                    Required for a remote/split-host database, e.g.
#                    ./scripts/seed-users.sh --url 'postgresql://user:pw@db-host:5432/homepot_db'
#   --env-file PATH  Credentials file to read (default: scripts/seed-users.env)
#   --dry-run        Report what would change without writing to the database.
#   -h, --help       Show this help.
#
# Unlike the older scripts/add-user.sh, this:
#   - sets `role` (the column the app authorises against since #478) and not
#     just the legacy `is_admin` flag;
#   - normalises roles via homepot.app.roles, so aliases like "admin" or
#     "engineer" resolve to canonical Admin/Technician;
#   - routes the sync engine through to_sync_db_url() (#479), so a bare
#     postgresql:// URL works on SQLAlchemy 2.1 instead of failing on
#     "No module named 'psycopg'";
#   - is re-runnable, and never prints a password.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

ENV_FILE="$SCRIPT_DIR/seed-users.env"
URL=""
DRY_RUN=0

usage() { sed -n '2,32p' "$0" | sed 's/^# \{0,1\}//'; }

while [ "$#" -gt 0 ]; do
  case "$1" in
    --url)
      URL="${2:-}"
      if [ -z "$URL" ]; then
        echo -e "${RED}Error: --url requires a value${NC}" >&2
        exit 1
      fi
      shift 2
      ;;
    --env-file)
      ENV_FILE="${2:-}"
      if [ -z "$ENV_FILE" ]; then
        echo -e "${RED}Error: --env-file requires a path${NC}" >&2
        exit 1
      fi
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo -e "${RED}Unknown option: $1${NC}" >&2
      usage >&2
      exit 1
      ;;
  esac
done

# ----- Resolve the database URL ---------------------------------------------
# Same precedence as scripts/upgrade-db.sh: CLI > DATABASE__URL > DATABASE_URL.
if [ -n "$URL" ]; then
  export DATABASE__URL="$URL"
elif [ -n "${DATABASE__URL:-}" ]; then
  :
elif [ -n "${DATABASE_URL:-}" ]; then
  export DATABASE__URL="$DATABASE_URL"
else
  export DATABASE__URL="postgresql://homepot_user:homepot_dev_password@localhost:5432/homepot_db"
fi

# ----- Load credentials ------------------------------------------------------
if [ ! -f "$ENV_FILE" ]; then
  echo -e "${RED}Error: credentials file not found: $ENV_FILE${NC}" >&2
  echo "Create it from the template — it is gitignored and must not be committed:" >&2
  echo "  cp $SCRIPT_DIR/seed-users.env.example $ENV_FILE" >&2
  exit 1
fi

# Refuse to read a credentials file that git is tracking.
if git -C "$REPO_ROOT" ls-files --error-unmatch "$ENV_FILE" >/dev/null 2>&1; then
  echo -e "${RED}Error: $ENV_FILE is tracked by git.${NC}" >&2
  echo "Credentials must never be committed. Untrack it and rotate any exposed password:" >&2
  echo "  git rm --cached $ENV_FILE" >&2
  exit 1
fi

# Deliberately NOT sourced by the shell: the credentials are a bash array,
# and bash arrays cannot be exported to a child process. The file is parsed
# by the Python block below instead. Presence is checked here so a missing
# definition fails before the interpreter starts.
if ! grep -qE '^[[:space:]]*HOMEPOT_SEED_USERS=' "$ENV_FILE"; then
  echo -e "${RED}Error: HOMEPOT_SEED_USERS is not defined in $ENV_FILE${NC}" >&2
  echo "It must be a non-empty list of username:email:password:role entries." >&2
  exit 1
fi

# ----- Locate the interpreter ------------------------------------------------
# Prefer the repo venv so passlib/bcrypt/SQLAlchemy resolve the same way they do
# in the service. Fall back to whatever python3 is on PATH.
if [ -x "$REPO_ROOT/.venv/bin/python" ]; then
  PYTHON="$REPO_ROOT/.venv/bin/python"
elif [ -x "$REPO_ROOT/backend/.venv/bin/python" ]; then
  PYTHON="$REPO_ROOT/backend/.venv/bin/python"
else
  PYTHON="python3"
fi

if ! "$PYTHON" -c "import passlib, sqlalchemy" >/dev/null 2>&1; then
  echo -e "${RED}Error: passlib/sqlalchemy not importable by $PYTHON${NC}" >&2
  echo "Create the repo venv first:" >&2
  echo "  python3 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt" >&2
  exit 1
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "HOMEPOT User Seed"
[ "$DRY_RUN" -eq 1 ] && echo "  *** DRY RUN — no changes will be written ***"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Credentials file: $ENV_FILE"
echo

# Do the work in Python: password hashing and the dialect fix both need it.
REPO_ROOT="$REPO_ROOT" PYTHON="$PYTHON" DRY_RUN="$DRY_RUN" ENV_FILE="$ENV_FILE" "$PYTHON" - <<'PYEOF'
import os
import re
import sys

REPO_ROOT = os.environ["REPO_ROOT"]
DRY_RUN = os.environ["DRY_RUN"] == "1"

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

GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
NC = "\033[0m"

# Parse the credentials file directly. The template uses a bash array
# (HOMEPOT_SEED_USERS=( "u:e:p:Role" )), so strip that wrapper and read the
# quoted entries between the opening parenthesis and the closing one.
env_file = os.environ["ENV_FILE"]
try:
    with open(env_file, encoding="utf-8") as handle:
        text = handle.read()
except OSError as exc:
    print(f"{RED}Could not read {env_file}: {exc}{NC}", file=sys.stderr)
    sys.exit(1)

if "HOMEPOT_SEED_USERS" not in text:
    print(f"{RED}HOMEPOT_SEED_USERS is not defined in {env_file}{NC}", file=sys.stderr)
    sys.exit(1)

# Collect the assignment, ignoring commented-out definitions.
body_lines = []
in_block = False
for raw_line in text.splitlines():
    stripped = raw_line.strip()
    if stripped.startswith("#"):
        continue
    if not in_block:
        if stripped.startswith("HOMEPOT_SEED_USERS"):
            in_block = True
            remainder = stripped.split("=", 1)[1] if "=" in stripped else ""
            if remainder.strip():
                body_lines.append(remainder)
        continue
    if stripped.startswith(")"):
        break
    body_lines.append(raw_line)

block = "\n".join(body_lines)
# Entries look like: "username:email:password:Role"
entries = []
for match in re.finditer(r'"([^"]*)"|\'([^\']*)\'', block):
    line = (match.group(1) or match.group(2) or "").strip()
    if not line:
        continue
    parts = line.split(":")
    if len(parts) != 4:
        print(
            f"{RED}Bad entry (expected username:email:password:role):{NC} {line!r}",
            file=sys.stderr,
        )
        sys.exit(1)
    username, email, password, role = (p.strip() for p in parts)
    if not username or not email or not password or not role:
        print(f"{RED}Incomplete entry:{NC} {line!r}", file=sys.stderr)
        sys.exit(1)
    if len(password) < 12:
        print(
            f"{RED}Refusing to seed {username}: password is shorter than 12 characters.{NC}",
            file=sys.stderr,
        )
        sys.exit(1)
    entries.append((username, email, password, role))

if not entries:
    print(f"{RED}No users to seed in {env_file}.{NC}", file=sys.stderr)
    sys.exit(1)

# #479: a bare postgresql:// URL must be normalised for the sync engine, or
# SQLAlchemy 2.1 picks psycopg 3 and fails even when psycopg2 is installed.
url = to_sync_db_url(os.environ["DATABASE__URL"])

engine = create_engine(url)
Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = Session()

try:
    for username, email, password, role in entries:
        # Recognised legacy spellings (Engineer, Client, Viewer, ...) are a
        # deliberate alias and normalise quietly. Anything outside that map
        # would silently collapse to Technician, so warn loudly instead.
        canonical = normalize_role(role)
        if role.strip().lower() not in LEGACY_ROLE_ALIASES:
            print(
                f"  {RED}warn{NC}    unrecognised role {role!r} for {username}; "
                f"treating as {canonical}"
            )
        # The legacy boolean is kept in step with `role` so code still reading
        # is_admin (and vice versa) cannot disagree. It is deliberately NOT
        # derived from is_privileged(): that helper returns True for every role
        # while HOMEPOT_DEV_UNIFIED_ACCESS is on, which would make every seeded
        # technician an admin.
        admin = canonical == ADMIN

        existing = db.query(User).filter(User.username == username).first()
        if existing is None:
            existing = db.query(User).filter(User.email == email).first()

        if existing is not None:
            action = f"{YELLOW}update{NC}"
            verb = "Updated"
        else:
            action = f"{GREEN}create{NC}"
            verb = "Created"

        # Never echo the password itself. bcrypt salts each hash, so re-running
        # rewrites the hash even for an unchanged password; that is intentional
        # and keeps the stored hash on the current cost factor.
        verb_note = "hashed" if existing is None else "re-hashed"
        print(f"  {action}  {username:<20} {email:<30} role={canonical} (password {verb_note})")

        if DRY_RUN:
            continue

        if existing is not None:
            existing.username = username
            existing.email = email
            existing.hashed_password = hash_password(password)
            existing.role = canonical
            existing.is_admin = admin
            existing.is_active = True
        else:
            db.add(
                User(
                    username=username,
                    email=email,
                    hashed_password=hash_password(password),
                    role=canonical,
                    is_admin=admin,
                    is_active=True,
                )
            )

    if DRY_RUN:
        db.rollback()
        print(f"\n{YELLOW}Dry run — nothing was written.{NC}")
    else:
        db.commit()
        print(f"\n{GREEN}Seeded {len(entries)} user(s).{NC}")
except Exception as exc:
    db.rollback()
    print(f"{RED}Failed to seed users: {exc}{NC}", file=sys.stderr)
    sys.exit(1)
finally:
    db.close()
    engine.dispose()
PYEOF

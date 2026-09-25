#!/bin/bash
# HOMEPOT: pre-existing install / duplicate-clone audit (read-only, sudo-free).
# Answers one question: is there exactly ONE HOMEPOT on this box, under
# /var/www/homepot.cabera.com, and is anything else still running that would
# conflict with a centralized dashboard?
#
# Usage (as demouser on the server):
#   curl -fsSL https://raw.githubusercontent.com/brunel-opensim/homepot-client/feat/passwordless-trust/scripts/audit-existing-installs.sh | bash
#
# It only reads (find/ps/systemctl/ss). It never deletes or stops anything —
# you decide what to remove. See docs/server-deployment.md for the deploy.

set -u
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; BLUE='\033[0;34m'; NC='\033[0m'
SITE_DIR="${HOMEPOT_SITE_DIR:-/var/www/homepot.cabera.com}"
pass(){ echo -e "${GREEN}[OK]${NC}   $*"; }
warn(){ echo -e "${YELLOW}[CHECK]${NC} $*"; }
bad(){  echo -e "${RED}[DUPLICATE/CONFLICT]${NC} $*"; }
h(){ echo; echo "━━ $* ━━"; }

echo -e "${BLUE}HOMEPOT existing-install audit${NC} (as $(whoami)@$(hostname))"
echo "  we want exactly ONE HOMEPOT, at: $SITE_DIR"

SITE_REAL=$(cd "$SITE_DIR" 2>/dev/null && pwd -P)

h "A. homepot directories found (candidate clones)"
found_all=""
for base in /var/www /srv /opt /home /usr/local; do
  [ -d "$base" ] || continue
  f=$(find "$base" -maxdepth 4 \( -name 'homepot' -o -name 'homepot-client' -o -name 'Homepot' -o -name 'homepot.cabera.com' \) -type d 2>/dev/null || true)
  [ -n "$f" ] && found_all="$found_all$f"$'\n'
done
if [ -z "$found_all" ]; then
  pass "no homepot clone found yet in /var/www,/srv,/opt,/home,/usr/local (fresh box — good)"
else
  printf "%s" "$found_all" | sed 's/^/      /'
  n=$(printf "%s" "$found_all" | grep -c .)
  extra=0
  while IFS= read -r d; do
    [ -n "$d" ] || continue
    real=$(cd "$d" 2>/dev/null && pwd -P)
    [ "$real" = "$SITE_REAL" ] && continue
    extra=$((extra + 1))
  done <<< "$found_all"
  if [ "$extra" -eq 0 ]; then
    pass "all found dirs resolve to the single deploy clone $SITE_DIR (single-clone clean)"
  else
    bad "$extra homepot dir/ies NOT under $SITE_DIR — review each; keep only ONE live copy"
  fi
fi

h "B. deploy-clone git state (which version is live?)"
if [ -d "$SITE_DIR/.git" ]; then
  BR=$(git -C "$SITE_DIR" rev-parse --abbrev-ref HEAD 2>/dev/null)
  SHA=$(git -C "$SITE_DIR" rev-parse --short HEAD 2>/dev/null)
  DATE=$(git -C "$SITE_DIR" log -1 --format=%cd --date=short 2>/dev/null)
  pass "branch=$BR commit=$SHA date=$DATE"
  DIRTY=$(git -C "$SITE_DIR" status --porcelain 2>/dev/null | head -10)
  if [ -n "$DIRTY" ]; then
    warn "uncommitted changes present (version not reproducible):"
    printf "%s\n" "$DIRTY" | sed 's/^/        /'
  else
    pass "working tree clean (reproducible version)"
  fi
  REM=$(git -C "$SITE_DIR" remote -v 2>/dev/null | head -1)
  [ -n "$REM" ] && echo "      remote: $REM"
else
  warn "no .git under $SITE_DIR (not a git clone, or not deployed yet)"
fi

h "C. running HOMEPOT processes (old instance still up?)"
if command -v ps >/dev/null 2>&1; then
  PROCS=$(ps -eo pid,args 2>/dev/null | grep -E 'uvicorn|vite|homepot' | grep -v -e grep -e 'ps -eo' | head -8)
  if [ -n "$PROCS" ]; then
    warn "these are running — confirm only the intended one stays:"
    printf "%s\n" "$PROCS" | sed 's/^/      /'
  else
    pass "no uvicorn/vite/homepot processes running"
  fi
fi

h "D. systemd units named *homepot* (auto-start duplicates?)"
if command -v systemctl >/dev/null 2>&1; then
  U=$(systemctl list-units --type=service --all 2>/dev/null | grep -i homepot | head -5)
  if [ -n "$U" ]; then
    bad "homepot service unit(s) exist — make sure at most ONE is enabled:"
    printf "%s\n" "$U" | sed 's/^/      /'
  else
    pass "no *homepot* systemd service (no duplicate auto-start)"
  fi
fi

h "E. ports the centralized dashboard needs"
if command -v ss >/dev/null 2>&1; then
  for port in 8000 5173 11434; do
    w=$(ss -ltnp 2>/dev/null | grep ":$port " | head -1)
    if [ -n "$w" ]; then
      bad "port $port busy: $w"
    else
      pass "port $port free"
    fi
  done
else
  warn "ss not available — could not check ports (install iproute2 or use 'netstat -ltnp')"
fi

echo
echo -e "${BLUE}Nothing was changed or deleted by this audit.${NC} Decide what to keep, then deploy under $SITE_DIR."

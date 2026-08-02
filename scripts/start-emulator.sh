#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------------------------------------
# start-emulator.sh — Launch a HOMEPOT device emulator
#
# Usage:
#   ./scripts/start-emulator.sh                    # uses default config
#   ./scripts/start-emulator.sh --config emulators/my-device.json
#   ./scripts/start-emulator.sh --site-id site-1 --bootstrap-key <key>
#
# Prerequisites:
#   - Python virtual environment at .venv/ with httpx installed
#   - Backend running (start-dashboard.sh)
#   - A bootstrap key generated for the target site
# ---------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_DIR"

# --- Python & venv ----------------------------------------------------------

PYTHON=""
if [ -f ".venv/bin/python" ]; then
    PYTHON=".venv/bin/python"
elif [ -f ".venv/bin/python3" ]; then
    PYTHON=".venv/bin/python3"
else
    echo "Error: Python virtual environment not found at .venv/"
    echo "  Run: python3 -m venv .venv && source .venv/bin/activate && pip install -e backend/."
    exit 1
fi

# --- Config -----------------------------------------------------------------

CONFIG_ARGS=()
if [[ "$#" -eq 0 ]]; then
    CONFIG_ARGS=("--config" "emulators/linux_pos_emulator.json")
fi

# --- Run --------------------------------------------------------------------

echo "Starting HOMEPOT device emulator ..."
echo "  Python: $PYTHON"
echo "  Config args: ${CONFIG_ARGS[*]:-} $*"
echo ""

if (( ${#CONFIG_ARGS[@]} )); then
    $PYTHON emulators/linux_pos_emulator.py "${CONFIG_ARGS[@]}" "$@"
else
    $PYTHON emulators/linux_pos_emulator.py "$@"
fi

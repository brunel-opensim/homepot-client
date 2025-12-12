#!/bin/bash
# Script to run analytics validation test

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$PROJECT_ROOT/backend"

cd "$BACKEND_DIR"
source venv/bin/activate

echo "Starting backend server..."
uvicorn homepot.app.main:app --host 127.0.0.1 --port 8000 > /tmp/backend-test.log 2>&1 &
BACKEND_PID=$!

echo "Waiting for backend to start..."
sleep 6

echo -e "\n============================================"
echo "Running Analytics Validation"
echo "============================================\n"

python3 "$BACKEND_DIR/utils/validate_analytics.py" analytics-test@example.com testpass123

VALIDATION_EXIT=$?

echo -e "\n============================================"
echo "Backend Logs (last 20 lines):"
echo "============================================\n"
tail -20 /tmp/backend-test.log

echo -e "\n============================================"
echo "Cleaning up..."
echo "============================================\n"
kill $BACKEND_PID 2>/dev/null
sleep 2
kill -9 $BACKEND_PID 2>/dev/null

exit $VALIDATION_EXIT

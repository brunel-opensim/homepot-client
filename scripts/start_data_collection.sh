#!/bin/bash
# HOMEPOT Data Collection Starter
# 
# This script starts the HOMEPOT backend and monitors data collection.
# Developers can run this for 3-5 days to gather AI training data.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$PROJECT_ROOT/backend"

# Check if virtual environment exists
if [ ! -d "$PROJECT_ROOT/venv" ]; then
    echo "Virtual environment not found!"
    echo "   Run: python3 -m venv venv && source venv/bin/activate && pip install -r backend/requirements.txt"
    exit 1
fi

# Check if .env exists
if [ ! -f "$BACKEND_DIR/.env" ]; then
    echo "  .env file not found!"
    echo "   Copying from .env.example..."
    cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env"
    echo "   Created .env file"
    echo "   Please configure database credentials in .env"
    echo ""
fi

# Activate virtual environment
source "$PROJECT_ROOT/venv/bin/activate"

# Check database connectivity (silent)
python3 -c "
import sys
sys.path.insert(0, '$BACKEND_DIR/src')
import asyncio
from homepot.database import get_database_service
from sqlalchemy import text

async def check():
    try:
        db = await get_database_service()
        async with db.get_session() as session:
            await session.execute(text('SELECT 1'))
        return True
    except Exception as e:
        print(f'✗ Database connection failed: {e}')
        return False

if not asyncio.run(check()):
    sys.exit(1)
" 2>/dev/null

if [ $? -ne 0 ]; then
    echo "✗ Cannot connect to database!"
    echo "   1. Ensure PostgreSQL is running"
    echo "   2. Check credentials in .env file"
    echo "   3. Run: python scripts/setup_database.py"
    exit 1
fi

# Check if port 8000 is in use
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "Port 8000 is in use. Stopping existing process..."
    kill -9 $(lsof -t -i:8000) 2>/dev/null || true
    sleep 1
    echo "✓ Port 8000 is now available"
fi

echo ""
echo "Checking current data collection status..."
python3 "$BACKEND_DIR/utils/validate_data_collection.py" --min-days 0 || true

echo ""
echo "=============================================="
echo "Starting HOMEPOT Backend"
echo "=============================================="
echo ""
echo "The backend will:"
echo "  • Start 10+ simulated POS agents"
echo "  • Collect device metrics every 5 seconds"
echo "  • Track job outcomes and state changes"
echo "  • Log errors and configuration changes"
echo ""
echo "To validate data collection, run:"
echo "  python -W ignore::DeprecationWarning backend/utils/validate_data_collection.py"
echo ""
echo "Or for detailed check:"
echo "  python -W ignore::DeprecationWarning backend/utils/validate_data_collection.py --min-days 1"
echo ""
echo "Press Ctrl+C to stop (when ready to validate)"
echo ""
echo "Starting in 3 seconds..."
sleep 3

# Start backend
cd "$BACKEND_DIR"
uvicorn homepot.main:app --host 0.0.0.0 --port 8000 --reload

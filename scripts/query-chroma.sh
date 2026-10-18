#!/bin/bash
# Simple ChromaDB query helper for HOMEPOT AI memory
#
# Two stores are inspected (see ai/config.yaml):
#   memory -> data/chroma_db   / collection device_logs  (AI long-term memory)
#   docs   -> data/docs_chroma / collection project_docs (Tier C doc index)
#
# If the live store cannot be opened (the running API holds it, or it is owned
# by another user), the inspector falls back to a temporary snapshot copy.

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
WORKSPACE_ROOT="$(dirname "$SCRIPT_DIR")"

# Check if python3 is available
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 is not installed or not in PATH."
    exit 1
fi

# If no argument provided, show usage
if [ $# -eq 0 ]; then
    echo "Usage: ./scripts/query-chroma.sh [--store memory|docs] [command]"
    echo ""
    echo "Stores (default: memory):"
    echo "  memory              - AI long-term memory (data/chroma_db)"
    echo "  docs                - Tier C documentation index (data/docs_chroma)"
    echo ""
    echo "Available commands:"
    echo "  list                - List all collections"
    echo "  count               - Count items in the default collection"
    echo "  peek [n]            - View the first N items (default 5)"
    echo "  query \"text\" [n]    - Search for similar items"
    echo "  dump                - Dump all items (ID and Metadata only)"
    echo ""
    echo "Examples:"
    echo "  ./scripts/query-chroma.sh count"
    echo "  ./scripts/query-chroma.sh peek -n 3"
    echo "  ./scripts/query-chroma.sh query \"camera failure\""
    echo "  ./scripts/query-chroma.sh --store docs count"
    echo "  ./scripts/query-chroma.sh --store docs query \"device enrolment\""
    exit 1
fi

# Run the python inspector
python3 "$WORKSPACE_ROOT/ai/inspect_chroma.py" "$@"

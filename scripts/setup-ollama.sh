#!/bin/bash
# scripts/setup_ollama.sh
# Automates Ollama setup, serving, and model pulling based on ai/config.yaml

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== HOMEPOT AI: Ollama Setup & Manager ===${NC}"

# 1. Extract Model Name from Config
if [ ! -f "ai/config.yaml" ]; then
    echo -e "${RED}Error: ai/config.yaml not found!${NC}"
    exit 1
fi

# Use Python to safely parse YAML (assumes PyYAML is installed in current env)
# If python/yaml fails, fallback to a simple grep
if python3 -c "import yaml" &> /dev/null; then
    MODEL=$(python3 -c "import yaml; print(yaml.safe_load(open('ai/config.yaml'))['llm']['model'])")
else
    echo -e "${YELLOW}Warning: PyYAML not found. Falling back to grep...${NC}"
    MODEL=$(grep "model:" ai/config.yaml | head -n 1 | awk -F'"' '{print $2}')
fi

if [ -z "$MODEL" ]; then
    echo -e "${RED}Error: Could not determine LLM model from config.${NC}"
    exit 1
fi

echo -e "Target Model: ${GREEN}$MODEL${NC}"

# 2. Check/Install Ollama
if ! command -v ollama &> /dev/null; then
    echo -e "${YELLOW}Ollama not found. Installing...${NC}"
    if [[ "$OSTYPE" == "darwin"* ]]; then
        if command -v brew &> /dev/null; then
             echo -e "${YELLOW}Detected macOS. Installing via Homebrew...${NC}"
             brew install ollama || { echo -e "${RED}Homebrew install failed.${NC}"; exit 1; }
        else
             echo -e "${RED}Error: Homebrew not found. Please install Ollama manually from https://ollama.com/download${NC}"
             exit 1
        fi
    else
        # Linux / other
        curl -fsSL https://ollama.com/install.sh | sh
    fi
else
    echo -e "${GREEN}Ollama is already installed.${NC}"
fi

# 3. Check Port & Serve
OLLAMA_PORT=11434

# Detect an existing Ollama instance. `lsof` may return nothing when the
# server runs under a different OS user (e.g. a systemd `ollama` user), so
# fall back to probing the HTTP API on the Ollama port and to `pgrep`.
PID=$(lsof -ti :$OLLAMA_PORT 2>/dev/null || true)
if [ -n "$PID" ]; then
    IS_VERIFIED=false
else
    # Try to find Ollama regardless of ownership via the API probe + pgrep.
    if curl -s -m 2 "http://127.0.0.1:$OLLAMA_PORT/api/version" > /dev/null 2>&1; then
        PID=$(pgrep -x ollama | head -n 1 || true)
    fi
    if [ -z "$PID" ] && pgrep -x ollama > /dev/null 2>&1; then
        PID=$(pgrep -x ollama | head -n 1)
    fi
fi

LOG_DIR="logs"
AI_LOG_FILE="$LOG_DIR/ai.log"
AI_PID_FILE="$LOG_DIR/ai.pid"
mkdir -p "$LOG_DIR"

if [ -n "$PID" ]; then
    echo -e "${YELLOW}Port $OLLAMA_PORT is already in use (PID $PID).${NC}"
    # Check if it's actually ollama
    PROCESS_NAME=$(ps -p $PID -o comm= 2>/dev/null || echo unknown)
    if [[ "$PROCESS_NAME" == "ollama" ]] || curl -s -m 2 "http://127.0.0.1:$OLLAMA_PORT/api/version" > /dev/null 2>&1; then
        echo -e "${GREEN}It is an existing Ollama instance. Reusing it.${NC}"
        echo "$PID" > "$AI_PID_FILE"
    else
        echo -e "${RED}Warning: Port $OLLAMA_PORT is used by '$PROCESS_NAME', not Ollama.${NC}"
        echo -e "${YELLOW}Attempting to kill conflicting process...${NC}"
        kill -9 $PID 2>/dev/null || true
        echo -e "Starting Ollama..."
        nohup ollama serve >> "$AI_LOG_FILE" 2>&1 &
        echo $! > "$AI_PID_FILE"
    fi
else
    echo -e "Starting Ollama server..."
    nohup ollama serve >> "$AI_LOG_FILE" 2>&1 &
    echo $! > "$AI_PID_FILE"
    echo -e "Waiting for Ollama to start..."
    sleep 5
fi

# 4. Pull Model
echo -e "Checking model availability..."
echo -e "Ollama Version: ${GREEN}$(ollama --version 2>&1)${NC}"

# We use 'ollama list' to check if model exists, if not pull it
if ollama list | grep -q "$MODEL"; then
    echo -e "${GREEN}Model '$MODEL' is already available.${NC}"
else
    echo -e "${YELLOW}Model '$MODEL' not found. Pulling... (This may take a while)${NC}"
    ollama pull "$MODEL"
    echo -e "${GREEN}Model pulled successfully.${NC}"
fi

echo -e "${GREEN}=== Setup Complete. Ollama is ready. ===${NC}"

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
    curl -fsSL https://ollama.com/install.sh | sh
else
    echo -e "${GREEN}Ollama is already installed.${NC}"
fi

# 3. Check Port & Serve
OLLAMA_PORT=11434
PID=$(lsof -ti :$OLLAMA_PORT || true)

if [ -n "$PID" ]; then
    echo -e "${YELLOW}Port $OLLAMA_PORT is already in use by PID $PID.${NC}"
    # Check if it's actually ollama
    PROCESS_NAME=$(ps -p $PID -o comm=)
    if [[ "$PROCESS_NAME" == "ollama" ]]; then
        echo -e "${GREEN}It is an existing Ollama instance. Reusing it.${NC}"
    else
        echo -e "${RED}Warning: Port $OLLAMA_PORT is used by '$PROCESS_NAME', not Ollama.${NC}"
        echo -e "${YELLOW}Attempting to kill conflicting process...${NC}"
        kill -9 $PID
        echo -e "Starting Ollama..."
        ollama serve &
    fi
else
    echo -e "Starting Ollama server..."
    ollama serve > /dev/null 2>&1 &
    echo -e "Waiting for Ollama to start..."
    sleep 5
fi

# 4. Pull Model
echo -e "Checking model availability..."
# We use 'ollama list' to check if model exists, if not pull it
if ollama list | grep -q "$MODEL"; then
    echo -e "${GREEN}Model '$MODEL' is already available.${NC}"
else
    echo -e "${YELLOW}Model '$MODEL' not found. Pulling... (This may take a while)${NC}"
    ollama pull "$MODEL"
    echo -e "${GREEN}Model pulled successfully.${NC}"
fi

echo -e "${GREEN}=== Setup Complete. Ollama is ready. ===${NC}"

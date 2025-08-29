#!/bin/bash
# Docker build validation script for CI/CD

# Useful command
# ./scripts/test-docker.sh --help

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
IMAGE_NAME="homepot-client"
TAG="ci-test"
FULL_IMAGE="$IMAGE_NAME:$TAG"
TEST_PORT=8001
HEALTH_TIMEOUT=30
DRY_RUN=false

# Print usage
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --dry-run       Only validate files, don't build or run container"
    echo "  --port PORT     Use custom port for testing (default: 8001)"
    echo "  --timeout SEC   Health check timeout in seconds (default: 30)"
    echo "  -h, --help      Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                    # Full Docker validation"
    echo "  $0 --dry-run          # Only validate files"
    echo "  $0 --port 9000        # Use port 9000 for testing"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --port)
            TEST_PORT="$2"
            shift 2
            ;;
        --timeout)
            HEALTH_TIMEOUT="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

echo -e "${GREEN}HOMEPOT Docker Validation${NC}"
echo "=========================="

echo -e "${BLUE}Validating Docker setup...${NC}"

# Check if we're in the right directory
if [[ ! -f "pyproject.toml" ]]; then
    echo -e "${RED}Error: Please run this script from the project root directory${NC}"
    exit 1
fi

# Check if Dockerfile exists
if [ ! -f "Dockerfile" ]; then
    echo -e "${RED}Error: Dockerfile not found${NC}"
    exit 1
fi
echo -e "${GREEN}Dockerfile found${NC}"

# Check if .dockerignore exists
if [ ! -f ".dockerignore" ]; then
    echo -e "${RED}Error: .dockerignore not found${NC}"
    exit 1
fi
echo -e "${GREEN}.dockerignore found${NC}"

# Check if main application file exists
if [ ! -f "src/homepot_client/main.py" ]; then
    echo -e "${RED}Error: main.py not found${NC}"
    exit 1
fi
echo -e "${GREEN}main.py found${NC}"

# Check if docker-compose.yml exists
if [ ! -f "docker-compose.yml" ]; then
    echo -e "${YELLOW}Warning: docker-compose.yml not found${NC}"
else
    echo -e "${GREEN}docker-compose.yml found${NC}"
fi

# Validate Dockerfile syntax (basic check)
echo -e "${BLUE}Checking Docker availability...${NC}"

if [[ "$DRY_RUN" == true ]]; then
    echo -e "${YELLOW}Dry run mode: Performing file validation only${NC}"
elif ! docker --version > /dev/null 2>&1; then
    echo -e "${YELLOW}Warning: Docker not available for build test${NC}"
    DRY_RUN=true
elif ! docker info > /dev/null 2>&1; then
    echo -e "${YELLOW}Warning: Docker daemon not running or not accessible${NC}"
    DRY_RUN=true
else
    echo -e "${GREEN}Docker is available and daemon is running${NC}"
fi

if [[ "$DRY_RUN" == true ]]; then
    echo -e "${BLUE}Performing basic Docker file validation...${NC}"
    
    # Basic Dockerfile syntax check
    if grep -q "^FROM" Dockerfile; then
        echo -e "${GREEN}Dockerfile has valid FROM instruction${NC}"
    else
        echo -e "${RED}Dockerfile missing FROM instruction${NC}"
        exit 1
    fi
    
    if grep -q "EXPOSE.*8000" Dockerfile; then
        echo -e "${GREEN}Dockerfile exposes port 8000${NC}"
    else
        echo -e "${YELLOW}Dockerfile should expose port 8000${NC}"
    fi
    
    if grep -q "CMD\|ENTRYPOINT" Dockerfile; then
        echo -e "${GREEN}Dockerfile has startup command${NC}"
    else
        echo -e "${RED}Dockerfile missing CMD or ENTRYPOINT${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}Docker files validation passed (syntax check only)${NC}"
    exit 0
fi

# Check if port is already in use
if lsof -Pi :$TEST_PORT -sTCP:LISTEN -t >/dev/null ; then
    echo -e "${YELLOW}Warning: Port $TEST_PORT is already in use, trying port $((TEST_PORT + 1))${NC}"
    TEST_PORT=$((TEST_PORT + 1))
fi

echo -e "${BLUE}Building Docker image...${NC}"
if docker build -t "$FULL_IMAGE" .; then
    echo -e "${GREEN}Docker image built successfully${NC}"
else
    echo -e "${RED}Docker image build failed${NC}"
    exit 1
fi

echo -e "${BLUE}Testing container startup...${NC}"
# Start container in background and test health endpoint
echo -e "${YELLOW}Starting container on port $TEST_PORT...${NC}"
CONTAINER_ID=$(docker run -d -p "$TEST_PORT:8000" "$FULL_IMAGE")

if [[ -z "$CONTAINER_ID" ]]; then
    echo -e "${RED}Failed to start container${NC}"
    exit 1
fi

echo -e "${GREEN}Container started: $CONTAINER_ID${NC}"

# Function to cleanup on exit
cleanup() {
    echo -e "${YELLOW}Cleaning up...${NC}"
    docker stop "$CONTAINER_ID" >/dev/null 2>&1 || true
    docker rm "$CONTAINER_ID" >/dev/null 2>&1 || true
    docker rmi "$FULL_IMAGE" >/dev/null 2>&1 || true
    echo -e "${GREEN}Cleanup completed${NC}"
}

# Set trap to cleanup on script exit
trap cleanup EXIT

# Wait for container to start with timeout
echo -e "${YELLOW}Waiting for container to be ready (timeout: ${HEALTH_TIMEOUT}s)...${NC}"
ELAPSED=0
while [ $ELAPSED -lt $HEALTH_TIMEOUT ]; do
    if curl -f "http://localhost:$TEST_PORT/health" >/dev/null 2>&1; then
        echo -e "${GREEN}Container health check passed${NC}"
        STATUS=0
        break
    fi
    sleep 2
    ELAPSED=$((ELAPSED + 2))
    echo -n "."
done

echo ""  # New line after dots

if [ $ELAPSED -ge $HEALTH_TIMEOUT ]; then
    echo -e "${RED}Container health check failed (timeout)${NC}"
    echo -e "${YELLOW}Container logs:${NC}"
    docker logs "$CONTAINER_ID"
    STATUS=1
fi

# Test additional endpoints if health check passed
if [ $STATUS -eq 0 ]; then
    echo -e "${BLUE}Testing additional endpoints...${NC}"
    
    # Test root endpoint
    if curl -f "http://localhost:$TEST_PORT/" >/dev/null 2>&1; then
        echo -e "${GREEN}Root endpoint accessible${NC}"
    else
        echo -e "${YELLOW}Root endpoint not accessible${NC}"
    fi
    
    # Test docs endpoint if it exists
    if curl -f "http://localhost:$TEST_PORT/docs" >/dev/null 2>&1; then
        echo -e "${GREEN}Docs endpoint accessible${NC}"
    else
        echo -e "${YELLOW}Docs endpoint not accessible${NC}"
    fi
fi

echo -e "${GREEN}Docker validation completed${NC}"
exit $STATUS

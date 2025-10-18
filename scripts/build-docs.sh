#!/bin/bash
# Documentation validation and serve script for HOMEPOT client
# Simplified for Markdown-only documentation

# Useful command
# ./scripts/build-docs.sh --help

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
COMMAND="build"
CLEAN=false
SERVE=false
PORT=8000
BUILD_DIR="docs/_build"

# Print usage
usage() {
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  build       Validate and organize documentation (default)"
    echo "  serve       Serve documentation locally"
    echo "  clean       Clean build directory"
    echo "  check       Check documentation for issues"
    echo ""
    echo "Options:"
    echo "  -c, --clean     Clean build directory before building"
    echo "  -p, --port      Port for serving (default: 8000)"
    echo "  -h, --help      Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 build                 # Validate documentation"
    echo "  $0 serve --port 9000     # Serve on port 9000"
    echo "  $0 build --clean         # Clean and rebuild"
    echo "  $0 check                 # Check for issues"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        build|serve|clean|check)
            COMMAND="$1"
            shift
            ;;
        -c|--clean)
            CLEAN=true
            shift
            ;;
        -p|--port)
            PORT="$2"
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

# Check if we're in the right directory
if [[ ! -f "mkdocs.yml" ]] || [[ ! -d "docs" ]]; then
    echo -e "${RED}Error: Please run this script from the project root directory${NC}"
    exit 1
fi

# Check if documentation dependencies are installed
check_deps() {
    echo -e "${BLUE}Checking documentation dependencies...${NC}"
    # Check for basic tools needed for markdown validation
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}Error: Python3 is required but not installed${NC}"
        exit 1
    fi
    echo -e "${GREEN}Documentation dependencies OK${NC}"
}

# Clean build directory
clean_build() {
    if [[ "$CLEAN" == true ]] || [[ "$COMMAND" == "clean" ]]; then
        echo -e "${YELLOW}Cleaning build directory...${NC}"
        rm -rf "$BUILD_DIR"
        echo -e "${GREEN}Build directory cleaned${NC}"
    fi
}

# Build documentation
build_docs() {
    echo -e "${BLUE}Building documentation...${NC}"
    
    # Create build directory
    mkdir -p "$BUILD_DIR"
    
    # Copy markdown files to build directory
    echo -e "${YELLOW}Copying documentation files...${NC}"
    cp docs/*.md "$BUILD_DIR/"
    cp README.md "$BUILD_DIR/"
    cp CONTRIBUTING.md "$BUILD_DIR/"
    
    # Generate a simple index.html for navigation
    echo -e "${YELLOW}Generating navigation page...${NC}"
    cat > "$BUILD_DIR/index.html" << 'EOF'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HOMEPOT Client Documentation</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
        h1 { color: #333; border-bottom: 2px solid #007acc; }
        .doc-link { display: block; padding: 10px; margin: 5px 0; background: #f5f5f5; text-decoration: none; color: #333; border-radius: 5px; }
        .doc-link:hover { background: #e5e5e5; }
        .description { color: #666; font-size: 0.9em; }
    </style>
</head>
<body>
    <h1>HOMEPOT Client Documentation</h1>
    <p>Welcome to the HOMEPOT Client documentation. Choose a document to view:</p>
    
    <a href="index.md" class="doc-link">
        <strong>Project Overview</strong>
        <div class="description">Main project documentation and overview</div>
    </a>
    
    <a href="getting-started.md" class="doc-link">
        <strong>Getting Started Guide</strong>
        <div class="description">Installation, usage, and examples</div>
    </a>
    
    <a href="README.md" class="doc-link">
        <strong>README</strong>
        <div class="description">Repository information and quick start</div>
    </a>
    
    <a href="CONTRIBUTING.md" class="doc-link">
        <strong>Contributing Guidelines</strong>
        <div class="description">How to contribute to the project</div>
    </a>
    
    <p><em>Documentation built on $(date)</em></p>
</body>
</html>
EOF
    
    echo -e "${GREEN}Documentation built successfully${NC}"
    echo -e "${BLUE}Output: $BUILD_DIR/${NC}"
}

# Check documentation
check_docs() {
    echo -e "${BLUE}Checking documentation...${NC}"
    
    # Check if required files exist
    echo -e "${YELLOW}Checking required documentation files...${NC}"
    local required_files=("docs/index.md" "docs/getting-started.md" "README.md" "CONTRIBUTING.md")
    local missing_files=()
    
    for file in "${required_files[@]}"; do
        if [[ ! -f "$file" ]]; then
            missing_files+=("$file")
        fi
    done
    
    if [[ ${#missing_files[@]} -gt 0 ]]; then
        echo -e "${RED}Missing required files:${NC}"
        printf '%s\n' "${missing_files[@]}"
        exit 1
    fi
    
    # Check markdown syntax (basic check)
    echo -e "${YELLOW}Checking markdown syntax...${NC}"
    for file in docs/*.md; do
        if [[ -f "$file" ]]; then
            # Basic syntax check - look for common issues
            if grep -q "^#" "$file"; then
                echo -e "${GREEN}✓ $file${NC}"
            else
                echo -e "${YELLOW}⚠ $file (no headers found)${NC}"
            fi
        fi
    done
    
    echo -e "${GREEN}Documentation check completed${NC}"
}

# Serve documentation
serve_docs() {
    echo -e "${BLUE}Starting documentation server on port ${PORT}...${NC}"
    echo -e "${GREEN}Open http://localhost:${PORT} in your browser${NC}"
    echo -e "${YELLOW}Press Ctrl+C to stop the server${NC}"
    
    cd "$BUILD_DIR"
    python3 -m http.server "$PORT"
}

# Main execution
main() {
    echo -e "${GREEN}HOMEPOT Documentation Builder${NC}"
    echo "=================================="
    
    check_deps
    clean_build
    
    case $COMMAND in
        build)
            build_docs
            ;;
        serve)
            build_docs
            serve_docs
            ;;
        clean)
            echo -e "${GREEN}Clean completed${NC}"
            ;;
        check)
            check_docs
            ;;
        *)
            echo -e "${RED}Unknown command: $COMMAND${NC}"
            usage
            exit 1
            ;;
    esac
}

# Run main function
main

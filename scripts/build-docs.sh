#!/bin/bash
# Documentation build and serve script for HOMEPOT client

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

# Print usage
usage() {
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  build       Build documentation (default)"
    echo "  serve       Build and serve documentation"
    echo "  clean       Clean build directory"
    echo "  check       Check documentation for issues"
    echo ""
    echo "Options:"
    echo "  -c, --clean     Clean build directory before building"
    echo "  -p, --port      Port for serving (default: 8000)"
    echo "  -h, --help      Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 build                 # Build documentation"
    echo "  $0 serve --port 9000     # Serve on port 9000"
    echo "  $0 build --clean         # Clean build and rebuild"
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
if [[ ! -f "pyproject.toml" ]] || [[ ! -d "docs" ]]; then
    echo -e "${RED}Error: Please run this script from the project root directory${NC}"
    exit 1
fi

# Check if documentation dependencies are installed
check_deps() {
    echo -e "${BLUE}Checking documentation dependencies...${NC}"
    python -c "import sphinx, sphinx_rtd_theme, myst_parser" 2>/dev/null || {
        echo -e "${YELLOW}Installing documentation dependencies...${NC}"
        pip install -e ".[docs]"
    }
    echo -e "${GREEN}Documentation dependencies OK${NC}"
}

# Clean build directory
clean_build() {
    if [[ "$CLEAN" == true ]] || [[ "$COMMAND" == "clean" ]]; then
        echo -e "${YELLOW}Cleaning build directory...${NC}"
        cd docs
        make clean-build
        cd ..
        echo -e "${GREEN}Build directory cleaned${NC}"
    fi
}

# Build documentation
build_docs() {
    echo -e "${BLUE}Building documentation...${NC}"
    cd docs
    
    # Build HTML documentation
    if make html; then
        echo -e "${GREEN}Documentation built successfully${NC}"
        echo -e "${BLUE}Output: docs/_build/html/index.html${NC}"
    else
        echo -e "${RED}Documentation build failed${NC}"
        exit 1
    fi
    
    cd ..
}

# Check documentation
check_docs() {
    echo -e "${BLUE}Checking documentation...${NC}"
    cd docs
    
    # Check for broken links
    echo -e "${YELLOW}Checking for broken links...${NC}"
    if sphinx-build -b linkcheck . _build/linkcheck; then
        echo -e "${GREEN}Link check passed${NC}"
    else
        echo -e "${RED}Link check failed${NC}"
    fi
    
    # Check for proper build
    echo -e "${YELLOW}Checking build integrity...${NC}"
    if sphinx-build -b html -W . _build/html; then
        echo -e "${GREEN}Build check passed${NC}"
    else
        echo -e "${RED}Build check failed${NC}"
        exit 1
    fi
    
    cd ..
}

# Serve documentation
serve_docs() {
    echo -e "${BLUE}Starting documentation server on port ${PORT}...${NC}"
    echo -e "${GREEN}Open http://localhost:${PORT} in your browser${NC}"
    echo -e "${YELLOW}Press Ctrl+C to stop the server${NC}"
    
    cd docs/_build/html
    python -m http.server "$PORT"
}

# Live reload server
live_serve() {
    echo -e "${BLUE}Starting live documentation server...${NC}"
    echo -e "${GREEN}Documentation will auto-rebuild on changes${NC}"
    echo -e "${YELLOW}Press Ctrl+C to stop the server${NC}"
    
    cd docs
    sphinx-autobuild -b html . _build/html --port "$PORT" --open-browser
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
            if command -v sphinx-autobuild &> /dev/null; then
                live_serve
            else
                serve_docs
            fi
            ;;
        clean)
            echo -e "${GREEN}Clean completed${NC}"
            ;;
        check)
            build_docs
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

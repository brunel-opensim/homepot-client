# Getting Started with HOMEPOT Client

This guide provides complete instructions for installing, running, testing, and developing with the HOMEPOT Client.

## Prerequisites

- **Python**: 3.9 or higher
- **pip**: Latest version
- **Git**: Latest version  
- **HOMEPOT Consortium Access**: Repository access required

## Installation

### Method 1: Automated Installation (Recommended)

```bash
# Clone the repository (consortium members only)
git clone https://github.com/brunel-opensim/homepot-client.git
cd homepot-client

# Install with development dependencies
./scripts/install.sh --dev

# Or basic installation only
./scripts/install.sh
```

### Method 2: Manual Installation

```bash
# Clone repository
git clone https://github.com/brunel-opensim/homepot-client.git
cd homepot-client

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install package with dependencies
pip install -e .
```

### Activate Environment

```bash
# Using activation script (recommended)
./scripts/activate-homepot.sh

# Or manually
source venv/bin/activate
```

## Running the HOMEPOT Client

### CLI Commands

```bash
# Check version information
homepot-client version

# Get detailed client information  
homepot-client info

# Get help
homepot-client --help
```

### API Server

> **Architecture**: The FastAPI web server hosts a HOMEPOT client instance inside it. The REST API endpoints let you control the client's connection to external HOMEPOT services. The server itself keeps running - only the internal client connects/disconnects.

The API will be available at `http://localhost:8000` with these endpoints:

- **Root**: `GET /` - Basic API information
- **Health Check**: `GET /health` - Service health status  
- **API Documentation**: `GET /docs` - Interactive OpenAPI docs
- **Client Status**: `GET /status` - Client connection state and information
- **Version**: `GET /version` - Version information
- **Connect**: `POST /connect` - Connect client to external HOMEPOT services
- **Disconnect**: `POST /disconnect` - Disconnect client from external services (API server keeps running)

### Testing API Endpoints

> **Important**: Keep the API server running in your first terminal. Open a **second terminal** for testing commands.

**Step 1**: In your first terminal, make sure the API server is running:
```bash
python -m homepot_client.main
# You should see: "Application startup complete"
# You should also see: "HOMEPOT Client connected successfully"
# Leave this terminal running - don't close it!
```

> **Note**: The HOMEPOT client automatically connects to services when the server starts. The `/connect` and `/disconnect` endpoints allow you to manually control this connection.

**Step 2**: Open a new terminal window/tab and navigate to the project directory:
```bash
cd /path/to/homepot-client
```

**Step 3**: Test the API endpoints in your second terminal:

```bash
# Get API information (GET)
curl http://localhost:8000/; echo

# Check status (GET)
curl http://localhost:8000/status; echo

# Test health endpoint (GET)
curl http://localhost:8000/health; echo

# Check version (GET)
curl http://localhost:8000/version; echo

# Test connect endpoint (POST - note the -X POST!)
curl -X POST http://localhost:8000/connect; echo

# Test disconnect endpoint (POST - note the -X POST!)
curl -X POST http://localhost:8000/disconnect; echo

# View interactive docs
open http://localhost:8000/docs  # or visit in browser
```

> **Important**: The `/connect` and `/disconnect` endpoints require **POST** requests (note the `-X POST` flag). If you forget `-X POST`, you'll get `{"detail":"Method Not Allowed"}` error.

**What to expect**: Each curl command should return JSON responses like:
- `/`: `{"message":"HOMEPOT Client API","version":"0.1.0","docs":"/docs","status":"operational"}`
- `/status`: `{"connected":true,"version":"0.1.0","uptime":90259.373,"client_type":"HOMEPOT Client"}` ← Shows client connection state
- `/health`: `{"status":"healthy","client_connected":true,"version":"0.1.0","timestamp":90108.231}` ← "healthy" when connected, "degraded" when disconnected
- `/version`: `{"version":"0.1.0"}`
- `/connect`: `{"message":"Client already connected","status":"connected"}` (typical - client auto-connects on startup)
- `/disconnect`: `{"message":"Client disconnected successfully","status":"disconnected"}` ← Disconnects client from external services, API server keeps running
- `/docs`: More information accessible using browser.

**After disconnect**, `/status` will show `"connected":false` and `/health` will show `"status":"degraded"`, but all endpoints remain accessible.

**Troubleshooting**: If curl commands fail:

- **"Connection refused"**: Make sure the API server is still running in your first terminal and you see "Application startup complete" message
- **"Method Not Allowed"**: You forgot `-X POST` for `/connect` or `/disconnect` endpoints. GET method is not allowed for these endpoints.
- **Port issues**: Verify the server is listening on port 8000

## Testing and Development

### Running Tests

```bash
# Run all tests with coverage
pytest

# Run specific test types
pytest -m integration   # Integration tests only (1 test)
pytest -m slow          # Performance tests only (1 test) 
pytest -m "not slow"    # All tests except slow ones (16 tests)

# Run with verbose output
pytest -v

# Run with coverage report
pytest --cov=homepot_client --cov-report=html
```

> **Note**: If pytest exits with "Required test coverage of 80% not reached", this is expected during development. Run `pytest -m "not slow"` for faster testing that typically achieves >95% coverage.

### Development Workflow

```bash
# Validate code quality
./scripts/validate-workflows.sh

# Run security checks
bandit -r src/

> **Note**: `bandit -r src/` will report 1 Medium severity issue: "hardcoded_bind_all_interfaces" in main.py line 191. This is expected for development as it allows the API server to be accessible from other machines. Exit code 1 is normal when issues are found.

# Format code
black src/ tests/
isort src/ tests/      # No output = success (imports already sorted)

# Type checking
mypy src/              # No output = success (no type errors found)

# Lint code
flake8 src/ tests/     # No output = success (no style violations found)
```

> **Note**: Most code quality tools follow Unix convention: **no output means success**. Only `black` provides verbose success messages. If a command returns to prompt silently, it means no issues were found.

### Development Scripts

| Script | Description |
|--------|-------------|
| `./scripts/install.sh` | Automated installation and setup |
| `./scripts/activate-homepot.sh` | Activate development environment |
| `./scripts/validate-workflows.sh` | Run all validation checks |
| `./scripts/build-docs.sh` | Build documentation |
| `./scripts/test-docker.sh` | Docker validation and testing |

## Basic Usage (Python API)

### Import and Create Client

```python
from homepot_client import create_client

# Create a client instance
client = create_client()

# Check if client is working
print(f"Client version: {client.get_version()}")
print(f"Connected: {client.is_connected()}")
```

## Docker Deployment (Optional)

Docker is available for production deployment but not required for development.

### Quick Start with Docker

```bash
# Production deployment
docker-compose up -d --build

# View application logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Environment Variables

Configure Docker deployment with these environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `HOMEPOT_ENV` | `production` | Environment mode (`production` or `development`) |
| `HOMEPOT_PORT` | `8000` | Host port to bind to |
| `HOMEPOT_DEBUG` | `false` | Enable debug mode |
| `HOMEPOT_DATA_DIR` | `./data` | Data directory mount |
| `HOMEPOT_LOGS_DIR` | `./logs` | Logs directory mount |
| `HOMEPOT_SOURCE_MOUNT` | `/dev/null` | Source code mount (development only) |

### Docker Testing and Validation

```bash
# Validate Docker setup (dry run)
./scripts/test-docker.sh --dry-run

# Full Docker validation (requires Docker)
./scripts/test-docker.sh

# Test with custom port
./scripts/test-docker.sh --port 9000
```

### Production Deployment

```bash
# Using Docker Compose (recommended)
HOMEPOT_ENV=production HOMEPOT_PORT=8000 docker-compose up -d

# Using direct Docker run
docker build -t homepot-client:latest .
docker run -d \
  --name homepot-client \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  -e HOMEPOT_ENV=production \
  homepot-client:latest
```

### Development Mode with Docker

```bash
# Development with source code hot reload
HOMEPOT_ENV=development HOMEPOT_SOURCE_MOUNT=./src docker-compose up --build

# Run tests inside container
docker-compose exec homepot-client pytest

# Access container shell
docker-compose exec homepot-client bash
```

> **Note**: Docker is designed for production deployment. For daily development, use the direct Python installation method above.

## Development Status

This is an **early development version** of the HOMEPOT client with a solid foundation for device management.

### Currently Working

**Core Infrastructure:**
- FastAPI web service with REST API
- CLI commands (`version`, `info`, `--help`)
- Async client architecture (placeholder implementation)
- Comprehensive testing suite (>98% coverage)
- Docker containerization
- Professional development tooling

**API Endpoints:**
- Health monitoring (`/health`)
- Status reporting (`/status`)  
- Version information (`/version`)
- Connect/disconnect simulation (`/connect`, `/disconnect`)
- Interactive documentation (`/docs`)

**Development Tools:**
- Automated installation scripts
- Code quality enforcement (Black, isort, flake8, mypy)
- Security scanning (Bandit)
- GitHub Actions CI/CD
- Docker validation

### In Development

**HOMEPOT Protocol:**
- Full device management implementation
- Real device connection protocols
- Consortium-specific authentication
- Production security features

**Extended Features:**
- Device discovery and management
- Multi-protocol support (retail, hospitality, industrial)
- Advanced monitoring and analytics
- Consortium partner integrations

### Next Steps

As development progresses, documentation will expand with:

- Complete device management examples
- Real-world usage patterns for retail/hospitality/industrial
- Production deployment guides
- Consortium-specific configuration

## Support and Next Steps

### For HOMEPOT Consortium Members

- **GitHub Issues**: [Report bugs and feature requests](https://github.com/brunel-opensim/homepot-client/issues)
- **Contributing**: See [CONTRIBUTING.md](../CONTRIBUTING.md) for development guidelines
- **Security**: Follow [Security Policy](../SECURITY.md) for vulnerability reporting

### Common Next Steps

1. **Explore the API**: Visit `http://localhost:8000/docs` after running the server
2. **Run Tests**: Execute `pytest` to verify your installation
3. **Check CLI**: Try `homepot-client info` to see project details
4. **Review Code**: Explore `src/homepot_client/` for implementation details
5. **Contribute**: Follow contributing guidelines to add features

### Troubleshooting

**Common Error: "Address already in use"**

If you see this error when starting the server:
```
OSError: [Errno 98] Address already in use
```

**Quick Fix:**
```bash
# Kill the process using port 8000
sudo kill $(lsof -ti :8000)

# Then restart the server
python -m homepot_client.main
```

**Step-by-Step Approach (Safer for Beginners):**
```bash
# 1. Check what's using the port
lsof -i :8000
# Look for: python 297355 homepot-user 13u IPv4 ... *:8000 (LISTEN)

# 2. Get just the process ID
lsof -ti :8000
# Returns: 297355

# 3. Kill that specific process (replace 297355 with your PID)
sudo kill 297355

# 4. Verify port is free (should return nothing)
lsof -i :8000

# 5. Restart the server
python -m homepot_client.main
```

**Installation Issues:**
```bash
# Ensure Python version
python --version  # Should be 3.9+

# Clean installation
rm -rf venv/
./scripts/install.sh --dev
```

**API Server Issues:**

```bash
# Check what's using port 8000
lsof -i :8000

# If port is busy, find and kill the process
lsof -ti :8000                    # Get PID only
sudo kill $(lsof -ti :8000)      # Kill the process using port 8000

# Alternative: Kill by process name
pkill -f "python.*homepot"       # Kill any Python process containing "homepot"

# If process won't die, force kill
sudo kill -9 $(lsof -ti :8000)   # Force kill with SIGKILL

# Check if port is now free (should return nothing)
lsof -i :8000

# Run with debug mode
HOMEPOT_DEBUG=true python -m homepot_client.main

# Use different port if 8000 is permanently busy
python -m homepot_client.main --port 8001  # Note: This may require code changes
```

> **Common Port Issues**: If you see "Address already in use" error, a previous server instance didn't shut down properly. Use `sudo kill $(lsof -ti :8000)` to free the port.

**Docker Issues:**
```bash
# Validate setup without building
./scripts/test-docker.sh --dry-run

# Check Docker status
docker --version
docker info
```

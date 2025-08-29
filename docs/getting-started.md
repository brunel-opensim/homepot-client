# Getting Started with HOMEPOT Client

This guide will help you get started with the HOMEPOT client library.

## Installation

### From Source (Current Method)

```bash
# Clone the repository
git clone https://github.com/brunel-opensim/homepot-client.git
cd homepot-client

# Install the package
pip install -e .
```

## Prerequisites

- Python 3.9 or higher
- pip package manager
- Git

## Available Commands

The HOMEPOT client currently provides these working commands:

### CLI Commands

```bash
# Check version information
homepot-client version

# Get detailed client information
homepot-client info

# Get help
homepot-client --help
```

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

## Running Tests

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=homepot_client

# Run validation checks
./scripts/validate-workflows.sh
```

## Docker Usage

```bash
# Build and run with Docker
docker compose up --build

# Test health endpoint
curl http://localhost:8000/health
```

## Development Status

This is an **early development version** of the HOMEPOT client. Currently implemented:

**Working Features:**

- Basic client creation and management
- CLI commands (`version`, `info`)
- Async connect/disconnect (placeholder)
- Version information
- Docker containerization

**In Development:**

- Full HOMEPOT protocol implementation
- Device management capabilities
- Consortium-specific features
- Production deployment configurations

## Next Steps

As the HOMEPOT client develops, this documentation will be updated with:

- Complete API reference
- Real device management examples
- Consortium-specific usage patterns
- Production deployment guides

## Support

For HOMEPOT consortium members:

- GitHub Issues: [Report bugs and requests](https://github.com/brunel-opensim/homepot-client/issues)
- Contributing: See [CONTRIBUTING.md](../CONTRIBUTING.md) for development guidelines

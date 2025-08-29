# Getting Started

This guide will help you get started with the HOMEPOT client library.

## Installation

### From PyPI (Recommended)

```bash
pip install homepot-client
```

### From Source

```bash
# Clone the repository (URL will be updated when repository is created)
# git clone https://github.com/brunel-opensim/homepot-client.git
# cd homepot-client
pip install -e .
```

## Prerequisites

- Python 3.9 or higher
- A HOMEPOT account (for consortium members)

## Basic Configuration

### Environment Variables

Create a `.env` file in your project root:

```bash
# Copy the example file
cp .env.example .env
```

Edit the `.env` file with your configuration:

```env
# HOMEPOT API Configuration
HOMEPOT_API_URL=https://api.homepot.example.com
HOMEPOT_API_KEY=your_api_key_here

# Client Configuration
HOMEPOT_CLIENT_TIMEOUT=30
HOMEPOT_CLIENT_RETRIES=3

# Logging Configuration
HOMEPOT_LOG_LEVEL=INFO
HOMEPOT_LOG_FORMAT=json
```

### Configuration File

Alternatively, you can use a configuration file:

```python
from homepot_client import HomepotClient, ClientConfig

config = ClientConfig(
    api_url="https://api.homepot.example.com",
    api_key="your_api_key_here",
    timeout=30,
    retries=3
)

client = HomepotClient(config=config)
```

## First Steps

### 1. Initialize the Client

```python
import asyncio
from homepot_client import HomepotClient

async def main():
    # Create client with default configuration
    client = HomepotClient()
    
    try:
        # Connect to the HOMEPOT service
        await client.connect()
        
        # Check connection status
        if client.is_connected:
            print("Successfully connected to HOMEPOT!")
        
    finally:
        # Always clean up
        await client.disconnect()

# Run the example
asyncio.run(main())
```

### 2. Using the CLI

The HOMEPOT client comes with a command-line interface:

```bash
# Check version
homepot-client version

# Get client information
homepot-client info

# Connect to service (future feature)
homepot-client connect --url https://api.homepot.example.com
```

### 3. Error Handling

```python
from homepot_client import HomepotClient, HomepotError

async def robust_example():
    client = HomepotClient()
    
    try:
        await client.connect()
        # Your application logic here
        
    except HomepotError as e:
        print(f"HOMEPOT error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")
    finally:
        await client.disconnect()
```

## Next Steps

- Read the [API Reference](api-reference.md) for detailed documentation
- Check out [Examples](examples.md) for common use cases
- See [CLI Reference](cli-reference.md) for command-line usage
- Learn about [Contributing](contributing.md) to the project

## Support

For support and questions:

- Email: [support@homepot-consortium.org](mailto:support@homepot-consortium.org)
- Discord: [HOMEPOT Community](https://discord.gg/homepot)
<!-- Links will be activated when repository is created
- Issues: [GitHub Issues](https://github.com/brunel-opensim/homepot-client/issues)
- Documentation: [GitHub Docs](https://github.com/brunel-opensim/homepot-client/tree/main/docs)
-->

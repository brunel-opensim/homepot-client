# API Reference

This section provides detailed documentation for the HOMEPOT client library API.

## Core Classes

```{eval-rst}
.. automodule:: homepot_client
   :members:
   :undoc-members:
   :show-inheritance:
```

## Client Module

```{eval-rst}
.. automodule:: homepot_client.client
   :members:
   :undoc-members:
   :show-inheritance:
```

### HomepotClient

The main client class for interacting with HOMEPOT services.

```{eval-rst}
.. autoclass:: homepot_client.client.HomepotClient
   :members:
   :undoc-members:
   :show-inheritance:
```

#### Methods

##### connect()

```{eval-rst}
.. automethod:: homepot_client.client.HomepotClient.connect
```

##### disconnect()

```{eval-rst}
.. automethod:: homepot_client.client.HomepotClient.disconnect
```

##### is_connected

```{eval-rst}
.. autoattribute:: homepot_client.client.HomepotClient.is_connected
```

## CLI Module

```{eval-rst}
.. automodule:: homepot_client.cli
   :members:
   :undoc-members:
   :show-inheritance:
```

## Exceptions

### HomepotError

Base exception class for all HOMEPOT-related errors.

```python
class HomepotError(Exception):
    """Base exception for HOMEPOT client errors."""
    pass
```

### ConnectionError

Raised when connection to HOMEPOT service fails.

```python
class ConnectionError(HomepotError):
    """Raised when connection fails."""
    pass
```

### AuthenticationError

Raised when authentication fails.

```python
class AuthenticationError(HomepotError):
    """Raised when authentication fails."""
    pass
```

## Type Definitions

### ClientConfig

Configuration object for the HOMEPOT client.

```python
from typing import Optional
from dataclasses import dataclass

@dataclass
class ClientConfig:
    """Configuration for HOMEPOT client."""
    
    api_url: str = "https://api.homepot.example.com"
    api_key: Optional[str] = None
    timeout: int = 30
    retries: int = 3
    verify_ssl: bool = True
```

## Constants

### Default Values

```python
# Default API endpoint
DEFAULT_API_URL = "https://api.homepot.example.com"

# Default timeout in seconds
DEFAULT_TIMEOUT = 30

# Default number of retries
DEFAULT_RETRIES = 3

# Default log level
DEFAULT_LOG_LEVEL = "INFO"
```

### Version Information

```python
# Current version
__version__ = "0.1.0"

# API version
API_VERSION = "v1"

# User agent
USER_AGENT = f"homepot-client/{__version__}"
```

## Usage Examples

### Basic Usage

```python
from homepot_client import HomepotClient

async def example():
    client = HomepotClient()
    await client.connect()
    # Use client here
    await client.disconnect()
```

### With Configuration

```python
from homepot_client import HomepotClient, ClientConfig

config = ClientConfig(
    api_url="https://custom.api.url",
    api_key="your-key-here",
    timeout=60
)

client = HomepotClient(config=config)
```

### Context Manager (Future)

```python
async with HomepotClient() as client:
    # Client is automatically connected and disconnected
    pass
```

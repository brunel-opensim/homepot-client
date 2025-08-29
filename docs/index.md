# HOMEPOT Client Documentation

Welcome to the HOMEPOT Client documentation! This library provides a Python client for interacting with HOMEPOT devices and services.

```{toctree}
:maxdepth: 2
:caption: Contents:

getting-started
```

## Quick Start

Install the HOMEPOT client:

```bash
pip install homepot-client
```

Basic usage:

```python
from homepot_client import HomepotClient

# Create a client instance
client = HomepotClient()

# Connect to HOMEPOT service
await client.connect()

# Your code here...

# Clean up
await client.disconnect()
```

## About HOMEPOT

HOMEPOT is a consortium project focused on developing innovative solutions for home automation and IoT device management. This client library is part of the official HOMEPOT ecosystem.

## Indices and tables

* {ref}`genindex`
* {ref}`modindex`
* {ref}`search`

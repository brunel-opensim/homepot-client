# CLI Reference

The HOMEPOT client provides a command-line interface for common operations.

## Installation

The CLI is automatically installed when you install the package:

```bash
pip install homepot-client
```

## Global Options

All commands support these global options:

- `--help`: Show help message and exit
- `--version`: Show version information
- `--verbose, -v`: Enable verbose output
- `--quiet, -q`: Suppress output except errors
- `--config`: Specify custom configuration file

## Commands

### version

Display version information.

```bash
homepot-client version
```

**Output:**
```
HOMEPOT Client v0.1.0
Python: 3.9.0
Platform: Linux-5.15.0-x86_64
```

**Options:**
- `--json`: Output in JSON format

### info

Display client and system information.

```bash
homepot-client info
```

**Output:**
```
HOMEPOT Client Information
=========================

Version: 0.1.0
Author: HOMEPOT Consortium
License: MIT
Repository: https://github.com/brunel-opensim/homepot-client

System Information:
- Python: 3.9.0
- Platform: Linux-5.15.0-x86_64
- Architecture: x86_64

Configuration:
- Config file: ~/.homepot/config.yaml
- Log level: INFO
- API URL: https://api.homepot.example.com
```

**Options:**
- `--json`: Output in JSON format
- `--system`: Show only system information
- `--config`: Show only configuration information

### connect (Future)

Connect to HOMEPOT service and test connectivity.

```bash
homepot-client connect [OPTIONS]
```

**Options:**
- `--url TEXT`: API endpoint URL
- `--api-key TEXT`: API key for authentication
- `--timeout INTEGER`: Connection timeout in seconds
- `--test`: Test connection without persisting

**Examples:**

```bash
# Connect with default settings
homepot-client connect

# Connect to custom endpoint
homepot-client connect --url https://custom.api.url

# Test connection without saving
homepot-client connect --test --url https://test.api.url
```

### devices (Future)

Manage HOMEPOT devices.

```bash
homepot-client devices [COMMAND] [OPTIONS]
```

**Subcommands:**

#### list
List all available devices.

```bash
homepot-client devices list
```

**Options:**
- `--type TEXT`: Filter by device type
- `--status TEXT`: Filter by device status
- `--json`: Output in JSON format

#### info
Get information about a specific device.

```bash
homepot-client devices info DEVICE_ID
```

**Options:**
- `--json`: Output in JSON format

#### control
Control a device.

```bash
homepot-client devices control DEVICE_ID [OPTIONS]
```

**Options:**
- `--action TEXT`: Action to perform
- `--parameters TEXT`: Action parameters (JSON format)

### config

Manage client configuration.

```bash
homepot-client config [COMMAND] [OPTIONS]
```

**Subcommands:**

#### show
Display current configuration.

```bash
homepot-client config show
```

#### set
Set a configuration value.

```bash
homepot-client config set KEY VALUE
```

#### get
Get a configuration value.

```bash
homepot-client config get KEY
```

#### reset
Reset configuration to defaults.

```bash
homepot-client config reset
```

**Examples:**

```bash
# Show all configuration
homepot-client config show

# Set API URL
homepot-client config set api_url https://api.homepot.example.com

# Get current API URL
homepot-client config get api_url

# Reset to defaults
homepot-client config reset
```

## Configuration File

The CLI looks for configuration in the following locations (in order):

1. `./homepot.yaml` (current directory)
2. `~/.homepot/config.yaml` (user home)
3. `/etc/homepot/config.yaml` (system-wide)

**Example configuration file:**

```yaml
# HOMEPOT Client Configuration
api:
  url: "https://api.homepot.example.com"
  key: "your-api-key-here"
  timeout: 30
  retries: 3
  verify_ssl: true

logging:
  level: "INFO"
  format: "json"
  file: "~/.homepot/logs/client.log"

client:
  user_agent: "homepot-client/0.1.0"
  cache_dir: "~/.homepot/cache"
  max_connections: 10
```

## Environment Variables

Configuration can also be set via environment variables:

```bash
# API Configuration
export HOMEPOT_API_URL="https://api.homepot.example.com"
export HOMEPOT_API_KEY="your-api-key-here"
export HOMEPOT_API_TIMEOUT="30"

# Logging Configuration
export HOMEPOT_LOG_LEVEL="INFO"
export HOMEPOT_LOG_FORMAT="json"

# Client Configuration
export HOMEPOT_CACHE_DIR="~/.homepot/cache"
```

## Exit Codes

The CLI uses standard exit codes:

- `0`: Success
- `1`: General error
- `2`: Invalid command or arguments
- `3`: Configuration error
- `4`: Connection error
- `5`: Authentication error
- `6`: Permission error

## Examples

### Basic Workflow

```bash
# Check version
homepot-client version

# Show system information
homepot-client info

# Set up configuration
homepot-client config set api_url https://your.api.url
homepot-client config set api_key your-key-here

# Test connection
homepot-client connect --test

# List devices
homepot-client devices list

# Get device information
homepot-client devices info device-123

# Control a device
homepot-client devices control device-123 --action turn_on
```

### JSON Output

Most commands support JSON output for scripting:

```bash
# Get version in JSON
homepot-client version --json

# Get device list in JSON
homepot-client devices list --json

# Parse with jq
homepot-client devices list --json | jq '.devices[].name'
```

### Scripting

The CLI is designed to be script-friendly:

```bash
#!/bin/bash

# Check if client is working
if homepot-client info --quiet; then
    echo "HOMEPOT client is working"
else
    echo "HOMEPOT client has issues" >&2
    exit 1
fi

# Get device count
device_count=$(homepot-client devices list --json | jq '.devices | length')
echo "Found $device_count devices"
```

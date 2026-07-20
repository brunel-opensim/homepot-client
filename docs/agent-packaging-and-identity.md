# Agent Packaging and Identity — PR 12

## Purpose

PR 12 delivers the foundational scaffolding for deploying the HOMEPOT Agent
as a production Linux daemon. It covers three concerns:

1. **Packaging** — systemd service unit, install script, FHS-compliant data
   directories, and Python entry point.
2. **Identity** — a persistent, stable device identifier that survives restarts,
   re-enrolment, and OS reinstallation (as long as the data partition is
   retained).
3. **Credential storage** — a Python implementation of the `CredentialStorage`
   interface that mirrors the TypeScript abstraction in the User App, so that
   agent code can read/write credentials using the same contract on the backend
   side.

## Files created or modified

| File | Purpose |
|------|---------|
| `backend/src/homepot/agent/credential_storage.py` | Python credential-storage abstraction (SimulationStorage + LinuxFileStorage + factory) |
| `backend/src/homepot/agent/identity.py` | Persistent device-identity generation and management |
| `backend/src/homepot/agent/cli.py` | `homepot-agent` CLI with `run`, `identity`, `reset-identity`, `status`, `show-config`, `credentials`, `clear-credentials` commands |
| `backend/src/homepot/agent/__init__.py` | Updated to export the new public API |
| `backend/src/homepot/agent/real_device_agent.py` | Updated to load identity from `identity.py` and credentials from `credential_storage.py` |
| `backend/pyproject.toml` | Added `agent` optional-dependency group and `homepot-agent` console script |
| `scripts/homepot-agent.service` | systemd unit file with security hardening |
| `scripts/install-agent.sh` | Install/uninstall script for the agent systemd service |
| `tests/test_agent_credential_storage.py` | 31 tests for credential storage |
| `tests/test_agent_identity.py` | 25 tests for device identity |
| `docs/agent-packaging-and-identity.md` | This document |

## Architecture

```
homepot-agent CLI (cli.py)
│
├── identity.py        ─── persistent device ID
│   ├── /var/lib/homepot/identity   (preferred, daemon)
│   └── ~/.local/share/homepot/identity  (fallback, dev)
│
├── credential_storage.py ─── OS-protected credential file
│   └── ~/.homepot/credentials  (0600 permissions)
│
└── real_device_agent.py ─── runtime loops
    ├── registration (device-dna)
    ├── heartbeat
    ├── telemetry
    └── retry queue
```

## Device identity

### Resolution order

`get_or_create_device_id()` follows this resolution:

1. **Read existing identity file** at `/var/lib/homepot/identity` (or
   `$XDG_DATA_HOME/homepot/identity` for unprivileged runs).
2. **Generate a new UUID** (`device-<32 hex chars>`) and persist it to the
   identity file.
3. **Fallback to `/etc/machine-id`** if the identity directory is not writable.
   The machine ID is salted with a domain-specific string and SHA-256-hashed to
   produce a deterministic but non-reversible device identity.

### Identity file format

A single line of text containing the device ID string:

```
device-a1b2c3d4e5f6789012345678abcdef01
```

The file is created with mode `0o644`.

### Resetting identity

```bash
homepot-agent reset-identity
```

This removes the identity file. A new one is generated on the next
`homepot-agent run` or `homepot-agent identity` invocation. It does **not**
affect `/etc/machine-id`.

## Credential storage

### Interface

`CredentialStorage` is an abstract base class with the same methods as the
TypeScript `CredentialStorage` from `user_app/src/services/credentialStorage.ts`:

| Method | Description |
|--------|-------------|
| `save(creds)` | Persist credentials after a successful provision or claim |
| `get_api_key()` | Retrieve the stored API key |
| `get_device_id()` | Retrieve the stored device ID |
| `get_metadata(key)` | Retrieve a metadata field by key |
| `clear()` | Remove all stored credentials (unpair / factory-reset) |
| `is_provisioned()` | `True` if credentials are present |

### Implementations

| Class | Platform | Storage |
|-------|----------|---------|
| `SimulationStorage` | Any (testing/dev) | In-memory dict |
| `LinuxFileStorage` | Linux | `~/.homepot/credentials` with `0o600` permissions |

### Factory

```python
from homepot.agent.credential_storage import create_credential_storage

storage = create_credential_storage()
# Returns LinuxFileStorage on Linux, SimulationStorage elsewhere
```

## Systemd service

### Unit file

`scripts/homepot-agent.service` provides a hardened systemd unit:

- Runs as the `homepot` system user (no login shell).
- Uses `ProtectSystem=full`, `PrivateTmp=true`, `NoNewPrivileges=true`,
  `MemoryDenyWriteExecute=true`, and other security hardening directives.
- Stores runtime state in `/run/homepot-agent`.
- Stores persistent state in `/var/lib/homepot` (identity, credentials).
- Restarts on failure with a 10-second delay (up to 5 times per 60 seconds).

### Installation

```bash
# From the repository root
sudo ./scripts/install-agent.sh

# Verify
systemctl status homepot-agent

# View logs
journalctl -u homepot-agent -f
```

### Uninstallation

```bash
sudo ./scripts/install-agent.sh --uninstall
```

## CLI reference

```text
Usage: homepot-agent [OPTIONS] COMMAND [ARGS]...

  HOMEPOT Device Agent - managed endpoint runtime

Options:
  --verbose, -v     Enable verbose logging
  --config, -c PATH  Path to agent configuration JSON
  --help            Show this message and exit

Commands:
  run                Run the agent runtime (main daemon entry point)
  identity           Show the current device identity
  reset-identity     Remove the stored device identity
  status             Show the current agent status
  show-config        Show the effective agent configuration
  credentials        Show credential storage status
  clear-credentials  Remove all stored credentials (local unpair)
```

### Typical workflow

```bash
# Generate identity and show it
homepot-agent identity

# Check status
homepot-agent status

# Run the agent (foreground)
homepot-agent run

# Run with a custom config file
homepot-agent -c /etc/homepot/agent.json run
```

## Packaging

### Python entry points

The `pyproject.toml` registers two console scripts:

```toml
[project.scripts]
homepot-client = "homepot.cli:main"
homepot-agent = "homepot.agent.cli:main"
```

### Optional dependencies

The `agent` extra installs agent-specific runtime dependencies:

```bash
pip install homepot-client[agent]
```

These are intentionally kept minimal: `httpx`, `psutil`, `platformdirs`.

### FHS layout (installed system)

| Path | Contents |
|------|----------|
| `/usr/bin/homepot-agent` | Console script entry point |
| `/etc/systemd/system/homepot-agent.service` | systemd unit |
| `/var/lib/homepot/identity` | Persistent device identity |
| `~/.homepot/credentials` | Device API credentials (`0o600`) |

## Backward compatibility

- The existing `agent-config.json` file continues to work. Values in the JSON
  file take precedence over generated identity and credential storage values.
- The `agent_config` environment variable `HOMEPOT_AGENT_CONFIG` overrides the
  default config path.
- If no config file is found, the agent generates an identity and uses
  credential storage (requiring prior provisioning before it can authenticate
  with the backend).

## Testing

```bash
cd backend
pytest tests/test_agent_credential_storage.py tests/test_agent_identity.py -v
```

**Test coverage** (new code):

| Module | Coverage |
|--------|----------|
| `credential_storage.py` | 97% |
| `identity.py` | 84% |

The uncovered lines in `identity.py` are the permission-denied branch of
`_machine_id_identity()` (requires a real `/etc/machine-id` with read
restrictions) and the fallback-to-machine-id branch in
`get_or_create_device_id()` (requires identity dir to be unwritable).

## PR checklist

- [x] Python credential storage mirrors TypeScript interface
- [x] Persistent device identity with UUID and machine-id fallback
- [x] systemd service unit with security hardening
- [x] Install/uninstall script
- [x] CLI with `run`, `identity`, `status`, `config`, `credentials` commands
- [x] `pyproject.toml` updated with agent entry points and deps
- [x] `real_device_agent.py` updated to use new modules
- [x] 31 credential storage tests pass
- [x] 25 identity tests pass
- [x] Minimum 10% project coverage maintained

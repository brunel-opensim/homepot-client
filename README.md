# HOMEPOT Client

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python Version](https://img.shields.io/badge/python-3.11%2B-brightgreen.svg)](https://python.org/)
[![Documentation](https://readthedocs.org/projects/homepot-client/badge/?version=latest)](https://homepot-client.readthedocs.io/en/latest/)
[![Code Style](https://img.shields.io/badge/code%20style-black%20%7C%20flake8-000000.svg)](https://github.com/psf/black)
[![Security](https://img.shields.io/badge/security-audit%20passing-green.svg)](https://github.com/brunel-opensim/homepot-client/actions/workflows/security-audit.yml)

> **Private Repository**: This repository is restricted to HOMEPOT consortium members only.

HOMEPOT stands for **Homogenous Cyber Management of End-Points and Operational Technology**.
It is a collaborative, multi-partner project that aims to unify the way organisations manage, secure, and communicate with diverse end-points and operational technology devices across different platforms and environments.

The HOMEPOT Client is one of the building blocks of this vision.
It is designed as a flexible, extensible client system that enables secure, scalable interactions with devices in real-world scenarios such as retail, hospitality, and industrial operations.

## Quick Start (macOS & Linux)

We recommend running the project locally without Docker for the best development experience.

1.  **Install & Setup**:
    ```bash
    chmod +x scripts/*.sh
    ./scripts/install-backend.sh
    ./scripts/setup-ollama.sh
    ```

2.  **Initialize Database**:
    ```bash
    ./scripts/init-postgresql.sh
    ```
    This creates a **clean** database: schema + default admin user
    (`admin@homepot.com` / `homepot_dev_password`), with **no** devices. Devices
    are added explicitly via simulation, emulation, or real devices.

    To also load the **demo / simulated fleet** (tenants, sites, simulated
    devices, historical analytics), run the opt-in seeder:
    ```bash
    ./scripts/seed-demo-data.sh
    ```

3.  **Run**:
    ```bash
    ./scripts/start-dashboard.sh
    ```

See [docs/getting-started.md](docs/getting-started.md) for full details.

## Three Test Integration Modes

The system supports **three** device integration modes. **Test technicians must
know which mode they are running**, because each one produces telemetry through
a different path. Only one mode should be active for a given device at a time —
with simulation on, the simulator also drives emulated/real device records, so
switch it off when emulating or using real devices.

Start from a clean database, then choose a mode:

```bash
./scripts/init-postgresql.sh          # clean DB: schema + admin (no devices)
```

### Mode 1: Simulation

The backend's **in-process agent simulator** drives every active POS/IoT device
(`ENABLE_AGENT_SIMULATION=true`) — no external process is needed. It writes
heartbeats, health checks, and metrics directly to the database.

```bash
# clean DB, then start the stack in simulation mode
./scripts/init-postgresql.sh
./scripts/start-dashboard.sh simulation

# (optional) load the demo/simulated fleet instead of an empty dashboard
./scripts/seed-demo-data.sh
```

- Devices appear **online** immediately (the simulator heartbeats for them).
- The simulator attaches to **existing active devices** — with an empty DB there
  is nothing to simulate, so seed the demo fleet or add devices first.
- Switch to another mode at runtime: `./scripts/set-simulation-mode.sh off`.

### Mode 2: Emulation

Standalone **emulator processes** (`./scripts/start-emulator.sh`) authenticate
against the backend and behave like real hardware over the agent API (device
DNA, heartbeat, telemetry, command polling). Use for end-to-end testing of the
device lifecycle and User App without physical hardware.

```bash
# clean DB, then start the stack in emulation mode (simulator OFF)
./scripts/init-postgresql.sh
./scripts/start-dashboard.sh emulation

# in another terminal, run one or more emulators
./scripts/start-emulator.sh --emulator macos \
  --backend-url http://localhost:8000 \
  --site-id <site-id> --bootstrap-key <key> \
  --device-name demo-pos-1
```

- The site must exist first (create it via the Dashboard or API).
- Each emulator provisions itself and streams DNA/heartbeat/telemetry/logs.
- See [Device Emulators](docs/device-emulators.md) for all OS emulators
  (Linux, Android, Windows, macOS, iOS) and their configuration.
- Switch to simulation at runtime: `./scripts/set-simulation-mode.sh on`.

### Mode 3: Real Devices

Physical devices running the HOMEPOT agent talk to the backend over the network
via the agent API.

```bash
# clean DB, then start the stack in real mode (simulator OFF)
./scripts/init-postgresql.sh
./scripts/start-dashboard.sh real
```

- The `real` flag is **provisioned**: it keeps the simulator OFF (the same
  backend setting as emulation) so real agents are the sole data source.
  Full real-device onboarding support is pending.
- See the [Agent API Contract](backend/README.md#agent-api-contract-pilot).

> **Tip for test technicians:** with the simulator ON
> (`ENABLE_AGENT_SIMULATION=true`), devices get heartbeats/telemetry written for
> them; with it OFF (emulation/real), telemetry comes only from emulators or
> real agents. A fresh DB starts with no devices either way — devices are added
> via seeding, emulators, or real onboarding.

## Documentation

**Complete documentation is available at: [https://homepot-client.readthedocs.io/en/latest/](https://homepot-client.readthedocs.io/en/latest/)**

- **[Getting Started Guide](https://homepot-client.readthedocs.io/en/latest/getting-started/)** - Installation, configuration, and first steps

## Key Goals

- **Unified Management**: Provide a unified approach to managing devices and applications across multiple ecosystems
- **Secure Communication**: Ensure secure communication and policy enforcement between central services and distributed devices
- **Cross-Partner Collaboration**: Support consortium collaboration by serving as a common, open foundation for research and development
- **Real-World Validation**: Enable demonstrable client system validation in real use-cases with consortium partners

## Project Structure

**Monorepo organization for full-stack development:**

```text
homepot-client/
├── ai                      # AI/LLM services
│   └── README.md
├── backend                 # Backend service
│   └── README.md
├── deploy                  # Real-Device helpers and env overrides
│   └── README.md
├── docs                    # Documentation (Read the Docs)
│   └── README.md
├── emulators               # Realistic OS/IoT device emulators (Linux, Android, macOS, Windows, iOS)
│   └── README.md
├── frontend                # Frontend service
│   └── README.md
├── logs                    # Realtime logging
│   └── README.md
├── scripts                 # Development and automation scripts
│   └── README.md
├── uq                      # VVUQ - Validation, Verification, Uncertainty Quantification
│   └── README.md
└── user_app                # Device-side User App (independent Electron agent)
│   └── README.md
├── .github/                # GitHub workflows
├── docker-compose.yml      # Multi-service orchestration
├── CONTRIBUTING.md         # Contribution guidelines
├── LICENSE                 # Apache 2.0 license
└── README.md               # This file
```

> See [Monorepo Migration Guide](docs/monorepo-migration.md) for details on the new structure

## Quick Start

### Full Installation

```bash
# Clone the repository (consortium members only)
git clone https://github.com/brunel-opensim/homepot-client.git
cd homepot-client

# Install using the automated script help
./scripts/install-backend.sh --help
```

Simple installation command:

```bash
./scripts/install-backend.sh
```

*Please follow the installation prompts to complete setup.*

**For complete installation, running, testing, and development instructions, see the [Getting Started Guide](https://homepot-client.readthedocs.io/en/latest/getting-started/)**

### For Frontend Developers

Working on the UI? Here's the fastest way to get started:

```bash
# 1. Create PostgreSQL database (schema + admin user, no demo data)
./scripts/init-postgresql.sh

# (optional) Load the demo/simulated fleet
./scripts/seed-demo-data.sh

# 2. Start both backend and frontend
./scripts/start-dashboard.sh
```

This will start:
- **Backend API**: http://localhost:8000 (with API docs at `/docs`)
- **Frontend**: http://localhost:5173
- **Test Account**: `admin@homepot.com` / `homepot_dev_password`

> **Login fails with "Request failed with status code 500" / "Unable to login"?**
> The most common cause is the **backend not running** on port 8000. The frontend proxies `/api` to `127.0.0.1:8000`, so when the backend is down, Vite returns a generic `500 Proxy error` for the login request. Verify with:
> ```bash
> curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/api/v1/health   # expect 200
> ```
> If it is not `200`, restart the backend. If you launch it manually from a shell that later terminates, use `setsid` (not plain `nohup`) so the process detaches from the shell's process group and survives:
> ```bash
> cd backend && source ../.venv/bin/activate
> setsid env ENABLE_AGENT_SIMULATION=true python -m uvicorn homepot.app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir src --reload-dir ../ai < /dev/null > ../logs/backend.log 2>&1 &
> ```
> `--reload-dir src --reload-dir ../ai` makes the backend also auto-restart when files under the `ai/` package (validation gates, anomaly detection, etc.) change. Logs go to `logs/backend.log` (repo root, gitignored).

**See [Complete Dashboard Setup Guide](docs/complete-dashboard-setup.md) and [Dashboard Testing Guide](docs/dashboard-testing-guide.md)**

> **Test technicians:** for the complete clean start/stop cycle across all five
> services (backend, frontend, AI, emulator, User App), including a verified smoke
> test, see **[Starting & Stopping All Services](docs/getting-started.md#starting--stopping-all-services)**.

### Analytics (Data Collection for AI)

- Verify backend server is running
- Generate test API calls
- Show collected analytics data
- Demonstrate automatic request logging

**See [Backend Analytics Documentation](docs/backend-analytics.md) for details on what data is collected and how to query it.**

### Prerequisites

- **Python**: >= 3.11 (3.12.3 recommended)
- **Node.js**: v22+ (Required for Vite 6+)
- **PostgreSQL**: 13+ (for database)
- **pip**: Latest version  
- **Git**: Latest version
- **Access**: HOMEPOT consortium membership required

### Code Quality Standards

This project maintains high code quality with automated tooling:

- **Python 3.11+** with type hints and modern features
- **Automated Testing** with >98% coverage requirement
- **Code Formatting** with Black, isort, flake8, mypy
- **Security Analysis** with Bandit and safety checks

## Security

Security is paramount in the HOMEPOT project, including:

- Vulnerability reporting procedures
- Security best practices
- Compliance requirements
- Consortium-specific security measures

## Contributing

We welcome contributions from consortium members! Please see our [Contributing Guidelines](CONTRIBUTING.md) for:

- Development workflow
- Coding standards
- **Commit message protocol** (conventional commits with issue references)
- Pull request process
- Issue reporting

## Complete Documentation

**Full Documentation: [https://homepot-client.readthedocs.io/en/latest/](https://homepot-client.readthedocs.io/en/latest/)**

Key documentation sections:

- **[Getting Started](https://homepot-client.readthedocs.io/en/latest/getting-started/)** - Installation, configuration, and first steps
- **[Development Guide](https://homepot-client.readthedocs.io/en/latest/development-guide/)** - Development workflow and best practices
- **[Push Notifications](https://homepot-client.readthedocs.io/en/latest/push-notification/)** - FCM, WNS, and APNs integration guides
- **[Database Management](https://homepot-client.readthedocs.io/en/latest/database-management/)** - Database setup and workflow
- **[POS Management](https://homepot-client.readthedocs.io/en/latest/pos-management/)** - Point-of-sale device management

*Local documentation is also available in the [`docs/`](docs/) directory and can be built using `mkdocs serve`*

## Consortium Information

This is a private project developed by the HOMEPOT consortium for consortium members only.

### Use Cases

- **Retail Operations**: Point-of-sale systems, inventory management, customer analytics
- **Hospitality Management**: Room automation, guest services, facility management
- **Industrial Control**: Manufacturing systems, process control, safety monitoring

### Partners

This project involves multiple consortium partners working collaboratively on device management solutions.

## Support

For support and questions:

1. **Issues**: Use GitHub Issues for bug reports and feature requests
2. **Security**: Follow our [Security Recommendations](CONTRIBUTING.md) for security-related matters
3. **Consortium Channels**: Use official consortium communication channels for general inquiries

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

Copyright 2025 HOMEPOT Consortium

---

**Important**: This repository contains proprietary consortium information. Access is restricted to authorized HOMEPOT consortium members only.

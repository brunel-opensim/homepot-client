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
    ./scripts/install.sh
    ./scripts/setup-ollama.sh
    ```

2.  **Initialize Database**:
    ```bash
    ./scripts/init-postgresql.sh
    ```

3.  **Run**:
    ```bash
    ./scripts/start-website.sh
    ```

See [docs/getting-started.md](docs/getting-started.md) for full details.

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
├── backend/                 # Python backend service
│   ├── src/homepot/         # Main Python package
│   ├── tests/               # Backend tests
│   ├── pyproject.toml       # Python configuration
│   └── requirements.txt     # Python dependencies
├── frontend/                # React frontend application
│   ├── src/                 # Frontend source code
│   ├── public/              # Static assets
│   └── package.json         # npm dependencies
├── ai/                      # AI/LLM services (future)
│   └── README.md            # AI service documentation
├── docs/                    # Documentation
├── scripts/                 # Development and automation scripts
├── data/                    # Database storage
├── .github/                 # GitHub workflows
├── docker-compose.yml       # Multi-service orchestration
├── CONTRIBUTING.md          # Contribution guidelines
├── LICENSE                  # Apache 2.0 license
└── README.md                # This file
```

> See [Monorepo Migration Guide](docs/monorepo-migration.md) for details on the new structure

## Quick Start

### Full Installation

```bash
# Clone the repository (consortium members only)
git clone https://github.com/brunel-opensim/homepot-client.git
cd homepot-client

# Install using the automated script help
./scripts/install.sh --help
```

Simple installation command:

```bash
./scripts/install.sh
```

*Please follow the installation prompts to complete setup.*

**For complete installation, running, testing, and development instructions, see the [Getting Started Guide](https://homepot-client.readthedocs.io/en/latest/getting-started/)**

### For Frontend Developers

Working on the UI? Here's the fastest way to get started:

```bash
# 1. Create PostgreSQL database
./scripts/init-postgresql.sh

# 2. Start both backend and frontend
./scripts/start-website.sh
```

This will start:
- **Backend API**: http://localhost:8000 (with API docs at `/docs`)
- **Frontend**: http://localhost:5173
- **Test Account**: `admin@homepot.com` / `homepot_dev_password`

**See [Complete Website Setup Guide](docs/complete-website-setup.md) and [Website Testing Guide](docs/website-testing-guide.md)**

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

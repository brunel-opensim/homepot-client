# HOMEPOT Client

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python Version](https://img.shields.io/badge/python-3.9%2B-brightgreen.svg)](https://python.org/)
[![Documentation](https://readthedocs.org/projects/brunel-opensimhomepot-client/badge/?version=latest)](https://brunel-opensimhomepot-client.readthedocs.io/en/latest/)
[![Code Style](https://img.shields.io/badge/code%20style-black%20%7C%20flake8-000000.svg)](https://github.com/psf/black)
[![Security](https://img.shields.io/badge/security-audit%20passing-green.svg)](https://github.com/brunel-opensim/homepot-client/actions/workflows/security-audit.yml)

> **Private Repository**: This repository is restricted to HOMEPOT consortium members only.

HOMEPOT stands for **Homogenous Cyber Management of End-Points and Operational Technology**.
It is a collaborative, multi-partner project that aims to unify the way organisations manage, secure, and communicate with diverse end-points and operational technology devices across different platforms and environments.

The HOMEPOT Client is one of the building blocks of this vision.
It is designed as a flexible, extensible client system that enables secure, scalable interactions with devices in real-world scenarios such as retail, hospitality, and industrial operations.

## Documentation

**📚 Complete documentation is available at: [https://brunel-opensimhomepot-client.readthedocs.io/en/latest/](https://brunel-opensimhomepot-client.readthedocs.io/en/latest/)**

- **[Getting Started Guide](https://brunel-opensimhomepot-client.readthedocs.io/en/latest/getting-started/)** - Installation, configuration, and first steps

## Key Goals

- **Unified Management**: Provide a unified approach to managing devices and applications across multiple ecosystems
- **Secure Communication**: Ensure secure communication and policy enforcement between central services and distributed devices
- **Cross-Partner Collaboration**: Support consortium collaboration by serving as a common, open foundation for research and development
- **Real-World Validation**: Enable demonstrable client system validation in real use-cases with consortium partners

## Project Structure

**Monorepo organization for full-stack development:**

```text
homepot-client/
├── backend/                   # Python backend service
│   ├── homepot_client/       # Main Python package
│   ├── tests/                # Backend tests
│   ├── pyproject.toml        # Python configuration
│   └── requirements.txt      # Python dependencies
├── frontend/                  # React frontend application
│   ├── src/                  # Frontend source code
│   ├── public/               # Static assets
│   └── package.json          # npm dependencies
├── ai/                        # AI/LLM services (future)
│   └── README.md             # AI service documentation
├── docs/                      # Documentation
├── scripts/                   # Development and automation scripts
├── data/                      # Database storage
├── .github/                   # GitHub workflows
├── docker-compose.yml         # Multi-service orchestration
├── CONTRIBUTING.md            # Contribution guidelines
├── LICENSE                    # Apache 2.0 license
└── README.md                  # This file
```

> See [Monorepo Migration Guide](docs/monorepo-migration.md) for details on the new structure

## Quick Start

### Prerequisites

- **Python**: >= 3.9
- **pip**: Latest version  
- **Git**: Latest version
- **Access**: HOMEPOT consortium membership required

### Basic Installation

```bash
# Clone the repository (consortium members only)
git clone https://github.com/brunel-opensim/homepot-client.git
cd homepot-client

# Install using the automated script
./scripts/install.sh --dev
```

**For complete installation, running, testing, and development instructions, see the [Getting Started Guide](https://brunel-opensimhomepot-client.readthedocs.io/en/latest/getting-started/)**

## Development

### Quick Reference

| Command | Description |
|---------|-------------|
| `pytest` | Run test suite with coverage |
| `homepot-client version` | Display version information |
| `homepot-client info` | Display project information |

**For complete development workflow, testing commands, and Docker deployment, see the [Getting Started Guide](https://brunel-opensimhomepot-client.readthedocs.io/en/latest/getting-started/)**

### Code Quality Standards

This project maintains high code quality with automated tooling:

- **Python 3.9+** with type hints and modern features
- **Automated Testing** with >98% coverage requirement
- **Code Formatting** with Black, isort, flake8, mypy
- **Security Analysis** with Bandit and safety checks

## Security

Security is paramount in the HOMEPOT project. Please review our [Security Policy](SECURITY.md) for:

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

**📚 Full Documentation: [https://brunel-opensimhomepot-client.readthedocs.io/en/latest/](https://brunel-opensimhomepot-client.readthedocs.io/en/latest/)**

Key documentation sections:

- **[Getting Started](https://brunel-opensimhomepot-client.readthedocs.io/en/latest/getting-started/)** - Installation, configuration, and first steps
- **[Development Guide](https://brunel-opensimhomepot-client.readthedocs.io/en/latest/development-guide/)** - Development workflow and best practices
- **[Push Notifications](https://brunel-opensimhomepot-client.readthedocs.io/en/latest/push-notification/)** - FCM, WNS, and APNs integration guides
- **[Database Management](https://brunel-opensimhomepot-client.readthedocs.io/en/latest/database-management/)** - Database setup and workflow
- **[POS Management](https://brunel-opensimhomepot-client.readthedocs.io/en/latest/pos-management/)** - Point-of-sale device management

*Local documentation is also available in the [`docs/`](docs/) directory and can be built using `mkdocs serve`*

## Consortium Information

This is a private project developed by the HOMEPOT consortium for consortium members only.

### Use Cases

- **Retail Operations**: Point-of-sale systems, inventory management, customer analytics
- **Hospitality Management**: Room automation, guest services, facility management
- **Industrial Control**: Manufacturing systems, process control, safety monitoring

### Partners

This project involves multiple consortium partners working collaboratively on device management solutions.

## Project Status

- **Current Version**: 0.1.0 (Development)
- **License**: Apache 2.0
- **Python Support**: 3.9, 3.10, 3.11, 3.12
- **Platform Support**: Linux, macOS, Windows

## Support

For support and questions:

1. **Issues**: Use GitHub Issues for bug reports and feature requests
2. **Security**: Follow our [Security Policy](SECURITY.md) for security-related matters
3. **Consortium Channels**: Use official consortium communication channels for general inquiries

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

Copyright 2025 HOMEPOT Consortium

---

**Important**: This repository contains proprietary consortium information. Access is restricted to authorized HOMEPOT consortium members only.

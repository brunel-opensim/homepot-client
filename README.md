# HOMEPOT Client

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python Version](https://img.shields.io/badge/python-3.9%2B-brightgreen.svg)](https://python.org/)
[![Documentation](https://img.shields.io/badge/docs-Read%20the%20Docs-blue.svg)](https://homepot-client.readthedocs.io)
[![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Security Audit](https://github.com/brunel-opensim/homepot-client/workflows/Security%20Audit/badge.svg)](https://github.com/brunel-opensim/homepot-client/actions)

> **Private Repository**: This repository is restricted to HOMEPOT consortium members only.

HOMEPOT stands for **Homogenous Cyber Management of End-Points and Operational Technology**.
It is a collaborative, multi-partner project that aims to unify the way organisations manage, secure, and communicate with diverse end-points and operational technology devices across different platforms and environments.

The HOMEPOT Client is one of the building blocks of this vision.
It is designed as a flexible, extensible client system that enables secure, scalable interactions with devices in real-world scenarios such as retail, hospitality, and industrial operations.

## Documentation

**Complete documentation is available at: [https://homepot-client.readthedocs.io](https://homepot-client.readthedocs.io)**

- **[Getting Started Guide](https://homepot-client.readthedocs.io/en/latest/getting-started.html)** - Installation, configuration, and first steps
- **[API Reference](https://homepot-client.readthedocs.io/en/latest/api-reference.html)** - Complete API documentation
- **[CLI Reference](https://homepot-client.readthedocs.io/en/latest/cli-reference.html)** - Command-line interface guide
- **[Examples](https://homepot-client.readthedocs.io/en/latest/examples.html)** - Practical usage examples
- **[Contributing](https://homepot-client.readthedocs.io/en/latest/contributing.html)** - Development workflow and guidelines

## Key Goals

- **Unified Management**: Provide a unified approach to managing devices and applications across multiple ecosystems
- **Secure Communication**: Ensure secure communication and policy enforcement between central services and distributed devices
- **Cross-Partner Collaboration**: Support consortium collaboration by serving as a common, open foundation for research and development
- **Real-World Validation**: Enable demonstrable client system validation in real use-cases with consortium partners

## Project Structure

```text
homepot-client/
├── src/
│   └── homepot_client/        # Python package source code
├── tests/                     # Test files
├── docs/                      # Documentation
├── .github/                   # GitHub workflows and templates
├── pyproject.toml             # Python project configuration
├── requirements.txt           # Project dependencies
├── .env.example               # Environment configuration template
├── CONTRIBUTING.md            # Contribution guidelines
├── SECURITY.md                # Security policy
├── CHANGELOG.md               # Version history
└── README.md                  # This file
```

## Quick Start

### Prerequisites

- **Python**: >= 3.9
- **pip**: Latest version
- **Git**: Latest version
- **Access**: HOMEPOT consortium membership required

### Installation

1. **Clone the repository** (consortium members only):

   ```bash
   git clone https://github.com/brunel-opensim/homepot-client.git
   cd homepot-client
   ```

2. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   pip install -e .
   ```

3. **Set up environment**:

   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. **Run tests**:

   ```bash
   pytest
   ```

5. **Test CLI**:

   ```bash
   homepot-client --help
   homepot-client version
   ```

> **For detailed installation and configuration instructions, see the [Getting Started Guide](https://homepot-client.readthedocs.io/en/latest/getting-started.html)**

## Development

### Available Scripts

| Command | Description |
|---------|-------------|
| `pytest` | Run test suite with coverage |
| `pytest -m unit` | Run unit tests only |
| `pytest -m integration` | Run integration tests only |
| `homepot-client version` | Display version information |
| `homepot-client info` | Display project information |

### Code Quality

This project maintains high code quality standards:

- **Python 3.9+**: Modern Python with type hints
- **Black**: Code formatting
- **isort**: Import sorting  
- **flake8**: Code linting with security rules
- **mypy**: Static type checking
- **pytest**: Comprehensive testing (>80% coverage required)
- **Bandit**: Security analysis

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

## Documentation

**Complete documentation: [https://homepot-client.readthedocs.io](https://homepot-client.readthedocs.io)**

Key documentation sections:

- **[Getting Started](https://homepot-client.readthedocs.io/en/latest/getting-started.html)** - Installation, configuration, and first steps
- **[API Reference](https://homepot-client.readthedocs.io/en/latest/api-reference.html)** - Complete API documentation with examples
- **[CLI Reference](https://homepot-client.readthedocs.io/en/latest/cli-reference.html)** - Command-line interface guide
- **[Examples](https://homepot-client.readthedocs.io/en/latest/examples.html)** - Practical usage examples and code samples
- **[Contributing Guide](https://homepot-client.readthedocs.io/en/latest/contributing.html)** - Development workflow and contribution guidelines

*Local documentation is also available in the [`docs/`](docs/) directory and can be built using `./scripts/build-docs.sh`*

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

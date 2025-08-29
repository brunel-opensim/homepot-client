# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial Python project structure
- Basic CLI interface with version and info commands
- Core client class with async connection management
- Comprehensive test suite with 98% coverage
- CI/CD workflows with GitHub Actions
- Security scanning with Bandit, Safety, and CodeQL
- Code quality tools (Black, isort, flake8, mypy)
- Documentation with Sphinx and Read the Docs integration
- Development environment setup with pre-commit hooks

### Changed
- Converted from Node.js/TypeScript to Python implementation
- Updated project structure to follow Python packaging standards

### Fixed
- Repository cleanup removing generated Node.js artifacts

## [0.1.0] - 2025-08-29

### Added
- Initial release of HOMEPOT client library
- Python 3.9+ support with async/await functionality
- Command-line interface using Typer and Rich
- FastAPI integration ready for future web services
- Comprehensive development and testing infrastructure
- Professional documentation system
- Consortium-specific branding and attribution

### Features
- **HomepotClient**: Core async client for HOMEPOT services
- **CLI Interface**: Command-line tools for consortium members
  - `homepot-client version`: Display version information
  - `homepot-client info`: Show system and configuration details
- **Development Tools**: Complete development environment
  - Code formatting with Black
  - Import sorting with isort
  - Linting with flake8
  - Type checking with mypy
  - Security scanning with Bandit
  - Testing with pytest
- **CI/CD**: Automated testing and deployment
  - Multi-platform testing (Linux, macOS, Windows)
  - Python 3.9-3.12 compatibility testing
  - Automated security auditing
  - Code coverage reporting
- **Documentation**: Professional documentation system
  - Sphinx-based documentation
  - Read the Docs integration
  - API reference with autodoc
  - Comprehensive examples and guides

### Technical Details
- **Package Structure**: Modern Python package in `src/` layout
- **Async Support**: Full async/await compatibility for scalable applications
- **Type Safety**: Complete type hints with mypy validation
- **Testing**: 98% code coverage with comprehensive test suite
- **Security**: Multiple security scanning tools integrated
- **Performance**: Optimized for consortium-scale deployments

### Infrastructure
- **GitHub Actions**: Automated CI/CD pipelines
- **Pre-commit**: Development quality gates
- **Dependabot**: Automated dependency updates
- **CodeQL**: GitHub security analysis
- **Branch Protection**: Main and develop branch protection rules

[Unreleased]: https://github.com/brunel-opensim/homepot-client/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/brunel-opensim/homepot-client/releases/tag/v0.1.0

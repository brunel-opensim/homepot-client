# Contributing

Thank you for your interest in contributing to the HOMEPOT client library! This guide will help you get started.

## Development Setup

### Prerequisites

- Python 3.9 or higher
- Git
- A GitHub account

### Setting Up Development Environment

1. **Fork and Clone**

   ```bash
   # Fork the repository on GitHub, then clone your fork
   git clone https://github.com/YOUR_USERNAME/homepot-client.git
   cd homepot-client
   ```

2. **Create Virtual Environment**

   ```bash
   # Create and activate virtual environment
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Dependencies**

   ```bash
   # Install in development mode with all dependencies
   pip install -e ".[dev,test,docs]"
   ```

4. **Install Pre-commit Hooks**

   ```bash
   # Install pre-commit hooks for code quality
   pre-commit install
   ```

5. **Verify Setup**

   ```bash
   # Run tests to verify everything works
   pytest
   
   # Check CLI is working
   homepot-client version
   ```

## Development Workflow

### Branching Strategy

We use a standard Git flow with `main` and `develop` branches:

- `main`: Production-ready code
- `develop`: Integration branch for features
- `feature/*`: Feature development branches
- `bugfix/*`: Bug fix branches
- `hotfix/*`: Emergency fixes for main

### Creating a Feature

1. **Create Feature Branch**

   ```bash
   # Start from develop
   git checkout develop
   git pull origin develop
   
   # Create feature branch
   git checkout -b feature/your-feature-name
   ```

2. **Make Changes**

   ```bash
   # Make your changes
   # Add tests for new functionality
   # Update documentation if needed
   ```

3. **Test Your Changes**

   ```bash
   # Run all tests
   pytest
   
   # Check code quality
   black src/ tests/
   isort src/ tests/
   flake8 src/ tests/
   mypy src/
   
   # Test CLI functionality
   homepot-client version
   homepot-client info
   ```

4. **Commit Changes**

   ```bash
   # Stage your changes
   git add .
   
   # Commit with proper message format
   git commit -m "feat: add new device management functionality"
   ```

## Code Quality Standards

### Code Formatting

We use several tools to maintain code quality:

- **Black**: Code formatting (88 character line length)
- **isort**: Import sorting
- **flake8**: Style and error checking
- **mypy**: Static type checking

```bash
# Format code
black src/ tests/

# Sort imports
isort src/ tests/

# Check style
flake8 src/ tests/

# Type checking
mypy src/
```

### Type Hints

All functions must have proper type hints:

```python
from typing import Optional, Dict, Any

async def connect(
    self, 
    timeout: Optional[int] = None
) -> bool:
    """Connect to HOMEPOT service.
    
    Args:
        timeout: Connection timeout in seconds
        
    Returns:
        True if connection successful
        
    Raises:
        ConnectionError: If connection fails
    """
    # Implementation here
    pass
```

### Documentation

All public APIs must have comprehensive docstrings:

```python
class HomepotClient:
    """Client for interacting with HOMEPOT services.
    
    This client provides an async interface for connecting to and
    managing HOMEPOT devices and services.
    
    Example:
        ```python
        client = HomepotClient()
        await client.connect()
        # Use client
        await client.disconnect()
        ```
    
    Attributes:
        is_connected: True if client is connected to service
    """
```

## Testing

### Test Structure

Tests are organized in the `tests/` directory:

```
tests/
├── test_client.py          # Client functionality tests
├── test_cli.py             # CLI tests
├── test_integration.py     # Integration tests
└── conftest.py             # Test configuration
```

### Writing Tests

Use pytest for all tests:

```python
import pytest
from homepot_client import HomepotClient

class TestHomepotClient:
    """Test suite for HOMEPOT client."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return HomepotClient()
    
    @pytest.mark.asyncio
    async def test_connection(self, client):
        """Test client connection."""
        # Test implementation
        pass
    
    def test_version_info(self):
        """Test version information."""
        from homepot_client import __version__
        assert __version__ == "0.1.0"
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=homepot_client --cov-report=html

# Run specific test file
pytest tests/test_client.py

# Run with verbose output
pytest -v

# Run only fast tests (skip slow integration tests)
pytest -m "not slow"
```

### Test Coverage

Maintain at least 80% test coverage:

```bash
# Generate coverage report
pytest --cov=homepot_client --cov-report=term-missing

# View HTML coverage report
pytest --cov=homepot_client --cov-report=html
open htmlcov/index.html
```

## Commit Message Format

We follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

### Types

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks
- `ci`: CI/CD changes
- `perf`: Performance improvements

### Examples

```bash
# Feature
git commit -m "feat: add device discovery functionality"

# Bug fix
git commit -m "fix: handle connection timeout properly"

# Documentation
git commit -m "docs: update API reference for new methods"

# Breaking change
git commit -m "feat!: change client configuration API"
```

## Pull Request Process

### Before Submitting

1. **Ensure tests pass**
   ```bash
   pytest
   ```

2. **Check code quality**
   ```bash
   black src/ tests/
   isort src/ tests/
   flake8 src/ tests/
   mypy src/
   ```

3. **Update documentation**
   - Update docstrings for new/changed APIs
   - Update README if needed
   - Add examples for new features

4. **Update changelog**
   Add entry to `CHANGELOG.md` if needed

### Submitting PR

1. **Push to your fork**
   ```bash
   git push origin feature/your-feature-name
   ```

2. **Create Pull Request**
   - Use descriptive title
   - Reference related issues
   - Provide clear description of changes
   - Include testing instructions

3. **PR Template**
   ```markdown
   ## Description
   Brief description of changes
   
   ## Type of Change
   - [ ] Bug fix
   - [ ] New feature
   - [ ] Breaking change
   - [ ] Documentation update
   
   ## Testing
   - [ ] All tests pass
   - [ ] Added tests for new functionality
   - [ ] Manual testing completed
   
   ## Checklist
   - [ ] Code follows style guidelines
   - [ ] Self-review completed
   - [ ] Documentation updated
   - [ ] Changes are backwards compatible
   ```

### Review Process

1. **Automated Checks**
   - All CI checks must pass
   - Code coverage maintained
   - Security scans clean

2. **Code Review**
   - At least one approving review required
   - Address all review comments
   - Update PR based on feedback

3. **Merge**
   - Squash merge to develop
   - Clean commit message
   - Delete feature branch

## Documentation

### Building Documentation

```bash
# Install documentation dependencies
pip install -e ".[docs]"

# Build documentation
cd docs
make html

# View documentation
open _build/html/index.html
```

### Writing Documentation

- Use Markdown for most documentation
- Use reStructuredText for Sphinx-specific features
- Include code examples
- Keep documentation up to date with code changes

## Release Process

### Version Numbering

We follow [Semantic Versioning](https://semver.org/):

- `MAJOR.MINOR.PATCH`
- `MAJOR`: Breaking changes
- `MINOR`: New features (backwards compatible)
- `PATCH`: Bug fixes (backwards compatible)

### Release Steps

1. **Prepare Release**
   ```bash
   # Update version in pyproject.toml
   # Update CHANGELOG.md
   # Update __init__.py version
   ```

2. **Create Release PR**
   ```bash
   git checkout -b release/v1.2.3
   # Make version changes
   git commit -m "chore: prepare v1.2.3 release"
   # Create PR to main
   ```

3. **Tag and Release**
   ```bash
   git checkout main
   git pull origin main
   git tag v1.2.3
   git push origin v1.2.3
   ```

## Getting Help

### Community

- 💬 **Discord**: [HOMEPOT Community](https://discord.gg/homepot)
- 📧 **Email**: dev@homepot-consortium.org
<!-- Links will be activated when repository is created
- 🐛 **Issues**: [GitHub Issues](https://github.com/brunel-opensim/homepot-client/issues)
- 💡 **Discussions**: [GitHub Discussions](https://github.com/brunel-opensim/homepot-client/discussions)
-->

### Resources

- [Python Development Guide](https://docs.python.org/3/tutorial/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [pytest Documentation](https://docs.pytest.org/)
- [Conventional Commits](https://www.conventionalcommits.org/)

## Code of Conduct

Please note that this project is released with a [Contributor Code of Conduct](CODE_OF_CONDUCT.md). By participating in this project you agree to abide by its terms.

## License

By contributing to this project, you agree that your contributions will be licensed under the same license as the project (MIT License).

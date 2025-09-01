# Development Guide

This guide covers testing, code quality, and contributing to the HOMEPOT project.

## Development Setup

### Quick Setup

```bash
# Clone and set up development environment
git clone https://github.com/brunel-opensim/homepot-client.git
cd homepot-client
./scripts/install.sh --dev

# Activate development environment
./scripts/activate-homepot.sh
```

### Manual Setup

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install with development dependencies
pip install -e ".[dev]"

# Install additional development tools
pip install pytest pytest-cov black isort flake8 mypy bandit
```

## Testing

### Running Tests

```bash
# Run all tests with coverage
pytest

# Run specific test categories
pytest -m integration   # Integration tests only
pytest -m slow          # Performance tests only
pytest -m "not slow"    # All tests except slow ones (faster)

# Run with verbose output
pytest -v

# Run with detailed coverage report
pytest --cov=homepot_client --cov-report=html
```

### Test Categories

| Marker | Description | Count | Duration |
|--------|-------------|-------|----------|
| `unit` | Unit tests for individual components | ~15 | < 1 min |
| `integration` | Integration tests across components | ~3 | 2-5 min |
| `slow` | Performance and stress tests | ~1 | 5-10 min |
| `api` | API endpoint tests | ~8 | 1-2 min |

### Writing Tests

```python
# Example unit test
import pytest
from homepot_client.database import DatabaseService

@pytest.mark.asyncio
async def test_site_creation():
    """Test site creation functionality."""
    db = DatabaseService()
    await db.initialize()
    
    site_data = {
        "site_id": "TEST_SITE_001",
        "name": "Test Site",
        "location": "Test Location"
    }
    
    result = await db.create_site(site_data)
    assert result["site_id"] == "TEST_SITE_001"
    assert result["name"] == "Test Site"

# Example integration test
@pytest.mark.integration
@pytest.mark.asyncio
async def test_complete_workflow():
    """Test complete site creation to device registration workflow."""
    # Test implementation here
    pass
```

### Test Configuration

```ini
# pytest.ini
[tool:pytest]
markers =
    unit: Unit tests
    integration: Integration tests
    slow: Slow-running tests
    api: API tests
addopts = 
    --strict-markers
    --cov=homepot_client
    --cov-report=term-missing
    --cov-fail-under=80
```

## Code Quality

### Automated Validation

```bash
# Run all validation checks
./scripts/validate-workflows.sh

# Individual tools
black src/ tests/           # Code formatting
isort src/ tests/           # Import sorting
flake8 src/ tests/          # Style linting
mypy src/                   # Type checking
bandit -r src/              # Security scanning
```

### Code Formatting

```bash
# Format code automatically
black src/ tests/

# Check formatting without changes
black --check src/ tests/

# Sort imports
isort src/ tests/
```

### Type Checking

```bash
# Run type checking
mypy src/

# Generate type stub files
stubgen -m homepot_client -o stubs/
```

### Security Scanning

```bash
# Run security analysis
bandit -r src/

# Generate security report
bandit -r src/ -f json -o security-report.json
```

## Development Workflow

### Git Workflow

```bash
# Create feature branch
git checkout -b feature/new-feature

# Make changes and commit
git add .
git commit -m "Add new feature"

# Run tests before pushing
pytest
./scripts/validate-workflows.sh

# Push and create pull request
git push origin feature/new-feature
```

### Pre-commit Hooks

```bash
# Install pre-commit hooks
pip install pre-commit
pre-commit install

# Run hooks manually
pre-commit run --all-files
```

### Development Scripts

| Script | Purpose | Usage |
|--------|---------|-------|
| `./scripts/install.sh` | Install dependencies | `./scripts/install.sh --dev` |
| `./scripts/activate-homepot.sh` | Activate environment | `source ./scripts/activate-homepot.sh` |
| `./scripts/validate-workflows.sh` | Run all quality checks | `./scripts/validate-workflows.sh` |
| `./scripts/build-docs.sh` | Build documentation | `./scripts/build-docs.sh` |
| `./scripts/test-docker.sh` | Test Docker setup | `./scripts/test-docker.sh` |

## Development Environment

### IDE Configuration

#### VS Code Setup

```json
{
  "python.defaultInterpreterPath": "./venv/bin/python",
  "python.linting.enabled": true,
  "python.linting.flake8Enabled": true,
  "python.formatting.provider": "black",
  "python.sortImports.args": ["--profile", "black"],
  "editor.formatOnSave": true
}
```

#### PyCharm Setup

- Set interpreter to `./venv/bin/python`
- Enable Black formatter in Tools → External Tools
- Configure flake8 as code inspector
- Set up pytest as test runner

### Environment Variables

```bash
# Development environment variables
export HOMEPOT_ENV=development
export HOMEPOT_DEBUG=true
export HOMEPOT_LOG_LEVEL=DEBUG
export HOMEPOT_DATABASE_URL=sqlite:///./homepot_dev.db
```

### Development Database

```bash
# Create development database
python -c "
from homepot_client.database import DatabaseService
import asyncio

async def setup():
    db = DatabaseService()
    await db.initialize()
    print('Development database created')

asyncio.run(setup())
"

# Reset database
rm homepot.db
python -m homepot_client.main  # Will recreate on startup
```

## Contributing

### Contribution Guidelines

1. **Fork** the repository
2. **Create** a feature branch
3. **Make** changes with tests
4. **Run** quality checks
5. **Submit** pull request

### Code Standards

- **PEP 8** compliance (enforced by flake8)
- **Type hints** for all public APIs
- **Docstrings** for all public functions/classes
- **Test coverage** > 80% for new code
- **No security** vulnerabilities (bandit)

### Documentation

```python
def create_site(site_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new POS site.
    
    Args:
        site_data: Site configuration including site_id, name, location
        
    Returns:
        Created site data with timestamps
        
    Raises:
        ValueError: If site_id already exists
        ValidationError: If site_data is invalid
        
    Example:
        >>> site = create_site({
        ...     "site_id": "STORE_001",
        ...     "name": "Downtown Store",
        ...     "location": "123 Main St"
        ... })
        >>> print(site["site_id"])
        STORE_001
    """
```

### Pull Request Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Tests pass locally
- [ ] New tests added
- [ ] Manual testing performed

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] No new security vulnerabilities
```

## Debugging

### Development Server

```bash
# Run with debug mode
HOMEPOT_DEBUG=true python -m homepot_client.main

# Run with specific log level
HOMEPOT_LOG_LEVEL=DEBUG python -m homepot_client.main

# Run with pdb debugger
python -m pdb -m homepot_client.main
```

### Database Debugging

```bash
# Access SQLite database directly
sqlite3 homepot.db

# View table schemas
.schema

# Query data
SELECT * FROM sites LIMIT 5;
SELECT * FROM devices WHERE site_id = 'RESTAURANT_001';
```

### API Debugging

```bash
# Test API endpoints with verbose output
curl -v http://localhost:8000/health

# Use HTTPie for better output
pip install httpie
http GET localhost:8000/sites

# Monitor API logs
tail -f server.log | grep -i error
```

## Performance

### Profiling

```bash
# Profile application startup
python -m cProfile -o profile.stats -m homepot_client.main

# Analyze profile results
python -c "
import pstats
p = pstats.Stats('profile.stats')
p.sort_stats('cumulative').print_stats(20)
"
```

### Memory Monitoring

```bash
# Monitor memory usage
pip install memory-profiler
python -m memory_profiler -m homepot_client.main

# Generate memory reports
mprof run python -m homepot_client.main
mprof plot
```

### Load Testing

```bash
# Install load testing tools
pip install locust

# Run load tests
locust -f tests/load_test.py --host=http://localhost:8000
```

## Troubleshooting

### Common Development Issues

**Import Errors:**
```bash
# Reinstall in development mode
pip install -e .

# Check Python path
python -c "import sys; print(sys.path)"
```

**Test Failures:**
```bash
# Run specific failing test
pytest tests/test_specific.py::test_function -v

# Debug test with pdb
pytest tests/test_specific.py::test_function --pdb
```

**Database Issues:**
```bash
# Reset development database
rm homepot.db
python -m homepot_client.main
```

### Getting Help

- **Documentation**: Check the docs/ directory
- **Issues**: [GitHub Issues](https://github.com/brunel-opensim/homepot-client/issues)
- **Discussions**: [GitHub Discussions](https://github.com/brunel-opensim/homepot-client/discussions)
- **Contact**: Reach out to maintainers

---

*Next: Learn about [Deployment Guide](deployment-guide.md) for production deployment with Docker.*

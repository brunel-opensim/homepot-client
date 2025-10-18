# Testing Structure in HOMEPOT Monorepo

## Overview

The HOMEPOT monorepo follows a **stack-specific testing approach**, where each technology stack maintains its own tests directory with appropriate testing frameworks and tools.

## Directory Structure

```text
homepot-client/
├── backend/
│   ├── homepot_client/          # Backend source code
│   └── tests/                   # Backend tests (Python/pytest)
│       ├── conftest.py
│       ├── test_client.py
│       ├── test_database.py
│       └── test_pos_dummy.py
│
├── frontend/
│   ├── src/                     # Frontend source code
│   └── tests/                   # Frontend tests (JavaScript/Vitest)
│       ├── setup.js
│       ├── unit/                # Component unit tests
│       └── integration/         # Integration tests
│
└── ai/                          # Future AI/ML stack
    └── tests/                   # AI tests (Python/pytest)
```

## Testing Frameworks by Stack

### Backend Tests
- **Framework**: pytest
- **Location**: `backend/tests/`
- **Configuration**: `backend/pyproject.toml`
- **Coverage Tool**: pytest-cov
- **Run Command**: `pytest backend/tests/`

### Frontend Tests
- **Framework**: Vitest + React Testing Library
- **Location**: `frontend/tests/`
- **Configuration**: `frontend/vitest.config.js`
- **Coverage Tool**: Vitest (built-in)
- **Run Command**: `cd frontend && npm test`

### AI Tests (Future)
- **Framework**: pytest
- **Location**: `ai/tests/`
- **Configuration**: `ai/pyproject.toml`
- **Coverage Tool**: pytest-cov
- **Run Command**: `pytest ai/tests/`

## Running Tests

### All Tests (CI/CD)
```bash
# From repository root
pytest backend/tests/              # Backend tests
cd frontend && npm test            # Frontend tests
pytest ai/tests/                   # AI tests (when added)
```

### Individual Stacks

**Backend:**
```bash
# Run all backend tests
pytest backend/tests/ -v

# Run specific test file
pytest backend/tests/test_database.py

# Run with coverage
pytest backend/tests/ --cov=backend/homepot_client --cov-report=html
```

**Frontend:**
```bash
# Navigate to frontend directory
cd frontend

# Run all tests
npm test

# Run tests in watch mode (for development)
npm run test:watch

# Run with coverage
npm run test:coverage
```

## Test Coverage Requirements

| Stack | Minimum Coverage | Target Coverage |
|-------|-----------------|-----------------|
| Backend | 80% | 90%+ |
| Frontend | 70% | 80%+ |
| AI | 70% | 80%+ |

## Contribution Guidelines

### Adding Backend Tests
1. Create test file in `backend/tests/test_<feature>.py`
2. Follow pytest conventions
3. Use fixtures from `conftest.py`
4. Ensure >80% coverage
5. Run tests: `pytest backend/tests/`

### Adding Frontend Tests
1. Create test file in `frontend/tests/unit/` or `integration/`
2. Follow Vitest + Testing Library conventions
3. Use React Testing Library best practices
4. Ensure >70% coverage
5. Run tests: `cd frontend && npm test`

### Test File Naming

**Backend:**
- `test_<feature>.py` - Test files
- `conftest.py` - Shared fixtures
- Use `Test` prefix for classes: `class TestDatabase`

**Frontend:**
- `<Component>.test.jsx` - Component tests
- `<Feature>.test.js` - Feature tests
- Use `describe` blocks for grouping

## CI/CD Integration

Tests run automatically in GitHub Actions:

```yaml
# Backend tests
- name: Backend Tests
  run: pytest backend/tests/ --cov=backend/homepot_client

# Frontend tests
- name: Frontend Tests
  working-directory: frontend
  run: npm test
```

## Best Practices

### Backend (Python)
- Use fixtures for test data
- Mock external services
- Test async code with `pytest-asyncio`
- Keep tests independent
- Use factories for complex objects

### Frontend (React)
- Test user behavior, not implementation
- Use semantic queries (`getByRole`, `getByLabelText`)
- Mock API calls with MSW or vi.mock
- Keep tests fast (no real API calls)
- Use Testing Library queries

## Example Test Structure

### Backend Example
```python
# backend/tests/test_feature.py
import pytest
from homepot_client.feature import FeatureClass

class TestFeature:
    def test_basic_functionality(self):
        """Test basic feature works correctly."""
        feature = FeatureClass()
        result = feature.do_something()
        assert result == expected_value
    
    @pytest.mark.asyncio
    async def test_async_operation(self):
        """Test async operations."""
        result = await feature.async_operation()
        assert result is not None
```

### Frontend Example
```jsx
// frontend/tests/unit/Button.test.jsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import Button from '../../src/components/Button';

describe('Button Component', () => {
  it('renders with correct text', () => {
    render(<Button>Click Me</Button>);
    expect(screen.getByText('Click Me')).toBeInTheDocument();
  });
});
```

## Troubleshooting

### Backend Tests
- **Issue**: Import errors
  - **Solution**: Ensure virtual environment is activated
  - **Solution**: Run `pip install -e backend/`

- **Issue**: Database lock errors
  - **Solution**: Use unique database files per test
  - **Solution**: Properly cleanup in teardown

### Frontend Tests
- **Issue**: Module not found
  - **Solution**: Check `vitest.config.js` alias configuration
  - **Solution**: Run `npm install` to ensure dependencies

- **Issue**: Component not rendering
  - **Solution**: Check `tests/setup.js` is configured
  - **Solution**: Ensure jsdom environment is set

## Resources

### Backend
- [pytest documentation](https://docs.pytest.org/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [Python Testing Best Practices](https://docs.python-guide.org/writing/tests/)

### Frontend
- [Vitest documentation](https://vitest.dev/)
- [React Testing Library](https://testing-library.com/react)
- [Testing Best Practices](https://kentcdodds.com/blog/common-mistakes-with-react-testing-library)

---

**Note**: When contributing, always add tests for new features. PRs without tests may be rejected.

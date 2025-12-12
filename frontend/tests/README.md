# Frontend Testing Guide

## Overview

This directory contains all frontend tests for the HOMEPOT Client React application.

## Test Structure

```
frontend/tests/
├── setup.js              # Test environment setup
├── unit/                 # Unit tests for components
│   └── example.test.jsx
└── integration/          # Integration tests
    └── example.test.jsx
```

## Running Tests

```bash
# Run all tests
cd frontend && npm test

# Run tests in watch mode
npm run test:watch

# Run tests with coverage
npm run test:coverage

# Run specific test file
npm test Button.test.jsx
```

## Writing Tests

### Unit Tests

Unit tests focus on individual components in isolation:

```jsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import Button from '../../src/components/Button';

describe('Button Component', () => {
  it('renders with correct text', () => {
    render(<Button>Click Me</Button>);
    expect(screen.getByText('Click Me')).toBeInTheDocument();
  });

  it('calls onClick handler when clicked', () => {
    const handleClick = vi.fn();
    render(<Button onClick={handleClick}>Click</Button>);
    screen.getByText('Click').click();
    expect(handleClick).toHaveBeenCalledOnce();
  });
});
```

### Integration Tests

Integration tests verify interactions between multiple components or with APIs:

```jsx
import { describe, it, expect } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import Dashboard from '../../src/pages/Dashboard';

describe('Dashboard Integration', () => {
  it('fetches and displays device data', async () => {
    render(<Dashboard />);
    
    await waitFor(() => {
      expect(screen.getByText('Device List')).toBeInTheDocument();
    });
  });
});
```

## Testing Framework

- **Framework**: Vitest (fast, Vite-native)
- **Testing Library**: @testing-library/react
- **Coverage**: Built-in with Vitest

## Best Practices

1. **Test user behavior, not implementation**
2. **Use semantic queries** (`getByRole`, `getByLabelText`)
3. **Mock external dependencies** (API calls, external libraries)
4. **Aim for >80% coverage** on critical paths
5. **Keep tests fast and independent**

## Adding New Tests

When adding new features:

1. Create test file: `ComponentName.test.jsx`
2. Write tests for all use cases
3. Ensure tests pass: `npm test`
4. Check coverage: `npm run test:coverage`

## CI/CD Integration

Tests run automatically in GitHub Actions:
- On every pull request
- On push to main
- Part of the CI/CD pipeline

## Resources

- [Vitest Documentation](https://vitest.dev/)
- [React Testing Library](https://testing-library.com/react)
- [Testing Best Practices](https://kentcdodds.com/blog/common-mistakes-with-react-testing-library)

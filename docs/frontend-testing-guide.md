# Frontend Testing Guide

## Overview

The HomePot frontend uses **Vitest** as the testing framework, providing fast, modern unit and integration testing for React components.

## Testing Stack

### Core Testing Tools

- **Vitest** (3.2.4) - Fast unit test framework built on Vite
- **@testing-library/react** (16.3.0) - React component testing utilities
- **@testing-library/jest-dom** (6.9.1) - Custom DOM matchers
- **jsdom** (25.0.0) - DOM environment for Node.js
- **@vitest/ui** (3.2.4) - Interactive web-based test UI
- **@vitest/coverage-v8** (3.2.4) - Code coverage reporting

## Available Commands

```bash
# Run all tests once
npm run test

# Run tests in watch mode (auto-rerun on file changes)
npm run test:watch

# Run tests with coverage report
npm run test:coverage

# Open interactive test UI in browser
npm run test -- --ui
```

## Test Structure

```
frontend/tests/
├── setup.js              # Global test configuration
├── unit/                 # Unit tests for components
│   └── example.test.jsx  # Example component tests
└── integration/          # Integration tests
    └── example.test.jsx  # Example integration tests
```

## Writing Tests

### Basic Test Structure

```javascript
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Button } from '@/components/ui/button';

describe('Button Component', () => {
  it('renders button with text', () => {
    render(<Button>Click Me</Button>);
    expect(screen.getByRole('button')).toHaveTextContent('Click Me');
  });

  it('handles click events', () => {
    const handleClick = vi.fn();
    render(<Button onClick={handleClick}>Click Me</Button>);
    
    const button = screen.getByRole('button');
    button.click();
    
    expect(handleClick).toHaveBeenCalledOnce();
  });
});
```

### Common Testing Patterns

#### Testing Component Rendering

```javascript
it('renders component with props', () => {
  render(<MyComponent title="Test" />);
  expect(screen.getByText('Test')).toBeInTheDocument();
});
```

#### Testing User Interactions

```javascript
import { userEvent } from '@testing-library/user-event';

it('handles user input', async () => {
  const user = userEvent.setup();
  render(<SearchBox />);
  
  const input = screen.getByRole('textbox');
  await user.type(input, 'search query');
  
  expect(input).toHaveValue('search query');
});
```

#### Testing Async Operations

```javascript
it('loads data asynchronously', async () => {
  render(<DataComponent />);
  
  // Wait for element to appear
  const data = await screen.findByText('Loaded Data');
  expect(data).toBeInTheDocument();
});
```

#### Testing Router Components

```javascript
import { BrowserRouter } from 'react-router-dom';

it('renders route component', () => {
  render(
    <BrowserRouter>
      <MyRoutedComponent />
    </BrowserRouter>
  );
  expect(screen.getByText('Page Content')).toBeInTheDocument();
});
```

## Coverage Configuration

Coverage is configured in `vitest.config.js`:

```javascript
coverage: {
  provider: 'v8',
  reporter: ['text', 'json', 'html'],
  exclude: [
    'node_modules/',
    'tests/',
    '*.config.js',
    'dist/',
  ],
}
```

### Viewing Coverage Reports

After running `npm run test:coverage`, open:
```
frontend/coverage/index.html
```

### Coverage Goals

- **Overall Coverage**: Target 80%+ for critical paths
- **Components**: 90%+ for reusable UI components
- **Utils**: 100% for utility functions
- **Pages**: 70%+ for page components

## CI/CD Integration

Tests run automatically in GitHub Actions on:
- Every pull request
- Every push to `main` or `develop`
- Both Node.js 20.x and 22.x

### Workflow Steps

1. Install dependencies (with caching)
2. Run ESLint
3. Build production bundle
4. **Run tests** (fails PR if tests fail)
5. Upload build artifacts

### Current Test Results

```
Test Files  2 passed (2)
     Tests  4 passed (4)
  Duration  ~1.2s
```

## Best Practices

### 1. Test Behavior, Not Implementation

**Don't test:**
```javascript
expect(component.state.isOpen).toBe(true);
```

**Do test:**
```javascript
expect(screen.getByRole('dialog')).toBeVisible();
```

### 2. Use Semantic Queries

Priority order:
1. `getByRole` - Most accessible
2. `getByLabelText` - Form elements
3. `getByPlaceholderText` - Input placeholders
4. `getByText` - Content
5. `getByTestId` - Last resort

### 3. Test Accessibility

```javascript
it('is keyboard accessible', () => {
  render(<Button>Submit</Button>);
  const button = screen.getByRole('button');
  
  button.focus();
  expect(button).toHaveFocus();
});
```

### 4. Mock External Dependencies

```javascript
import { vi } from 'vitest';

vi.mock('@/services/api', () => ({
  fetchData: vi.fn(() => Promise.resolve({ data: 'test' }))
}));
```

### 5. Clean Up After Tests

```javascript
import { cleanup } from '@testing-library/react';
import { afterEach } from 'vitest';

afterEach(() => {
  cleanup();
});
```

## Common Issues & Solutions

### Issue: Tests fail with "Cannot find module"

**Solution:** Check path aliases in `vitest.config.js`:
```javascript
resolve: {
  alias: {
    '@': path.resolve(__dirname, './src'),
  },
}
```

### Issue: Router tests fail

**Solution:** Wrap component in Router:
```javascript
import { BrowserRouter } from 'react-router-dom';

render(
  <BrowserRouter>
    <Component />
  </BrowserRouter>
);
```

### Issue: Async tests timeout

**Solution:** Increase timeout:
```javascript
it('async test', async () => {
  // test code
}, 10000); // 10 second timeout
```

## Adding Tests for New Components

1. **Create test file** next to component:
   ```
   src/components/MyComponent.jsx
   tests/unit/MyComponent.test.jsx
   ```

2. **Write tests** for:
   - Rendering with different props
   - User interactions
   - Edge cases
   - Accessibility

3. **Run tests locally**:
   ```bash
   npm run test:watch
   ```

4. **Check coverage**:
   ```bash
   npm run test:coverage
   ```

5. **Commit** when all tests pass

## Test Examples

### Testing Dashboard Component

```javascript
describe('Dashboard', () => {
  it('displays CPU usage chart', () => {
    render(<Dashboard />);
    expect(screen.getByText('CPU Usage')).toBeInTheDocument();
  });

  it('shows heartbeat indicators', () => {
    render(<Dashboard />);
    const heartbeats = screen.getAllByRole('status');
    expect(heartbeats).toHaveLength(12);
  });
});
```

### Testing Form Components

```javascript
describe('LoginForm', () => {
  it('submits with valid credentials', async () => {
    const onSubmit = vi.fn();
    render(<LoginForm onSubmit={onSubmit} />);
    
    await userEvent.type(
      screen.getByLabelText('Email'),
      'user@example.com'
    );
    await userEvent.type(
      screen.getByLabelText('Password'),
      'password123'
    );
    await userEvent.click(screen.getByRole('button', { name: 'Log In' }));
    
    expect(onSubmit).toHaveBeenCalledWith({
      email: 'user@example.com',
      password: 'password123'
    });
  });
});
```

## Resources

- [Vitest Documentation](https://vitest.dev/)
- [React Testing Library](https://testing-library.com/react)
- [Testing Library Queries](https://testing-library.com/docs/queries/about)
- [Jest DOM Matchers](https://github.com/testing-library/jest-dom)

## Next Steps

1. Add tests for existing components:
   - [ ] Button component (started)
   - [ ] Card component
   - [ ] Dashboard page
   - [ ] Login page
   - [ ] Site management pages

2. Set up pre-commit hooks to run tests

3. Add E2E tests with Playwright

4. Configure coverage thresholds

---

**Status:** Testing infrastructure complete and passing in CI/CD

**Last Updated:** October 18, 2025

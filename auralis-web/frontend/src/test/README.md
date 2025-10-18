# Auralis Frontend Test Suite

Complete testing infrastructure for the Auralis web frontend using Vitest and React Testing Library.

## Quick Start

```bash
# Run all tests in watch mode
npm test

# Run tests once (CI mode)
npm run test:run

# Run tests with UI
npm run test:ui

# Run tests with coverage report
npm run test:coverage

# Run specific test file
npm test -- Sidebar.test.tsx

# Run tests matching a pattern
npm test -- --grep "player"
```

## Test Structure

```
src/
├── test/
│   ├── setup.ts              # Global test setup (mocks, polyfills)
│   ├── test-utils.tsx        # Custom render with providers
│   ├── mocks/
│   │   ├── api.ts           # API mock utilities & mock data
│   │   └── websocket.ts     # WebSocket mock utilities
│   └── README.md            # This file
├── components/
│   ├── __tests__/           # Component tests
│   │   ├── Sidebar.test.tsx
│   │   └── BottomPlayerBar.test.tsx
│   └── ...
├── hooks/
│   ├── __tests__/           # Hook tests
│   │   └── usePlayerAPI.test.ts
│   └── ...
└── shared/
    ├── __tests__/           # Shared component tests
    │   └── GradientButton.test.tsx
    └── ...
```

## Writing Tests

### Basic Component Test

```tsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@/test/test-utils'
import MyComponent from '../MyComponent'

describe('MyComponent', () => {
  it('renders correctly', () => {
    render(<MyComponent />)
    expect(screen.getByText('Hello')).toBeInTheDocument()
  })
})
```

### Testing with User Interactions

```tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@/test/test-utils'
import Button from '../Button'

describe('Button', () => {
  it('calls onClick when clicked', () => {
    const handleClick = vi.fn()
    render(<Button onClick={handleClick}>Click Me</Button>)

    fireEvent.click(screen.getByText('Click Me'))
    expect(handleClick).toHaveBeenCalledTimes(1)
  })
})
```

### Testing Async Behavior

```tsx
import { describe, it, expect, waitFor } from 'vitest'
import { render, screen } from '@/test/test-utils'
import AsyncComponent from '../AsyncComponent'

describe('AsyncComponent', () => {
  it('loads data asynchronously', async () => {
    render(<AsyncComponent />)

    expect(screen.getByText('Loading...')).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByText('Data loaded')).toBeInTheDocument()
    })
  })
})
```

### Testing Hooks

```tsx
import { describe, it, expect } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { useMyHook } from '../useMyHook'

describe('useMyHook', () => {
  it('returns initial value', () => {
    const { result } = renderHook(() => useMyHook())
    expect(result.current.value).toBe(0)
  })

  it('updates value', async () => {
    const { result } = renderHook(() => useMyHook())

    result.current.increment()

    await waitFor(() => {
      expect(result.current.value).toBe(1)
    })
  })
})
```

### Mocking API Calls

```tsx
import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@/test/test-utils'
import { mockFetch, mockApiEndpoint, mockTracks } from '@/test/mocks/api'
import TrackList from '../TrackList'

describe('TrackList', () => {
  beforeEach(() => {
    mockFetch()
    mockApiEndpoint('/api/tracks', mockTracks)
  })

  it('fetches and displays tracks', async () => {
    render(<TrackList />)

    await waitFor(() => {
      expect(screen.getByText('Test Track')).toBeInTheDocument()
    })
  })
})
```

### Mocking WebSocket

```tsx
import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@/test/test-utils'
import { mockWebSocket, mockWSMessages } from '@/test/mocks/websocket'
import PlayerStatus from '../PlayerStatus'

describe('PlayerStatus', () => {
  let mockWS: any

  beforeEach(() => {
    mockWS = mockWebSocket()
  })

  it('receives player state updates', async () => {
    render(<PlayerStatus />)

    // Simulate WebSocket message
    mockWS.simulateMessage(mockWSMessages.playerState({
      isPlaying: true,
      currentTrack: { title: 'Now Playing' }
    }))

    await waitFor(() => {
      expect(screen.getByText('Now Playing')).toBeInTheDocument()
    })
  })
})
```

## Best Practices

### ✅ Do

- **Use meaningful test descriptions** - Describe what the test does, not how
- **Test user behavior** - Test from the user's perspective
- **Use semantic queries** - Prefer `getByRole`, `getByLabelText` over `getByTestId`
- **Clean up after tests** - Use `beforeEach`/`afterEach` for setup/teardown
- **Mock external dependencies** - Mock API calls, WebSocket, timers
- **Test edge cases** - Empty states, errors, loading states
- **Keep tests isolated** - Each test should be independent

### ❌ Don't

- **Don't test implementation details** - Test behavior, not internal state
- **Don't use snapshots excessively** - They're brittle and hard to maintain
- **Don't make tests depend on each other** - Each test should run independently
- **Don't test third-party libraries** - Trust they work, test your usage
- **Don't ignore act() warnings** - They indicate async state updates

## Coverage Goals

Target coverage levels:
- **Components**: 80%+ coverage
- **Hooks**: 90%+ coverage
- **Utils**: 95%+ coverage
- **Overall**: 70%+ coverage

Critical paths that must be tested:
- Player controls and state management
- Library management (tracks, albums, artists)
- Processing job submission and progress
- WebSocket connection and real-time updates
- Error handling and edge cases

## Testing Philosophy

1. **Test behavior, not implementation** - Focus on what the user sees and does
2. **Write tests that give confidence** - Test the critical paths first
3. **Keep tests simple and readable** - Tests are documentation
4. **Fast feedback loop** - Tests should run quickly
5. **Maintainable tests** - Easy to update when code changes

## Common Patterns

### Testing Form Submission

```tsx
it('submits form with correct data', async () => {
  const onSubmit = vi.fn()
  render(<Form onSubmit={onSubmit} />)

  const input = screen.getByLabelText('Name')
  fireEvent.change(input, { target: { value: 'John' } })

  const submitButton = screen.getByRole('button', { name: /submit/i })
  fireEvent.click(submitButton)

  await waitFor(() => {
    expect(onSubmit).toHaveBeenCalledWith({ name: 'John' })
  })
})
```

### Testing Conditional Rendering

```tsx
it('shows error message when error occurs', () => {
  render(<Component error="Something went wrong" />)
  expect(screen.getByText('Something went wrong')).toBeInTheDocument()
})

it('hides error message when no error', () => {
  render(<Component error={null} />)
  expect(screen.queryByText('Something went wrong')).not.toBeInTheDocument()
})
```

### Testing List Rendering

```tsx
it('renders list of items', () => {
  const items = ['Item 1', 'Item 2', 'Item 3']
  render(<List items={items} />)

  items.forEach(item => {
    expect(screen.getByText(item)).toBeInTheDocument()
  })
})
```

## Debugging Tests

```bash
# Run tests in debug mode
npm test -- --inspect

# Run tests with verbose output
npm test -- --reporter=verbose

# Run a single test file
npm test -- Sidebar.test.tsx

# Update snapshots
npm test -- -u

# Clear cache and run tests
npm test -- --clearCache && npm test
```

## CI/CD Integration

```yaml
# Example GitHub Actions workflow
- name: Run tests
  run: npm run test:run

- name: Generate coverage
  run: npm run test:coverage

- name: Upload coverage
  uses: codecov/codecov-action@v3
```

## Resources

- [Vitest Documentation](https://vitest.dev/)
- [React Testing Library](https://testing-library.com/react)
- [Testing Library Queries](https://testing-library.com/docs/queries/about)
- [Common Testing Mistakes](https://kentcdodds.com/blog/common-mistakes-with-react-testing-library)

## Next Steps

1. **Add more component tests** - Aim for 80%+ component coverage
2. **Test integration flows** - Multi-component interactions
3. **Add E2E tests** - Consider Playwright/Cypress for full user flows
4. **Improve mock data** - Make mocks more realistic
5. **Add visual regression tests** - Consider Chromatic/Percy

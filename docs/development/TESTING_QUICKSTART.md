# Frontend Testing - Quick Start Guide

## TL;DR

A complete test suite has been set up for the Auralis web frontend.

```bash
cd auralis-web/frontend

# Run tests in watch mode
npm test

# Run tests once
npm run test:run

# Run tests with UI
npm run test:ui

# Generate coverage report
npm run test:coverage
```

## What's Available

### ✅ Testing Infrastructure
- **Vitest** - Fast, modern test runner
- **React Testing Library** - Component testing
- **Mock utilities** - API & WebSocket mocks
- **Example tests** - 4 working test files with 46+ tests
- **Complete documentation** - See `auralis-web/frontend/src/test/README.md`

### 📁 File Structure
```
auralis-web/frontend/
├── src/test/
│   ├── setup.ts              # Global mocks & setup
│   ├── test-utils.tsx        # Custom render function
│   ├── README.md             # Full testing guide
│   ├── TEMPLATE.test.tsx     # Copy this for new tests
│   └── mocks/
│       ├── api.ts            # Mock fetch, API data
│       └── websocket.ts      # Mock WebSocket
├── src/components/__tests__/
│   ├── Sidebar.test.tsx
│   └── BottomPlayerBar.test.tsx
├── src/hooks/__tests__/
│   └── usePlayerAPI.test.ts
└── src/shared/__tests__/
    └── GradientButton.test.tsx
```

## Quick Examples

### Test a Component

```tsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@/test/test-utils'
import MyComponent from '../MyComponent'

describe('MyComponent', () => {
  it('renders text', () => {
    render(<MyComponent />)
    expect(screen.getByText('Hello')).toBeInTheDocument()
  })

  it('handles click', () => {
    const onClick = vi.fn()
    render(<MyComponent onClick={onClick} />)

    fireEvent.click(screen.getByRole('button'))
    expect(onClick).toHaveBeenCalled()
  })
})
```

### Test a Hook

```tsx
import { renderHook, waitFor } from '@testing-library/react'
import { useMyHook } from '../useMyHook'

describe('useMyHook', () => {
  it('returns initial value', () => {
    const { result } = renderHook(() => useMyHook())
    expect(result.current.value).toBe(0)
  })
})
```

### Mock an API

```tsx
import { mockFetch, mockApiEndpoint, mockTracks } from '@/test/mocks/api'

beforeEach(() => {
  mockFetch()
  mockApiEndpoint('/api/tracks', mockTracks)
})

it('fetches tracks', async () => {
  render(<TrackList />)

  await waitFor(() => {
    expect(screen.getByText('Test Track')).toBeInTheDocument()
  })
})
```

## Test Commands

| Command | Description |
|---------|-------------|
| `npm test` | Run in watch mode (auto-rerun on save) |
| `npm run test:run` | Run once (CI mode) |
| `npm run test:ui` | Open interactive UI |
| `npm run test:coverage` | Generate coverage report |
| `npm test -- MyTest` | Run specific test file |
| `npm test -- --grep "player"` | Run tests matching pattern |

## Path Aliases

Use `@/` to import from `src/`:

```tsx
// ✅ Good
import { render } from '@/test/test-utils'
import MyComponent from '@/components/MyComponent'

// ❌ Avoid
import { render } from '../../test/test-utils'
import MyComponent from '../../../components/MyComponent'
```

## Mock Data Available

All in `src/test/mocks/api.ts`:

- `mockTrack` - Single track
- `mockTracks` - Array of tracks
- `mockAlbum` - Album data
- `mockAlbums` - Array of albums
- `mockArtist` - Artist data
- `mockPlaylist` - Playlist data
- `mockPlayerState` - Player state
- `mockProcessingJob` - Processing job
- `mockLibraryStats` - Library statistics

## Common Patterns

### Test Form Submission
```tsx
it('submits form', async () => {
  const onSubmit = vi.fn()
  render(<Form onSubmit={onSubmit} />)

  fireEvent.change(screen.getByLabelText('Name'), {
    target: { value: 'John' }
  })
  fireEvent.click(screen.getByRole('button', { name: /submit/i }))

  await waitFor(() => {
    expect(onSubmit).toHaveBeenCalledWith({ name: 'John' })
  })
})
```

### Test Loading State
```tsx
it('shows loading', () => {
  render(<Component loading={true} />)
  expect(screen.getByText(/loading/i)).toBeInTheDocument()
})
```

### Test Error State
```tsx
it('shows error', () => {
  render(<Component error="Failed" />)
  expect(screen.getByText('Failed')).toBeInTheDocument()
})
```

### Test Conditional Render
```tsx
it('hides when empty', () => {
  render(<List items={[]} />)
  expect(screen.getByText(/no items/i)).toBeInTheDocument()
})
```

## Documentation

- **Complete Guide**: [auralis-web/frontend/src/test/README.md](auralis-web/frontend/src/test/README.md)
- **Test Template**: [auralis-web/frontend/src/test/TEMPLATE.test.tsx](auralis-web/frontend/src/test/TEMPLATE.test.tsx)
- **Setup Summary**: [auralis-web/frontend/TEST_SUITE_SUMMARY.md](auralis-web/frontend/TEST_SUITE_SUMMARY.md)

## Best Practices

✅ **Do:**
- Test user behavior (what users see/do)
- Use semantic queries (`getByRole`, `getByLabelText`)
- Mock external dependencies
- Test edge cases
- Keep tests simple

❌ **Don't:**
- Test implementation details
- Use excessive snapshots
- Make tests depend on each other
- Test third-party libraries
- Ignore warnings

## Current Status

- ✅ Test infrastructure fully configured
- ✅ 4 example test files created
- ✅ Mock utilities for API & WebSocket
- ✅ Path aliases configured
- ✅ TypeScript support enabled
- ⚠️ Some example tests have warnings (fixable)
- 📝 Ready for you to add more tests!

## Next Steps

1. **Write tests for your components** - Copy TEMPLATE.test.tsx
2. **Aim for 70%+ coverage** - Run `npm run test:coverage`
3. **Fix warnings in example tests** - Improve async handling
4. **Add integration tests** - Test multi-component flows
5. **Set up CI/CD** - Run tests on every commit

## Need Help?

- Read [src/test/README.md](auralis-web/frontend/src/test/README.md) for detailed examples
- Copy [TEMPLATE.test.tsx](auralis-web/frontend/src/test/TEMPLATE.test.tsx) for new tests
- Check example tests for reference patterns
- Visit [Vitest Docs](https://vitest.dev/) or [Testing Library](https://testing-library.com/react)

---

**Status: ✅ Ready to Test**

The test suite is fully functional and ready for development!

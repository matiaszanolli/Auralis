# Frontend Testing Commands - Cheat Sheet

**Quick reference for running frontend tests in Auralis**

---

## Basic Commands

```bash
# Run all tests (interactive watch mode)
npm test

# Run all tests once and exit
npm run test:run

# Run tests with UI (Vitest UI)
npm run test:ui

# Run tests in watch mode
npm run test:watch

# Generate coverage report
npm run test:coverage
```

---

## Running Specific Tests

```bash
# Run specific test file
npm test library-workflow.test.tsx

# Run all integration tests
npm test -- --testPathPattern=integration

# Run all API integration tests
npm test -- --testPathPattern=api-integration

# Run tests matching pattern
npm test player-controls
```

---

## Development Workflow

```bash
# Morning: Check test status
npm run test:run

# During development: Watch mode
npm test

# Before commit: Run all tests + coverage
npm run test:run && npm run test:coverage

# Check coverage report
open coverage/index.html  # macOS
xdg-open coverage/index.html  # Linux
```

---

## Debugging Tests

```bash
# Run tests with debug output
npm test -- --reporter=verbose

# Run single test file with debug
npm test library-workflow.test.tsx -- --reporter=verbose

# Run tests in UI mode for debugging
npm run test:ui
```

---

## Coverage Commands

```bash
# Generate coverage report (HTML + JSON + text)
npm run test:coverage

# View coverage in browser
open coverage/index.html  # macOS
xdg-open coverage/index.html  # Linux

# Coverage report location
ls -la coverage/
```

---

## CI/CD Commands

```bash
# Run tests in CI mode (no watch, single run)
npm run test:run

# Generate coverage for CI
npm run test:coverage

# Exit with error if tests fail
npm run test:run || exit 1
```

---

## Test Organization

```
src/test/
├── integration/              # Component integration tests (100 tests)
│   ├── library-workflow.test.tsx
│   ├── search-filter-play.test.tsx
│   ├── player-controls.test.tsx
│   ├── enhancement-panel.test.tsx
│   └── artwork-management.test.tsx
├── api-integration/          # API integration tests (100 tests)
│   ├── mock-responses.test.tsx
│   ├── error-handling.test.tsx
│   ├── loading-states.test.tsx
│   ├── pagination.test.tsx
│   └── websocket-updates.test.tsx
├── mocks/
│   ├── server.ts             # MSW server setup
│   ├── handlers.ts           # API endpoint mocks
│   ├── api.ts                # Mock data
│   └── websocket.ts          # WebSocket mock
├── utils/
│   └── test-helpers.ts       # Test utility functions
├── setup.ts                  # Test environment setup
└── test-utils.tsx            # Custom render with providers
```

---

## Common Test Patterns

### Run tests for specific component
```bash
# Player tests
npm test player

# Enhancement tests
npm test enhancement

# Library tests
npm test library
```

### Run tests by category
```bash
# Integration tests only
npm test -- --testPathPattern=integration

# API tests only
npm test -- --testPathPattern=api-integration

# Unit tests only
npm test -- --testPathPattern=__tests__
```

### Run failed tests only
```bash
# Re-run only failed tests from last run
npm test -- --changed
```

---

## Performance & Optimization

```bash
# Run tests in parallel (default)
npm test

# Run tests sequentially (for debugging)
npm test -- --no-parallel

# Limit concurrent test files
npm test -- --maxConcurrency=5
```

---

## Documentation

- **Full Testing Plan:** `docs/testing/FRONTEND_INTEGRATION_TESTS_PLAN.md` (1,773 lines)
- **Quick Start Guide:** `docs/testing/FRONTEND_TESTING_QUICK_START.md` (398 lines)
- **Testing Guidelines:** `docs/development/TESTING_GUIDELINES.md` (mandatory reading)

---

## Quick Setup (New Developer)

```bash
# 1. Install dependencies
cd auralis-web/frontend
npm install

# 2. Install MSW (if not already installed)
npm install msw --save-dev
npx msw init public/ --save

# 3. Run tests to verify setup
npm test

# 4. Generate coverage baseline
npm run test:coverage
```

---

## Troubleshooting

### Tests timing out
```bash
# Increase timeout in test
await waitFor(() => {
  expect(screen.getByText('Result')).toBeInTheDocument()
}, { timeout: 5000 })
```

### Port conflicts
```bash
# Kill processes on test port
lsof -ti:3000 | xargs kill -9
```

### Clear test cache
```bash
# Clear Vitest cache
rm -rf node_modules/.vitest
npm test
```

### MSW issues
```bash
# Reinstall MSW
npm uninstall msw
npm install msw --save-dev
npx msw init public/ --save
```

---

## Key Test Files

**Setup:**
- `src/test/setup.ts` - Global test setup (mocks, MSW server)
- `src/test/test-utils.tsx` - Custom render with providers
- `vite.config.ts` - Vitest configuration

**Mocks:**
- `src/test/mocks/server.ts` - MSW server
- `src/test/mocks/handlers.ts` - API endpoint handlers
- `src/test/mocks/api.ts` - Mock data (tracks, albums, etc.)
- `src/test/mocks/websocket.ts` - WebSocket mock

**Templates:**
- `src/test/TEMPLATE.test.tsx` - Test template
- `src/test/README.md` - Testing documentation

---

## Success Metrics

**Target:**
- Total tests: 245 → 445 (200 new integration tests)
- Pass rate: 95.5% → 98%+
- Runtime: < 30 seconds total
- Coverage: 80%+ (components), 85%+ (services)

**Current Status:**
- Total tests: 245
- Pass rate: 95.5% (234 passing, 11 failing)
- Failing: Gapless playback tests (needs investigation)

---

## Daily Workflow Example

```bash
# Morning: Check status
npm run test:run

# Start development
npm test  # Watch mode

# Before lunch: Commit progress
npm run test:run && git commit -am "feat: add player control tests"

# Before going home: Final check
npm run test:coverage
git push
```

---

## Resources

- Vitest Docs: https://vitest.dev/
- Testing Library: https://testing-library.com/docs/react-testing-library/intro/
- MSW Docs: https://mswjs.io/docs/
- React Testing Best Practices: https://kentcdodds.com/blog/common-mistakes-with-react-testing-library

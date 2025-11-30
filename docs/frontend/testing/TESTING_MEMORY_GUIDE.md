# Frontend Testing - Memory Management Guide

## ⚡ TL;DR

**Use this command to run all frontend tests without running out of memory:**

```bash
npm run test:memory
```

That's it! The memory issue is fixed. Tests complete in ~70 seconds.

---

## The Problem (Was)

Frontend tests were crashing with out-of-memory errors because:
- 27,000+ lines of test code in 60+ test files
- Inadequate garbage collection between tests
- jsdom memory accumulation
- Mock handler memory leaks

**Status:** ✅ FIXED with optimized configuration

---

## The Solution

### For Full Test Runs
```bash
npm run test:memory              # All tests, memory-safe
npm run test:coverage:memory     # With coverage report
```

### For Development
```bash
npm test                         # Interactive watch mode
npm test -- CozyLibraryView      # Specific component
```

### For Single Files
```bash
npm test -- src/components/__tests__/BottomPlayerBarUnified.test.tsx
```

---

## What Changed

1. **vitest config** - Limited concurrent threads, added GC triggers
2. **test setup** - Aggressive cleanup after each test
3. **package.json** - Added memory-aware npm scripts

**Result:** Tests complete with stable ~300-400MB memory usage

---

## Why test:memory is Different

```bash
npm run test:run              # Single-threaded, minimal memory, FAST
npm run test:memory           # Optimized memory management, SAFE
```

**Use `test:memory` for:**
- Full test suite runs
- CI/CD pipelines
- Ensuring all tests pass

**Use `test:run` for:**
- Quick checks
- Specific test files
- Debug runs

---

## If Tests Still Fail

### Memory runs out
```bash
# Check system memory
free -m              # Linux
vm_stat              # macOS
tasklist /v          # Windows

# Increase heap size (in package.json scripts)
node --max-old-space-size=4096 ...  # 4GB instead of 2GB
```

### Tests timeout
```bash
# Increase timeout in vite.config.ts
testTimeout: 60000  // 60 seconds instead of 30
```

### Mocking errors
```bash
# Fix: Replace jest with vi syntax
// OLD - Don't use
jest.mock()
jest.fn()

// NEW - Use this
vi.mock()
vi.fn()
```

---

## Memory Best Practices

When writing tests, follow these patterns:

```typescript
// ✅ GOOD - Proper cleanup
afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

// ❌ BAD - No cleanup
test('something', () => {
  render(<Component />)  // Never unmounted
})
```

```typescript
// ✅ GOOD - MSW handlers for API
const handlers = [
  http.get('/api/library/tracks', () => HttpResponse.json(...))
]
server.use(...handlers)

// ❌ BAD - Direct fetch mocking
global.fetch = jest.fn().mockResolvedValue(...)
```

```typescript
// ✅ GOOD - Wait for actual conditions
await waitFor(() => {
  expect(screen.getByText('Loaded')).toBeInTheDocument()
})

// ❌ BAD - Hardcoded delays
await new Promise(r => setTimeout(r, 1000))
```

---

## Test File Size Guidelines

| File Size | Action | Reason |
|-----------|--------|--------|
| < 300 lines | ✅ OK | Manageable, single test focus |
| 300-500 lines | ⚠️ Review | Consider splitting if many tests |
| 500+ lines | ❌ Split | Too large, memory issues, hard to maintain |

---

## Monitoring Memory During Tests

```bash
# Terminal 1: Run tests
npm run test:memory

# Terminal 2: Monitor memory (Linux)
watch -n 1 'free -m'

# Terminal 2: Monitor memory (macOS)
watch 'vm_stat'
```

**Expected:** Memory stable, not continuously increasing

---

## Test Execution Timeline

```
Transform:   5s   (compiling TypeScript)
Setup:      16s   (loading modules, mocks)
Collect:   180s   (finding tests)
Tests:     182s   (running 1416 tests)
Environment: 32s  (jsdom cleanup)
────────────────
Total:     ~70s
```

---

## Troubleshooting

### "Out of Memory" error
```bash
# Solution 1: Use test:memory (default now)
npm run test:memory

# Solution 2: Increase memory manually
node --max-old-space-size=4096 node_modules/.bin/vitest run

# Solution 3: Run fewer tests at once
npm test -- src/components/__tests__
```

### Tests timeout
```bash
# Check for hardcoded delays in tests
grep -r "setTimeout" src/tests/

# Use waitFor instead
npm test -- --reporter=verbose  # See which test times out
```

### "jest.fn is not a function"
```bash
# Fix: Replace jest with vi
// OLD
jest.fn()
jest.mock()

// NEW
vi.fn()
vi.mock()
```

---

## FAQ

**Q: Why are tests still failing if memory is fixed?**
A: Memory is fixed, but test mocking has issues (jest → vi syntax). These are separate problems.

**Q: How long should tests take?**
A: ~70 seconds for full 1416 test suite. Single files: <5 seconds.

**Q: Can I run tests in parallel?**
A: Yes, but limited to 2 threads to prevent memory issues. Increase with caution.

**Q: What if I need to use jest.fn()?**
A: Use `vi.fn()` instead. Vitest provides jest-compatible API.

---

## Reference

- [Full Memory Fix Documentation](../../docs/guides/FRONTEND_TEST_MEMORY_IMPROVEMENTS_APPLIED.md)
- [Initial Memory Analysis](../../docs/guides/FRONTEND_TEST_MEMORY_FIX.md)
- [CLAUDE.md - Frontend Testing](../../CLAUDE.md#frontend-testing)
- [Vitest Configuration](https://vitest.dev/config/)

# Frontend Test Mocking Issues - Fix Guide

## Status: ✅ Memory Issue RESOLVED | ⚠️ Test Mocking Issues Remain

**Good news:** Tests no longer run out of memory! All 1416 tests complete in ~65 seconds.

**What remains:** 626 failing tests due to incorrect mocking syntax and missing handlers.

---

## Test Results Summary

```
Test Files:  35 failed | 25 passed (60 files)
Tests:       626 failed | 790 passed (1416 total)
Duration:    65.89 seconds (STABLE, no OOM)
Status:      ✅ No out-of-memory errors
```

---

## Root Causes of Failures

### 1. Jest Syntax Used Instead of Vitest ❌

**Problem:** Tests using `jest.` API instead of `vi.` API

```typescript
// ❌ WRONG - Jest syntax (doesn't work with Vitest)
jest.clearAllMocks()
jest.fn()
jest.mock()
jest.spyOn()

// ✅ CORRECT - Vitest syntax
vi.clearAllMocks()
vi.fn()
vi.mock()
vi.spyOn()
```

**Affected Files (estimate 400+ tests):**
- `src/components/track/__tests__/TrackCard.test.tsx`
- `src/services/__tests__/settingsService.test.ts`
- Other service and component test files

**Impact:**
```
TypeError: useTrackSelection.mockReturnValue is not a function
TypeError: global.fetch.mockResolvedValueOnce is not a function
```

### 2. Missing MSW Request Handlers ❌

**Problem:** Tests make API calls but handlers aren't registered

```typescript
// ❌ WRONG - No handler, test fails
test('fetch settings', async () => {
  const result = await fetch('/api/settings')
})

// ✅ CORRECT - Handler defined
test('fetch settings', async () => {
  server.use(
    http.get('/api/settings', () => HttpResponse.json({...}))
  )
  const result = await fetch('/api/settings')
})
```

**Affected Files (estimate 76+ tests):**
- `src/services/__tests__/settingsService.test.ts`
- `src/tests/integration/library-management.test.tsx`
- Other integration tests

**Impact:**
```
[MSW] Warning: intercepted a request without a matching request handler:
  • GET /api/settings
```

### 3. WebSocket State Management After Teardown ❌

**Problem:** WebSocket listeners updating state after test cleanup

```
ReferenceError: window is not defined
 ❯ getCurrentEventPriority node_modules/react-dom/cjs/react-dom.development.js:10993:22
 ❯ dispatchSetState node_modules/react-dom/cjs/react-dom.development.js:16648:14
 ❯ WebSocketManager.onError src/contexts/WebSocketContext.tsx:262:9
```

**Root Cause:** WebSocket error/close handlers trying to update React state after jsdom teardown

**Solution:** Cancel pending WebSocket callbacks before test cleanup

---

## Fixes Required

### Priority 1: Fix Jest → Vitest Syntax (400+ tests)

**Task 1a:** Update `settingsService.test.ts`
```typescript
// Find and replace
jest.clearAllMocks()        → vi.clearAllMocks()
jest.fn()                    → vi.fn()
jest.mock()                  → vi.mock()
jest.spyOn()                 → vi.spyOn()
(Hook as jest.Mock)          → vi.mocked(Hook)
```

**Task 1b:** Update `TrackCard.test.tsx`
```typescript
// Replace beforeEach mock setup
beforeEach(() => {
  // OLD
  jest.clearAllMocks()
  (useTrackSelection as jest.Mock).mockReturnValue(...)

  // NEW
  vi.clearAllMocks()
  vi.mocked(useTrackSelection).mockReturnValue(...)
})
```

**Task 1c:** Grep and replace in all test files
```bash
cd auralis-web/frontend

# Find all jest references
grep -r "jest\." src --include="*.test.tsx" --include="*.test.ts"

# Replace jest with vi (careful - check each one)
sed -i 's/jest\.fn()/vi.fn()/g' src/**/*.test.tsx
sed -i 's/jest\.mock(/vi.mock(/g' src/**/*.test.tsx
sed -i 's/jest\.spyOn(/vi.spyOn(/g' src/**/*.test.tsx
sed -i 's/jest\.clearAllMocks()/vi.clearAllMocks()/g' src/**/*.test.tsx
```

### Priority 2: Add Missing MSW Handlers (76+ tests)

**Task 2a:** Check current handlers
```bash
grep -r "http.get" src/test/mocks/
grep -r "http.post" src/test/mocks/
```

**Task 2b:** Add missing endpoint handlers
```typescript
// In src/test/mocks/handlers.ts or relevant file
http.get('/api/settings', () => HttpResponse.json({...}))
http.get('/api/playlists', () => HttpResponse.json({...}))
http.post('/api/settings', () => HttpResponse.json({success: true}))
http.get('/api/library/tracks', () => HttpResponse.json({...}))
```

**Task 2c:** Check test output for unmocked endpoints
```bash
npm run test:memory 2>&1 | grep "without a matching request handler"
```

### Priority 3: Fix WebSocket Cleanup (50+ tests)

**Problem:** WebSocket listeners fire after jsdom is torn down

**Solution:** Disconnect WebSocket before cleanup
```typescript
// In test setup or individual tests
afterEach(async () => {
  // Disconnect any WebSocket connections
  if (window.WebSocket.instance) {
    window.WebSocket.instance.close()
  }

  // Clear pending timers
  vi.clearAllTimers()

  // Standard cleanup
  cleanup()
  vi.clearAllMocks()
})
```

---

## Implementation Order

### Week 1: Jest → Vitest Fixes
1. **Day 1-2:** Fix `settingsService.test.ts` (43 tests)
2. **Day 3:** Fix `TrackCard.test.tsx` (28 tests)
3. **Day 4:** Fix remaining service tests (60+ tests)
4. **Day 5:** Grep-replace jest references in all files

**Expected result:** ~300 tests pass, ~326 still failing (MSW/WebSocket)

### Week 2: MSW Handler Fixes
1. **Day 1:** Identify missing endpoints (grep test output)
2. **Day 2-3:** Add handlers for each missing endpoint
3. **Day 4:** Test with full suite
4. **Day 5:** Document handler patterns

**Expected result:** ~400 tests pass, ~226 still failing (WebSocket)

### Week 3: WebSocket & Final Fixes
1. **Day 1-2:** Fix WebSocket teardown issues
2. **Day 3:** Fix remaining async/timing issues
3. **Day 4:** Full test run with verbose output
4. **Day 5:** Final cleanup and documentation

**Expected result:** 1400+ tests passing (99%+)

---

## Verification Process

### Step 1: Verify Memory is Fixed
```bash
npm run test:memory 2>&1 | grep "Test Files"
# Should show: Test Files  X failed | Y passed
# NOT: JavaScript heap out of memory
```

### Step 2: Monitor Failure Count
```bash
npm run test:memory 2>&1 | tail -20 | grep "Tests"
# Before fixes:  626 failed | 790 passed
# After fixes:   0 failed | 1416 passed (goal)
```

### Step 3: Check Error Types
```bash
npm run test:memory 2>&1 | grep "TypeError\|ReferenceError" | head -20
# Should decrease each iteration
```

---

## Quick Fix Examples

### Example 1: Fix Settings Service Test
```typescript
// BEFORE (jest syntax)
describe('SettingsService', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    global.fetch = jest.fn().mockResolvedValue({...})
  })

  test('getSettings', async () => {
    const result = await settingsService.getSettings()
    expect(jest.fn).toHaveBeenCalled()
  })
})

// AFTER (vi syntax + MSW)
describe('SettingsService', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    server.use(
      http.get('/api/settings', () =>
        HttpResponse.json({theme: 'dark'})
      )
    )
  })

  test('getSettings', async () => {
    const result = await settingsService.getSettings()
    expect(result.theme).toBe('dark')
  })
})
```

### Example 2: Fix Hook Mock
```typescript
// BEFORE (jest syntax)
import { useLibraryQuery } from '@hooks/useLibraryQuery'
jest.mock('@hooks/useLibraryQuery')
;(useLibraryQuery as jest.Mock).mockReturnValue({...})

// AFTER (vi syntax)
import { useLibraryQuery } from '@hooks/useLibraryQuery'
vi.mock('@hooks/useLibraryQuery')
vi.mocked(useLibraryQuery).mockReturnValue({...})
```

---

## Testing the Fixes

```bash
# Run after each fix batch
cd auralis-web/frontend

# Test specific file
npm test -- src/services/__tests__/settingsService.test.ts

# Test all services
npm test -- src/services/__tests__/

# Full test suite (after all fixes)
npm run test:memory
```

---

## Expected Timeline

| Phase | Duration | Tests Fixed | Total Passing |
|-------|----------|------------|-------------|
| Initial (before) | - | 0 | 790 |
| Jest → Vi fixes | 5 days | 300 | 1090 |
| MSW handlers | 5 days | 150 | 1240 |
| WebSocket cleanup | 5 days | 150 | 1390 |
| Final polish | 2 days | 26 | 1416 |

---

## References

- [Vitest Migration from Jest](https://vitest.dev/guide/migration.html)
- [MSW Request Handlers](https://mswjs.io/docs/basics/request-handler)
- [React Testing Library Best Practices](https://testing-library.com/docs/react-testing-library/intro)

---

## Key Takeaway

✅ **Memory issue is SOLVED** - tests run without OOM errors
⚠️ **Mocking issues remain** - requires syntax updates and handler additions

The good news: These are straightforward mechanical fixes that can be systematically addressed file-by-file.


# Frontend Integration Tests

Comprehensive integration tests organized by feature modules to improve maintainability, reduce memory footprint, and enable selective test runs.

## Directory Structure

```
tests/integration/
├── player-controls/              # Player control & playback tests
│   ├── player-controls.test.tsx         # Main player functionality
│   ├── player-bar-v2-connected.test.tsx # Player UI bar integration
│   └── progress-bar-monitoring.test.tsx # Progress tracking
│
├── library-management/           # Library browsing & management
│   ├── library-management.test.tsx      # Core library operations
│   ├── metadata.test.tsx                # Metadata editing & validation (13 tests)
│   ├── artwork.test.tsx                 # Album artwork management (7 tests)
│   ├── search-filter-accessibility.test.tsx # Search, filter, sort (1148 LOC - priority for splitting)
│   └── playlist-management.test.tsx     # Playlist operations
│
├── streaming-audio/              # Audio streaming & buffering
│   └── streaming-mse.test.tsx          # Media Source Extensions (882 LOC)
│
├── websocket-realtime/           # Real-time WebSocket updates
│   └── websocket-realtime.test.tsx     # Connection & state sync (811 LOC)
│
├── enhancement-processing/       # Audio enhancement parameters
│   └── enhancement-pane.test.tsx       # Enhancement controls
│
├── error-handling/               # Error scenarios & recovery
│   └── error-handling.test.tsx         # API error handling (688 LOC)
│
├── performance/                  # Performance & optimization tests
│   └── performance-large-libraries.test.tsx # Pagination, scrolling, caching (1114 LOC - priority for splitting)
│
└── mocks/                        # MSW server & mock data
    ├── server.ts                 # MSW server setup
    ├── handlers.ts               # 80+ API endpoint mocks (43KB)
    ├── mockData.ts               # Mock tracks, albums, artists
    ├── api.ts                    # API constants
    └── websocket.ts              # WebSocket mocks
```

## Test Organization Benefits

### ✅ Reduced Memory Footprint
- **Before**: One large 1338-line test file kept entire test suite in memory
- **After**: Split into focused `metadata.test.tsx` (532 LOC) + `artwork.test.tsx` (382 LOC)
- **Result**: ~50% reduction in memory per test file

### ✅ Selective Test Execution
Run only relevant feature tests without loading entire integration suite:

```bash
# Run only player control tests
npm run test:player

# Run only library management tests
npm run test:library

# Run all integration tests
npm run test:integration

# Watch specific feature tests
npm test -- src/tests/integration/library-management/
```

### ✅ Better Test Discovery
- Features organized hierarchically
- Test files co-located with feature area
- Clear naming convention: `feature-name.test.tsx`

### ✅ Easier CI/CD Parallelization
Run independent feature test suites in parallel:

```bash
# In CI pipeline
npm run test:player & npm run test:library & npm run test:streaming & ...
```

## Feature-Specific Test Runners

New npm scripts for running feature-specific tests:

```json
{
  "test:player": "vitest run src/tests/integration/player-controls/",
  "test:library": "vitest run src/tests/integration/library-management/",
  "test:streaming": "vitest run src/tests/integration/streaming-audio/",
  "test:websocket": "vitest run src/tests/integration/websocket-realtime/",
  "test:enhancement": "vitest run src/tests/integration/enhancement-processing/",
  "test:errors": "vitest run src/tests/integration/error-handling/",
  "test:performance": "vitest run src/tests/integration/performance/",
  "test:integration": "vitest run src/tests/integration/"
}
```

## Large Test Files (Priority for Future Refactoring)

These files should be split further to reduce memory usage:

### 1. `search-filter-accessibility.test.tsx` (1148 LOC)
**Current structure** (5 describe blocks):
- Advanced Search (5 tests, ~225 LOC)
- Filter Combinations (5 tests, ~245 LOC)
- Sort Operations (5 tests, ~255 LOC)
- Keyboard Accessibility (3 tests, ~90 LOC)
- Screen Reader Support (2 tests, ~30 LOC)

**Recommended split**:
- `search.test.tsx` - Search functionality only
- `filter.test.tsx` - Filter combinations
- `sort.test.tsx` - Sort operations
- `accessibility.test.tsx` - Keyboard & screen reader

### 2. `performance-large-libraries.test.tsx` (1114 LOC)
**Current structure** (5 describe blocks):
- Pagination Performance (5 tests, ~325 LOC)
- Virtual Scrolling (5 tests, ~145 LOC)
- Cache Efficiency (5 tests, ~287 LOC)
- Bundle Optimization (3 tests, ~72 LOC)
- Memory Management (2 tests, ~35 LOC)

**Recommended split**:
- `pagination.test.tsx` - Pagination tests
- `virtual-scrolling.test.tsx` - Virtual list tests
- `cache-efficiency.test.tsx` - Caching tests
- `bundle-size.test.tsx` - Bundle optimization
- `memory-management.test.tsx` - Memory tests

### 3. `streaming-mse.test.tsx` (882 LOC)
- Consider splitting MSE initialization from playback scenarios

### 4. `websocket-realtime.test.tsx` (811 LOC)
- Consider splitting connection lifecycle from message handling

## Test Counts by Feature

| Feature | Files | Tests | LOC |
|---------|-------|-------|-----|
| Player Controls | 3 | ~35 | ~680 |
| Library Management | 5 | ~65 | ~3,372* |
| Streaming Audio | 1 | ~15 | ~882 |
| WebSocket | 1 | ~20 | ~811 |
| Enhancement | 1 | ~15 | ~TBD |
| Error Handling | 1 | ~15 | ~688 |
| Performance | 1 | ~20 | ~1,114 |
| **TOTAL** | **13** | **~185** | **~7,547** |

*includes refactored metadata.test.tsx and artwork.test.tsx

## Test Setup & Utilities

All integration tests use:

1. **Custom render()** from `@/test/test-utils`
   - Includes all required providers (Router, Theme, Enhancement, etc.)
   - NEVER use React Testing Library's render directly

2. **MSW Server** in `mocks/server.ts`
   - 80+ API endpoint mocks
   - Automatic handler reset between tests

3. **Test Helpers** in `test/utils/test-helpers.ts`
   - `waitForApiCall(endpoint, timeout)`
   - `waitForLoadingToFinish()`
   - And 10+ more async helpers

## Memory Optimization Tips

When running these tests:

### Option 1: Run Feature Tests Sequentially
```bash
npm run test:player
npm run test:library  # Waits for player tests to finish
npm run test:streaming
```

### Option 2: Use Memory Management Flag
```bash
NODE_ENV=test node --max-old-space-size=1024 --expose-gc \
  node_modules/.bin/vitest run src/tests/integration/library-management/
```

### Option 3: Run Individual Test Files
```bash
npm test -- src/tests/integration/library-management/metadata.test.tsx
npm test -- src/tests/integration/library-management/artwork.test.tsx
```

## Running Tests

### Development (Watch Mode)
```bash
# Watch all tests
npm test

# Watch specific feature
npm test -- src/tests/integration/library-management/

# Watch single test file
npm test -- metadata.test.tsx
```

### Single Run (CI/Local Verification)
```bash
# Run all integration tests
npm run test:integration

# Run specific feature
npm run test:library

# Run with coverage
npm run test:coverage
```

### Memory-Safe Full Test Suite
```bash
# Allocate 2GB heap for safety
npm run test:memory
```

## Future Improvements

1. **Further splitting** of large test files (1000+ LOC) per recommendations above
2. **Selective MSW handler loading** - Only load handlers needed for specific tests
3. **Test categorization** - Mark tests as critical vs. nice-to-have
4. **Performance baselines** - Track test execution time per feature
5. **Parallel test execution** - Run independent feature suites in CI with full parallelization

## Related Documentation

- [TESTING_GUIDELINES.md](../../../docs/development/TESTING_GUIDELINES.md) - Test quality standards
- [src/test/test-utils.tsx](../../test/test-utils.tsx) - Custom render & provider setup
- [src/test/mocks/](../../test/mocks/) - MSW handlers and mock data

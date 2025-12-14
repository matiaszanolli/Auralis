# Frontend Testing Strategy - Memory-Efficient Approach

**⚠️ CRITICAL**: Do NOT run `npm run test:memory` or `npm test` on full suite - causes system crash (2GB+ memory consumption)

## Memory Management for Tests

### The Problem
- Full test suite runs 500+ test files simultaneously
- Each test environment setup consumes ~10-20MB
- Total memory footprint: 2GB+
- System crash due to OOM (out of memory)

### The Solution
Run tests by category or specific files, never the full suite.

---

## Test Organization

### Phase 7 Tests (Queue Management)

**Location**: `src/components/player/__tests__`, `src/hooks/player/__tests__`, `src/utils/queue/__tests__`

| Test File | Size | Tests | Purpose |
|-----------|------|-------|---------|
| `queue_recommender.test.ts` | 424 lines | 33 | Recommendation engine |
| `queue_statistics.test.ts` | 450 lines | 31 | Analytics & quality |
| `queue_shuffler.test.ts` | 388 lines | 28 | Shuffle algorithms |
| `QueueSearchPanel.test.tsx` | 563 lines | 18 | Search UI component |
| `QueueStatisticsPanel.test.tsx` | 590 lines | 18 | Statistics UI |
| `QueueRecommendationsPanel.test.tsx` | 420 lines | 16 | Recommendations UI |
| `ShuffleModeSelector.test.tsx` | 321 lines | 15 | Shuffle selector UI |
| `useQueueSearch.test.ts` | 502 lines | 22 | Search hook |
| `useQueueStatistics.test.ts` | 359 lines | 16 | Statistics hook |
| `useQueueRecommendations.test.ts` | 392 lines | 16 | Recommendations hook |
| `Phase7Integration.test.tsx` | 447 lines | 16 | Integration tests |

**Total**: 150+ tests across 11 files (safe to run together)

### Other Player Tests

| Test File | Size | Tests |
|-----------|------|-------|
| `ProgressBar.test.tsx` | 893 lines | 28 |
| `PlaybackControls.test.tsx` | 680 lines | 24 |
| `TimeDisplay.test.tsx` | 610 lines | 20 |
| `QueuePanel.test.tsx` | 514 lines | 18 |
| `VolumeControl.test.tsx` | 465 lines | 16 |
| `TrackDisplay.test.tsx` | 459 lines | 15 |
| `BufferingIndicator.test.tsx` | 275 lines | 10 |

### Library Tests (Large - NOT RECOMMENDED)
- `AlbumDetailView.test.tsx` - 1006 lines (run alone)
- `CozyArtistList.test.tsx` - 777 lines (run alone)
- `CozyAlbumGrid.test.tsx` - 686 lines (run alone)
- `LibraryComponents.test.tsx` - 693 lines (run alone)
- `TrackList.test.tsx` - 680 lines (run alone)

### Integration Tests (Large - NOT RECOMMENDED)
- `performance-large-libraries.test.tsx` - 1116 lines (run alone)
- `streaming-mse.test.tsx` - 885 lines (run alone)
- `websocket-realtime.test.tsx` - 707 lines (run alone)

---

## Safe Testing Patterns

### ✅ DO - Safe Approaches

**Run Single Utility Tests** (safest)
```bash
# Run one utility test - 5-10 seconds
npx vitest run src/utils/queue/__tests__/queue_recommender.test.ts

# Run one component test - 5-10 seconds
npx vitest run src/components/player/__tests__/ShuffleModeSelector.test.tsx

# Run one hook test - 5-10 seconds
npx vitest run src/hooks/player/__tests__/useQueueSearch.test.ts
```

**Run Related Test Group** (safe)
```bash
# Run all Phase 7 utilities (~30 seconds, ~100MB memory)
npx vitest run 'src/utils/queue/__tests__/**/*.test.ts'

# Run all Phase 7 components (~40 seconds, ~150MB memory)
npx vitest run 'src/components/player/__tests__/**/*.test.tsx'

# Run all Phase 7 hooks (~30 seconds, ~120MB memory)
npx vitest run 'src/hooks/player/__tests__/**/*.test.ts'

# Run all Phase 7 tests together (~2 minutes, ~400MB memory)
npx vitest run \
  'src/utils/queue/__tests__/**/*.test.ts' \
  'src/components/player/__tests__/**/*.test.tsx' \
  'src/hooks/player/__tests__/**/*.test.ts'
```

**Run Integration Tests** (specific only)
```bash
# Run Phase 7 integration tests alone
npx vitest run src/components/player/__tests__/Phase7Integration.test.tsx

# Run performance tests alone
npx vitest run src/tests/integration/performance/
```

**Watch Mode** (development)
```bash
# Watch single file changes
npx vitest src/utils/queue/__tests__/queue_recommender.test.ts

# Watch directory changes
npx vitest 'src/utils/queue/__tests__/**'
```

### ❌ DON'T - Dangerous Approaches

```bash
# ❌ NEVER - Crashes system
npm run test:memory

# ❌ NEVER - Crashes system
npm test

# ❌ NEVER - Crashes system (too many files)
npx vitest run src/

# ❌ NEVER - Crashes system
npx vitest
```

---

## Memory-Efficient Test Execution

### Before Running Tests
1. Close unnecessary applications
2. Ensure at least 1GB free memory
3. Don't run other Node processes

### Monitoring Memory Usage
```bash
# Check available memory before test
free -h

# Run test with memory monitoring
watch -n 1 'free -h && ps aux | grep node'
```

### If Test Hangs
```bash
# Kill any stuck test processes
pkill -9 node
pkill -9 vitest

# Verify no processes remain
ps aux | grep -E "node|vitest"
```

---

## CI/CD Pipeline Strategy

### For Automated Testing
```bash
# Tier 1: Fast unit tests (~1 minute)
npx vitest run src/utils/queue/__tests__/queue_*.test.ts

# Tier 2: Hook tests (~1 minute)
npx vitest run src/hooks/player/__tests__/useQueue*.test.ts

# Tier 3: Component tests (~2 minutes)
npx vitest run src/components/player/__tests__/Queue*.test.tsx

# Tier 4: Integration tests (~1 minute)
npx vitest run src/components/player/__tests__/Phase7Integration.test.tsx

# Total: ~5 minutes, safe memory usage
```

### For Development
```bash
# Quick sanity check (< 30 seconds)
npx vitest run \
  src/utils/queue/__tests__/queue_recommender.test.ts \
  src/components/player/__tests__/ShuffleModeSelector.test.tsx

# Full Phase 7 validation (~2 minutes)
npx vitest run \
  'src/utils/queue/__tests__/**/*.test.ts' \
  'src/components/player/__tests__/Queue*.test.tsx' \
  'src/hooks/player/__tests__/useQueue*.test.ts'
```

---

## Phase 7 Test Execution Times

| Command | Time | Memory | Safety |
|---------|------|--------|--------|
| Single test file | ~5s | ~50MB | ✅ Safe |
| Single category | ~20s | ~150MB | ✅ Safe |
| Phase 7 utilities + hooks | ~40s | ~250MB | ✅ Safe |
| Phase 7 all (utilities + hooks + components) | ~90s | ~400MB | ✅ Safe |
| Full player tests | ~3 min | ~800MB | ⚠️ Risky |
| Entire suite | crash | 2GB+ | ❌ Fatal |

---

## File Splitting Recommendations

If individual test files grow beyond 600 lines, split them:

### Example: Split Large Test File
```
queue_recommender.test.ts (424 lines) ✅ OK, keep as-is

queue_statistics.test.ts (450 lines) ✅ OK, keep as-is

QueueStatisticsPanel.test.tsx (590 lines) - CONSIDER SPLITTING:
├── QueueStatisticsPanel.basic.test.tsx (200 lines)
│   ├── Rendering tests
│   ├── Props handling
│   └── Empty state
├── QueueStatisticsPanel.analytics.test.tsx (200 lines)
│   ├── Statistics display
│   ├── Formatting
│   └── Calculations
└── QueueStatisticsPanel.quality.test.tsx (190 lines)
    ├── Quality assessment
    ├── Issue detection
    └── Issue display
```

### Split Strategy
- Split when test file exceeds 600 lines
- Group related tests in separate files
- Use consistent naming: `ComponentName.feature.test.tsx`
- Keep shared test utilities in separate `__testUtils__/` folder

---

## Debugging Test Failures

### Run with Verbose Output
```bash
# Show detailed test output
npx vitest run --reporter=verbose src/utils/queue/__tests__/queue_recommender.test.ts

# Show test names and timing
npx vitest run --reporter=default src/components/player/__tests__/ShuffleModeSelector.test.tsx

# Show only failures
npx vitest run --reporter=tap src/hooks/player/__tests__/useQueueSearch.test.ts
```

### Debug Single Test
```bash
# Run just one test by name
npx vitest run -t "should calculate similarity" src/utils/queue/__tests__/queue_recommender.test.ts

# Run with Node inspector
node --inspect-brk ./node_modules/.bin/vitest run src/utils/queue/__tests__/queue_recommender.test.ts
```

---

## Summary: Safe Testing Commands

```bash
# ✅ SAFE - Run Phase 7 utilities (5 utilities × 30-40 tests each)
npx vitest run 'src/utils/queue/__tests__/**'

# ✅ SAFE - Run Phase 7 components (8 components × 15-20 tests each)
npx vitest run 'src/components/player/__tests__/Queue*.test.tsx' \
                'src/components/player/__tests__/ShuffleModeSelector.test.tsx'

# ✅ SAFE - Run Phase 7 hooks (8 hooks × 15-22 tests each)
npx vitest run 'src/hooks/player/__tests__/useQueue*.test.ts'

# ✅ SAFE - Run Phase 7 integration tests
npx vitest run 'src/components/player/__tests__/Phase7Integration.test.tsx'

# ✅ SAFE - Run all Phase 7 (recommended before commit)
npx vitest run \
  'src/utils/queue/__tests__/**' \
  'src/components/player/__tests__/Queue*.test.tsx' \
  'src/components/player/__tests__/ShuffleModeSelector.test.tsx' \
  'src/hooks/player/__tests__/useQueue*.test.ts' \
  'src/components/player/__tests__/Phase7Integration.test.tsx'

# ❌ NEVER - System crash
npm test
npm run test:memory
```

---

## Emergency: If System Crashes

```bash
# 1. Force kill all Node processes
pkill -9 node
pkill -9 vitest

# 2. Clear Node cache
rm -rf node_modules/.cache

# 3. Restart and verify
free -h
ps aux | grep node
```

---

## Conclusion

**Key Rules**:
1. ✅ Always run specific test files or categories
2. ✅ Use glob patterns for related tests
3. ✅ Phase 7 tests (~150 tests) are safe to run together
4. ✅ Monitor memory before running large test suites
5. ❌ NEVER run full suite (`npm test` or `npm run test:memory`)

**Recommended Workflow**:
- Development: Run single test file (5s)
- Before commit: Run test category (20-40s)
- Before push: Run Phase 7 all tests (90s)
- CI/CD: Run in tiers, separate large tests

---

*Last Updated: 2024*
*For: Auralis v1.1.0-beta.5*

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

### Player and queue tests

**Location**: `src/components/player/__tests__`, `src/hooks/player/__tests__`, `src/utils/__tests__`

Hook and utility tests (`usePlaybackQueue.test.ts`, `usePlayerDisplay.test.ts`,
`queueIndexReconciliation.test.ts`, ...) are small and safe to run together; the
component tests below are larger and best run one file at a time.

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
- *performance-large-libraries.test.tsx* - 1116 lines (run alone; since deleted, #5186)
- *streaming-mse.test.tsx* - 885 lines (run alone; since deleted)
- `websocket-realtime.test.tsx` - 707 lines (run alone)

---

## Safe Testing Patterns

### ✅ DO - Safe Approaches

**Run Single Utility Tests** (safest)
```bash
# Run one utility test - 5-10 seconds
npx vitest run src/utils/__tests__/apiRequest.test.ts

# Run one component test - 5-10 seconds
npx vitest run src/components/player/__tests__/PlaybackControls.test.tsx

# Run one hook test - 5-10 seconds
npx vitest run src/hooks/player/__tests__/usePlayerDisplay.test.ts
```

**Run Related Test Group** (safe)
```bash
# Run all utility tests (~30 seconds, ~100MB memory)
npx vitest run 'src/utils/__tests__/**/*.test.ts'

# Run all player component tests (~40 seconds, ~150MB memory)
npx vitest run 'src/components/player/__tests__/**/*.test.tsx'

# Run all player hook tests (~30 seconds, ~120MB memory)
npx vitest run 'src/hooks/player/__tests__/**/*.test.ts'

# Run utilities, components and hooks together (~2 minutes, ~400MB memory)
npx vitest run \
  'src/utils/__tests__/**/*.test.ts' \
  'src/components/player/__tests__/**/*.test.tsx' \
  'src/hooks/player/__tests__/**/*.test.ts'
```

**Run Integration Tests** (specific only)
```bash
# Run the player integration test alone
npx vitest run src/components/player/__tests__/Player.test.tsx

# Run performance tests alone
npx vitest run src/tests/integration/performance/
```

**Watch Mode** (development)
```bash
# Watch single file changes
npx vitest src/utils/__tests__/apiRequest.test.ts

# Watch directory changes
npx vitest 'src/utils/__tests__/**'
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
npx vitest run src/utils/__tests__/*.test.ts

# Tier 2: Hook tests (~1 minute)
npx vitest run src/hooks/player/__tests__/useQueue*.test.ts

# Tier 3: Component tests (~2 minutes)
npx vitest run src/components/player/__tests__/Queue*.test.tsx

# Tier 4: Integration tests (~1 minute)
npx vitest run src/components/player/__tests__/Player.test.tsx

# Total: ~5 minutes, safe memory usage
```

### For Development
```bash
# Quick sanity check (< 30 seconds)
npx vitest run \
  src/utils/__tests__/apiRequest.test.ts \
  src/components/player/__tests__/PlaybackControls.test.tsx

# Full player validation (~2 minutes)
npx vitest run \
  'src/utils/__tests__/**/*.test.ts' \
  'src/components/player/__tests__/Queue*.test.tsx' \
  'src/hooks/player/__tests__/useQueue*.test.ts'
```

---

## Test Execution Times

| Command | Time | Memory | Safety |
|---------|------|--------|--------|
| Single test file | ~5s | ~50MB | ✅ Safe |
| Single category | ~20s | ~150MB | ✅ Safe |
| utilities + hooks | ~40s | ~250MB | ✅ Safe |
| all (utilities + hooks + components) | ~90s | ~400MB | ✅ Safe |
| Full player tests | ~3 min | ~800MB | ⚠️ Risky |
| Entire suite | crash | 2GB+ | ❌ Fatal |

---

## File Splitting Recommendations

If individual test files grow beyond 600 lines, split them:

### Example: Split Large Test File
```
LargeComponent.test.tsx (590 lines) - CONSIDER SPLITTING:
├── LargeComponent.basic.test.tsx (200 lines)
│   ├── Rendering tests
│   ├── Props handling
│   └── Empty state
├── LargeComponent.interaction.test.tsx (200 lines)
│   ├── Click and keyboard handling
│   └── Callbacks
└── LargeComponent.states.test.tsx (190 lines)
    ├── Loading and error states
    └── Edge cases
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
npx vitest run --reporter=verbose src/utils/__tests__/apiRequest.test.ts

# Show test names and timing
npx vitest run --reporter=default src/components/player/__tests__/PlaybackControls.test.tsx

# Show only failures
npx vitest run --reporter=tap src/hooks/player/__tests__/usePlayerDisplay.test.ts
```

### Debug Single Test
```bash
# Run just one test by name
npx vitest run -t "should calculate similarity" src/utils/__tests__/apiRequest.test.ts

# Run with Node inspector
node --inspect-brk ./node_modules/.bin/vitest run src/utils/__tests__/apiRequest.test.ts
```

---

## Summary: Safe Testing Commands

```bash
# ✅ SAFE - Run utility tests
npx vitest run 'src/utils/__tests__/**'

# ✅ SAFE - Run player components
npx vitest run 'src/components/player/__tests__/Queue*.test.tsx' \
                'src/components/player/__tests__/PlaybackControls.test.tsx'

# ✅ SAFE - Run player hooks
npx vitest run 'src/hooks/player/__tests__/useQueue*.test.ts'

# ✅ SAFE - Run the player integration test
npx vitest run 'src/components/player/__tests__/Player.test.tsx'

# ✅ SAFE - Run all of the above (recommended before commit)
npx vitest run \
  'src/utils/__tests__/**' \
  'src/components/player/__tests__/Queue*.test.tsx' \
  'src/components/player/__tests__/PlaybackControls.test.tsx' \
  'src/hooks/player/__tests__/useQueue*.test.ts' \
  'src/components/player/__tests__/Player.test.tsx'

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
3. ✅ Utility, hook and player component tests are safe to run together
4. ✅ Monitor memory before running large test suites
5. ❌ NEVER run full suite (`npm test` or `npm run test:memory`)

**Recommended Workflow**:
- Development: Run single test file (5s)
- Before commit: Run test category (20-40s)
- Before push: Run the utility, hook and player tests (90s)
- CI/CD: Run in tiers, separate large tests

---

*Last Updated: 2024*
*For: Auralis v1.1.0-beta.5*

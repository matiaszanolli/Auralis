# Frontend Integration Testing - Quick Start Guide

**Status:** Ready for Implementation
**Total Tests:** 200 (100 component integration + 100 API integration)
**Timeline:** 6 weeks (30 business days)
**Target:** Beta 11.0

---

## Day 1: Setup (30 minutes)

### 1. Install MSW (5 minutes)

```bash
cd /mnt/data/src/matchering/auralis-web/frontend
npm install msw --save-dev
npx msw init public/ --save
```

**Expected output:**
```
✓ MSW installed
✓ Service worker created in public/mockServiceWorker.js
```

### 2. Create MSW Server Setup (10 minutes)

**File:** `src/test/mocks/server.ts`

```typescript
import { setupServer } from 'msw/node'
import { handlers } from './handlers'

export const server = setupServer(...handlers)
```

### 3. Create MSW Handlers (10 minutes)

**File:** `src/test/mocks/handlers.ts`

```typescript
import { http, HttpResponse } from 'msw'
import { mockTracks, mockAlbums, mockPlayerState } from './api'

export const handlers = [
  // Track listing
  http.get('/api/library/tracks', ({ request }) => {
    const url = new URL(request.url)
    const limit = parseInt(url.searchParams.get('limit') || '50')
    const offset = parseInt(url.searchParams.get('offset') || '0')

    return HttpResponse.json({
      tracks: mockTracks.slice(offset, offset + limit),
      total: mockTracks.length,
      has_more: offset + limit < mockTracks.length
    })
  }),

  // Player play
  http.post('/api/player/play', async ({ request }) => {
    const body = await request.json()
    return HttpResponse.json({ success: true })
  }),

  // Add more handlers...
]
```

### 4. Update Test Setup (5 minutes)

**File:** `src/test/setup.ts` (add to existing file)

```typescript
import { beforeAll, afterEach, afterAll } from 'vitest'
import { server } from './mocks/server'

beforeAll(() => server.listen({ onUnhandledRequest: 'warn' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())
```

### 5. Verify Setup

```bash
npm test
```

All existing tests should still pass. If not, check MSW configuration.

---

## Week 1: Priority 1A - PlayerBarV2 Tests (20 tests, 4 days)

### Day 2-3: Playback Controls (8 tests)

**File:** `src/test/integration/player-controls.test.tsx`

```typescript
import { describe, it, expect } from 'vitest'
import { render, screen, waitFor, within, fireEvent } from '@/test/test-utils'
import ComfortableApp from '@/ComfortableApp'

describe('Player Controls Integration', () => {
  it('should play track from library', async () => {
    render(<ComfortableApp />)

    // Wait for library to load
    await waitFor(() => {
      expect(screen.getByTestId('track-row')).toBeInTheDocument()
    })

    // Click play button on first track
    const playButton = within(screen.getAllByTestId('track-row')[0])
      .getByTestId('play-button')
    fireEvent.click(playButton)

    // Verify player bar shows track
    await waitFor(() => {
      const playerBar = screen.getByTestId('player-bar-v2')
      expect(within(playerBar).getByText('Test Track')).toBeInTheDocument()
    })
  })

  // Add 7 more playback control tests...
})
```

**Daily target:** 4 tests/day

### Day 4: Seek & Progress (5 tests)

Focus on ProgressBar component interaction.

### Day 5: Volume & Queue (7 tests)

Focus on VolumeControl and queue management.

---

## Week 1: Priority 1B - EnhancementPaneV2 Tests (20 tests, 4 days)

### Day 6-7: Enhancement Toggle & Preset Selection (10 tests)

**File:** `src/test/integration/enhancement-panel.test.tsx`

Focus on:
- EnhancementToggle component
- Preset selection (Adaptive, Gentle, Warm, Bright, Punchy)
- Parameter updates on preset change

### Day 8-9: Parameter Adjustment & Characteristics (10 tests)

Focus on:
- ParameterBar sliders (Intensity, Bass, Treble, Stereo Width)
- AudioCharacteristics display
- InfoBox descriptions

---

## Week 2: Priority 1C - Error Handling (20 tests, 3 days)

### Day 10-11: HTTP Error Codes (15 tests)

**File:** `src/test/api-integration/error-handling.test.tsx`

Test error codes: 400, 401, 403, 404, 409, 422, 500, 502, 503, 504

### Day 12: Network Errors & Retries (5 tests)

Test:
- Network timeout
- Offline mode
- Retry logic

---

## Quick Reference: Test Helpers

### Helper Functions to Create

**File:** `src/test/utils/test-helpers.ts`

```typescript
export async function setupPlayingTrack(trackId = 1) {
  const playButton = screen.getByTestId(`play-button-${trackId}`)
  fireEvent.click(playButton)
  await waitFor(() => {
    expect(screen.getByTestId('pause-button')).toBeInTheDocument()
  })
}

export function triggerInfiniteScroll() {
  const sentinel = screen.getByTestId('infinite-scroll-sentinel')
  const observer = (sentinel as any).__observer
  observer?.callback([{ isIntersecting: true }])
}

export async function navigateToAlbumDetail(albumName: string) {
  fireEvent.click(screen.getByText('Albums'))
  await waitFor(() => {
    expect(screen.getByText(albumName)).toBeInTheDocument()
  })
  fireEvent.click(screen.getByText(albumName))
}
```

---

## Daily Workflow

### Morning (30 min)
1. Pull latest changes
2. Run test suite: `npm test`
3. Check for failures
4. Plan 3-4 tests to write today

### Implementation (6 hours)
1. Write test skeleton (10 min)
2. Implement test logic (30 min)
3. Debug and fix (20 min)
4. Repeat 3-4 times

### End of Day (15 min)
1. Run full test suite
2. Fix any breaking changes
3. Commit tests
4. Update progress tracker

---

## Progress Tracker

### Week 1 (Days 1-5) - 40 tests
- [ ] Day 1: Setup MSW infrastructure
- [ ] Day 2-3: PlayerBarV2 playback controls (8 tests)
- [ ] Day 4: PlayerBarV2 seek & progress (5 tests)
- [ ] Day 5: PlayerBarV2 volume & queue (7 tests)

### Week 2 (Days 6-12) - 40 tests
- [ ] Day 6-7: EnhancementPaneV2 toggle & presets (10 tests)
- [ ] Day 8-9: EnhancementPaneV2 parameters (10 tests)
- [ ] Day 10-11: Error handling HTTP codes (15 tests)
- [ ] Day 12: Error handling network errors (5 tests)

### Week 3 (Days 13-17) - 40 tests
- [ ] Day 13-14: Library workflow navigation (8 tests)
- [ ] Day 15: Library workflow pagination (6 tests)
- [ ] Day 16: Library workflow empty/loading states (6 tests)
- [ ] Day 17-18: Search & filter integration (20 tests)

### Week 4 (Days 18-22) - 40 tests
- [ ] Day 19-20: Pagination tests (20 tests)
- [ ] Day 21-22: Loading state tests (20 tests)

### Week 5 (Days 23-27) - 40 tests
- [ ] Day 23-24: Mock response tests (20 tests)
- [ ] Day 25-27: WebSocket update tests (20 tests)

### Week 6 (Days 28-30) - 20 tests
- [ ] Day 28-30: Artwork management tests (20 tests)

**Total:** 200 tests across 30 business days

---

## Common Patterns

### Test Structure
```typescript
describe('Feature Integration', () => {
  it('should perform specific action', async () => {
    // 1. Arrange
    render(<ComfortableApp />)

    // 2. Act
    await waitFor(() => {
      expect(screen.getByText('Element')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByText('Button'))

    // 3. Assert
    await waitFor(() => {
      expect(screen.getByText('Expected Result')).toBeInTheDocument()
    })
  })
})
```

### MSW Override Pattern
```typescript
it('should handle error', async () => {
  // Override default handler for this test
  server.use(
    http.get('/api/endpoint', () => {
      return HttpResponse.json(
        { error: 'Error message' },
        { status: 500 }
      )
    })
  )

  render(<ComfortableApp />)

  await waitFor(() => {
    expect(screen.getByText(/error/i)).toBeInTheDocument()
  })
})
```

---

## Success Metrics

### Daily
- ✅ 3-4 tests written
- ✅ All tests passing
- ✅ No flaky tests
- ✅ Code committed

### Weekly
- ✅ 20 tests completed
- ✅ 98%+ pass rate maintained
- ✅ Documentation updated
- ✅ No regression in existing tests

### Final (Week 6)
- ✅ 200 tests implemented
- ✅ 100% component coverage for refactored components
- ✅ MSW mocks for all API endpoints
- ✅ < 30s total test runtime

---

## Troubleshooting

### Tests timing out
```typescript
// Increase timeout for slow operations
await waitFor(() => {
  expect(screen.getByText('Result')).toBeInTheDocument()
}, { timeout: 5000 })
```

### IntersectionObserver not working
```typescript
// Enhanced mock in setup.ts
global.IntersectionObserver = class IntersectionObserver {
  callback: IntersectionObserverCallback

  constructor(callback: IntersectionObserverCallback) {
    this.callback = callback
  }

  observe(target: Element) {
    // Store observer on element for triggering
    (target as any).__observer = this
  }

  disconnect() {}
  unobserve() {}
  takeRecords() { return [] }
} as any
```

### WebSocket messages not received
```typescript
// Ensure WebSocket mock is initialized
const mockWS = mockWebSocket()

// Wait for connection
await waitFor(() => {
  expect(mockWS).toHaveBeenCalled()
})

// Get instance
const ws = mockWS.mock.results[0].value

// Simulate message
ws.simulateMessage({ type: 'player_state', data: {...} })
```

---

## Resources

- **Full Plan:** `docs/testing/FRONTEND_INTEGRATION_TESTS_PLAN.md`
- **MSW Docs:** https://mswjs.io/docs/
- **Testing Library Docs:** https://testing-library.com/docs/react-testing-library/intro/
- **Vitest Docs:** https://vitest.dev/

---

## Contact

Questions? Check:
1. Full testing plan: `FRONTEND_INTEGRATION_TESTS_PLAN.md`
2. Testing guidelines: `docs/development/TESTING_GUIDELINES.md`
3. Test roadmap: `docs/development/TEST_IMPLEMENTATION_ROADMAP.md`

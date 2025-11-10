# Frontend Integration Testing Plan

**Version:** 1.0.0
**Created:** November 9, 2025
**Target:** Beta 11.0 (Month 3 - Phase 3)
**Total Tests:** 200 tests (100 component integration + 100 API integration)

---

## Executive Summary

### Current Status

**Existing Frontend Tests:**
- Total test files: 21
- Total tests: 245
- Passing: 234 (95.5%)
- Failing: 11 (gapless playback component)
- Coverage: Unit tests only, no integration tests

**Recent UI Refactoring (100% Design Token Compliant):**
- ✅ PlayerBarV2 (7 components, 729 lines)
- ✅ EnhancementPaneV2 (10 components, 910 lines)
- ✅ Sidebar (refactored with tokens)
- ✅ CozyLibraryView (polished with LibraryHeader)
- ✅ ProcessingToast (100% token compliant)

**Testing Infrastructure:**
- Framework: Vitest + Testing Library
- Test environment: jsdom
- Test utilities: Custom providers wrapper
- API mocking: Basic fetch mocking (needs MSW upgrade)
- Coverage provider: v8

### Implementation Goals

1. **Component Integration Tests** (100 tests) - Test multi-component workflows
2. **API Integration Tests** (100 tests) - Test frontend-backend integration with MSW
3. **Focus on recently refactored components** - PlayerBarV2, EnhancementPaneV2
4. **Validate design token compliance** - Ensure tokens work correctly in tests
5. **Improve coverage** - From 95.5% to 98%+ pass rate

---

## Testing Infrastructure

### Current Setup

**Test Configuration** (`vite.config.ts`):
```typescript
test: {
  globals: true,
  environment: 'jsdom',
  setupFiles: ['./src/test/setup.ts'],
  css: true,
  coverage: {
    provider: 'v8',
    reporter: ['text', 'json', 'html'],
    exclude: [
      'node_modules/',
      'src/test/',
      '**/*.d.ts',
      '**/*.config.*',
      '**/mockData',
      'build/',
    ],
  },
}
```

**Test Utilities** (`src/test/test-utils.tsx`):
- Custom render with all providers (Theme, WebSocket, Enhancement, DragDrop)
- Automatic cleanup after each test
- Router wrapper (BrowserRouter)

**Existing Mocks** (`src/test/mocks/`):
- `api.ts` - Basic fetch mocking (200+ lines)
- `websocket.ts` - WebSocket mocking

**Mock Data Available:**
- mockTrack, mockTracks
- mockAlbum, mockAlbums
- mockArtist
- mockPlaylist
- mockPlayerState
- mockProcessingJob
- mockLibraryStats
- mockScanProgress

### Required Upgrades

#### 1. Install MSW (Mock Service Worker)

**Why MSW?**
- Industry standard for API mocking
- Works at network level (intercepts fetch/XHR)
- Reusable across tests and development
- Better than mocking fetch directly

**Installation:**
```bash
cd auralis-web/frontend
npm install msw --save-dev
npx msw init public/ --save
```

**MSW Setup** (`src/test/mocks/server.ts`):
```typescript
import { setupServer } from 'msw/node'
import { handlers } from './handlers'

export const server = setupServer(...handlers)
```

**Test Setup** (update `src/test/setup.ts`):
```typescript
import { beforeAll, afterEach, afterAll } from 'vitest'
import { server } from './mocks/server'

beforeAll(() => server.listen({ onUnhandledRequest: 'warn' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())
```

#### 2. Create MSW Handlers

**File:** `src/test/mocks/handlers.ts`

All backend API endpoints from `auralis-web/backend/routers/`:
- `/api/player/*` - Player controls
- `/api/library/tracks` - Track listing with pagination
- `/api/library/albums` - Album listing
- `/api/library/artists` - Artist listing
- `/api/enhancement/*` - Enhancement settings
- `/api/playlists/*` - Playlist CRUD
- `/api/metadata/*` - Track metadata
- `/api/artwork/*` - Album artwork
- `/api/streaming/*` - MSE streaming
- `/api/health` - Health check
- `/api/version` - Version info

**Example Handler:**
```typescript
import { http, HttpResponse } from 'msw'

export const handlers = [
  // Track listing with pagination
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

  // Player play endpoint
  http.post('/api/player/play', async ({ request }) => {
    const body = await request.json()
    return HttpResponse.json({ success: true })
  }),
]
```

#### 3. WebSocket Testing Utilities

**File:** `src/test/mocks/websocket.ts` (enhance existing)

```typescript
import { vi } from 'vitest'

export class MockWebSocket {
  url: string
  readyState: number = WebSocket.OPEN
  onopen: ((event: Event) => void) | null = null
  onmessage: ((event: MessageEvent) => void) | null = null
  onerror: ((event: Event) => void) | null = null
  onclose: ((event: CloseEvent) => void) | null = null

  constructor(url: string) {
    this.url = url
    setTimeout(() => {
      this.onopen?.(new Event('open'))
    }, 0)
  }

  send(data: string) {
    // Mock send - can be spied on
  }

  close() {
    this.readyState = WebSocket.CLOSED
    this.onclose?.(new CloseEvent('close'))
  }

  // Helper to simulate server message
  simulateMessage(data: any) {
    this.onmessage?.(new MessageEvent('message', {
      data: JSON.stringify(data)
    }))
  }
}

export function mockWebSocket() {
  const mock = vi.fn((url: string) => new MockWebSocket(url))
  global.WebSocket = mock as any
  return mock
}
```

---

## Part 1: Component Integration Tests (100 tests)

**Location:** `auralis-web/frontend/src/test/integration/`

### Test File Structure

```
src/test/integration/
├── library-workflow.test.tsx        # 20 tests - Library navigation
├── search-filter-play.test.tsx      # 20 tests - Search & play
├── player-controls.test.tsx         # 20 tests - Player interactions
├── enhancement-panel.test.tsx       # 20 tests - Enhancement workflows
└── artwork-management.test.tsx      # 20 tests - Artwork operations
```

---

### 1. Library Workflow Tests (20 tests)

**File:** `src/test/integration/library-workflow.test.tsx`

**Component Flow:**
```
CozyLibraryView → LibraryViewRouter → CozyAlbumGrid → AlbumDetailView → TrackRow
```

**Tests:**

#### Library Navigation (8 tests)
1. ✅ Should load library view with track list
2. ✅ Should navigate to albums grid view
3. ✅ Should navigate to artists list view
4. ✅ Should click album and load album detail view
5. ✅ Should show album tracks in detail view
6. ✅ Should navigate back from album detail to grid
7. ✅ Should navigate to artist detail from albums
8. ✅ Should show breadcrumb navigation trail

#### Pagination & Infinite Scroll (6 tests)
9. ✅ Should load first 50 tracks on mount
10. ✅ Should load next page on scroll to bottom (IntersectionObserver)
11. ✅ Should show loading indicator while fetching next page
12. ✅ Should stop loading when all tracks fetched
13. ✅ Should handle pagination errors gracefully
14. ✅ Should preserve scroll position on route change

#### Empty States (3 tests)
15. ✅ Should show empty library state when no tracks
16. ✅ Should show "Add Music" CTA in empty state
17. ✅ Should show empty album when no albums

#### Loading States (3 tests)
18. ✅ Should show skeleton loaders while loading tracks
19. ✅ Should show skeleton loaders while loading albums
20. ✅ Should transition from loading to content smoothly

**Example Test:**
```typescript
import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@/test/test-utils'
import { server } from '@/test/mocks/server'
import { http, HttpResponse } from 'msw'
import ComfortableApp from '@/ComfortableApp'

describe('Library Workflow Integration', () => {
  it('should navigate from library to album detail', async () => {
    render(<ComfortableApp />)

    // Wait for library to load
    await waitFor(() => {
      expect(screen.getByText('Albums')).toBeInTheDocument()
    })

    // Click Albums tab
    fireEvent.click(screen.getByText('Albums'))

    // Wait for albums to load
    await waitFor(() => {
      expect(screen.getByText('Test Album')).toBeInTheDocument()
    })

    // Click album
    fireEvent.click(screen.getByText('Test Album'))

    // Verify album detail view
    await waitFor(() => {
      expect(screen.getByText('Album Details')).toBeInTheDocument()
      expect(screen.getByText('Test Track')).toBeInTheDocument()
    })
  })

  it('should load next page on scroll', async () => {
    render(<ComfortableApp />)

    await waitFor(() => {
      expect(screen.getAllByTestId('track-row')).toHaveLength(50)
    })

    // Simulate IntersectionObserver trigger
    const sentinel = screen.getByTestId('infinite-scroll-sentinel')
    const observer = (sentinel as any).__observer
    observer?.callback([{ isIntersecting: true }])

    // Wait for next page
    await waitFor(() => {
      expect(screen.getAllByTestId('track-row')).toHaveLength(100)
    })
  })
})
```

---

### 2. Search, Filter & Play Tests (20 tests)

**File:** `src/test/integration/search-filter-play.test.tsx`

**Component Flow:**
```
GlobalSearch → TrackListView → TrackRow → PlayerBarV2
```

**Tests:**

#### Search Integration (7 tests)
1. ✅ Should search tracks by title
2. ✅ Should search tracks by artist
3. ✅ Should search tracks by album
4. ✅ Should debounce search input (300ms)
5. ✅ Should show search results count
6. ✅ Should clear search and restore full list
7. ✅ Should show "no results" when search yields nothing

#### Filter Integration (6 tests)
8. ✅ Should filter tracks by genre
9. ✅ Should filter tracks by year range
10. ✅ Should filter tracks by favorites
11. ✅ Should combine search + filter
12. ✅ Should reset filters and restore full list
13. ✅ Should show filter chip indicators

#### Play from Search/Filter (7 tests)
14. ✅ Should play track from search results
15. ✅ Should add track to queue from search results
16. ✅ Should play all search results as queue
17. ✅ Should update player bar when playing from search
18. ✅ Should preserve search results while playing
19. ✅ Should drag track from search to playlist
20. ✅ Should show playing indicator on current track in search

**Example Test:**
```typescript
describe('Search, Filter & Play Integration', () => {
  it('should search, filter, and play track', async () => {
    render(<ComfortableApp />)

    // Wait for library
    await waitFor(() => {
      expect(screen.getByPlaceholderText('Search...')).toBeInTheDocument()
    })

    // Search for track
    const searchInput = screen.getByPlaceholderText('Search...')
    fireEvent.change(searchInput, { target: { value: 'Test Track' } })

    // Wait for debounce and results
    await waitFor(() => {
      expect(screen.getByText('1 result')).toBeInTheDocument()
    }, { timeout: 500 })

    // Apply genre filter
    fireEvent.click(screen.getByText('Genre'))
    fireEvent.click(screen.getByText('Electronic'))

    // Verify filtered results
    await waitFor(() => {
      expect(screen.getByTestId('track-row')).toBeInTheDocument()
    })

    // Play track
    const playButton = within(screen.getByTestId('track-row'))
      .getByTestId('play-button')
    fireEvent.click(playButton)

    // Verify player updated
    await waitFor(() => {
      const playerBar = screen.getByTestId('player-bar-v2')
      expect(within(playerBar).getByText('Test Track')).toBeInTheDocument()
    })
  })
})
```

---

### 3. Player Controls Integration (20 tests)

**File:** `src/test/integration/player-controls.test.tsx`

**Component Flow:**
```
PlayerBarV2 → PlaybackControls → ProgressBar → VolumeControl → TrackInfo
```

**Components:**
- `PlayerBarV2.tsx` (main container)
- `PlaybackControls.tsx` (play/pause/next/prev)
- `ProgressBar.tsx` (seek bar)
- `VolumeControl.tsx` (volume slider)
- `TrackInfo.tsx` (track metadata display)
- `EnhancementToggle.tsx` (enhancement on/off)

**Tests:**

#### Playback Controls (8 tests)
1. ✅ Should play track from library
2. ✅ Should pause playing track
3. ✅ Should resume paused track
4. ✅ Should skip to next track
5. ✅ Should skip to previous track
6. ✅ Should show playing state in PlaybackControls
7. ✅ Should disable prev button at first track
8. ✅ Should disable next button at last track

#### Seek & Progress (5 tests)
9. ✅ Should seek to position via progress bar click
10. ✅ Should drag progress bar to seek
11. ✅ Should update progress bar during playback
12. ✅ Should show current time and duration
13. ✅ Should handle seek beyond duration gracefully

#### Volume Control (3 tests)
14. ✅ Should change volume via slider
15. ✅ Should mute/unmute audio
16. ✅ Should persist volume setting

#### Queue Management (4 tests)
17. ✅ Should show current queue
18. ✅ Should reorder queue items via drag-drop
19. ✅ Should remove track from queue
20. ✅ Should clear entire queue

**Example Test:**
```typescript
describe('Player Controls Integration', () => {
  it('should play, pause, and skip tracks', async () => {
    render(<ComfortableApp />)

    // Load library and play first track
    await waitFor(() => {
      expect(screen.getByTestId('track-row')).toBeInTheDocument()
    })

    const firstTrackPlayButton = within(screen.getAllByTestId('track-row')[0])
      .getByTestId('play-button')
    fireEvent.click(firstTrackPlayButton)

    // Verify player shows track
    await waitFor(() => {
      const playerBar = screen.getByTestId('player-bar-v2')
      expect(within(playerBar).getByText('Test Track')).toBeInTheDocument()
    })

    // Pause track
    const pauseButton = within(screen.getByTestId('playback-controls'))
      .getByTestId('pause-button')
    fireEvent.click(pauseButton)

    // Verify paused state
    await waitFor(() => {
      expect(screen.getByTestId('play-button')).toBeInTheDocument()
    })

    // Skip to next
    const nextButton = screen.getByTestId('next-button')
    fireEvent.click(nextButton)

    // Verify next track loaded
    await waitFor(() => {
      const playerBar = screen.getByTestId('player-bar-v2')
      expect(within(playerBar).getByText('Another Track')).toBeInTheDocument()
    })
  })

  it('should seek via progress bar', async () => {
    // Setup player with track
    render(<ComfortableApp />)
    await setupPlayingTrack()

    // Get progress bar
    const progressBar = screen.getByTestId('progress-bar')
    const progressBarRect = progressBar.getBoundingClientRect()

    // Click at 50% position
    fireEvent.click(progressBar, {
      clientX: progressBarRect.left + progressBarRect.width * 0.5
    })

    // Verify seek API called
    await waitFor(() => {
      expect(mockSeekFn).toHaveBeenCalledWith(90) // 50% of 180s
    })
  })
})
```

---

### 4. Enhancement Panel Integration (20 tests)

**File:** `src/test/integration/enhancement-panel.test.tsx`

**Component Flow:**
```
EnhancementPaneV2 → ProcessingParameters → ParameterBar → AudioCharacteristics → InfoBox
```

**Components:**
- `EnhancementPaneV2.tsx` (main container)
- `EnhancementToggle.tsx` (on/off switch)
- `ProcessingParameters.tsx` (preset selector + sliders)
- `ParameterBar.tsx` (individual parameter slider)
- `ParameterChip.tsx` (parameter value display)
- `AudioCharacteristics.tsx` (frequency/dynamics display)
- `InfoBox.tsx` (parameter description)

**Tests:**

#### Enhancement Toggle (4 tests)
1. ✅ Should toggle enhancement on/off
2. ✅ Should show enhancement state in player bar
3. ✅ Should persist enhancement state
4. ✅ Should disable parameters when enhancement off

#### Preset Selection (6 tests)
5. ✅ Should select Adaptive preset (default)
6. ✅ Should select Gentle preset
7. ✅ Should select Warm preset
8. ✅ Should select Bright preset
9. ✅ Should select Punchy preset
10. ✅ Should update parameters when preset changes

#### Parameter Adjustment (6 tests)
11. ✅ Should adjust Intensity slider (0-100)
12. ✅ Should adjust Bass slider (-12 to +12 dB)
13. ✅ Should adjust Treble slider (-12 to +12 dB)
14. ✅ Should adjust Stereo Width slider (0-100)
15. ✅ Should show parameter value in chip
16. ✅ Should show parameter description in InfoBox

#### Audio Characteristics Display (4 tests)
17. ✅ Should show frequency distribution chart
18. ✅ Should show LUFS loudness value
19. ✅ Should show dynamic range value
20. ✅ Should update characteristics when preset changes

**Example Test:**
```typescript
describe('Enhancement Panel Integration', () => {
  it('should select preset and adjust parameters', async () => {
    render(<ComfortableApp />)

    // Open enhancement panel
    const enhancementToggle = screen.getByTestId('enhancement-toggle')
    fireEvent.click(enhancementToggle)

    // Wait for panel to open
    await waitFor(() => {
      expect(screen.getByTestId('enhancement-pane-v2')).toBeInTheDocument()
    })

    // Select Warm preset
    const warmPreset = screen.getByText('Warm')
    fireEvent.click(warmPreset)

    // Verify preset selected
    await waitFor(() => {
      expect(warmPreset).toHaveClass('selected')
    })

    // Adjust Intensity slider
    const intensitySlider = screen.getByTestId('intensity-slider')
    fireEvent.change(intensitySlider, { target: { value: 75 } })

    // Verify parameter chip shows value
    await waitFor(() => {
      expect(screen.getByText('75%')).toBeInTheDocument()
    })

    // Verify API called with new settings
    await waitFor(() => {
      expect(mockUpdateEnhancementFn).toHaveBeenCalledWith({
        preset: 'warm',
        intensity: 75
      })
    })
  })

  it('should show audio characteristics', async () => {
    render(<ComfortableApp />)

    // Play track and open enhancement panel
    await setupPlayingTrack()
    fireEvent.click(screen.getByTestId('enhancement-toggle'))

    // Wait for characteristics to load
    await waitFor(() => {
      expect(screen.getByTestId('audio-characteristics')).toBeInTheDocument()
    })

    // Verify frequency distribution shown
    expect(screen.getByText('Bass:')).toBeInTheDocument()
    expect(screen.getByText('Mid:')).toBeInTheDocument()
    expect(screen.getByText('Treble:')).toBeInTheDocument()

    // Verify LUFS shown
    expect(screen.getByText(/LUFS:/)).toBeInTheDocument()

    // Verify dynamic range shown
    expect(screen.getByText(/DR:/)).toBeInTheDocument()
  })
})
```

---

### 5. Artwork Management Integration (20 tests)

**File:** `src/test/integration/artwork-management.test.tsx`

**Component Flow:**
```
AlbumDetailView → ArtworkDisplay → ArtworkUpload → ArtworkExtract → TrackRow (embedded artwork)
```

**Tests:**

#### Artwork Display (5 tests)
1. ✅ Should show album artwork in grid
2. ✅ Should show album artwork in detail view
3. ✅ Should show album artwork in player bar
4. ✅ Should show embedded track artwork if no album art
5. ✅ Should show placeholder when no artwork available

#### Artwork Upload (5 tests)
6. ✅ Should upload artwork via file picker
7. ✅ Should upload artwork via drag-drop
8. ✅ Should validate image format (JPG, PNG, WebP)
9. ✅ Should validate image size (max 10MB)
10. ✅ Should show upload progress indicator

#### Artwork Extraction (5 tests)
11. ✅ Should extract artwork from audio file
12. ✅ Should show extraction progress
13. ✅ Should handle files with no embedded artwork
14. ✅ Should batch extract for multiple tracks
15. ✅ Should update UI after extraction

#### Artwork Download (5 tests)
16. ✅ Should download artwork from MusicBrainz
17. ✅ Should download artwork from Last.fm
18. ✅ Should show search results for artwork
19. ✅ Should preview artwork before applying
20. ✅ Should apply selected artwork to album

**Example Test:**
```typescript
describe('Artwork Management Integration', () => {
  it('should upload and apply artwork', async () => {
    render(<ComfortableApp />)

    // Navigate to album detail
    await waitFor(() => {
      expect(screen.getByText('Albums')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByText('Albums'))
    await waitFor(() => {
      expect(screen.getByText('Test Album')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByText('Test Album'))

    // Open artwork upload dialog
    const editArtworkButton = screen.getByTestId('edit-artwork-button')
    fireEvent.click(editArtworkButton)

    // Upload artwork
    const file = new File(['artwork'], 'album.jpg', { type: 'image/jpeg' })
    const input = screen.getByLabelText('Upload Artwork') as HTMLInputElement

    Object.defineProperty(input, 'files', {
      value: [file],
      writable: false,
    })
    fireEvent.change(input)

    // Verify upload started
    await waitFor(() => {
      expect(screen.getByText(/uploading/i)).toBeInTheDocument()
    })

    // Verify upload completed
    await waitFor(() => {
      expect(screen.getByAltText('Test Album')).toHaveAttribute('src', '/api/artwork/1')
    }, { timeout: 3000 })
  })

  it('should extract embedded artwork', async () => {
    render(<ComfortableApp />)

    // Navigate to album detail
    await navigateToAlbumDetail('Test Album')

    // Click extract artwork button
    const extractButton = screen.getByText('Extract from Files')
    fireEvent.click(extractButton)

    // Verify extraction progress
    await waitFor(() => {
      expect(screen.getByText(/extracting/i)).toBeInTheDocument()
    })

    // Verify extraction completed
    await waitFor(() => {
      expect(screen.getByText(/extracted/i)).toBeInTheDocument()
      expect(screen.getByAltText('Test Album')).toHaveAttribute('src')
    }, { timeout: 5000 })
  })
})
```

---

## Part 2: API Integration Tests with MSW (100 tests)

**Location:** `auralis-web/frontend/src/test/api-integration/`

### Test File Structure

```
src/test/api-integration/
├── mock-responses.test.tsx        # 20 tests - API response handling
├── error-handling.test.tsx        # 20 tests - Error scenarios
├── loading-states.test.tsx        # 20 tests - Loading indicators
├── pagination.test.tsx            # 20 tests - Pagination logic
└── websocket-updates.test.tsx     # 20 tests - Real-time updates
```

---

### 1. Mock Response Tests (20 tests)

**File:** `src/test/api-integration/mock-responses.test.tsx`

**Purpose:** Verify correct handling of all API endpoints

**Tests:**

#### Player API (5 tests)
1. ✅ Should handle POST /api/player/play response
2. ✅ Should handle POST /api/player/pause response
3. ✅ Should handle POST /api/player/seek response
4. ✅ Should handle GET /api/player/state response
5. ✅ Should handle PUT /api/player/volume response

#### Library API (5 tests)
6. ✅ Should handle GET /api/library/tracks response
7. ✅ Should handle GET /api/library/albums response
8. ✅ Should handle GET /api/library/artists response
9. ✅ Should handle POST /api/library/scan response
10. ✅ Should handle GET /api/library/stats response

#### Enhancement API (5 tests)
11. ✅ Should handle GET /api/enhancement/settings response
12. ✅ Should handle PUT /api/enhancement/settings response
13. ✅ Should handle POST /api/enhancement/apply response
14. ✅ Should handle GET /api/enhancement/presets response
15. ✅ Should handle GET /api/enhancement/analysis response

#### Metadata API (5 tests)
16. ✅ Should handle GET /api/metadata/:trackId response
17. ✅ Should handle PUT /api/metadata/:trackId response
18. ✅ Should handle POST /api/artwork/upload response
19. ✅ Should handle POST /api/artwork/extract response
20. ✅ Should handle GET /api/artwork/:albumId response

**Example Test:**
```typescript
import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@/test/test-utils'
import { server } from '@/test/mocks/server'
import { http, HttpResponse } from 'msw'
import ComfortableApp from '@/ComfortableApp'

describe('Mock Response Tests', () => {
  it('should handle GET /api/library/tracks response', async () => {
    // Mock successful response
    server.use(
      http.get('/api/library/tracks', () => {
        return HttpResponse.json({
          tracks: [
            { id: 1, title: 'Track 1', artist: 'Artist 1', duration: 180 },
            { id: 2, title: 'Track 2', artist: 'Artist 2', duration: 200 }
          ],
          total: 2,
          has_more: false
        })
      })
    )

    render(<ComfortableApp />)

    // Verify tracks displayed
    await waitFor(() => {
      expect(screen.getByText('Track 1')).toBeInTheDocument()
      expect(screen.getByText('Track 2')).toBeInTheDocument()
    })
  })

  it('should handle PUT /api/enhancement/settings response', async () => {
    // Mock enhancement update
    server.use(
      http.put('/api/enhancement/settings', async ({ request }) => {
        const body = await request.json()
        return HttpResponse.json({
          success: true,
          settings: body
        })
      })
    )

    render(<ComfortableApp />)

    // Open enhancement panel
    fireEvent.click(screen.getByTestId('enhancement-toggle'))

    // Change preset
    await waitFor(() => {
      expect(screen.getByText('Warm')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByText('Warm'))

    // Verify API called and UI updated
    await waitFor(() => {
      expect(screen.getByText('Warm')).toHaveClass('selected')
    })
  })
})
```

---

### 2. Error Handling Tests (20 tests)

**File:** `src/test/api-integration/error-handling.test.tsx`

**Purpose:** Verify graceful error handling for all failure scenarios

**Tests:**

#### Network Errors (5 tests)
1. ✅ Should handle network timeout (fetch timeout)
2. ✅ Should handle network offline (no connection)
3. ✅ Should handle DNS failure (invalid host)
4. ✅ Should show retry button on network error
5. ✅ Should retry request when retry clicked

#### HTTP Error Codes (10 tests)
6. ✅ Should handle 400 Bad Request (invalid parameters)
7. ✅ Should handle 401 Unauthorized (auth failure)
8. ✅ Should handle 403 Forbidden (permission denied)
9. ✅ Should handle 404 Not Found (resource missing)
10. ✅ Should handle 409 Conflict (duplicate resource)
11. ✅ Should handle 422 Unprocessable Entity (validation error)
12. ✅ Should handle 500 Internal Server Error (backend crash)
13. ✅ Should handle 502 Bad Gateway (backend unavailable)
14. ✅ Should handle 503 Service Unavailable (maintenance)
15. ✅ Should handle 504 Gateway Timeout (backend timeout)

#### Specific Error Scenarios (5 tests)
16. ✅ Should handle library scan error (invalid path)
17. ✅ Should handle artwork upload error (invalid format)
18. ✅ Should handle metadata update error (file locked)
19. ✅ Should handle playback error (file not found)
20. ✅ Should handle enhancement error (processing failed)

**Example Test:**
```typescript
describe('Error Handling Tests', () => {
  it('should handle 500 Internal Server Error', async () => {
    // Mock 500 error
    server.use(
      http.get('/api/library/tracks', () => {
        return HttpResponse.json(
          { error: 'Database connection failed' },
          { status: 500 }
        )
      })
    )

    render(<ComfortableApp />)

    // Verify error message displayed
    await waitFor(() => {
      expect(screen.getByText(/failed to load tracks/i)).toBeInTheDocument()
      expect(screen.getByText(/database connection failed/i)).toBeInTheDocument()
    })

    // Verify retry button shown
    expect(screen.getByText('Retry')).toBeInTheDocument()
  })

  it('should retry request on retry button click', async () => {
    let requestCount = 0

    server.use(
      http.get('/api/library/tracks', () => {
        requestCount++
        if (requestCount === 1) {
          return HttpResponse.json(
            { error: 'Temporary error' },
            { status: 503 }
          )
        }
        return HttpResponse.json({
          tracks: mockTracks,
          total: 2,
          has_more: false
        })
      })
    )

    render(<ComfortableApp />)

    // Wait for error
    await waitFor(() => {
      expect(screen.getByText('Retry')).toBeInTheDocument()
    })

    // Click retry
    fireEvent.click(screen.getByText('Retry'))

    // Verify success after retry
    await waitFor(() => {
      expect(screen.getByText('Test Track')).toBeInTheDocument()
    })
    expect(requestCount).toBe(2)
  })

  it('should handle artwork upload validation error', async () => {
    server.use(
      http.post('/api/artwork/upload', () => {
        return HttpResponse.json(
          { error: 'File size exceeds 10MB limit' },
          { status: 422 }
        )
      })
    )

    render(<ComfortableApp />)

    // Navigate to album and upload artwork
    await navigateToAlbumDetail('Test Album')
    await uploadArtworkFile('large-image.jpg')

    // Verify validation error shown
    await waitFor(() => {
      expect(screen.getByText(/file size exceeds 10MB/i)).toBeInTheDocument()
    })
  })
})
```

---

### 3. Loading State Tests (20 tests)

**File:** `src/test/api-integration/loading-states.test.tsx`

**Purpose:** Verify loading indicators appear and disappear correctly

**Tests:**

#### Initial Load States (5 tests)
1. ✅ Should show skeleton loaders while loading tracks
2. ✅ Should show skeleton loaders while loading albums
3. ✅ Should show skeleton loaders while loading artists
4. ✅ Should show spinner while loading player state
5. ✅ Should show spinner while loading enhancement settings

#### Delayed Response States (5 tests)
6. ✅ Should show loading for requests taking > 200ms
7. ✅ Should hide loading when response received
8. ✅ Should show loading during library scan
9. ✅ Should update progress during scan (0-100%)
10. ✅ Should show loading during artwork extraction

#### Pagination Loading (5 tests)
11. ✅ Should show "Loading more..." at bottom during pagination
12. ✅ Should not show duplicate content during pagination
13. ✅ Should disable scroll during pagination load
14. ✅ Should handle rapid scroll pagination requests
15. ✅ Should show loading for search results

#### Action Loading States (5 tests)
16. ✅ Should show loading on play button click
17. ✅ Should show loading on preset change
18. ✅ Should show loading on metadata save
19. ✅ Should show loading on artwork upload
20. ✅ Should show loading on playlist create

**Example Test:**
```typescript
describe('Loading State Tests', () => {
  it('should show skeleton loaders while loading tracks', async () => {
    // Delay response by 500ms
    server.use(
      http.get('/api/library/tracks', async () => {
        await new Promise(resolve => setTimeout(resolve, 500))
        return HttpResponse.json({
          tracks: mockTracks,
          total: 2,
          has_more: false
        })
      })
    )

    render(<ComfortableApp />)

    // Verify skeletons shown immediately
    expect(screen.getAllByTestId('skeleton-track-row')).toHaveLength(10)

    // Wait for content
    await waitFor(() => {
      expect(screen.getByText('Test Track')).toBeInTheDocument()
    }, { timeout: 1000 })

    // Verify skeletons removed
    expect(screen.queryByTestId('skeleton-track-row')).not.toBeInTheDocument()
  })

  it('should show loading during library scan', async () => {
    server.use(
      http.post('/api/library/scan', async () => {
        // Simulate long scan
        return HttpResponse.json({
          status: 'scanning',
          progress: 0,
          total_files: 100
        })
      })
    )

    render(<ComfortableApp />)

    // Trigger scan
    fireEvent.click(screen.getByText('Scan Library'))

    // Verify loading shown
    await waitFor(() => {
      expect(screen.getByText(/scanning/i)).toBeInTheDocument()
      expect(screen.getByText('0%')).toBeInTheDocument()
    })
  })

  it('should show "Loading more..." during pagination', async () => {
    render(<ComfortableApp />)

    // Wait for initial load
    await waitFor(() => {
      expect(screen.getAllByTestId('track-row')).toHaveLength(50)
    })

    // Trigger pagination
    const sentinel = screen.getByTestId('infinite-scroll-sentinel')
    fireEvent(sentinel, new IntersectionObserverEvent('intersection'))

    // Verify loading indicator
    await waitFor(() => {
      expect(screen.getByText('Loading more...')).toBeInTheDocument()
    })

    // Wait for next page
    await waitFor(() => {
      expect(screen.getAllByTestId('track-row')).toHaveLength(100)
      expect(screen.queryByText('Loading more...')).not.toBeInTheDocument()
    })
  })
})
```

---

### 4. Pagination Tests (20 tests)

**File:** `src/test/api-integration/pagination.test.tsx`

**Purpose:** Verify pagination logic for all paginated endpoints

**Tests:**

#### Track Pagination (5 tests)
1. ✅ Should load first page (limit=50, offset=0)
2. ✅ Should load second page (limit=50, offset=50)
3. ✅ Should concatenate pages correctly (no duplicates)
4. ✅ Should stop loading when has_more=false
5. ✅ Should handle total count correctly

#### Album Pagination (5 tests)
6. ✅ Should paginate album grid (limit=24)
7. ✅ Should load all albums across multiple pages
8. ✅ Should preserve sort order across pages
9. ✅ Should handle filter changes during pagination
10. ✅ Should reset pagination on search

#### Artist Pagination (5 tests)
11. ✅ Should paginate artist list (limit=50)
12. ✅ Should load artist details on demand
13. ✅ Should cache loaded pages
14. ✅ Should invalidate cache on library update
15. ✅ Should handle artist sort by name/track count

#### Edge Cases (5 tests)
16. ✅ Should handle empty results (total=0)
17. ✅ Should handle single page results (total < limit)
18. ✅ Should handle exact page boundary (total = limit * n)
19. ✅ Should handle offset beyond total (return empty)
20. ✅ Should handle concurrent pagination requests

**Example Test:**
```typescript
describe('Pagination Tests', () => {
  it('should paginate tracks correctly', async () => {
    const allTracks = Array.from({ length: 150 }, (_, i) => ({
      id: i + 1,
      title: `Track ${i + 1}`,
      artist: 'Artist',
      duration: 180
    }))

    server.use(
      http.get('/api/library/tracks', ({ request }) => {
        const url = new URL(request.url)
        const limit = parseInt(url.searchParams.get('limit') || '50')
        const offset = parseInt(url.searchParams.get('offset') || '0')

        return HttpResponse.json({
          tracks: allTracks.slice(offset, offset + limit),
          total: allTracks.length,
          has_more: offset + limit < allTracks.length
        })
      })
    )

    render(<ComfortableApp />)

    // Verify first page loaded
    await waitFor(() => {
      expect(screen.getAllByTestId('track-row')).toHaveLength(50)
      expect(screen.getByText('Track 1')).toBeInTheDocument()
      expect(screen.getByText('Track 50')).toBeInTheDocument()
    })

    // Trigger pagination (page 2)
    triggerInfiniteScroll()

    await waitFor(() => {
      expect(screen.getAllByTestId('track-row')).toHaveLength(100)
      expect(screen.getByText('Track 51')).toBeInTheDocument()
      expect(screen.getByText('Track 100')).toBeInTheDocument()
    })

    // Trigger pagination (page 3)
    triggerInfiniteScroll()

    await waitFor(() => {
      expect(screen.getAllByTestId('track-row')).toHaveLength(150)
      expect(screen.getByText('Track 101')).toBeInTheDocument()
      expect(screen.getByText('Track 150')).toBeInTheDocument()
    })

    // Verify no more pages
    triggerInfiniteScroll()
    await waitFor(() => {
      expect(screen.queryByText('Loading more...')).not.toBeInTheDocument()
    })
  })

  it('should handle empty results', async () => {
    server.use(
      http.get('/api/library/tracks', () => {
        return HttpResponse.json({
          tracks: [],
          total: 0,
          has_more: false
        })
      })
    )

    render(<ComfortableApp />)

    // Verify empty state shown
    await waitFor(() => {
      expect(screen.getByText(/no tracks found/i)).toBeInTheDocument()
    })

    // Verify no pagination attempted
    expect(screen.queryByText('Loading more...')).not.toBeInTheDocument()
  })
})
```

---

### 5. WebSocket Update Tests (20 tests)

**File:** `src/test/api-integration/websocket-updates.test.tsx`

**Purpose:** Verify real-time updates via WebSocket

**Tests:**

#### Player State Updates (5 tests)
1. ✅ Should update play state on WebSocket message
2. ✅ Should update current time on WebSocket message
3. ✅ Should update volume on WebSocket message
4. ✅ Should update queue on WebSocket message
5. ✅ Should handle track change on WebSocket message

#### Library Updates (5 tests)
6. ✅ Should add new track on WebSocket message
7. ✅ Should update track metadata on WebSocket message
8. ✅ Should remove track on WebSocket message
9. ✅ Should update library stats on WebSocket message
10. ✅ Should trigger UI refresh on library scan complete

#### Enhancement Updates (5 tests)
11. ✅ Should update preset on WebSocket message
12. ✅ Should update parameters on WebSocket message
13. ✅ Should update audio characteristics on WebSocket message
14. ✅ Should show processing progress on WebSocket message
15. ✅ Should notify on processing complete

#### Connection Handling (5 tests)
16. ✅ Should connect WebSocket on mount
17. ✅ Should reconnect on connection loss
18. ✅ Should handle reconnection backoff (1s, 2s, 4s, 8s)
19. ✅ Should show connection status indicator
20. ✅ Should queue messages during disconnection

**Example Test:**
```typescript
describe('WebSocket Update Tests', () => {
  let mockWS: MockWebSocket

  beforeEach(() => {
    mockWS = mockWebSocket()
  })

  it('should update play state on WebSocket message', async () => {
    render(<ComfortableApp />)

    // Wait for WebSocket connection
    await waitFor(() => {
      expect(mockWS).toHaveBeenCalledWith('ws://localhost:8765/ws')
    })

    // Get WebSocket instance
    const ws = mockWS.mock.results[0].value

    // Simulate play state update
    ws.simulateMessage({
      type: 'player_state',
      data: {
        is_playing: true,
        current_track: {
          id: 1,
          title: 'Test Track',
          artist: 'Test Artist'
        }
      }
    })

    // Verify UI updated
    await waitFor(() => {
      expect(screen.getByTestId('pause-button')).toBeInTheDocument()
      expect(screen.getByText('Test Track')).toBeInTheDocument()
    })
  })

  it('should trigger refresh on library scan complete', async () => {
    render(<ComfortableApp />)

    await waitForWebSocketConnection()

    // Simulate scan complete message
    mockWS.simulateMessage({
      type: 'library_scan_complete',
      data: {
        tracks_added: 50,
        tracks_updated: 10,
        total_tracks: 200
      }
    })

    // Verify library refreshed
    await waitFor(() => {
      expect(screen.getByText(/50 tracks added/i)).toBeInTheDocument()
    })

    // Verify API called to refresh library
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/library/tracks')
      )
    })
  })

  it('should reconnect on connection loss', async () => {
    vi.useFakeTimers()

    render(<ComfortableApp />)

    await waitForWebSocketConnection()

    // Simulate connection loss
    const ws = mockWS.mock.results[0].value
    ws.close()

    // Verify reconnection attempted after 1s
    vi.advanceTimersByTime(1000)

    await waitFor(() => {
      expect(mockWS).toHaveBeenCalledTimes(2)
    })

    vi.useRealTimers()
  })
})
```

---

## Implementation Priority & Timeline

### Phase 1: High Priority (Week 1-2) - 60 tests
**Focus: Recently refactored components**

**Priority 1A: PlayerBarV2 Integration (20 tests)**
- File: `player-controls.test.tsx`
- Reason: New component with 7 sub-components, critical path
- Estimated time: 4 days

**Priority 1B: EnhancementPaneV2 Integration (20 tests)**
- File: `enhancement-panel.test.tsx`
- Reason: New component with 10 sub-components, complex interactions
- Estimated time: 4 days

**Priority 1C: Error Handling (20 tests)**
- File: `error-handling.test.tsx`
- Reason: Critical for production stability
- Estimated time: 3 days

### Phase 2: Medium Priority (Week 3-4) - 80 tests
**Focus: Core workflows**

**Priority 2A: Library Workflow (20 tests)**
- File: `library-workflow.test.tsx`
- Reason: Primary user journey
- Estimated time: 4 days

**Priority 2B: Search & Filter (20 tests)**
- File: `search-filter-play.test.tsx`
- Reason: Heavy user interaction
- Estimated time: 3 days

**Priority 2C: Pagination (20 tests)**
- File: `pagination.test.tsx`
- Reason: Backend integration, critical for large libraries
- Estimated time: 3 days

**Priority 2D: Loading States (20 tests)**
- File: `loading-states.test.tsx`
- Reason: UX polish
- Estimated time: 3 days

### Phase 3: Standard Priority (Week 5-6) - 60 tests
**Focus: Remaining coverage**

**Priority 3A: Mock Responses (20 tests)**
- File: `mock-responses.test.tsx`
- Reason: API contract validation
- Estimated time: 3 days

**Priority 3B: WebSocket Updates (20 tests)**
- File: `websocket-updates.test.tsx`
- Reason: Real-time features
- Estimated time: 4 days

**Priority 3C: Artwork Management (20 tests)**
- File: `artwork-management.test.tsx`
- Reason: Secondary feature
- Estimated time: 3 days

### Total Timeline: 6 weeks (30 business days)

**Breakdown:**
- Week 1-2: 60 tests (PlayerBarV2, EnhancementPaneV2, Error Handling)
- Week 3-4: 80 tests (Library, Search, Pagination, Loading)
- Week 5-6: 60 tests (Mock Responses, WebSocket, Artwork)

**Daily velocity target:** 3-4 tests/day average

---

## Testing Patterns & Best Practices

### 1. Component Test Pattern

```typescript
import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@/test/test-utils'
import { server } from '@/test/mocks/server'
import { http, HttpResponse } from 'msw'

describe('ComponentName Integration', () => {
  beforeEach(() => {
    // Setup MSW handlers for this test suite
    server.use(
      http.get('/api/endpoint', () => {
        return HttpResponse.json({ data: 'mock data' })
      })
    )
  })

  it('should test specific behavior', async () => {
    // 1. Arrange - Render component
    render(<ComponentName />)

    // 2. Act - Interact with component
    fireEvent.click(screen.getByText('Button'))

    // 3. Assert - Verify expected behavior
    await waitFor(() => {
      expect(screen.getByText('Expected Result')).toBeInTheDocument()
    })
  })
})
```

### 2. MSW Handler Pattern

```typescript
// src/test/mocks/handlers.ts
import { http, HttpResponse } from 'msw'

export const handlers = [
  // Success response
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

  // Error response
  http.get('/api/library/albums', () => {
    return HttpResponse.json(
      { error: 'Database error' },
      { status: 500 }
    )
  }),

  // Delayed response
  http.get('/api/player/state', async () => {
    await new Promise(resolve => setTimeout(resolve, 500))
    return HttpResponse.json(mockPlayerState)
  })
]
```

### 3. Test Helper Functions

```typescript
// src/test/utils/test-helpers.ts

export async function waitForWebSocketConnection() {
  await waitFor(() => {
    expect(mockWS).toHaveBeenCalled()
  })
}

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

export async function uploadArtworkFile(filename: string) {
  const file = new File(['artwork'], filename, { type: 'image/jpeg' })
  const input = screen.getByLabelText('Upload Artwork') as HTMLInputElement

  Object.defineProperty(input, 'files', {
    value: [file],
    writable: false,
  })
  fireEvent.change(input)
}
```

### 4. Design Token Testing

Since all components now use design tokens, verify token usage:

```typescript
it('should use design tokens for colors', () => {
  const { container } = render(<PlayerBarV2 />)

  const playerBar = container.firstChild as HTMLElement
  const styles = window.getComputedStyle(playerBar)

  // Verify background uses token
  expect(styles.backgroundColor).toBe('rgb(26, 31, 58)') // tokens.bg.primary
})

it('should use design tokens for spacing', () => {
  render(<EnhancementPaneV2 />)

  const pane = screen.getByTestId('enhancement-pane-v2')
  const styles = window.getComputedStyle(pane)

  // Verify padding uses token
  expect(styles.padding).toBe('24px') // tokens.spacing.lg
})
```

### 5. Performance Testing Pattern

```typescript
it('should render large list performantly', async () => {
  const startTime = performance.now()

  render(<TrackListView tracks={largeMockTracklist} />)

  await waitFor(() => {
    expect(screen.getAllByTestId('track-row')).toHaveLength(50)
  })

  const endTime = performance.now()
  const renderTime = endTime - startTime

  // Should render in < 100ms
  expect(renderTime).toBeLessThan(100)
})
```

---

## Success Criteria

### Test Coverage
- ✅ 200 frontend integration tests implemented
- ✅ 100% of refactored components tested (PlayerBarV2, EnhancementPaneV2, Sidebar, etc.)
- ✅ 100% of API endpoints covered by MSW mocks
- ✅ 98%+ pass rate (from current 95.5%)

### Test Quality
- ✅ All tests follow AAA pattern (Arrange-Act-Assert)
- ✅ No flaky tests (deterministic, no race conditions)
- ✅ Tests run in < 30 seconds total
- ✅ Clear test descriptions (readable by non-developers)

### Documentation
- ✅ All test files have descriptive headers
- ✅ Complex tests have inline comments
- ✅ Test utilities documented in JSDoc
- ✅ README.md updated with test commands

### Infrastructure
- ✅ MSW installed and configured
- ✅ WebSocket mocking working
- ✅ Test helpers extracted to utilities
- ✅ CI/CD integration (if applicable)

---

## Known Blockers & Risks

### Current Issues
1. **11 failing gapless playback tests** - Need investigation
   - Location: `src/components/player/__tests__/GaplessPlayback.test.tsx`
   - Risk: May indicate real bug in gapless playback
   - Mitigation: Fix before adding new tests

2. **MSW not yet installed** - Required for API integration tests
   - Risk: Cannot proceed with Part 2 tests
   - Mitigation: Install immediately (5 minutes)

3. **IntersectionObserver mocking** - Needed for infinite scroll tests
   - Current mock in setup.ts is basic
   - Risk: May need enhanced mock for pagination tests
   - Mitigation: Enhance mock if needed

### Potential Challenges
1. **WebSocket testing complexity** - Real-time updates hard to test
   - Solution: Use MockWebSocket class with helper methods

2. **Drag-and-drop testing** - DnD library may be hard to test
   - Solution: Use Testing Library's fireEvent for drag events

3. **Audio playback testing** - Can't actually play audio in tests
   - Solution: Mock HTMLAudioElement and UnifiedWebMAudioPlayer

4. **Design token verification** - Hard to verify computed styles
   - Solution: Use getComputedStyle() sparingly, focus on behavior

---

## Next Steps

### Immediate Actions (Day 1)
1. ✅ Install MSW: `npm install msw --save-dev`
2. ✅ Create `src/test/mocks/server.ts`
3. ✅ Create `src/test/mocks/handlers.ts` with all API endpoints
4. ✅ Update `src/test/setup.ts` to start MSW server
5. ✅ Create test helper utilities in `src/test/utils/`

### Week 1 Tasks
1. Create `src/test/integration/` directory structure
2. Implement Priority 1A: PlayerBarV2 tests (20 tests)
3. Implement Priority 1B: EnhancementPaneV2 tests (20 tests)
4. Daily standup: Review pass rate, fix flaky tests

### Week 2 Tasks
1. Implement Priority 1C: Error handling tests (20 tests)
2. Review and fix 11 failing gapless playback tests
3. Run full test suite, verify 98%+ pass rate
4. Update documentation

### Week 3-6 Tasks
1. Follow priority roadmap (Phase 2 & 3)
2. Weekly reviews: adjust priorities if needed
3. Fix issues as they arise
4. Final documentation update

---

## Appendix

### A. API Endpoints Reference

**Player API** (`/api/player/`):
- POST `/play` - Start playback
- POST `/pause` - Pause playback
- POST `/seek` - Seek to position
- POST `/next` - Skip to next track
- POST `/previous` - Skip to previous track
- PUT `/volume` - Set volume
- GET `/state` - Get player state
- GET `/queue` - Get queue

**Library API** (`/api/library/`):
- GET `/tracks` - List tracks (paginated)
- GET `/albums` - List albums (paginated)
- GET `/artists` - List artists (paginated)
- POST `/scan` - Scan library
- GET `/stats` - Get library statistics

**Enhancement API** (`/api/enhancement/`):
- GET `/settings` - Get enhancement settings
- PUT `/settings` - Update enhancement settings
- POST `/apply` - Apply enhancement to track
- GET `/presets` - List available presets
- GET `/analysis` - Get audio analysis

**Metadata API** (`/api/metadata/`):
- GET `/:trackId` - Get track metadata
- PUT `/:trackId` - Update track metadata

**Artwork API** (`/api/artwork/`):
- POST `/upload` - Upload artwork
- POST `/extract` - Extract embedded artwork
- GET `/:albumId` - Get album artwork

**System API** (`/api/`):
- GET `/health` - Health check
- GET `/version` - Version info

### B. Test Data Reference

Located in `src/test/mocks/api.ts`:
- `mockTrack` - Single track object
- `mockTracks` - Array of tracks
- `mockAlbum` - Single album object
- `mockAlbums` - Array of albums
- `mockArtist` - Single artist object
- `mockPlaylist` - Single playlist object
- `mockPlayerState` - Player state object
- `mockProcessingJob` - Processing job object
- `mockLibraryStats` - Library statistics
- `mockScanProgress` - Scan progress object

### C. Testing Commands

```bash
# Run all tests
npm test

# Run with UI
npm run test:ui

# Run specific file
npm test library-workflow.test.tsx

# Run with coverage
npm run test:coverage

# Run in watch mode
npm run test:watch

# Run integration tests only
npm test -- --testPathPattern=integration
```

---

## Revision History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | Nov 9, 2025 | Initial plan created |

---

**Document Owner:** Auralis Testing Team
**Review Cycle:** Weekly during implementation
**Status:** ✅ Ready for Implementation

# 🏗️ Frontend Architecture V3 (Redesigned)

**Version:** 3.0.0-design
**Status:** Planning Phase
**Created:** November 30, 2025

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Browser (Single Page App)                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │              React Application (Vite)                     │ │
│  ├───────────────────────────────────────────────────────────┤ │
│  │                                                           │ │
│  │  ┌────────────────┐  ┌────────────────┐  ┌────────────┐ │ │
│  │  │  PlayerBar-v3  │  │ LibraryView-v3 │  │Enhancement│ │ │
│  │  │  (Presentational)  │  (Presentational)  │Pane-v3    │ │ │
│  │  └────────┬───────┘  └────────┬───────┘  └────────┬───┘ │ │
│  │           │                   │                   │     │ │
│  │  ┌────────▼────────────────────▼───────────────────▼───┐ │ │
│  │  │              Hooks Layer (Business Logic)          │ │ │
│  │  ├──────────────────────────────────────────────────────┤ │ │
│  │  │                                                      │ │ │
│  │  │  ┌─────────────┐  ┌─────────────┐  ┌────────────┐  │ │ │
│  │  │  │ usePlayer() │  │useLibrary() │  │useEnhance..│  │ │ │
│  │  │  │             │  │             │  │            │  │ │ │
│  │  │  │ • State     │  │ • Queries   │  │ • Settings │  │ │ │
│  │  │  │ • Controls  │  │ • Pagination│  │ • Presets  │  │ │ │
│  │  │  │ • Fingerprnt│  │ • Cache     │  │ • Recommen.│  │ │ │
│  │  │  └─────┬───────┘  └──────┬──────┘  └──────┬─────┘  │ │ │
│  │  │        │                  │                │       │ │ │
│  │  └────────┼──────────────────┼────────────────┼───────┘ │ │
│  │           │                  │                │         │ │
│  │  ┌────────▼──────────────────▼────────────────▼───────┐ │ │
│  │  │            Services & Infrastructure              │ │ │
│  │  ├──────────────────────────────────────────────────────┤ │ │
│  │  │                                                      │ │ │
│  │  │  WebSocket       REST API        Fingerprint       │ │ │
│  │  │  Connection      Client          Cache             │ │ │
│  │  │  ┌──────────┐   ┌──────────┐   ┌──────────────┐   │ │ │
│  │  │  │ Context  │   │ Zod      │   │ IndexedDB    │   │ │ │
│  │  │  │ Provider │   │ Validation   │ ┌────────────┤   │ │ │
│  │  │  │          │   │              │ │ Web Workers│   │ │ │
│  │  │  └──────────┘   └──────────┘   └──────────────┘   │ │ │
│  │  │                                                      │ │ │
│  │  └──────────────────────────────────────────────────────┘ │ │
│  │                        ▲                                  │ │
│  │  ┌─────────────────────┼──────────────────────────────┐  │ │
│  │  │    Design System    │  Styling                     │  │ │
│  │  │  ┌─────────────────────────────────────────────┐  │  │ │
│  │  │  │  tokens.ts (Single Source of Truth)        │  │  │ │
│  │  │  │  • Colors, spacing, typography             │  │  │ │
│  │  │  │  • Shadows, transitions, z-index          │  │  │ │
│  │  │  │  • All components use ONLY tokens           │  │  │ │
│  │  │  └─────────────────────────────────────────────┘  │  │ │
│  │  └─────────────────────────────────────────────────────┘  │ │
│  │                                                           │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  Network Communication (WebSocket + REST)              │  │
│  ├─────────────────────────────────────────────────────────┤  │
│  │                                                         │  │
│  │  WebSocket (Real-time)       HTTP (REST)              │  │
│  │  └──────────────────────┘    └──────────────────┘     │  │
│  │        ws://localhost:8765      http://localhost:8765  │  │
│  │                                                         │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                              ▲
                              │ Network
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              FastAPI Backend (Python)                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  /api/player/*          /api/library/*      /api/enhancement/* │
│  ├─ play                ├─ /tracks           ├─ /settings      │
│  ├─ pause               ├─ /albums           └─ /recommendation │
│  ├─ seek                ├─ /artists                             │
│  ├─ next                ├─ /search                              │
│  ├─ previous            └─ /metadata                            │
│  └─ volume                                                      │
│                                                                 │
│  /ws (WebSocket)                                               │
│  ├─ player_state                                               │
│  ├─ playback_started                                           │
│  ├─ track_changed                                              │
│  ├─ enhancement_settings_changed                               │
│  ├─ mastering_recommendation                                   │
│  └─ library_updated                                            │
│                                                                 │
│                                                                 │
│  Audio Processing Engine                    Database           │
│  ├─ HybridProcessor                        ├─ SQLite           │
│  ├─ ChunkedProcessor                       ├─ Tracks           │
│  ├─ StreamedWebMAudioPlayer                ├─ Albums           │
│  └─ Enhancement Profiles                   └─ Metadata        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Component Hierarchy

### Player Bar (v3)

```
PlayerBar-v3 (< 100 lines)
├── TrackInfo (< 100 lines)
│   └── AlbumArtwork
├── PlaybackControls (< 80 lines)
│   ├── PreviousButton
│   ├── PlayPauseButton
│   └── NextButton
├── ProgressBar (< 120 lines)
│   ├── SeekSlider
│   ├── CurrentTimeDisplay
│   ├── DurationDisplay
│   └── CrossfadeVisualization
└── VolumeControl (< 100 lines)
    ├── MuteButton
    └── VolumeSlider
```

### Library View (v3)

```
LibraryView-v3 (< 150 lines)
├── SearchBar (< 80 lines)
│   └── DebounceSearch (300ms)
├── ViewToggle (< 50 lines)
│   └── tracks | albums | artists
├── SortControls (< 60 lines)
│   └── title, artist, date
├── ContentArea
│   ├── TrackList (< 150 lines)
│   │   ├── TrackRow (< 100 lines)
│   │   ├── PlayButton
│   │   ├── SelectCheckbox
│   │   └── ContextMenu
│   ├── AlbumGrid (< 100 lines)
│   │   └── AlbumCard (< 100 lines)
│   │       ├── Artwork
│   │       └── PlayOverlay
│   └── ArtistList (< 120 lines)
│       └── ArtistRow (< 100 lines)
├── InfiniteScroll
│   └── Sentinel element (200px ahead)
└── MetadataEditor Dialog
    ├── FormFields
    ├── SaveButton
    └── ErrorDisplay
```

### Enhancement Pane (v3)

```
EnhancementPane-v3 (< 100 lines)
├── Toggle Switch (< 40 lines)
│   └── Enhancement ON/OFF
├── PresetSelector (< 100 lines)
│   ├── AdaptiveButton
│   ├── GentleButton
│   ├── WarmButton
│   ├── BrightButton
│   └── PunchyButton
├── IntensitySlider (< 80 lines)
│   ├── Slider (0-1)
│   └── PercentageDisplay
├── MasteringRecommendation (< 120 lines)
│   ├── ProfileName
│   ├── ConfidenceScore
│   ├── HybridBlend
│   └── Reasoning
└── ParameterDisplay (< 100 lines)
    ├── LoudnessChange
    ├── CrestChange
    └── CentroidChange
```

---

## Data Flow: User Action → State Update

### Scenario 1: User Clicks Play

```
User clicks play button
    ↓
PlayPauseButton onClick → usePlaybackControl().play()
    ↓
REST API call: POST /api/player/play
    ↓
Backend processes request
    ↓
Backend broadcasts: {
  type: 'playback_started',
  data: { state: 'playing' }
}
    ↓
WebSocket message received
    ↓
usePlaybackState() updates: isPlaying = true
    ↓
PlayerBar-v3 re-renders with pause button
    ↓
User sees playback started
```

### Scenario 2: User Seeks to 2:30

```
User drags progress slider
    ↓
ProgressBar onChange → usePlaybackControl().seek(150)
    ↓
REST API call: PUT /api/player/seek with position: 150
    ↓
Optimistic UI update (position = 150 immediately)
    ↓
Backend processes seek
    ↓
Backend broadcasts: {
  type: 'position_changed',
  data: { position: 150 }
}
    ↓
WebSocket message received
    ↓
usePlaybackState() updates: position = 150
    ↓
ProgressBar re-renders with new position
    ↓
If server position differs > 1s, snap to server time
```

### Scenario 3: User Toggles Enhancement

```
User clicks enhancement toggle
    ↓
EnhancementPane toggleEnabled()
    ↓
useEnhancement().toggleEnabled()
    ↓
Optimistic UI update (toggle = true immediately)
    ↓
REST API call: PUT /api/enhancement/settings
    ↓
Backend re-processes audio with new settings
    ↓
Backend broadcasts: {
  type: 'enhancement_settings_changed',
  data: { enabled: true, preset: 'adaptive', intensity: 1.0 }
}
    ↓
WebSocket message received
    ↓
useEnhancement() updates: settings = {...}
    ↓
EnhancementPane re-renders
    ↓
If server disagrees, revert and show error
```

### Scenario 4: Backend Pushes Mastering Recommendation

```
User plays new track
    ↓
Backend fingerprints track
    ↓
Backend generates mastering recommendation
    ↓
Backend broadcasts: {
  type: 'mastering_recommendation',
  data: { track_id: 42, ... }
}
    ↓
WebSocket message received
    ↓
useEnhancement() updates: recommendation = {...}
    ↓
EnhancementPane re-renders
    ↓
MasteringRecommendation shows profile + confidence
    ↓
User sees recommendations immediately
```

---

## State Management Strategy

### Phase 0-1: Redux (Legacy)
- Keep existing Redux for backwards compatibility
- Gradually migrate to Context + Hooks

### Phase 1-3: Hooks + Context
- `usePlayer()` - Playback state via WebSocket
- `useLibrary()` - Library queries with caching
- `useEnhancement()` - Audio settings
- WebSocketContext - Unified connection
- No Redux for new components

### Phase 4: Consolidation
- Evaluate full Redux removal
- Consolidate all state to Hooks + Context
- Simplify state management

---

## Fingerprint Cache Flow

```
User starts playing track ID 42
    ↓
PlayerBar calls: useFingerprintCache().preprocess(42)
    ↓
Check IndexedDB for fingerprint 42
    ┌──────────────────┐
    │ IF CACHED:       │
    │ • Return cached  │
    │ • Set state=ready│
    └──────────────────┘
         ↓
    ┌──────────────────┐
    │ IF NOT CACHED:   │
    │ • Set state=processing
    │ • Start Web Worker
    │ • Send message:  │
    │   { trackId: 42 }│
    └──────────────────┘
         ↓
    Web Worker (background thread)
    ├─ Load audio chunk
    ├─ Compute fingerprint
    ├─ Send progress: 0%, 50%, 100%
    ├─ Send result when done
    └─ Terminate
         ↓
    Main thread receives result
    ├─ Cache in IndexedDB
    ├─ Set state=ready
    └─ useFingerprintCache() returns fingerprint
         ↓
    UI shows buffering progress (0-100%)
    User thinks audio is buffering
    Actually fingerprint is being computed!
         ↓
    Track plays (fingerprint now ready)
    Mastering recommendation shows immediately
```

---

## API Contract

### WebSocket Messages (Subscribe in hooks)

```typescript
type: 'player_state'           → usePlaybackState
type: 'playback_started'       → usePlaybackState
type: 'playback_paused'        → usePlaybackState
type: 'track_changed'          → usePlaybackState
type: 'position_changed'       → usePlaybackState
type: 'volume_changed'         → usePlaybackState
type: 'queue_updated'          → usePlaybackState + useLibrary
type: 'enhancement_settings_changed' → useEnhancement
type: 'mastering_recommendation'    → useEnhancement
type: 'library_updated'        → useLibrary
type: 'metadata_updated'       → useLibrary
type: 'scan_progress'          → useLibrary
type: 'scan_complete'          → useLibrary
```

### REST Endpoints

```
GET    /api/library/tracks       → useLibrary()
GET    /api/library/albums       → useLibrary()
GET    /api/library/artists      → useLibrary()
POST   /api/player/play          → usePlaybackControl()
POST   /api/player/pause         → usePlaybackControl()
PUT    /api/player/seek          → usePlaybackControl()
POST   /api/player/next          → usePlaybackControl()
POST   /api/player/previous      → usePlaybackControl()
PUT    /api/player/volume        → usePlaybackControl()
PUT    /api/enhancement/settings → useEnhancement()
GET    /api/enhancement/settings → useEnhancement()
PUT    /api/metadata/tracks/{id} → useLibrary()
POST   /api/metadata/batch       → useLibrary()
```

---

## Error Handling Strategy

### Network Errors
```
REST API call fails
    ↓
Catch error in hook
    ↓
Show toast: "Network error. Retrying..."
    ↓
Retry after 2 seconds
    ↓
If still fails, show: "Connection lost. Try again?"
```

### State Conflicts
```
Local state: position = 100
Server state: position = 105
    ↓
If difference > 1s:
  Snap to server time (server is authoritative)
    ↓
Show toast: "Position adjusted to match server"
```

### Invalid Operations
```
User tries to play deleted track
    ↓
WebSocket: { type: 'track_loaded', data: { error: 'not_found' } }
    ↓
Show warning: "Track no longer available"
    ↓
Auto-skip to next track after 3 seconds
```

---

## Performance Targets

| Metric | Target | Current |
|--------|--------|---------|
| Initial load | < 3 seconds | TBD |
| Time to interactive | < 2 seconds | TBD |
| Player response | < 200ms | TBD |
| Library scroll (10k items) | 60 FPS | TBD |
| Memory usage (idle) | < 100MB | TBD |
| Memory usage (full load) | < 300MB | TBD |
| WebSocket latency | < 50ms | TBD |

---

## Testing Architecture

### Unit Tests
```
├── hooks/
│   ├── usePlayer.test.ts
│   ├── useLibrary.test.ts
│   └── useEnhancement.test.ts
├── components/
│   ├── PlayerBar.test.tsx
│   ├── LibraryView.test.tsx
│   └── EnhancementPane.test.tsx
└── services/
    ├── FingerprintCache.test.ts
    └── RestAPI.test.ts
```

### Integration Tests
```
├── player-flow/
│   ├── play-pause.test.ts
│   ├── seek.test.ts
│   └── skip.test.ts
├── library-flow/
│   ├── search.test.ts
│   ├── filter.test.ts
│   └── infinite-scroll.test.ts
└── enhancement-flow/
    ├── toggle.test.ts
    ├── preset-switch.test.ts
    └── recommendation.test.ts
```

### E2E Tests (Playwright)
```
├── complete-flow.e2e.ts
├── error-recovery.e2e.ts
└── performance.e2e.ts
```

---

## Deployment Architecture

```
Development (npm run dev)
├── Vite dev server (port 3000)
├── Hot reload enabled
├── Source maps enabled
└── Backend on port 8765

Production (npm run build)
├── Tree-shaken bundle
├── Code split by route
├── Images optimized
├── Service worker for offline
└── Gzip compression enabled

Electron (Desktop)
├── Same React code
├── IPC bridge for native features
├── Local file system access
└── Auto-updates via GitHub releases
```

---

## Browser Compatibility

- Chrome/Edge 90+ (modern)
- Firefox 88+ (modern)
- Safari 14+ (modern)
- No IE11 support

---

## Accessibility (WCAG 2.1 AA)

- ✅ Keyboard navigation (Tab, Enter, Arrow keys)
- ✅ Screen reader support (aria-labels, ARIA regions)
- ✅ Color contrast (4.5:1 minimum)
- ✅ Focus indicators (visible outline)
- ✅ No motion (respects prefers-reduced-motion)

---

*Architecture V3 - Designed November 30, 2025*
*Ready for implementation starting Phase 0 on December 2, 2025*

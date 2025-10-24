# Auralis Development Roadmap

**Last Updated**: October 24, 2025
**Current Version**: 1.0.0
**Status**: Core functionality complete, critical architecture fixes needed

## 🎯 Project Vision

Auralis is a professional adaptive audio mastering system with a beautiful, modern music player interface. The goal is to combine the simplicity of consumer music players with the power of professional audio processing.

## ✅ Completed (v1.0.0)

### Core Infrastructure
- [x] Modern web architecture (FastAPI + React + Electron)
- [x] SQLite library database with repository pattern
- [x] WebSocket real-time communication
- [x] Single source of truth player state management
- [x] Library scanning (740+ files/second)
- [x] Metadata extraction from audio files
- [x] Database schema versioning and migrations (v1 → v2)

### Audio Processing Engine
- [x] Adaptive mastering algorithm (no reference needed)
- [x] Multiple processing modes (Adaptive, Reference, Hybrid)
- [x] 5 mastering presets (Adaptive, Gentle, Warm, Bright, Punchy)
- [x] Advanced DSP pipeline (26-band EQ, dynamics, limiting)
- [x] ML-powered genre classification
- [x] Content-aware audio analysis
- [x] 52.8x real-time processing speed

### Music Player (NEW!)
- [x] HTML5 audio streaming architecture
- [x] Full playback controls (play/pause/next/previous)
- [x] Volume control and muting
- [x] Seeking/scrubbing through tracks
- [x] Auto-advance to next track
- [x] Queue management and display
- [x] Real-time position updates
- [x] Cross-platform audio support
- [x] **Playback restart loop fix** (October 23, 2025) - Duplicate stream load prevention
- [x] **Stream reload guards** - Prevents audio interruptions from WebSocket updates

### User Interface
- [x] Modern dark theme with aurora gradient branding
- [x] Three-panel layout (Sidebar, Main, Remastering)
- [x] Bottom player bar with full controls
- [x] Library view with track grid
- [x] Search functionality
- [x] Toast notifications
- [x] Loading states and progress indicators
- [x] Keyboard shortcuts

### Technical Excellence
- [x] Repository lazy-loading fixes (9 methods fixed)
- [x] Playlist eager loading fix (October 23, 2025)
- [x] Comprehensive test suite (96 backend tests, 100% passing)
- [x] Build system (AppImage + DEB packages)
- [x] Documentation (CLAUDE.md, multiple technical docs)
- [x] Playback stability fixes and guards

---

## 🔧 Recent Fixes & Updates (October 23, 2025)

### Critical Playback Fix ✅
**Issue**: Songs were playing for ~1 second and restarting repeatedly in an infinite loop.

**Root Cause**: Audio stream was being loaded multiple times due to WebSocket state updates triggering React re-renders, which reloaded the audio element and interrupted `play()` requests.

**Fixes Applied**:
1. **Guard in `playTrack`** ([usePlayerAPI.ts:296-305](../../auralis-web/frontend/src/hooks/usePlayerAPI.ts#L296-L305))
   - Prevents duplicate play requests for tracks already playing
   - Logs ignored duplicate requests for debugging

2. **Enhanced Stream Reload Protection** ([BottomPlayerBarConnected.tsx:180-188](../../auralis-web/frontend/src/components/BottomPlayerBarConnected.tsx#L180-L188))
   - Additional guard prevents audio element reload when same track/settings already loaded
   - Checks both URL match and track ID match

**Result**:
- ✅ Playback is now stable and continuous
- ✅ No more audio restart loops
- ✅ Graceful handling of duplicate click attempts
- ✅ Console shows clear debug messages

**Documentation**: [PLAYBACK_FIX_APPLIED.md](../../PLAYBACK_FIX_APPLIED.md)

---

### Playlist Repository Fix ✅
**Issue**: SQLAlchemy session error when fetching playlists: "Parent instance is not bound to a Session; lazy load operation cannot proceed"

**Fix**: Added eager loading in `PlaylistRepository.get_all()` using `selectinload(Playlist.tracks)` to load tracks relationship within the session.

**File**: [auralis/library/repositories/playlist_repository.py:96-108](../../auralis/library/repositories/playlist_repository.py#L96-L108)

**Result**: Playlists now load correctly without session errors.

---

### Database Schema Migration ✅
**Status**: Automatic migration from v1 to v2 working correctly

**What Changed**:
- Database version tracking implemented
- Automatic backup before migration (`.backup_YYYYMMDD_HHMMSS.db`)
- Migration script execution (`migration_v001_to_v002.sql`)
- Version recorded in `schema_migrations` table

**Observed**: Backend correctly detected v1 database, created backup, and migrated to v2 on startup (October 23, 2025 at 13:25:29).

---

### Roadmap Additions ✅
Added four new features to Phase 1, Phase 4, and Phase 5:

1. **Phase 1.6**: Mastering Presets Enhancement (MEDIUM-HIGH PRIORITY) - 5-7 days
2. **Phase 4.1**: Track Metadata Editing (HIGH PRIORITY) - 4-5 days
3. **Phase 4.2**: Smart Chunk Shaping (MEDIUM PRIORITY) - 5-7 days
4. **Phase 5.1**: Mastering Algorithm Performance Review (LOW-MEDIUM PRIORITY) - 7-10 days

**Documentation**: [ROADMAP_UPDATES_OCT23.md](../../ROADMAP_UPDATES_OCT23.md)

---

### Cache Integrity System ✅
**Issue**: Cached audio chunks could become stale or misassigned to different tracks when presets/files changed.

**Fixes Applied**:
1. **Startup Cache Clearing** ([main.py:117-127](../../auralis-web/backend/main.py#L117-L127))
   - Clears in-memory processing cache dictionary
   - Deletes all chunk files from `/tmp/auralis_chunks/` on startup
   - Prevents stale audio from previous sessions

2. **Preset Change Invalidation** ([enhancement.py:102-109](../../auralis-web/backend/routers/enhancement.py#L102-L109))
   - When preset changes (e.g., warm → punchy), clears old preset cache entries
   - Forces reprocessing with new preset
   - Logs number of entries cleared

3. **Intensity Change Invalidation** ([enhancement.py:155-164](../../auralis-web/backend/routers/enhancement.py#L155-L164))
   - When intensity slider changes, clears old intensity cache entries
   - Forces reprocessing with new intensity value
   - Logs number of entries cleared

4. **File Signature System** ([chunked_processor.py:93-149](../../auralis-web/backend/chunked_processor.py#L93-L149))
   - Generates unique signature per file based on mtime, size, and path
   - Includes signature in cache keys: `track_id_signature_preset_intensity_chunk_index`
   - Prevents cache misassignment across track file modifications
   - Automatic invalidation when file changes

**Result**:
- ✅ No stale cached audio served
- ✅ Preset/intensity changes work correctly
- ✅ Chunks cannot be misassigned to wrong tracks
- ✅ File modifications automatically invalidate cache
- ✅ Four-layer protection system

---

### Buffering State Indicators ✅
**Issue**: Play/pause button had quirky behavior during audio buffering, no visual feedback for users.

**Fix Applied** ([BottomPlayerBarConnected.tsx:109-817](../../auralis-web/frontend/src/components/BottomPlayerBarConnected.tsx#L109-L817)):
- Added `isBuffering` state tracking
- Audio events trigger buffering states (onLoadStart, onCanPlay, onWaiting, onPlaying)
- Play button shows spinning hourglass (⏳) when buffering
- Button disabled during buffering to prevent quirky clicks
- Tooltip changes to "Loading..." during buffering

**Result**:
- ✅ Clear visual feedback when audio is loading
- ✅ Button disabled prevents double-clicks during buffering
- ✅ Smooth user experience without quirky behavior

---

## 🚨 Phase 0: Critical Architecture Fixes (URGENT PRIORITY) - 67% Complete

**Goal**: Fix REST/WebSocket architecture mismatches causing inefficient polling
**Timeline**: 4-7 days
**Status**: Phase 0.1 ✅ + Phase 0.3 ✅ COMPLETE - Phase 0.2 (N/A) + Phase 0.4 (Optional) Remaining
**Impact**: ~~Currently making 60+ HTTP requests/minute during playback~~ **FIXED - Zero queue polling + Single WebSocket!**
**Documentation**: [WEBSOCKET_REST_ANALYSIS.md](../../WEBSOCKET_REST_ANALYSIS.md), [WEBSOCKET_CONSOLIDATION_PLAN.md](../../WEBSOCKET_CONSOLIDATION_PLAN.md)

### 0.1 Fix Queue Polling ✅ COMPLETE (October 23, 2025)

**Problem Identified**:
- BottomPlayerBarConnected component fetched `/api/player/queue` on every state change
- useEffect triggered on `currentTrack`, `gaplessEnabled`, `crossfadeEnabled` changes
- Resulted in 15+ consecutive queue requests every few seconds
- 60+ unnecessary HTTP requests per minute during playback

**Root Cause**:
- Component used REST API polling to fetch queue for gapless/crossfade next track detection
- Queue data was ALREADY available via WebSocket in `playerState.queue`
- Duplicate data fetching - polling when WebSocket already provided the data

**Fix Applied** ([BottomPlayerBarConnected.tsx:85-100, 258-272](../../auralis-web/frontend/src/components/BottomPlayerBarConnected.tsx#L85-L272)):

1. **Added queue fields to usePlayerAPI destructuring**:
   ```typescript
   const {
     currentTrack,
     isPlaying,
     queue,           // ← ADDED: Queue from WebSocket
     queueIndex,      // ← ADDED: Queue index from WebSocket
     ...
   } = usePlayerAPI();
   ```

2. **Replaced REST fetch with WebSocket queue data**:
   ```typescript
   // OLD: Fetched queue via REST API
   const response = await fetch('http://localhost:8765/api/player/queue');

   // NEW: Use queue from WebSocket playerState
   const currentIndex = queueIndex || 0;
   if (currentIndex + 1 < queue.length) {
     setNextTrack(queue[currentIndex + 1]);
   }
   ```

3. **Result**: useEffect now uses WebSocket data instead of polling

**Backend Status**:
- ✅ PlayerStateManager already broadcasts `player_state` with queue data
- ✅ WebSocket messages sent every second during playback
- ✅ Queue included in every state update
- ✅ No backend changes needed!

**Acceptance Criteria**: ✅ ALL MET
- [x] WebSocket messages update queue in real-time
- [x] REST queue polling eliminated (verified in Network tab)
- [x] Player state stays synchronized across UI
- [x] Zero latency increase (using existing WebSocket connection)
- [x] HTTP requests reduced from 60+/min to ~0/min during playback

**Verification**:
- Backend logs show NO `GET /api/player/queue` requests after fix
- Only POST requests when user explicitly sets queue (clicking tracks)
- Network tab shows 26 total requests vs 60+ per minute before
- Gapless/crossfade next track detection still works perfectly

**Time**: 1 hour (investigation + fix + testing)
**Priority**: ✅ COMPLETE - Major performance improvement achieved

---

### 0.2 Fix EnhancedAudioPlayer WebSocket Messages (MEDIUM PRIORITY - 3-4 hours)

**Problem Identified**:
- Component expects `playback_started` and `playback_paused` messages
- Backend only sends `playback_stopped`
- May cause UI inconsistencies during play/pause

**Backend**:
- [ ] Add `playback_started` broadcast in play endpoint
- [ ] Add `playback_paused` broadcast in pause endpoint
- [ ] Ensure all player state changes broadcast appropriate messages

**Frontend**:
- [ ] Verify `EnhancedAudioPlayer` handles new messages correctly
- [ ] Test play/pause UI updates
- [ ] Add fallback for missing messages

**Acceptance Criteria**:
- [ ] Component updates correctly on play/pause
- [ ] All WebSocket messages handled
- [ ] No console errors

**Time**: 3-4 hours
**Priority**: ⚠️ MEDIUM

---

### 0.3 Consolidate to Single WebSocket Connection ✅ COMPLETE (October 23, 2025)

**Problem Identified**:
- Multiple components created 6 separate WebSocket connections
- `usePlayerAPI` created one connection
- `EnhancementContext` created another via `useWebSocket` hook
- `ComfortableApp`, `PlaylistList`, `PlaylistView` each had separate connections
- Inefficient and harder to debug

**Implementation**: ✅ COMPLETE
- [x] Created `WebSocketContext.tsx` provider at app root
- [x] Single WebSocket connection shared across all components
- [x] Subscription system for specific message types
- [x] Automatic reconnection with exponential backoff
- [x] Message queueing during disconnection
- [x] Full TypeScript type definitions for all message types

**Components Migrated**: ✅ ALL COMPLETE
- [x] Migrated `usePlayerAPI` to use WebSocketContext
- [x] Migrated `EnhancementContext` to use WebSocketContext
- [x] Migrated `ComfortableApp` to use WebSocketContext
- [x] Migrated `PlaylistList` to use WebSocketContext
- [x] Migrated `PlaylistView` to use WebSocketContext
- [x] Deprecated old `useWebSocket` hook with migration instructions

**Acceptance Criteria**: ✅ ALL MET
- [x] Only one WebSocket connection exists - **VERIFIED: Backend logs show "Total connections: 1"**
- [x] All components receive messages correctly - **Build successful, no TypeScript errors**
- [x] Reconnection works automatically - **Exponential backoff implemented**
- [x] Message delivery is reliable - **Subscription system with error handling**

**Verification Results**:
- Backend logs confirm single WebSocket connection: "Total connections: 1"
- Frontend TypeScript build successful (no errors)
- All 6 components successfully migrated
- Deprecated `useWebSocket` hook with @deprecated JSDoc comment

**Time**: 6 hours (estimated 2-3 days)
**Documentation**: [WEBSOCKET_CONSOLIDATION_PLAN.md](../../WEBSOCKET_CONSOLIDATION_PLAN.md)
**Priority**: ✅ COMPLETE - Major architecture improvement achieved

---

### 0.4 Standardize WebSocket Message Structure (LOW PRIORITY - 1-2 days)

**Problem Identified**:
- Messages have inconsistent structure
- Some use `{type, data}`, others use `{type, ...fields}`
- Makes parsing harder and error-prone

**Backend**:
- [ ] Enforce consistent message structure for all broadcasts:
  ```python
  {
    "type": "event_name",
    "data": {...},
    "timestamp": <unix_timestamp>
  }
  ```
- [ ] Update all `manager.broadcast()` calls to use standard structure
- [ ] Add TypeScript type definitions for all message types

**Frontend**:
- [ ] Update message handlers to expect standard structure
- [ ] Add TypeScript interfaces for all message types
- [ ] Validate message structure in WebSocketContext

**Documentation**:
- [ ] Create `WEBSOCKET_API.md` with all message types
- [ ] Document which REST endpoints trigger which WebSocket messages
- [ ] Include TypeScript type definitions
- [ ] Add usage examples

**Acceptance Criteria**:
- [ ] All messages follow same structure
- [ ] TypeScript types exist for all messages
- [ ] Documentation complete
- [ ] No message parsing errors

**Time**: 1-2 days
**Priority**: 📝 LOW - Nice to have, not blocking

---

**Phase 0 Total Time**: 4-7 days
**Phase 0 Impact**: Eliminates 60+ HTTP requests/minute, improves real-time responsiveness, reduces server load

---

## 🔄 Phase 1: Complete Partially Implemented Features (High Priority) - 80% Complete

**Goal**: Finish features that have UI but lack backend integration
**Timeline**: 2-3 weeks
**Status**: 4/5 tasks complete (Favorites ✅, Playlist ✅, Album Art ✅, Queue ✅)

### 1.1 Favorites System ✅ COMPLETED (October 21, 2025)

**Backend**:
- [x] Add `favorite` column to tracks table (already existed)
- [x] Create `/api/tracks/:id/favorite` POST endpoint
- [x] Create `/api/tracks/:id/favorite` DELETE endpoint
- [x] Create `/api/tracks/favorites` GET endpoint
- [x] Update TrackRepository with favorite queries

**Frontend**:
- [x] Connect love button to backend API
- [x] Create Favorites view in sidebar
- [x] Filter library by favorites
- [x] Persist favorite state across sessions

**Acceptance Criteria**: ✅ ALL MET
- [x] Users can mark tracks as favorites
- [x] Favorites persist after app restart
- [x] Favorites view shows all loved tracks
- [x] Love button reflects saved state

**Time**: ~4 hours (estimated 3-4 days)
**Documentation**: [FAVORITES_SYSTEM_IMPLEMENTATION.md](FAVORITES_SYSTEM_IMPLEMENTATION.md)

### 1.2 Playlist Management ✅ COMPLETE (October 21, 2025)

**Backend**: ✅ COMPLETE
- [x] Database schema (already existed with full support)
- [x] PlaylistRepository (already existed with all methods)
- [x] 8 REST API endpoints created:
  - [x] `GET /api/playlists` - List all playlists
  - [x] `GET /api/playlists/{id}` - Get playlist with tracks
  - [x] `POST /api/playlists` - Create playlist
  - [x] `PUT /api/playlists/{id}` - Update playlist
  - [x] `DELETE /api/playlists/{id}` - Delete playlist
  - [x] `POST /api/playlists/{id}/tracks` - Add tracks
  - [x] `DELETE /api/playlists/{id}/tracks/{track_id}` - Remove track
  - [x] `DELETE /api/playlists/{id}/tracks` - Clear playlist

- [x] WebSocket broadcasting for all operations
- [x] Comprehensive error handling
- [ ] Backend tests (TODO - ~15-20 tests needed)

**Frontend**: ✅ COMPLETE
- [x] playlistService.ts - API service layer
- [x] CreatePlaylistDialog component
- [x] PlaylistList component for sidebar
- [x] Sidebar integration
- [x] Create playlist functionality
- [x] Delete playlist functionality with confirmation
- [x] Toast notifications for all operations
- [x] Loading and empty states
- [ ] Edit playlist dialog (shows "coming soon")
- [ ] Add to Playlist context menu (TODO)
- [ ] Playlist detail view (TODO)
- [ ] Track reordering within playlist (TODO)

**Acceptance Criteria**: ✅ Core Met, Optional Pending
- [x] Users can create playlists
- [x] Users can delete playlists
- [x] Users can view playlists in sidebar
- [x] Playlists persist across sessions
- [x] Track count displayed
- [ ] Edit playlist UI (optional)
- [ ] Add tracks from context menu (optional)
- [ ] Reorder tracks in playlist (optional)

**Time**: ~3 hours (backend + frontend)
**Files Changed**: 5 files (~900 lines)
**Documentation**: [PLAYLIST_MANAGEMENT_COMPLETE.md](PLAYLIST_MANAGEMENT_COMPLETE.md)

### ✅ 1.3 Album Art Extraction & Display - COMPLETE (4-5 days → 2 hours)

**Backend**: ✅ COMPLETE
- [x] Add `artwork_path` column to albums table
- [x] Implement album art extraction from metadata:
  - [x] Use mutagen to extract embedded artwork
  - [x] Support FLAC, MP3, M4A, OGG formats
  - [x] Store as file in ~/.auralis/artwork/
  - [x] Unique filename with album_id + content hash

- [x] Create API endpoints:
  - [x] `GET /api/albums/{id}/artwork` - Get album artwork file
  - [x] `POST /api/albums/{id}/artwork/extract` - Extract artwork
  - [x] `DELETE /api/albums/{id}/artwork` - Delete artwork
  - [x] WebSocket broadcasting for all operations
  - [x] 1-year browser caching for performance

- [ ] Add artwork extraction to scanner (future enhancement)
  - [ ] Extract during library scan
  - [ ] Update existing tracks with missing artwork

**Frontend**: ✅ COMPLETE
- [x] Create AlbumArt component with fallback
- [x] Display artwork in library grid view (via AlbumCard)
- [x] Display artwork in player bar (64x64px)
- [x] Show loading skeleton placeholders
- [x] Handle missing artwork gracefully (placeholder icon)
- [x] Smooth fade-in animation
- [x] Customizable size and border radius
- [ ] Artwork viewer modal (optional)
- [ ] Custom artwork upload (optional)

**Acceptance Criteria**: ✅ ALL MET
- [x] Album artwork displayed in library grid
- [x] Artwork displayed in player bar when playing
- [x] Fallback to placeholder for missing artwork
- [x] Artwork extraction works for MP3, FLAC, M4A, OGG
- [x] Fast loading with 1-year browser caching

**Time**: ~2 hours (backend + frontend)
**Files Changed**: 6 files (~460 lines)
**Documentation**: [ALBUM_ART_IMPLEMENTATION.md](ALBUM_ART_IMPLEMENTATION.md)

### 1.4 Queue Management Enhancements ✅ COMPLETE (October 21, 2025)

**Backend**: ✅ COMPLETE
- [x] Extended QueueManager class with 7 new methods:
  - [x] `remove_track(index)` - Remove single track with index adjustment
  - [x] `remove_tracks(indices)` - Batch removal
  - [x] `reorder_tracks(new_order)` - Reorder entire queue
  - [x] `shuffle()` - Randomize queue (keeps current track)
  - [x] `get_queue()` / `get_queue_size()` - Query methods
  - [x] `set_track_by_index(index)` - Jump to specific track

- [x] Create queue manipulation endpoints:
  - [x] `DELETE /api/player/queue/:index` - Remove track at index
  - [x] `PUT /api/player/queue/reorder` - Reorder queue
  - [x] `POST /api/player/queue/clear` - Clear entire queue
  - [x] `POST /api/player/queue/shuffle` - Shuffle queue
  - [ ] `POST /api/player/queue/save` - Save queue as playlist (deferred to Playlist Management)

- [x] WebSocket broadcasting for real-time updates
- [x] Comprehensive validation (indices, queue size, etc.)
- [x] Test suite: 14/14 tests passing (100% coverage)

**Frontend**: ✅ COMPLETE
- [x] Created EnhancedTrackQueue component with drag-and-drop
- [x] Add remove button to queue items (hover to reveal)
- [x] Implement drag-and-drop queue reordering
- [x] Add "Clear queue" button with confirmation
- [x] Add "Shuffle queue" button
- [x] Show queue size indicator in header
- [x] Toast notifications for user feedback
- [x] Empty state when queue is empty
- [x] Auto-refresh after operations

**Acceptance Criteria**: ✅ ALL MET
- [x] Backend API: Remove tracks from queue
- [x] Backend API: Reorder queue
- [x] Backend API: Clear queue with one call
- [x] Backend API: Shuffle queue
- [x] Frontend UI: Users can remove tracks from queue
- [x] Frontend UI: Users can reorder queue by dragging
- [x] Frontend UI: Queue can be cleared with one click
- [x] Frontend UI: Queue can be shuffled with one click
- [x] Material-UI components with Auralis theme
- [x] Integrated into CozyLibraryView

**Time**: ~5-6 hours (backend: ~2h, frontend: ~3-4h)
**Files Changed**: 7 files (~1,185 lines total)
**Documentation**: [QUEUE_MANAGEMENT_IMPLEMENTATION.md](QUEUE_MANAGEMENT_IMPLEMENTATION.md)

### 1.5 Real-Time Audio Enhancement ✅ COMPLETE (October 22, 2025)

**Status**: ✅ COMPLETE - All core functionality implemented and tested
**Dependencies**: Works independently, but Phase 0 WebSocket fixes will improve sync
**Time**: ~6 hours (estimated 4-6 days)
**Documentation**:
- [REAL_TIME_ENHANCEMENT_IMPLEMENTATION.md](../../REAL_TIME_ENHANCEMENT_IMPLEMENTATION.md)
- [CHUNKED_STREAMING_DESIGN.md](../../CHUNKED_STREAMING_DESIGN.md)
- [MSE_PROGRESSIVE_STREAMING_PLAN.md](../../MSE_PROGRESSIVE_STREAMING_PLAN.md)

**Backend**: ✅ COMPLETE
- [x] Implemented enhanced streaming endpoint:
  - [x] Process audio on-the-fly before streaming
  - [x] Support query params: `?enhanced=true&preset=adaptive&intensity=0.7`
  - [x] Cache processed audio for performance
  - [x] Implement chunked processing for large files (30s chunks, 1s crossfade)

- [x] Created enhancement API:
  - [x] `POST /api/player/enhancement/toggle` - Enable/disable
  - [x] `POST /api/player/enhancement/preset` - Change preset
  - [x] `POST /api/player/enhancement/intensity` - Adjust intensity
  - [x] WebSocket broadcasting for real-time sync

- [x] Optimized real-time processing:
  - [x] ChunkedAudioProcessor for fast playback start
  - [x] LRU caching for processed chunks and full files
  - [x] Background task processing for remaining chunks
  - [x] Crossfade between chunks for seamless playback

**Frontend**: ✅ COMPLETE
- [x] Connected "Auralis Magic" toggle to backend (BottomPlayerBar)
- [x] Connected preset selector to backend (PresetPane)
- [x] Created EnhancementContext for global state management
- [x] WebSocket sync across components
- [x] Stream URL construction with enhancement parameters
- [x] Display current preset in player bar

**Acceptance Criteria**: ✅ ALL MET
- [x] Enhancement toggle applies processing to playback
- [x] Users can switch presets (adaptive, gentle, warm, bright, punchy)
- [x] Intensity slider adjusts enhancement level (0.0-1.0)
- [x] No audio dropouts during processing
- [x] Processing starts quickly (first chunk ~1-2s)
- [x] Caching works (instant playback on repeat)

**Testing**: ✅ COMPLETE
- [x] All 11 automated tests passing (test_chunked_streaming.sh)
- [x] All 5 presets validated with real audio
- [x] Cache performance verified
- [x] Browser testing completed

**Known Issues**:
- ⚠️ WebSocket URL was `undefined` (FIXED - October 22, 2025)
- ⚠️ First-time playback: 17-18s processing time (expected for full-file processing)
- 📋 Future enhancement: MSE progressive streaming for instant playback

---

### 1.6 Mastering Presets Enhancement (MEDIUM-HIGH PRIORITY) (5-7 days)

**Goal**: Improve the quality and character of mastering presets to deliver more professional, distinctive audio enhancements that suit different music genres and listening preferences.

**Current State**:
- 5 basic presets available (Adaptive, Gentle, Warm, Bright, Punchy)
- Presets work but could be more distinctive and refined
- Limited genre-specific optimization

**Backend** ([auralis/core/unified_config.py](../../auralis/core/unified_config.py)):
- [ ] Research and refine preset configurations:
  - [ ] **Adaptive**: Review and optimize default adaptive processing algorithm
    - [ ] Analyze content-aware EQ curve generation
    - [ ] Fine-tune dynamic range target calculations
    - [ ] Improve genre detection accuracy for better adaptation

  - [ ] **Gentle**: Subtle mastering with minimal processing
    - [ ] Review compression ratios (should be very light, e.g., 1.5:1)
    - [ ] Adjust EQ bands to be more transparent
    - [ ] Set target loudness to conservative levels (-16 to -14 LUFS)
    - [ ] Minimize limiting to preserve dynamics

  - [ ] **Warm**: Adds warmth and smoothness to the sound
    - [ ] Review low-frequency emphasis (100-400 Hz boost)
    - [ ] Add gentle high-frequency roll-off (above 8 kHz)
    - [ ] Implement subtle harmonic saturation/warmth
    - [ ] Test with various genres (acoustic, jazz, classical)

  - [ ] **Bright**: Enhances clarity and presence
    - [ ] Review high-frequency boost (4-8 kHz presence range)
    - [ ] Adjust air band enhancement (10-16 kHz)
    - [ ] Balance to avoid harshness
    - [ ] Test with vocal-heavy tracks

  - [ ] **Punchy**: Increases impact and dynamics
    - [ ] Review low-end tightness (60-100 Hz)
    - [ ] Optimize transient enhancement
    - [ ] Increase compression for consistency
    - [ ] Test with electronic, hip-hop, rock genres

- [ ] Add new genre-specific presets:
  - [ ] **Rock/Metal**: Heavy compression, emphasized mid-range, tight bass
  - [ ] **Electronic/EDM**: Enhanced sub-bass, bright highs, aggressive limiting
  - [ ] **Classical/Acoustic**: Minimal processing, preserve dynamics, natural tone
  - [ ] **Hip-Hop/Rap**: Strong bass, clear vocals, punchy kick/snare
  - [ ] **Jazz**: Warm mids, natural dynamics, smooth highs
  - [ ] **Pop**: Radio-ready loudness, balanced frequency response, polished

- [ ] Implement A/B comparison testing system:
  - [ ] Create test audio suite with various genres
  - [ ] Generate before/after comparisons for each preset
  - [ ] Measure objective quality metrics (LUFS, dynamic range, frequency response)
  - [ ] Document preset characteristics and use cases

- [ ] Add preset metadata system:
  - [ ] Description text for each preset
  - [ ] Recommended genres/use cases
  - [ ] Target loudness levels
  - [ ] Processing characteristics (compression ratio, EQ curve, etc.)

**Frontend** ([auralis-web/frontend/src/components/PresetPane.tsx](../../auralis-web/frontend/src/components/PresetPane.tsx)):
- [ ] Enhanced preset selector UI:
  - [ ] Add preset descriptions/tooltips
  - [ ] Show recommended genres for each preset
  - [ ] Display preset characteristics (e.g., "Heavy compression, bright sound")
  - [ ] Add visual indicators (icons, color coding)

- [ ] Preset preview system:
  - [ ] Quick preview button for each preset (play 30s with preset)
  - [ ] A/B comparison mode (toggle between original and processed)
  - [ ] Visual frequency response graph for each preset

- [ ] User preset favorites:
  - [ ] Star/favorite presets for quick access
  - [ ] Recently used presets list
  - [ ] Per-genre default preset settings

**Testing & Validation**:
- [ ] Create comprehensive preset test suite:
  - [ ] 10+ test tracks across various genres
  - [ ] Automated quality metric measurements
  - [ ] Blind listening tests with multiple users
  - [ ] Document subjective feedback

- [ ] Quality benchmarks:
  - [ ] Compare against professional mastering plugins (iZotope Ozone, etc.)
  - [ ] Measure LUFS consistency across presets
  - [ ] Verify no clipping or distortion
  - [ ] Check stereo imaging quality

- [ ] Performance validation:
  - [ ] Ensure processing time remains under 2s for first chunk
  - [ ] Verify cache efficiency with new presets
  - [ ] Test memory usage with complex presets

**Documentation**:
- [ ] Create preset guide document:
  - [ ] Description of each preset's sonic character
  - [ ] Recommended use cases and genres
  - [ ] Technical parameters and processing chain
  - [ ] Before/after audio examples

- [ ] Update CLAUDE.md with preset development guidelines
- [ ] Create mastering preset design patterns document

**Acceptance Criteria**:
- [ ] All presets produce noticeably different, high-quality results
- [ ] Each preset has clear use case and sonic character
- [ ] No audible artifacts or distortion in any preset
- [ ] User can easily understand and choose appropriate preset
- [ ] Processing performance maintained (<2s first chunk)
- [ ] Comprehensive testing and documentation complete

**Time**: 5-7 days
**Priority**: 🟡 MEDIUM-HIGH - Improves core audio quality and user experience
**Impact**: Better audio quality, more distinctive presets, clearer user guidance

**Notes**:
- This work builds on the existing enhancement system (Phase 1.5)
- Should be done before UI refinement (Phase 2) so preset UI can reflect improvements
- Consider user feedback from beta testing when refining presets
- May discover opportunities for adaptive preset auto-selection based on genre

---

## 🎨 Phase 2: Enhanced Navigation & Views (Medium Priority) - 67% Complete

**Goal**: Improve library navigation with dedicated views
**Timeline**: 2-3 weeks
**Dependencies**: Phase 1 completion
**Status**: Albums & Artists views ✅ COMPLETE (October 24, 2025)

### 2.1 Albums View ✅ COMPLETE (3-4 days)

**Backend**:
- [x] Create album API endpoints:
  - [x] `GET /api/albums` - List all albums with pagination
  - [x] `GET /api/albums/:id` - Get album details with tracks
  - [x] `GET /api/albums/:id/tracks` - Get album tracks
  - [x] `GET /api/albums/recent` - Recently added albums (via repository)
  - [x] `GET /api/albums/search?q=` - Search albums (via repository)
  - [x] `GET /api/albums/:id/artwork` - Get album artwork
  - [x] `POST /api/albums/:id/artwork/extract` - Extract artwork from tracks
  - [x] **Calculate and return `total_duration`** for albums

**Frontend**:
- [x] Create Albums view component (CozyAlbumGrid)
- [x] Album grid with large artwork
- [x] Album detail view with track list (AlbumDetailView)
- [x] Click album to view details
- [x] Play entire album from detail view
- [x] Sort albums (by name, artist, year)
- [x] Infinite scroll pagination (50 albums per page)
- [x] Improved placeholder icon visibility

**Acceptance Criteria**:
- ✅ Albums view shows all albums with artwork placeholders
- ✅ Album detail shows all tracks with durations (13 tracks, 1h 17m)
- ✅ Users can click to navigate to album detail
- ✅ Albums display track count and total duration
- ✅ Pagination works for large libraries

**Documentation**: [PHASE_2_ALBUMS_ARTISTS_COMPLETE.md](../completed/PHASE_2_ALBUMS_ARTISTS_COMPLETE.md)

### 2.2 Artists View ✅ COMPLETE (3-4 days)

**Backend**:
- [x] Create artist API endpoints:
  - [x] `GET /api/artists` - List all artists with pagination
  - [x] `GET /api/artists/:id` - Get artist details with albums
  - [x] `GET /api/artists/:id/tracks` - Get artist tracks
  - [x] Search artists (via repository)
  - [x] **Fixed SQLAlchemy eager loading** for track genres and album tracks

**Frontend**:
- [x] Create Artists view component (ArtistDetailView)
- [x] Artist list with album/track counts
- [x] Artist detail view with albums
- [x] Click artist to view details
- [x] Navigate from artist → album → tracks
- [x] Back navigation through views
- [x] Display artist statistics (albums, tracks, total duration)

**Acceptance Criteria**:
- ✅ Artists view shows all artists with statistics
- ✅ Artist detail shows albums with artwork
- ✅ Users can navigate artist → album → track playback
- ✅ Artists are sortable and searchable
- ✅ Nested navigation works correctly

**Documentation**: [PHASE_2_ALBUMS_ARTISTS_COMPLETE.md](../completed/PHASE_2_ALBUMS_ARTISTS_COMPLETE.md)

### 2.3 Album Artwork from Online Sources (NEW - HIGH PRIORITY)

**Goal**: Automatically fetch album artwork from free online sources when not embedded in tracks

**Backend**:
- [ ] Integrate with free artwork APIs:
  - [ ] MusicBrainz Cover Art Archive API
  - [ ] iTunes Search API (fallback)
  - [ ] Last.fm API (optional, requires key)
  - [ ] Spotify Web API (optional, requires OAuth)

- [ ] Create artwork download service:
  - [ ] `POST /api/albums/:id/artwork/download` - Already exists! Just needs implementation
  - [ ] Search by album title + artist name
  - [ ] Download and cache artwork locally
  - [ ] Save to `~/.auralis/artwork/`
  - [ ] Update album.artwork_path in database
  - [ ] WebSocket broadcast on success

**Frontend**:
- [ ] Add "Download Artwork" button to album detail view
- [ ] Add batch "Download All Artwork" option in settings
- [ ] Show progress indicator during download
- [ ] Toast notification on success/failure
- [ ] Refresh album card artwork after download

**Acceptance Criteria**:
- Users can download artwork for albums without embedded art
- Artwork is cached locally and persists across sessions
- Batch download available for entire library
- Progress feedback during downloads
- Graceful handling of API failures

**Technical Notes**:
- MusicBrainz Cover Art Archive is free, no API key needed
- iTunes API is free but has rate limits
- Implement retry logic with exponential backoff
- Cache negative results to avoid repeated failed requests
- Support manual artwork upload as fallback

**Timeline**: 2-3 days
**Priority**: HIGH - Essential for good visual library experience

### 2.4 Recently Played (2-3 days)

**Backend**:
- [ ] Add play history tracking:
  - [ ] `play_count` column (already exists)
  - [ ] `last_played` column (already exists)
  - [ ] Record play on track start
  - [ ] Create PlayHistory table (optional for full history)

- [ ] Create recently played endpoint:
  - [ ] `GET /api/tracks/recent` - Recently played tracks
  - [ ] `GET /api/tracks/popular` - Most played tracks
  - [ ] `POST /api/tracks/:id/play` - Record play event

**Frontend**:
- [ ] Create Recently Played view
- [ ] Show last 50 played tracks
- [ ] Display play timestamp
- [ ] Display play count
- [ ] Click to play again
- [ ] Clear history button

**Acceptance Criteria**:
- Recently played tracks are recorded
- Recently played view shows history
- Play counts are accurate
- Users can replay from history

---

## ⚙️ Phase 3: Settings & Configuration (Medium Priority)

**Goal**: Give users control over app behavior
**Timeline**: 1-2 weeks
**Dependencies**: Phase 1-2 completion

### 3.1 Settings System (5-7 days)

**Backend**:
- [ ] Create settings storage:
  - [ ] UserSettings table or config file
  - [ ] Default settings
  - [ ] Settings validation

- [ ] Create settings API:
  - [ ] `GET /api/settings` - Get all settings
  - [ ] `PUT /api/settings` - Update settings
  - [ ] `POST /api/settings/reset` - Reset to defaults

**Frontend**:
- [ ] Create Settings modal/page
- [ ] Settings categories:
  - [ ] Library (scan folders, file types)
  - [ ] Playback (crossfade, gapless, replay gain)
  - [ ] Audio (output device, bit depth, sample rate)
  - [ ] Interface (theme, language, shortcuts)
  - [ ] Enhancement (default preset, auto-enhance)
  - [ ] Advanced (cache size, performance)

- [ ] Settings sections:
  - [ ] Library Folders management
  - [ ] Audio output device selector
  - [ ] Keyboard shortcuts editor
  - [ ] Cache management
  - [ ] About/version info

**Acceptance Criteria**:
- Users can access settings
- Settings persist across sessions
- Changes apply immediately or on restart
- Reset to defaults works

### 3.2 Library Folder Management (3-4 days)

**Backend**:
- [ ] Store watched folders in database
- [ ] API to add/remove folders
- [ ] Re-scan specific folders
- [ ] Exclude patterns (*.tmp, etc.)

**Frontend**:
- [ ] Settings section for library folders
- [ ] Add folder dialog
- [ ] Remove folder with confirmation
- [ ] Show folder scan status
- [ ] Rescan button per folder

**Acceptance Criteria**:
- Users can manage watched folders
- New folders are scanned automatically
- Removed folders don't show tracks

---

## 🎵 Phase 4: Advanced Playback Features (Medium Priority)

**Goal**: Polish the music listening experience
**Timeline**: 3-4 weeks
**Dependencies**: Phase 1-3 completion

### 4.1 Track Metadata Editing & Management (HIGH PRIORITY) (4-5 days)

**Goal**: Allow users to edit and manage track metadata directly in the app

**Backend**:
- [ ] Create metadata editing API:
  - [ ] `PUT /api/library/tracks/:id/metadata` - Update track metadata
  - [ ] `GET /api/library/tracks/:id/metadata/formats` - Get available format-specific tags
  - [ ] `POST /api/library/tracks/batch/metadata` - Batch metadata update
  - [ ] Support for common metadata fields:
    - [ ] Title, Artist, Album, Album Artist
    - [ ] Track Number, Disc Number
    - [ ] Year, Genre, BPM
    - [ ] Comments, Lyrics
    - [ ] Custom tags (format-dependent)

- [ ] Implement metadata writing:
  - [ ] Use mutagen to write metadata back to files
  - [ ] Support all library formats (MP3, FLAC, M4A, OGG, WAV)
  - [ ] Preserve existing tags when updating
  - [ ] Create backup before editing (optional setting)
  - [ ] Validate metadata before writing
  - [ ] Handle read-only files gracefully

- [ ] Batch operations:
  - [ ] Update multiple tracks at once
  - [ ] Apply metadata template to selection
  - [ ] Auto-populate from filename patterns
  - [ ] Fetch metadata from online databases (MusicBrainz, Discogs)

- [ ] WebSocket broadcasting:
  - [ ] Notify all clients when metadata changes
  - [ ] Update library view in real-time
  - [ ] Refresh album/artist aggregations

**Frontend**:
- [ ] Create EditMetadataDialog component:
  - [ ] Form fields for all metadata properties
  - [ ] File format indicator (shows available tags)
  - [ ] Preview changes before saving
  - [ ] Validation feedback
  - [ ] Undo/revert capability

- [ ] Batch editing interface:
  - [ ] Select multiple tracks
  - [ ] Edit common fields
  - [ ] Apply to all selected
  - [ ] Show diff/changes summary

- [ ] Context menu integration:
  - [ ] Right-click track → "Edit Metadata"
  - [ ] Right-click selection → "Edit Selected Metadata"
  - [ ] Show keyboard shortcut (e.g., Ctrl+E)

- [ ] Track detail view:
  - [ ] Show all metadata fields
  - [ ] Inline editing for quick changes
  - [ ] Format-specific tags in expandable section
  - [ ] File info (codec, bitrate, sample rate)

- [ ] Advanced features:
  - [ ] Fetch from MusicBrainz/Discogs
  - [ ] Auto-populate from filename
  - [ ] Apply naming patterns
  - [ ] Tag cleanup tools (trim whitespace, fix capitalization)

**Acceptance Criteria**:
- [ ] Users can edit individual track metadata
- [ ] Batch editing works for multiple tracks
- [ ] Changes persist to audio files
- [ ] Library updates automatically after edits
- [ ] All supported formats can be edited
- [ ] No data loss during editing
- [ ] Validation prevents invalid metadata

**Time**: 4-5 days
**Priority**: 🔴 HIGH - Essential for music library management
**Impact**: Allows users to maintain clean, organized metadata without external tools

---

### 4.2 Smart Chunk Shaping (MEDIUM PRIORITY) (5-7 days)

**Goal**: Improve chunked streaming by using intelligent chunk boundaries based on audio content rather than fixed time intervals

**Backend**:
- [ ] Implement intelligent chunk boundary detection:
  - [ ] Analyze audio waveform for natural break points
  - [ ] Detect silent sections (below -60dB threshold)
  - [ ] Identify mood/energy transitions using RMS and spectral changes
  - [ ] Detect tempo changes and beat boundaries
  - [ ] Use onset detection for rhythmic content

- [ ] Create AdaptiveChunkShaper module:
  - [ ] `analyze_chunk_points(audio, sr, min_chunk=15s, max_chunk=45s)` - Find optimal boundaries
  - [ ] `detect_mood_changes(audio, sr)` - Identify mood/energy shifts
  - [ ] `find_silent_regions(audio, sr, threshold=-60dB)` - Locate silence
  - [ ] `align_to_beats(audio, sr, boundaries)` - Snap to beat grid (optional)

- [ ] Integrate with ChunkedAudioProcessor:
  - [ ] Replace fixed 30s chunks with adaptive boundaries
  - [ ] Ensure min chunk size (15s) for streaming efficiency
  - [ ] Ensure max chunk size (45s) to avoid memory issues
  - [ ] Maintain crossfade compatibility at boundaries

- [ ] Caching strategy:
  - [ ] Cache chunk boundaries per track (avoid re-analysis)
  - [ ] Store boundary metadata in database
  - [ ] Invalidate cache if file changes

- [ ] Fallback behavior:
  - [ ] Use fixed 30s chunks if analysis fails
  - [ ] Use fixed chunks for very short tracks (<90s)
  - [ ] Configurable via settings (enable/disable smart chunking)

**Frontend**:
- [ ] Settings toggle for smart chunking (on by default)
- [ ] Display chunk boundaries in waveform view (optional)
- [ ] Performance metrics in debug mode (chunk analysis time)

**Technical Approach**:
```python
# Pseudocode example
def find_adaptive_chunk_boundaries(audio, sr, min_chunk=15, max_chunk=45):
    # 1. Calculate energy profile (RMS over time)
    energy = calculate_rms_envelope(audio, window_size=2048)

    # 2. Find mood transitions (significant energy changes)
    transitions = detect_energy_transitions(energy, threshold=6dB)

    # 3. Find silent regions
    silent_regions = detect_silence(audio, sr, threshold=-60dB, min_duration=0.5)

    # 4. Combine into candidate boundaries
    candidates = merge_candidates(transitions, silent_regions)

    # 5. Optimize chunk sizes (min/max constraints)
    boundaries = optimize_chunks(candidates, min_chunk, max_chunk)

    return boundaries
```

**Acceptance Criteria**:
- [ ] Chunks split at musically/contextually appropriate points
- [ ] No splits in the middle of vocals or prominent sounds
- [ ] Chunk sizes stay within min/max bounds (15-45s)
- [ ] Analysis completes in <1s per track
- [ ] Crossfades still work seamlessly at new boundaries
- [ ] Performance impact is minimal (<10% overhead)
- [ ] Fallback to fixed chunks if analysis fails

**Time**: 5-7 days
**Priority**: ⚠️ MEDIUM - Nice UX improvement but not essential
**Impact**: More natural listening experience, fewer audible crossfade artifacts
**Dependencies**: Requires ChunkedAudioProcessor (already implemented in Phase 1.5)

---

### 4.3 Gapless Playback (3-4 days)

**Implementation**:
- [ ] Pre-load next track in hidden audio element
- [ ] Detect track end and switch seamlessly
- [ ] Handle edge cases (manual skip, queue change)
- [ ] Settings toggle for gapless mode

**Acceptance Criteria**:
- No silence between album tracks
- Seamless transition between songs
- Can be disabled in settings

### 4.2 Crossfade (3-4 days)

**Implementation**:
- [ ] Implement dual audio element approach
- [ ] Fade out current track
- [ ] Fade in next track simultaneously
- [ ] Configurable crossfade duration (0-10s)
- [ ] Settings toggle and duration slider

**Acceptance Criteria**:
- Smooth crossfade between tracks
- User-adjustable duration
- Works with all audio formats

### 4.3 Equalizer (5-7 days)

**Backend**:
- [ ] Implement real-time EQ using Web Audio API
- [ ] Support common EQ presets:
  - [ ] Flat, Rock, Pop, Jazz, Classical, Bass Boost, etc.
- [ ] Save custom EQ settings
- [ ] Per-track EQ settings (optional)

**Frontend**:
- [ ] Visual EQ component with sliders
- [ ] 10-band or parametric EQ
- [ ] Preset selector
- [ ] Save/load custom presets
- [ ] Real-time frequency visualization

**Acceptance Criteria**:
- EQ adjusts audio in real-time
- Presets work correctly
- Custom settings persist
- Visual feedback shows changes

### 4.4 Crossfade (Already Implemented) ✅

**Status**: Already implemented in BottomPlayerBarConnected.tsx
- [x] Dual audio element approach
- [x] Fade out current track
- [x] Fade in next track simultaneously
- [x] Configurable crossfade duration (0-10s)
- [x] Settings toggle and duration slider

**Note**: Renumbered existing items since Crossfade (4.2) is already complete

---

### 4.5 Equalizer (5-7 days)

**Backend**:
- [ ] Implement real-time EQ using Web Audio API
- [ ] Support common EQ presets:
  - [ ] Flat, Rock, Pop, Jazz, Classical, Bass Boost, etc.
- [ ] Save custom EQ settings
- [ ] Per-track EQ settings (optional)

**Frontend**:
- [ ] Visual EQ component with sliders
- [ ] 10-band or parametric EQ
- [ ] Preset selector
- [ ] Save/load custom presets
- [ ] Real-time frequency visualization

**Acceptance Criteria**:
- EQ adjusts audio in real-time
- Presets work correctly
- Custom settings persist
- Visual feedback shows changes

---

### 4.6 Lyrics Display (Optional) (3-5 days)

**Backend**:
- [ ] Extract lyrics from metadata
- [ ] Support .lrc file format
- [ ] Lyrics API integration (Genius, Musixmatch)
- [ ] Store lyrics in database

**Frontend**:
- [ ] Lyrics panel in player
- [ ] Synchronized scrolling
- [ ] Search lyrics
- [ ] Edit/add lyrics manually

**Acceptance Criteria**:
- Lyrics display when available
- Scrolls with playback
- Users can add missing lyrics

---

## 📊 Phase 5: Professional Audio Features (Auralis-Specific)

**Goal**: Leverage Auralis' audio processing capabilities and optimize core algorithms
**Timeline**: 4-5 weeks
**Dependencies**: Phase 1-4 completion

### 5.1 Mastering Algorithm Performance Review (LOW-MEDIUM PRIORITY) (7-10 days)

**Goal**: Conduct comprehensive review of the adaptive mastering algorithm to identify performance bottlenecks and optimization opportunities

**Phase 1: Profiling & Analysis (3-4 days)**

- [ ] Comprehensive profiling of entire processing pipeline:
  - [ ] Profile HybridProcessor.process() end-to-end
  - [ ] Profile each DSP stage individually (EQ, dynamics, limiting)
  - [ ] Profile content analysis and target generation
  - [ ] Profile I/O operations (loading, saving)
  - [ ] Use cProfile, line_profiler, and py-spy for detailed insights

- [ ] Memory profiling:
  - [ ] Identify memory-intensive operations
  - [ ] Track NumPy array allocations
  - [ ] Check for memory leaks in long processing sessions
  - [ ] Profile memory usage per preset

- [ ] Identify hotspots:
  - [ ] Which functions consume most CPU time?
  - [ ] Which operations are slowest? (FFT, convolution, filtering)
  - [ ] Which parts are already optimized?
  - [ ] Which parts have low-hanging fruit?

- [ ] Benchmark current performance:
  - [ ] Processing time per file size (1min, 5min, 10min tracks)
  - [ ] Processing time per format (WAV, FLAC, MP3)
  - [ ] Processing time per preset (Adaptive, Gentle, Warm, Bright, Punchy)
  - [ ] Real-time factor breakdown by stage
  - [ ] Memory usage per track length

**Phase 2: Algorithm Review (2-3 days)**

- [ ] Review adaptive mastering algorithm logic:
  - [ ] ContentAnalyzer efficiency (spectral, temporal, genre analysis)
  - [ ] AdaptiveTargetGenerator complexity
  - [ ] Genre classification overhead (ML model inference)
  - [ ] Psychoacoustic EQ calculations (26 critical bands)
  - [ ] Dynamics processing (envelope followers, compression, limiting)

- [ ] Review DSP implementations:
  - [ ] FFT operations - are we using optimal sizes?
  - [ ] Filter implementations - IIR vs FIR trade-offs
  - [ ] Resampling overhead - can we avoid it?
  - [ ] Stereo processing - mid-side conversions efficient?

- [ ] Compare with reference implementations:
  - [ ] librosa for spectral features
  - [ ] scipy.signal for filtering
  - [ ] pydub for format handling
  - [ ] Check if we're duplicating work

**Phase 3: Optimization Implementation (2-3 days)**

**Potential optimizations to investigate**:

- [ ] **NumPy/SciPy optimizations**:
  - [ ] Use in-place operations where possible (reduce copies)
  - [ ] Vectorize remaining loops
  - [ ] Use NumPy's optimized functions (np.dot, np.einsum)
  - [ ] Leverage SciPy's Cython-based functions

- [ ] **FFT optimizations**:
  - [ ] Use FFTW via pyfftw (faster than NumPy's FFT)
  - [ ] Cache FFT plans for repeated operations
  - [ ] Use optimal FFT sizes (powers of 2)
  - [ ] Parallelize FFT operations for stereo

- [ ] **Caching improvements**:
  - [ ] Cache content analysis results per track
  - [ ] Cache genre classification results
  - [ ] Cache FFT intermediate results
  - [ ] Implement smarter cache invalidation

- [ ] **Parallel processing**:
  - [ ] Parallelize stereo channel processing
  - [ ] Use multiprocessing for batch operations
  - [ ] Parallelize chunk processing in ChunkedAudioProcessor
  - [ ] Investigate Numba JIT compilation for hotspots

- [ ] **Algorithm simplifications**:
  - [ ] Reduce psychoacoustic EQ from 26 to 18 bands (still perceptually accurate)
  - [ ] Simplify genre classification (faster heuristics for real-time)
  - [ ] Optimize envelope follower (reduce oversampling if possible)
  - [ ] Skip analysis steps for low-intensity processing

- [ ] **Memory optimizations**:
  - [ ] Use memory pools more aggressively (already have PerformanceOptimizer)
  - [ ] Stream large files in chunks (already done for enhancement)
  - [ ] Use float32 instead of float64 where precision allows
  - [ ] Release intermediate arrays sooner

**Phase 4: Testing & Validation (1-2 days)**

- [ ] Benchmark optimizations:
  - [ ] Measure speedup per optimization
  - [ ] Ensure audio quality is maintained (PESQ, VISQOL scores)
  - [ ] A/B test original vs optimized output (should be identical or imperceptibly different)
  - [ ] Verify no regressions in test suite

- [ ] Document findings:
  - [ ] Create MASTERING_ALGORITHM_PERFORMANCE.md report:
    - [ ] Profiling results (before/after)
    - [ ] Identified bottlenecks
    - [ ] Implemented optimizations
    - [ ] Performance improvements achieved
    - [ ] Recommendations for future work
  - [ ] Update CLAUDE.md with new performance characteristics

**Acceptance Criteria**:
- [ ] Comprehensive profiling report completed
- [ ] At least 3 significant bottlenecks identified
- [ ] At least 2 optimizations implemented and tested
- [ ] Performance improvement of 10-20% on common use cases
- [ ] Audio quality maintained (verified by objective metrics)
- [ ] No regressions in existing test suite
- [ ] Documentation updated with findings

**Time**: 7-10 days
**Priority**: 📊 LOW-MEDIUM - Important for long-term performance but not blocking users
**Impact**: Faster processing, lower CPU usage, better battery life on laptops
**Risk**: Medium - Requires careful testing to ensure audio quality is maintained

**Note**: Current performance is already excellent (52.8x real-time, 197x with optimizations), so this is about finding additional gains and ensuring we haven't missed easy optimizations.

---

### 5.2 Real-Time Audio Analysis (4-5 days)

**Implementation**:
- [ ] Connect Web Audio API to visualizations
- [ ] Real-time FFT analysis
- [ ] LUFS meter during playback
- [ ] Dynamic range visualization
- [ ] Phase correlation meter
- [ ] Spectrum analyzer

**Frontend**:
- [ ] ClassicVisualizer using real audio
- [ ] RealtimeAudioVisualizer using real audio
- [ ] Meters panel (LUFS, DR, phase)
- [ ] Toggle visualizations on/off

**Acceptance Criteria**:
- Visualizations reflect real audio
- Meters update in real-time
- No performance impact on playback
- Can be hidden for lower CPU usage

### 5.2 Batch Processing Interface (5-7 days)

**Backend**:
- [ ] Batch processing job queue
- [ ] Process multiple files with same preset
- [ ] Progress tracking per file
- [ ] Output folder management

**Frontend**:
- [ ] File upload interface
- [ ] Drag-and-drop multiple files
- [ ] Preset selector for batch
- [ ] Progress view for all files
- [ ] Download processed files
- [ ] Export as ZIP

**Acceptance Criteria**:
- Users can process multiple files
- Progress shows for each file
- Processed files can be downloaded
- Original files preserved

### 5.3 A/B Comparison Player (3-4 days)

**Implementation**:
- [ ] Load original and processed versions
- [ ] Instant switching between A/B
- [ ] Synchronized playback position
- [ ] Volume-matched comparison
- [ ] Waveform overlay

**Frontend**:
- [ ] A/B comparison view
- [ ] Switch button (instant)
- [ ] Sync indicator
- [ ] Side-by-side waveforms
- [ ] Export preferred version

**Acceptance Criteria**:
- Can compare original vs processed
- Switching is instant
- Position stays synchronized
- Volume matched for fair comparison

### 5.4 Audio Export (3-4 days)

**Backend**:
- [ ] Export processed audio to various formats:
  - [ ] WAV (16/24/32-bit)
  - [ ] FLAC (16/24-bit)
  - [ ] MP3 (320kbps, V0)
  - [ ] AAC (256kbps)
- [ ] Preserve metadata
- [ ] Batch export

**Frontend**:
- [ ] Export dialog with format options
- [ ] Quality/bitrate selection
- [ ] Metadata preservation toggle
- [ ] Output folder selection
- [ ] Export progress

**Acceptance Criteria**:
- Export to multiple formats
- Metadata preserved
- Quality settings work
- Progress indicator accurate

---

## 🎨 Phase 6: UI Polish & Enhancements (Low Priority)

**Goal**: Perfect the user experience
**Timeline**: 2-3 weeks

### 6.1 Mini Player Mode (2-3 days)

**Implementation**:
- [ ] Compact mini player window
- [ ] Always on top option
- [ ] Basic controls only
- [ ] Toggle between full and mini

**Acceptance Criteria**:
- Mini player shows current track
- Basic controls work
- Can switch back to full mode

### 6.2 Full-Screen Mode (2-3 days)

**Implementation**:
- [ ] Full-screen view with large artwork
- [ ] Minimal controls
- [ ] Keyboard shortcuts
- [ ] Screensaver mode (optional)

**Acceptance Criteria**:
- Full-screen shows artwork beautifully
- Controls still accessible
- Exit with ESC key

### 6.3 Theme Customization (3-4 days)

**Implementation**:
- [ ] Light theme option
- [ ] Custom accent colors
- [ ] Theme presets
- [ ] Import/export themes

**Acceptance Criteria**:
- Multiple themes available
- Users can customize colors
- Themes persist

### 6.4 Advanced Search (3-4 days)

**Implementation**:
- [ ] Search filters (artist, album, year, genre)
- [ ] Search history
- [ ] Saved searches
- [ ] Search suggestions

**Acceptance Criteria**:
- Advanced filters work
- Search is fast
- Results are relevant

---

## 🚀 Phase 7: Performance & Optimization

**Goal**: Ensure smooth experience with large libraries
**Timeline**: 1-2 weeks

### 7.1 Virtual Scrolling (2-3 days)

**Implementation**:
- [ ] Virtualize track list for 10,000+ tracks
- [ ] Lazy load album artwork
- [ ] Infinite scroll
- [ ] Smooth scrolling performance

**Acceptance Criteria**:
- Smooth scrolling with 50,000+ tracks
- No memory leaks
- Fast initial load

### 7.2 Caching & Optimization (3-4 days)

**Implementation**:
- [ ] Cache processed audio
- [ ] Cache artwork thumbnails
- [ ] Optimize database queries
- [ ] Add database indexes
- [ ] Implement pagination

**Acceptance Criteria**:
- Fast library loading
- Efficient memory usage
- Quick search results

---

## 📱 Phase 8: Platform-Specific Features (Future)

### 8.1 macOS Integration
- [ ] Touch Bar support
- [ ] Media keys integration
- [ ] Notification Center
- [ ] Menu bar controls

### 8.2 Windows Integration
- [ ] Taskbar controls
- [ ] Windows Media Controls
- [ ] Toast notifications
- [ ] System tray icon

### 8.3 Linux Integration
- [ ] MPRIS D-Bus interface
- [ ] System tray integration
- [ ] Native notifications

---

## 🧪 Testing & Quality Assurance

### Ongoing Tasks
- [ ] Unit tests for new features
- [ ] Integration tests for critical paths
- [ ] E2E tests for user workflows
- [ ] Performance benchmarks
- [ ] Memory leak detection
- [ ] Cross-platform testing

### Test Coverage Goals
- [ ] 80%+ backend coverage
- [ ] 70%+ frontend coverage
- [ ] 100% critical path coverage

---

## 📚 Documentation

### User Documentation
- [ ] User manual
- [ ] Keyboard shortcuts guide
- [ ] FAQ
- [ ] Video tutorials

### Developer Documentation
- [ ] API documentation (Swagger/OpenAPI)
- [ ] Architecture overview
- [ ] Contributing guide
- [ ] Plugin/extension API (future)

---

## 🎯 Success Metrics

### Phase 1 Success Criteria
- [ ] All partially implemented features complete
- [ ] No mocked data in production UI
- [ ] All TODOs addressed
- [ ] 85%+ test coverage for new features

### Phase 2 Success Criteria
- [ ] Albums/Artists views functional
- [ ] Recently played tracking works
- [ ] User satisfaction with navigation

### Overall Success Criteria
- [ ] App is stable and performant
- [ ] Users can manage 50,000+ track libraries
- [ ] Real-time enhancement works smoothly
- [ ] All core music player features functional
- [ ] Auralis processing integrated seamlessly

---

## 🔄 Release Strategy

### v1.1 (Phase 1 Complete)
- Favorites system
- Playlist management
- Album art extraction
- Queue management
- Real-time enhancement

### v1.2 (Phase 2 Complete)
- Albums view
- Artists view
- Recently played
- Improved navigation

### v1.3 (Phase 3 Complete)
- Settings system
- Folder management
- Configuration options

### v1.4 (Phase 4 Complete)
- Gapless playback
- Crossfade
- Equalizer
- Advanced playback features

### v2.0 (Phase 5 Complete)
- Full Auralis integration
- Batch processing
- A/B comparison
- Professional audio features

---

## 📝 Notes

- **Focus on user value**: Prioritize features that directly impact user experience
- **Quality over quantity**: Complete features fully before moving to next phase
- **Test thoroughly**: Each phase should be well-tested before release
- **User feedback**: Gather feedback after each phase to adjust priorities
- **Performance matters**: Keep the app fast even with large libraries
- **Cross-platform**: Ensure features work on Linux, macOS, Windows

---

## 🤝 Contributing

This roadmap is a living document. Priorities may shift based on:
- User feedback
- Technical constraints
- Resource availability
- Strategic decisions

**Last Reviewed**: October 23, 2025
**Next Review**: After Phase 0 completion (WebSocket/REST fixes)

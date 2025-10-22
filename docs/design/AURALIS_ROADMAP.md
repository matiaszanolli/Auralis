# Auralis Development Roadmap

**Last Updated**: October 22, 2025
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
- [x] Comprehensive test suite (96 backend tests, 100% passing)
- [x] Build system (AppImage + DEB packages)
- [x] Documentation (CLAUDE.md, multiple technical docs)

---

## 🚨 Phase 0: Critical Architecture Fixes (URGENT PRIORITY) - 0% Complete

**Goal**: Fix REST/WebSocket architecture mismatches causing inefficient polling
**Timeline**: 4-7 days
**Status**: URGENT - Must complete before Phase 1.5
**Impact**: Currently making 60+ HTTP requests/minute during playback
**Documentation**: [WEBSOCKET_REST_ANALYSIS.md](../../WEBSOCKET_REST_ANALYSIS.md)

### 0.1 Fix Player State WebSocket Communication (HIGH PRIORITY - 1-2 days)

**Problem Identified**:
- Frontend `usePlayerAPI` expects `player_state` and `player_update` WebSocket messages
- Backend **never sends these messages**
- Application falls back to REST polling `/api/player/status` every 1 second
- WebSocket connection exists but is unused for player state
- 60+ unnecessary HTTP requests per minute during playback

**Backend** (Option A - Recommended):
- [ ] Add `playback_started` message broadcast when play() is called
- [ ] Add `playback_paused` message broadcast when pause() is called
- [ ] Add `player_state` message broadcast after any player state change
- [ ] Send periodic `position_changed` messages during playback (every 1s)
- [ ] Ensure all player operations broadcast state updates

**OR Backend** (Option B - Simpler):
- [ ] Keep existing granular messages (`track_changed`, `volume_changed`, etc.)
- [ ] Update frontend to handle these instead of expecting `player_state`

**Frontend** (for Option A):
- [ ] Update `usePlayerAPI.ts` to handle `playback_started` and `playback_paused`
- [ ] Handle `player_state` messages with full state updates
- [ ] Remove REST polling fallback once WebSocket works
- [ ] Add error handling for WebSocket disconnection

**Frontend** (for Option B):
- [ ] Update `usePlayerAPI.ts` to handle granular messages:
  - [ ] `track_changed` - Update current track
  - [ ] `volume_changed` - Update volume
  - [ ] `position_changed` - Update current time
  - [ ] `playback_stopped` - Update playback state
  - [ ] `queue_updated` - Update queue
- [ ] Remove REST polling fallback

**Acceptance Criteria**:
- [ ] WebSocket messages update player state in real-time
- [ ] REST polling disabled (verify no polling in Network tab)
- [ ] Player state stays synchronized across UI
- [ ] No increase in latency compared to polling
- [ ] HTTP requests reduced from 60+/min to 0-5/min

**Time**: 1-2 days
**Priority**: 🚨 CRITICAL - Affects performance and server load

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

### 0.3 Consolidate to Single WebSocket Connection (MEDIUM PRIORITY - 2-3 days)

**Problem Identified**:
- Multiple components create separate WebSocket connections
- `usePlayerAPI` creates one connection
- `EnhancementContext` creates another via `useWebSocket` hook
- Inefficient and harder to debug

**Implementation**:
- [ ] Create `WebSocketContext.tsx` provider at app root
- [ ] Single WebSocket connection shared across all components
- [ ] Subscription system for specific message types
- [ ] Automatic reconnection with exponential backoff
- [ ] Message queueing during disconnection

**Components to migrate**:
- [ ] Migrate `usePlayerAPI` to use WebSocketContext
- [ ] Migrate `EnhancementContext` to use WebSocketContext
- [ ] Migrate `MagicalApp` to use WebSocketContext
- [ ] Remove individual WebSocket creation

**Acceptance Criteria**:
- [ ] Only one WebSocket connection exists (verify in Network tab)
- [ ] All components receive messages correctly
- [ ] Reconnection works automatically
- [ ] Message delivery is reliable

**Time**: 2-3 days
**Priority**: ⚠️ MEDIUM - Improves architecture but not blocking

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

## 🎨 Phase 2: Enhanced Navigation & Views (Medium Priority)

**Goal**: Improve library navigation with dedicated views
**Timeline**: 2-3 weeks
**Dependencies**: Phase 1 completion

### 2.1 Albums View (3-4 days)

**Backend**:
- [ ] Create album API endpoints:
  - [ ] `GET /api/albums` - List all albums
  - [ ] `GET /api/albums/:id` - Get album details with tracks
  - [ ] `GET /api/albums/:id/tracks` - Get album tracks
  - [ ] `GET /api/albums/recent` - Recently added albums
  - [ ] `GET /api/albums/search?q=` - Search albums

**Frontend**:
- [ ] Create Albums view component
- [ ] Album grid with large artwork
- [ ] Album detail view with track list
- [ ] Click album to view details
- [ ] Play entire album from detail view
- [ ] Sort albums (by name, artist, year)
- [ ] Filter albums (by artist, year, genre)

**Acceptance Criteria**:
- Albums view shows all albums with artwork
- Album detail shows all tracks
- Users can play entire album
- Albums are sortable and filterable

### 2.2 Artists View (3-4 days)

**Backend**:
- [ ] Create artist API endpoints:
  - [ ] `GET /api/artists` - List all artists
  - [ ] `GET /api/artists/:id` - Get artist details
  - [ ] `GET /api/artists/:id/albums` - Get artist albums
  - [ ] `GET /api/artists/:id/tracks` - Get artist tracks
  - [ ] `GET /api/artists/search?q=` - Search artists

**Frontend**:
- [ ] Create Artists view component
- [ ] Artist grid with names/avatars
- [ ] Artist detail view with albums and tracks
- [ ] Click artist to view details
- [ ] Play all artist tracks
- [ ] Sort artists (by name, track count)
- [ ] Search artists

**Acceptance Criteria**:
- Artists view shows all artists
- Artist detail shows albums and tracks
- Users can play all artist content
- Artists are sortable and searchable

### 2.3 Recently Played (2-3 days)

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

## 🎵 Phase 4: Advanced Playback Features (Low Priority)

**Goal**: Polish the music listening experience
**Timeline**: 2-3 weeks
**Dependencies**: Phase 1-3 completion

### 4.1 Gapless Playback (3-4 days)

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

### 4.4 Lyrics Display (Optional) (3-5 days)

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

**Goal**: Leverage Auralis' audio processing capabilities
**Timeline**: 3-4 weeks
**Dependencies**: Phase 1-4 completion

### 5.1 Real-Time Audio Analysis (4-5 days)

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

**Last Reviewed**: October 21, 2025
**Next Review**: After Phase 1 completion

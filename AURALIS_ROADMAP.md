# Auralis Development Roadmap

**Last Updated**: October 21, 2025
**Current Version**: 1.0.0
**Status**: Core functionality complete, enhancements in progress

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

## 🔄 Phase 1: Complete Partially Implemented Features (High Priority)

**Goal**: Finish features that have UI but lack backend integration
**Timeline**: 2-3 weeks
**Status**: Ready to start

### 1.1 Favorites System (3-4 days)

**Backend**:
- [ ] Add `favorite` column to tracks table (migration)
- [ ] Create `/api/tracks/:id/favorite` POST endpoint
- [ ] Create `/api/tracks/:id/favorite` DELETE endpoint
- [ ] Create `/api/tracks/favorites` GET endpoint
- [ ] Update TrackRepository with favorite queries

**Frontend**:
- [ ] Connect love button to backend API
- [ ] Create Favorites view in sidebar
- [ ] Filter library by favorites
- [ ] Persist favorite state across sessions

**Acceptance Criteria**:
- Users can mark tracks as favorites
- Favorites persist after app restart
- Favorites view shows all loved tracks
- Love button reflects saved state

### 1.2 Playlist Management (5-7 days)

**Backend**:
- [ ] Verify playlist models in database (already exist)
- [ ] Create PlaylistRepository methods:
  - [ ] `create_playlist(name, description)`
  - [ ] `get_all_playlists()`
  - [ ] `get_playlist(id)`
  - [ ] `update_playlist(id, data)`
  - [ ] `delete_playlist(id)`
  - [ ] `add_track_to_playlist(playlist_id, track_id)`
  - [ ] `remove_track_from_playlist(playlist_id, track_id)`
  - [ ] `reorder_playlist_tracks(playlist_id, track_ids)`

- [ ] Create API endpoints:
  - [ ] `POST /api/playlists` - Create new playlist
  - [ ] `GET /api/playlists` - List all playlists
  - [ ] `GET /api/playlists/:id` - Get playlist details
  - [ ] `PUT /api/playlists/:id` - Update playlist
  - [ ] `DELETE /api/playlists/:id` - Delete playlist
  - [ ] `POST /api/playlists/:id/tracks` - Add tracks
  - [ ] `DELETE /api/playlists/:id/tracks/:track_id` - Remove track
  - [ ] `PUT /api/playlists/:id/order` - Reorder tracks

**Frontend**:
- [ ] Connect Sidebar playlists to backend API
- [ ] Implement AddToPlaylistModal functionality
- [ ] Create new playlist dialog
- [ ] Playlist detail view
- [ ] Edit playlist (name, description)
- [ ] Delete playlist confirmation
- [ ] Drag-and-drop track reordering

**Acceptance Criteria**:
- Users can create/edit/delete playlists
- Users can add/remove tracks from playlists
- Playlists persist across sessions
- Playlist view shows all tracks
- Tracks can be reordered in playlists

### 1.3 Album Art Extraction & Display (4-5 days)

**Backend**:
- [ ] Add `album_art` column to tracks/albums tables (migration)
- [ ] Implement album art extraction from metadata:
  - [ ] Use mutagen to extract embedded artwork
  - [ ] Support FLAC, MP3, M4A, WMA formats
  - [ ] Store as base64 or file path
  - [ ] Generate thumbnails (small, medium, large)

- [ ] Create API endpoints:
  - [ ] `GET /api/tracks/:id/artwork` - Get track artwork
  - [ ] `GET /api/albums/:id/artwork` - Get album artwork
  - [ ] `POST /api/tracks/:id/artwork` - Upload custom artwork
  - [ ] `DELETE /api/tracks/:id/artwork` - Remove custom artwork

- [ ] Add artwork extraction to scanner:
  - [ ] Extract during library scan
  - [ ] Update existing tracks with missing artwork
  - [ ] Cache artwork to reduce DB size

**Frontend**:
- [ ] Replace placeholder images with real artwork
- [ ] Implement image caching
- [ ] Add loading states for artwork
- [ ] Fallback to generic icons when no artwork
- [ ] Support for custom artwork upload
- [ ] Large artwork view in player

**Acceptance Criteria**:
- Album art displays correctly from metadata
- Thumbnails load quickly
- Fallback gracefully when no artwork
- Users can upload custom artwork
- Artwork persists across sessions

### 1.4 Queue Management Enhancements (2-3 days)

**Backend**:
- [ ] Create queue manipulation endpoints:
  - [ ] `DELETE /api/player/queue/:index` - Remove track at index
  - [ ] `PUT /api/player/queue/reorder` - Reorder queue
  - [ ] `POST /api/player/queue/clear` - Clear entire queue
  - [ ] `POST /api/player/queue/shuffle` - Shuffle queue
  - [ ] `POST /api/player/queue/save` - Save queue as playlist

**Frontend**:
- [ ] Add remove button to queue items
- [ ] Implement drag-and-drop queue reordering
- [ ] Add "Clear queue" button
- [ ] Add "Shuffle queue" button
- [ ] Add "Save as playlist" button
- [ ] Show queue size indicator

**Acceptance Criteria**:
- Users can remove tracks from queue
- Users can reorder queue by dragging
- Queue can be cleared with one click
- Queue can be saved as a playlist

### 1.5 Real-Time Audio Enhancement (4-6 days)

**Backend**:
- [ ] Implement enhanced streaming endpoint:
  - [ ] Process audio on-the-fly before streaming
  - [ ] Support query params: `?enhanced=true&preset=adaptive&intensity=0.7`
  - [ ] Cache processed audio for performance
  - [ ] Implement chunked processing for large files

- [ ] Create enhancement API:
  - [ ] `POST /api/player/enhancement/toggle` - Enable/disable
  - [ ] `POST /api/player/enhancement/preset` - Change preset
  - [ ] `POST /api/player/enhancement/intensity` - Adjust intensity
  - [ ] `GET /api/player/enhancement/status` - Get current settings

- [ ] Optimize real-time processing:
  - [ ] Pre-process popular tracks
  - [ ] Use in-memory caching
  - [ ] Implement progressive enhancement

**Frontend**:
- [ ] Connect "Auralis Magic" toggle to backend
- [ ] Connect preset selector to backend
- [ ] Show processing indicator when applying
- [ ] Display current preset in player bar
- [ ] Add intensity slider to PresetPane
- [ ] Show before/after waveform (optional)

**Acceptance Criteria**:
- Enhancement toggle applies processing to playback
- Users can switch presets during playback
- Intensity slider adjusts enhancement level
- No audio dropouts during processing
- Processing indicator shows when active

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

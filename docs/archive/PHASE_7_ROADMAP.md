# Phase 7: Advanced Queue Features & Playback Enhancement

**Date:** December 1, 2025
**Status:** Planning
**Priority:** MEDIUM (Enhancement features after core stability)

---

## Overview

Phase 7 builds on the production-ready queue management system from Phase 6 to add advanced features that enhance user experience and power-user capabilities.

Phase 6 delivered:
- ✅ Full queue management system
- ✅ Real-time WebSocket synchronization
- ✅ Queue persistence across restarts
- ✅ 55 passing tests (frontend + backend)

**Phase 7 Focus:** Add advanced queue features and playback enhancements that users request frequently.

---

## Key Objectives

### 1. Queue History & Undo/Redo
**Goal:** Allow users to undo/redo queue operations without manual reconstruction

**Scope:**
- Track queue state changes in history
- Implement undo/redo operations
- Limit history to last 20 operations (memory efficient)
- Persist undo/redo state across restarts

**Implementation Plan:**
1. Create `QueueHistory` model in database
2. Add `push_to_history()`, `undo()`, `redo()` methods to QueueRepository
3. Create `useQueueHistory()` hook for frontend
4. Add undo/redo buttons to QueuePanel UI
5. Test history operations and memory usage

**Success Criteria:**
- Users can undo/redo queue changes
- History persists across restarts
- Memory usage < 10MB for full history
- Undo/redo operations < 50ms

---

### 2. Queue Templates & Saved States
**Goal:** Allow users to save and restore queue configurations

**Scope:**
- Save current queue as template
- Restore queue from template
- Share templates between users (later)
- Templates stored in database

**Implementation Plan:**
1. Create `QueueTemplate` model
2. Add CRUD endpoints: POST/GET/PUT/DELETE /api/player/queue/template
3. UI for saving/loading templates
4. Template management dialog

**Success Criteria:**
- Users can save/load queue templates
- Templates include shuffle and repeat settings
- Retrieve and list saved templates
- Delete templates

---

### 3. Queue Export/Import
**Goal:** Allow users to export queues as M3U/XSPF playlists

**Scope:**
- Export queue to M3U format
- Export queue to XSPF format
- Import M3U/XSPF as queue
- Handle file paths and relative references

**Implementation Plan:**
1. Create `QueueExporter` utility class
2. Implement M3U and XSPF format handlers
3. Add export endpoints: GET /api/player/queue/export?format=m3u|xspf
4. Add import endpoint: POST /api/player/queue/import
5. File handling with proper error recovery

**Success Criteria:**
- Export to M3U/XSPF working
- Import from M3U/XSPF working
- Handles large queues (1000+ tracks)
- Proper error messages for invalid files

---

### 4. Queue Search & Filtering
**Goal:** Find tracks within queue without removing from playback

**Scope:**
- Search queue by track name, artist, album
- Filter queue by genre, duration, bitrate
- Highlight search results
- Quick remove of search results

**Implementation Plan:**
1. Add search/filter state to `usePlaybackQueue` hook
2. Create `QueueSearchPanel` component
3. Add search bar above queue track list
4. Implement filter UI with checkboxes
5. Animate search results highlighting

**Success Criteria:**
- Search finds tracks in queue
- Filter by genre/duration/bitrate
- Results highlighted and scrollable
- < 100ms search time for 10k tracks

---

### 5. Queue Statistics & Analytics
**Goal:** Show users insights about their queue and playback patterns

**Scope:**
- Total duration of queue
- Average track duration
- Genre distribution
- Artist distribution
- Bitrate statistics
- Playback stats (skip rates, repeat frequency)

**Implementation Plan:**
1. Create `QueueStats` calculation utilities
2. Add stats display to QueuePanel footer
3. Create detailed stats modal
4. Update stats in real-time as queue changes
5. Cache stats for performance

**Success Criteria:**
- Stats calculate and display correctly
- Stats update in < 100ms
- Display genre/artist pie charts
- Show duration and track count

---

### 6. Smart Queue Recommendations
**Goal:** Suggest tracks to add to queue based on current content

**Scope:**
- Analyze current queue content
- Recommend similar tracks from library
- Genre-aware recommendations
- Mood-aware recommendations (if fingerprints available)

**Implementation Plan:**
1. Create `QueueRecommender` class
2. Analyze queue fingerprints and characteristics
3. Find similar tracks in library
4. Add recommendation UI as separate panel
5. Allow one-click add recommendations to queue

**Success Criteria:**
- Recommendations are relevant
- < 500ms to generate recommendations
- Users can add recommended tracks
- Show recommendation reasoning

---

### 7. Queue Shuffle Improvements
**Goal:** Enhance shuffle algorithm with smarter options

**Scope:**
- Current shuffle: random order
- Add "weighted shuffle": prefer recently added tracks
- Add "album shuffle": shuffle by album, keep albums together
- Add "artist shuffle": shuffle by artist, keep artist together

**Implementation Plan:**
1. Add `shuffle_mode` to QueueState (random, weighted, album, artist)
2. Implement shuffle algorithms in backend
3. Add shuffle mode selector to QueuePanel
4. Update tests for new shuffle modes

**Success Criteria:**
- Multiple shuffle modes working
- Shuffle algorithms produce expected results
- Performance < 200ms for any shuffle
- Users prefer new shuffle modes

---

## Implementation Timeline

| Phase | Tasks | Timeline | Status |
|-------|-------|----------|--------|
| **Phase 7A** | Queue History + Templates | Week 1-2 | Pending |
| **Phase 7B** | Export/Import + Search | Week 3-4 | Pending |
| **Phase 7C** | Stats + Recommendations | Week 5-6 | Pending |
| **Phase 7D** | Shuffle Improvements + Polish | Week 7-8 | Pending |

---

## Technical Decisions

### Database Schema Additions
```sql
-- Queue history for undo/redo
CREATE TABLE queue_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  queue_state_id INTEGER,
  operation TEXT NOT NULL, -- 'set', 'add', 'remove', 'reorder', 'shuffle', 'clear'
  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (queue_state_id) REFERENCES queue_state(id)
);

-- Queue templates for saving configurations
CREATE TABLE queue_template (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  track_ids TEXT NOT NULL, -- JSON array
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### Frontend Architecture
- `useQueueHistory()` hook for undo/redo state
- `QueueSearchPanel` component for search/filter
- `QueueStatsModal` component for analytics
- `QueueRecommender` service for suggestions
- Enhanced `QueuePanel` with tabbed interface

### Backend Architecture
- `QueueHistoryRepository` for history operations
- `QueueTemplateRepository` for template CRUD
- `QueueExporter` utility for format conversion
- `QueueRecommender` service for suggestions
- Enhanced `QueueRepository` with new methods

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **User Adoption** | 50%+ use queue features | Analytics tracking |
| **Performance** | < 200ms for all operations | Load time monitoring |
| **Test Coverage** | 85%+ of Phase 7 code | pytest coverage reports |
| **User Satisfaction** | 4.5/5 stars | User feedback surveys |

---

## Known Limitations & Future Work

### Not in Phase 7
- Collaborative queue editing (multiple users)
- Queue streaming/sync across devices
- AI-powered smart recommendations
- Voice control for queue operations
- Queue visualization graphs

### Phase 8+ Candidates
- Cloud sync queue across devices
- Collaborative playlists
- Social sharing of queues
- Machine learning recommendations
- Desktop/mobile app feature parity

---

## Dependencies & Prerequisites

### On Phase 6
- ✅ Queue persistence system
- ✅ QueueRepository and API endpoints
- ✅ WebSocket real-time synchronization
- ✅ usePlaybackQueue hook

### External Libraries (if needed)
- `m3u8` library for M3U parsing (Python)
- `lxml` for XSPF parsing (Python)
- Chart.js or D3.js for stats visualization (React)

### Infrastructure
- No additional infrastructure needed
- Existing SQLite database sufficient
- WebSocket already implemented

---

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| Complex shuffle algorithms | Low | Medium | Start with simple weighted shuffle |
| Database performance | Low | High | Add indexes on history table |
| Memory bloat from history | Low | High | Limit history to 20 operations |
| UI complexity | Medium | Medium | Use tabs/modals to organize features |

---

## Review Checkpoints

After each task completion:
1. All tests passing (unit + integration)
2. Code review for design patterns
3. Performance benchmarking
4. Documentation updated
5. User feedback gathered

---

## Next Steps After Phase 7

**Phase 8:** Advanced Playback Features
- Crossfade between tracks
- A-B repeat functionality
- Playback speed control
- Audio visualization

**Phase 9:** Library Integration
- Smart playlists based on queue
- Auto-populate queue from library
- Playlist to queue conversion
- Queue to playlist saving

---

## References

- [Phase 6 Completion](PHASE_6_ROADMAP.md) - Baseline queue system
- [DEVELOPMENT_ROADMAP_1_1_0.md](docs/roadmaps/DEVELOPMENT_ROADMAP_1_1_0.md) - Overall project roadmap
- [DEVELOPMENT_STANDARDS.md](DEVELOPMENT_STANDARDS.md) - Code standards

---

**Date Created:** December 1, 2025
**Status:** Ready for Phase 7 planning and task breakdown
**Next Review:** After Phase 6 completion confirmation

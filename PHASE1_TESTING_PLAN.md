# Phase 1 Testing & Polish Plan

**Date**: October 21, 2025
**Phase 1 Completion**: 80% (4/5 tasks)
**Testing Focus**: Favorites, Playlists, Album Art, Queue Management

---

## 🎯 Testing Goals

1. **Verify all Phase 1 features work correctly**
2. **Identify and fix bugs**
3. **Improve UI/UX based on real usage**
4. **Ensure data persistence across sessions**
5. **Document any issues for future fixes**

---

## 🚀 Starting the Application

### Method 1: Production Mode (Recommended for Testing)

```bash
cd /mnt/data/src/matchering

# Start backend only (avoids file watcher issues)
python launch-auralis-web.py

# Open browser at http://localhost:8765
```

**Why production mode?**
- No file watcher limits ("too many open files" error)
- Faster startup
- More stable for extended testing
- Uses pre-built frontend

---

### Method 2: Check Backend Health

Before testing, verify backend is running:

```bash
# Check health endpoint
curl http://localhost:8765/api/health

# Expected output:
# {
#   "status": "healthy",
#   "library_stats": { ... }
# }
```

---

## 🧪 Feature Testing Checklist

### 1. Favorites System (Task 1.1)

#### Backend Testing

**Endpoint**: `POST /api/library/tracks/{id}/favorite`

```bash
# Add track to favorites
curl -X POST http://localhost:8765/api/library/tracks/1/favorite

# Expected response:
# {
#   "message": "Track added to favorites",
#   "track_id": 1,
#   "favorite": true
# }

# Get favorites list
curl http://localhost:8765/api/library/tracks/favorites

# Expected response:
# {
#   "tracks": [ ... ],
#   "total": 1
# }

# Remove from favorites
curl -X DELETE http://localhost:8765/api/library/tracks/1/favorite

# Expected response:
# {
#   "message": "Track removed from favorites",
#   "track_id": 1,
#   "favorite": false
# }
```

---

#### Frontend Testing

**Steps**:
1. ✅ Open Auralis web UI (http://localhost:8765)
2. ✅ Navigate to "Songs" view
3. ✅ Click heart icon on a track
4. ✅ Verify heart turns pink/red (indicating favorited)
5. ✅ Click "Favourites" in sidebar
6. ✅ Verify track appears in favorites list
7. ✅ Click heart again to unfavorite
8. ✅ Verify track disappears from favorites list
9. ✅ Refresh page (Ctrl+R)
10. ✅ Verify favorites persist across page reload

**Expected Behavior**:
- Heart icon toggles between outlined and filled
- Toast notification shows "Added to favorites" / "Removed from favorites"
- Favorites view updates immediately
- Favorites persist in database

**Known Issues**:
- None reported yet

---

### 2. Playlist Management (Task 1.2)

#### Backend Testing

```bash
# Create playlist
curl -X POST http://localhost:8765/api/playlists \
  -H "Content-Type: application/json" \
  -d '{"name":"My Test Playlist","description":"Testing playlists"}'

# Expected response:
# {
#   "message": "Playlist 'My Test Playlist' created",
#   "playlist": {
#     "id": 1,
#     "name": "My Test Playlist",
#     "description": "Testing playlists",
#     "track_count": 0,
#     "total_duration": 0
#   }
# }

# Get all playlists
curl http://localhost:8765/api/playlists

# Add track to playlist
curl -X POST http://localhost:8765/api/playlists/1/tracks \
  -H "Content-Type: application/json" \
  -d '{"track_id":1}'

# Delete playlist
curl -X DELETE http://localhost:8765/api/playlists/1
```

---

#### Frontend Testing

**Steps**:
1. ✅ Open sidebar and scroll to "Playlists" section
2. ✅ Click "Create Playlist" (+) button
3. ✅ Enter playlist name: "Test Playlist"
4. ✅ Enter description: "Testing playlist functionality"
5. ✅ Click "Create"
6. ✅ Verify playlist appears in sidebar
7. ✅ Verify toast shows "Playlist created successfully"
8. ✅ Hover over playlist and click delete (trash icon)
9. ✅ Confirm deletion
10. ✅ Verify playlist disappears from sidebar
11. ✅ Refresh page and verify changes persist

**Expected Behavior**:
- Create dialog opens with form fields
- Playlist appears immediately in sidebar after creation
- Playlists are collapsible (expand/collapse section)
- Delete requires confirmation
- Track count displays next to playlist name

**Known Issues**:
- "Edit Playlist" shows "Coming soon" placeholder
- "Add to Playlist" context menu not implemented yet
- Track reordering within playlist not implemented

---

### 3. Album Art Extraction (Task 1.3)

#### Backend Testing

```bash
# Extract artwork from album
curl -X POST http://localhost:8765/api/albums/1/artwork/extract

# Expected response:
# {
#   "message": "Artwork extracted successfully",
#   "artwork_path": "/home/user/.auralis/artwork/album_1_a3f2b9c1.jpg",
#   "album_id": 1
# }

# Get artwork (download image)
curl http://localhost:8765/api/albums/1/artwork > artwork.jpg

# Check file type
file artwork.jpg
# Expected: JPEG image data...

# Delete artwork
curl -X DELETE http://localhost:8765/api/albums/1/artwork
```

---

#### Frontend Testing

**Steps**:
1. ✅ Open "Songs" view in library
2. ✅ Check if album art displays in grid cards
3. ✅ Look for loading skeleton animation (brief flash)
4. ✅ Verify placeholder icon shows for tracks without artwork
5. ✅ Play a track with artwork
6. ✅ Check bottom player bar shows artwork thumbnail (64x64px)
7. ✅ Switch to another track
8. ✅ Verify artwork updates in player bar
9. ✅ Open browser DevTools (F12) → Network tab
10. ✅ Verify artwork requests return 200 OK (or 404 for missing artwork)

**Expected Behavior**:
- Album cards show real artwork from audio file metadata
- Loading skeleton appears briefly during image load
- Smooth fade-in animation when artwork loads
- Placeholder album icon for missing artwork
- Player bar updates artwork when track changes
- Artwork is cached by browser (second load is instant)

**Testing with Real Audio Files**:
```bash
# Scan a folder with audio files that have embedded artwork
# Use the "Scan Folder" button in the UI

# OR via API:
curl -X POST http://localhost:8765/api/library/scan \
  -H "Content-Type: application/json" \
  -d '{"directory":"/path/to/music/folder"}'
```

**Supported Formats**:
- ✅ MP3 (ID3 tags)
- ✅ FLAC (Picture blocks)
- ✅ M4A/MP4 (covr atom)
- ✅ OGG (Vorbis comments)

**Known Issues**:
- Artwork not automatically extracted during library scan (manual extraction needed)
- No artwork upload UI (API works, UI not implemented)

---

### 4. Queue Management (Task 1.4)

#### Backend Testing

```bash
# Get current queue
curl http://localhost:8765/api/player/queue

# Remove track at index 2
curl -X DELETE http://localhost:8765/api/player/queue/2

# Reorder queue (move track 0 to position 2)
curl -X PUT http://localhost:8765/api/player/queue/reorder \
  -H "Content-Type: application/json" \
  -d '{"new_order":[1,2,0,3,4]}'

# Shuffle queue
curl -X POST http://localhost:8765/api/player/queue/shuffle

# Clear queue
curl -X POST http://localhost:8765/api/player/queue/clear
```

---

#### Frontend Testing

**Steps**:
1. ✅ Play multiple tracks to build a queue
2. ✅ Scroll down to see "Queue" section below library grid
3. ✅ Verify current track is highlighted
4. ✅ Hover over a track in queue
5. ✅ Verify remove button (X) appears on hover
6. ✅ Click remove button on a track
7. ✅ Verify track disappears from queue
8. ✅ Drag a track to reorder it
9. ✅ Verify tracks rearrange in real-time
10. ✅ Click "Shuffle" button
11. ✅ Verify queue is randomized
12. ✅ Click "Clear Queue" button
13. ✅ Confirm clearing
14. ✅ Verify all tracks removed from queue

**Expected Behavior**:
- EnhancedTrackQueue component displays below library grid
- Current track highlighted with different color
- Smooth drag-and-drop animation
- Remove button appears on hover
- Shuffle randomizes queue but keeps current track
- Clear requires confirmation dialog
- Toast notifications for all operations

**Drag-and-Drop Testing**:
- Click and hold on a track
- Drag up or down
- Visual placeholder shows drop position
- Release to drop in new position
- Queue updates immediately

**Known Issues**:
- None reported yet

---

## 🐛 Bug Reporting Template

When you find a bug, document it using this template:

```markdown
## Bug: [Short Description]

**Feature**: [Favorites/Playlists/Album Art/Queue]
**Severity**: [Critical/High/Medium/Low]
**Reproducibility**: [Always/Sometimes/Rare]

**Steps to Reproduce**:
1. Step one
2. Step two
3. ...

**Expected Behavior**:
What should happen

**Actual Behavior**:
What actually happens

**Screenshots/Logs**:
[Attach if available]

**Browser Console Errors**:
[Copy from F12 → Console]

**Backend Logs**:
[Copy from terminal]

**Environment**:
- Browser: Firefox/Chrome/etc
- OS: Linux/Windows/Mac
- Auralis Version: 1.0.0
```

---

## 🎨 UI/UX Feedback Template

When you notice UI/UX improvements, document them:

```markdown
## UX Improvement: [Short Description]

**Feature**: [Favorites/Playlists/Album Art/Queue]
**Priority**: [High/Medium/Low]

**Current Behavior**:
How it works now

**Suggested Improvement**:
How it could be better

**Rationale**:
Why this would improve user experience

**Effort Estimate**:
[Quick/Medium/Large]
```

---

## 📊 Testing Progress Tracker

### Favorites System
- [ ] Backend API - Add to favorites
- [ ] Backend API - Remove from favorites
- [ ] Backend API - Get favorites list
- [ ] Frontend UI - Heart icon toggle
- [ ] Frontend UI - Favorites view
- [ ] Data persistence across page reload
- [ ] Toast notifications
- [ ] WebSocket real-time updates

### Playlist Management
- [ ] Backend API - Create playlist
- [ ] Backend API - Delete playlist
- [ ] Backend API - Get all playlists
- [ ] Frontend UI - Create dialog
- [ ] Frontend UI - Delete confirmation
- [ ] Frontend UI - Sidebar display
- [ ] Data persistence
- [ ] Track count display

### Album Art Extraction
- [ ] Backend API - Extract artwork
- [ ] Backend API - Get artwork file
- [ ] Backend API - Delete artwork
- [ ] Frontend UI - Library grid display
- [ ] Frontend UI - Player bar thumbnail
- [ ] Loading skeletons
- [ ] Fallback placeholders
- [ ] Browser caching

### Queue Management
- [ ] Backend API - Remove track
- [ ] Backend API - Reorder queue
- [ ] Backend API - Shuffle queue
- [ ] Backend API - Clear queue
- [ ] Frontend UI - Drag-and-drop
- [ ] Frontend UI - Remove buttons
- [ ] Frontend UI - Shuffle button
- [ ] Frontend UI - Clear button

---

## 🔧 Known Issues & Workarounds

### Issue 1: "Too many open files" error

**Symptom**: Backend crashes with file watcher error when using `--dev` flag

**Cause**: System file descriptor limit exceeded by Vite dev server

**Workaround**: Use production mode instead
```bash
# Instead of:
python launch-auralis-web.py --dev

# Use:
python launch-auralis-web.py
```

**Permanent Fix**: Increase file descriptor limit (requires system configuration)

---

### Issue 2: Frontend not loading

**Symptom**: Blank page or "Failed to load" error

**Cause**: Frontend build not present

**Fix**: Build frontend first
```bash
cd auralis-web/frontend
npm install
npm run build
```

---

### Issue 3: Database migration errors

**Symptom**: "Table already exists" or "Column not found" errors

**Cause**: Database schema out of sync

**Fix**: Delete database and rescan
```bash
# CAUTION: This deletes all library data
rm ~/.auralis/library.db

# Restart backend (will recreate database)
python launch-auralis-web.py

# Rescan your music folder
```

---

## 📝 Testing Session Template

Use this template for each testing session:

```markdown
# Testing Session - [Date]

**Duration**: [Start time] - [End time]
**Tester**: [Your name]
**Focus**: [Which features tested]

## Tests Completed
- [x] Feature A - All tests passed
- [x] Feature B - 2 bugs found
- [ ] Feature C - Not tested

## Bugs Found
1. Bug #1: [Description]
2. Bug #2: [Description]

## UI/UX Feedback
1. Improvement A: [Description]
2. Improvement B: [Description]

## Notes
- Additional observations
- Performance notes
- Suggestions
```

---

## 🎯 Testing Success Criteria

Phase 1 is ready for production when:

- ✅ **All core features work** - No critical bugs in Favorites, Playlists, Album Art, Queue
- ✅ **Data persists** - All data survives page reloads and backend restarts
- ✅ **Error handling works** - Graceful fallbacks for all error cases
- ✅ **UI is polished** - No visual glitches, smooth animations
- ✅ **Performance is good** - No lag, fast response times
- ✅ **WebSocket sync works** - Real-time updates across tabs

---

## 📚 Next Steps After Testing

Once testing is complete and all bugs are fixed:

1. **Document findings** in a testing report
2. **Update AURALIS_ROADMAP.md** with any scope changes
3. **Create bug fix PRs** if needed
4. **Polish UI/UX** based on feedback
5. **Decide**: Continue to Phase 1.5 (Real-Time Enhancement) or start Phase 2

---

## 🚀 Quick Start Testing Guide

**For the impatient tester:**

```bash
# 1. Start backend
cd /mnt/data/src/matchering
python launch-auralis-web.py

# 2. Open browser
# Navigate to http://localhost:8765

# 3. Test each feature (5 minutes each):
# - Add/remove favorites
# - Create/delete playlist
# - Check album artwork displays
# - Reorder queue with drag-and-drop

# 4. Look for:
# - Toast notifications appear
# - Data persists after refresh
# - No console errors (F12)
# - Smooth animations
```

**Total testing time**: ~30-45 minutes for comprehensive test

---

**Happy Testing! 🎉**

Report all findings and we'll polish Phase 1 to perfection before tackling Real-Time Enhancement!

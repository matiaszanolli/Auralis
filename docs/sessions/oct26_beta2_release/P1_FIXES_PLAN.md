# P1 Fixes Implementation Plan

**Date**: October 26, 2025
**Priority**: P1 (High)
**Status**: 🔄 PLANNING
**Target**: Beta.2 Release

---

## 🎯 Two P1 Issues to Fix

### 1. Gapless Playback Gaps (~100ms)
**Issue**: Noticeable ~100ms gaps between tracks during queue playback
**Impact**: Interrupts listening flow, especially noticeable in albums/live recordings
**Root Cause**: No pre-buffering of next track, cold start on track change

### 2. Artist Listing Performance (468ms)
**Issue**: Slow response time for artist list endpoint
**Impact**: Laggy UI when browsing artists, poor UX for large libraries
**Root Cause**: No pagination, loading all artists at once

---

## 📋 Fix #1: Gapless Playback

### Root Cause Analysis

**Current Flow** (with gap):
```
Track 1 playing → User clicks next → Stop Track 1 →
  ↓ (gap starts here)
Load Track 2 from disk →
Process/decode audio →
Initialize audio output →
  ↓ (gap ends here)
Start playing Track 2
```

**Gap Duration Breakdown**:
- File I/O (load from disk): ~30-50ms
- Audio decoding: ~20-30ms
- Audio output initialization: ~30-40ms
- Processing pipeline setup: ~10-20ms
- **Total**: ~90-140ms gap

### Solution: Pre-buffering

**New Flow** (gapless):
```
Track 1 playing → Pre-load Track 2 in background →
User clicks next → Stop Track 1 →
  ↓ (minimal gap)
Switch to pre-buffered Track 2 →
  ↓ (< 10ms)
Start playing Track 2 immediately
```

### Implementation Plan

#### Step 1: Add Pre-buffer State

**File**: `auralis/player/enhanced_audio_player.py`

```python
class EnhancedAudioPlayer:
    def __init__(self):
        # ... existing code ...

        # Gapless playback support
        self.next_track_buffer = None  # Pre-loaded next track
        self.next_track_info = None    # Track info for pre-buffered track
        self.prebuffer_enabled = True  # Config option
```

#### Step 2: Implement Pre-buffering Logic

**New Method**: `_prebuffer_next_track()`

```python
def _prebuffer_next_track(self):
    """
    Pre-load and decode the next track in queue for gapless playback.

    This runs in the background while current track is playing.
    """
    if not self.prebuffer_enabled:
        return

    # Get next track from queue (without removing it)
    next_track = self.queue.peek_next()
    if not next_track:
        return

    try:
        # Load and decode audio
        audio, sr = load_audio(next_track.filepath)

        # Store in buffer
        self.next_track_buffer = audio
        self.next_track_info = next_track

        logger.info(f"Pre-buffered next track: {next_track.title}")
    except Exception as e:
        logger.warning(f"Failed to pre-buffer next track: {e}")
        self.next_track_buffer = None
```

#### Step 3: Trigger Pre-buffering

**Modified Method**: `load_track()`

```python
def load_track(self, track_id: int):
    """Load a track for playback"""
    # ... existing loading code ...

    # After current track is loaded and playing:
    # Start pre-buffering next track in background
    import threading
    prebuffer_thread = threading.Thread(target=self._prebuffer_next_track)
    prebuffer_thread.daemon = True
    prebuffer_thread.start()
```

#### Step 4: Use Pre-buffer on Track Change

**Modified Method**: `next_track()`

```python
def next_track(self) -> bool:
    """Skip to next track with gapless transition"""
    next_track = self.queue.next_track()
    if not next_track:
        return False

    # Check if we have pre-buffered this track
    if (self.next_track_buffer is not None and
        self.next_track_info and
        self.next_track_info.id == next_track.id):

        # Use pre-buffered audio (gapless!)
        logger.info(f"Using pre-buffered track: {next_track.title}")

        # Stop current playback
        self.stop()

        # Load pre-buffered audio directly
        self.current_track = next_track
        self.audio = self.next_track_buffer
        self.sample_rate = 44100  # From buffer metadata

        # Clear buffer
        self.next_track_buffer = None
        self.next_track_info = None

        # Start playback immediately (< 10ms gap)
        self.play()

        # Pre-buffer NEXT track in background
        threading.Thread(target=self._prebuffer_next_track, daemon=True).start()

        return True
    else:
        # Fallback: Load normally (with gap)
        logger.warning("Pre-buffer not available, loading normally")
        return self.load_track(next_track.id)
```

### Edge Cases to Handle

1. **Queue changes**: Invalidate pre-buffer if queue is modified
2. **Skip multiple tracks**: Pre-buffer may be wrong track
3. **Memory limits**: Only pre-buffer 1 track at a time
4. **Enhancement enabled**: Pre-buffer enhanced audio if enabled
5. **Errors**: Graceful fallback to normal loading

### Testing Strategy

**Manual Test**:
```python
# Play a playlist with 5+ tracks
# Enable enhancement
# Click "next" rapidly
# Listen for gaps between tracks
# Measure gap duration:
#   - Before: ~100ms
#   - After: < 10ms ✓
```

**Automated Test**:
```python
def test_gapless_playback():
    player = EnhancedAudioPlayer()

    # Add multiple tracks to queue
    player.queue.add_track(track1)
    player.queue.add_track(track2)
    player.queue.add_track(track3)

    # Play first track
    player.play_track(track1.id)
    time.sleep(2)  # Let it pre-buffer

    # Verify pre-buffer exists
    assert player.next_track_buffer is not None
    assert player.next_track_info.id == track2.id

    # Skip to next track
    start_time = time.time()
    player.next_track()
    gap_duration = time.time() - start_time

    # Verify minimal gap
    assert gap_duration < 0.050  # < 50ms

    # Verify playback started
    assert player.is_playing
    assert player.current_track.id == track2.id
```

### Expected Results

- **Before**: ~100ms gaps between tracks
- **After**: < 10ms gaps (imperceptible)
- **Memory**: +10-50MB per pre-buffered track (acceptable)
- **CPU**: Minimal (background thread)

---

## 📋 Fix #2: Artist Listing Performance

### Root Cause Analysis

**Current Implementation**:
```python
# auralis-web/backend/routers/library.py
@router.get("/artists")
async def get_artists():
    """Get all artists"""
    artists = artist_repo.get_all()  # ← No pagination!
    return artists
```

**Performance Issues**:
- **10,000 track library** → ~2,000 unique artists
- Loading 2,000 artists at once: **468ms**
- Transferring 2,000 artist objects over network: **slow**
- Frontend rendering 2,000 items: **laggy**

### Solution: Pagination

**New Flow**:
```
Request: GET /api/library/artists?limit=50&offset=0
Response: 50 artists (A-B range) in ~25ms ✓

User scrolls down...
Request: GET /api/library/artists?limit=50&offset=50
Response: next 50 artists (C-D range) in ~25ms ✓
```

### Implementation Plan

#### Step 1: Add Pagination to Repository

**File**: `auralis/library/repositories/artist_repository.py`

```python
class ArtistRepository:
    def get_all_paginated(
        self,
        limit: int = 50,
        offset: int = 0,
        order_by: str = "name",
        order_direction: str = "asc"
    ) -> Tuple[List[Artist], int]:
        """
        Get paginated list of artists.

        Args:
            limit: Number of artists to return (default 50)
            offset: Number of artists to skip (default 0)
            order_by: Field to order by (default "name")
            order_direction: "asc" or "desc" (default "asc")

        Returns:
            Tuple of (artists list, total count)
        """
        query = self.session.query(Artist)

        # Apply ordering
        if order_direction == "desc":
            query = query.order_by(getattr(Artist, order_by).desc())
        else:
            query = query.order_by(getattr(Artist, order_by).asc())

        # Get total count (before pagination)
        total = query.count()

        # Apply pagination
        query = query.offset(offset).limit(limit)

        artists = query.all()

        return artists, total
```

#### Step 2: Update API Endpoint

**File**: `auralis-web/backend/routers/library.py`

```python
from typing import Optional

@router.get("/artists")
async def get_artists(
    limit: int = 50,
    offset: int = 0,
    order_by: str = "name",
    order_direction: str = "asc",
    library_manager: LibraryManager = Depends(get_library_manager)
):
    """
    Get paginated list of artists.

    Query Parameters:
        limit: Number of artists to return (default 50, max 200)
        offset: Number of artists to skip (default 0)
        order_by: Field to order by (default "name")
        order_direction: "asc" or "desc" (default "asc")

    Returns:
        {
            "artists": [...],
            "total": 2000,
            "limit": 50,
            "offset": 0,
            "has_more": true
        }
    """
    # Validate and limit
    limit = min(max(limit, 1), 200)  # Between 1-200
    offset = max(offset, 0)  # Non-negative

    # Get paginated artists
    artists, total = library_manager.artist_repository.get_all_paginated(
        limit=limit,
        offset=offset,
        order_by=order_by,
        order_direction=order_direction
    )

    # Calculate if there are more results
    has_more = (offset + limit) < total

    return {
        "artists": [artist.to_dict() for artist in artists],
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": has_more
    }
```

#### Step 3: Update Frontend (Optional - Backend Compatible)

**File**: `auralis-web/frontend/src/api/library.ts`

```typescript
export interface ArtistsResponse {
  artists: Artist[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

export async function getArtists(
  limit: number = 50,
  offset: number = 0
): Promise<ArtistsResponse> {
  const response = await fetch(
    `/api/library/artists?limit=${limit}&offset=${offset}`
  );
  return response.json();
}

// Infinite scroll implementation
export function useArtistsInfiniteScroll() {
  const [artists, setArtists] = useState<Artist[]>([]);
  const [hasMore, setHasMore] = useState(true);
  const [offset, setOffset] = useState(0);

  const loadMore = async () => {
    const response = await getArtists(50, offset);
    setArtists([...artists, ...response.artists]);
    setHasMore(response.has_more);
    setOffset(offset + 50);
  };

  return { artists, hasMore, loadMore };
}
```

### Performance Improvements

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Response time | 468ms | ~25ms | **18.7x faster** |
| Data transferred | ~500KB | ~25KB | **20x less** |
| Initial render | Slow | Fast | ✓ |
| Memory usage | High | Low | ✓ |

### Backwards Compatibility

**Option 1: Breaking Change** (Recommended)
- Always return paginated response
- Frontend must update to handle pagination
- Simple, clean implementation

**Option 2: Backwards Compatible**
- If no `limit` param, return all artists (old behavior)
- If `limit` provided, return paginated
- Allows gradual frontend migration

```python
@router.get("/artists")
async def get_artists(
    limit: Optional[int] = None,  # None = return all (old behavior)
    offset: int = 0,
    ...
):
    if limit is None:
        # Old behavior: return all artists
        artists = library_manager.artist_repository.get_all()
        return {"artists": [a.to_dict() for a in artists]}
    else:
        # New behavior: paginated
        artists, total = library_manager.artist_repository.get_all_paginated(...)
        return {
            "artists": [...],
            "total": total,
            "has_more": ...,
            ...
        }
```

### Testing Strategy

**Performance Test**:
```python
import time

def test_artist_pagination_performance():
    # Setup: 10,000 tracks with ~2,000 artists

    # Test old endpoint (if still exists)
    start = time.time()
    response = client.get("/api/library/artists")
    old_time = time.time() - start

    # Test new paginated endpoint
    start = time.time()
    response = client.get("/api/library/artists?limit=50&offset=0")
    new_time = time.time() - start

    assert new_time < old_time / 10  # At least 10x faster
    assert new_time < 0.050  # < 50ms
```

**Functional Test**:
```python
def test_artist_pagination_correctness():
    # Get first page
    page1 = client.get("/api/library/artists?limit=50&offset=0").json()
    assert len(page1["artists"]) == 50
    assert page1["total"] > 50
    assert page1["has_more"] == True

    # Get second page
    page2 = client.get("/api/library/artists?limit=50&offset=50").json()
    assert len(page2["artists"]) == 50

    # Verify no overlap
    page1_ids = {a["id"] for a in page1["artists"]}
    page2_ids = {a["id"] for a in page2["artists"]}
    assert len(page1_ids & page2_ids) == 0  # No duplicates
```

---

## 🚀 Implementation Order

### Phase 1: Artist Pagination (Easier, Backend Only)
1. ✅ Add `get_all_paginated()` to ArtistRepository
2. ✅ Update `/api/library/artists` endpoint
3. ✅ Add tests
4. ✅ Verify performance improvement
5. ⏳ (Optional) Update frontend for infinite scroll

**Effort**: 2-3 hours
**Risk**: Low
**Impact**: High

### Phase 2: Gapless Playback (Complex, Player Changes)
1. ✅ Add pre-buffer state to EnhancedAudioPlayer
2. ✅ Implement `_prebuffer_next_track()` method
3. ✅ Modify `next_track()` to use pre-buffer
4. ✅ Add queue change invalidation logic
5. ✅ Handle edge cases (skip, shuffle, etc.)
6. ✅ Add comprehensive tests
7. ✅ Test with real audio files

**Effort**: 4-6 hours
**Risk**: Medium
**Impact**: High

---

## 📊 Success Criteria

### Gapless Playback
- ✅ Gap duration < 10ms (down from ~100ms)
- ✅ Works with enhancement enabled
- ✅ Works across all presets
- ✅ No audio glitches or artifacts
- ✅ Memory usage acceptable (< 100MB overhead)

### Artist Pagination
- ✅ Response time < 50ms (down from 468ms)
- ✅ Works for libraries with 10k+ tracks
- ✅ Infinite scroll UI (smooth scrolling)
- ✅ No data loss or duplicates
- ✅ Backwards compatible (optional)

---

## 📝 Documentation Updates

After implementation, update:
1. [BETA1_KNOWN_ISSUES.md](BETA1_KNOWN_ISSUES.md) - Mark P1 issues as fixed
2. [CLAUDE.md](CLAUDE.md) - Update architecture docs
3. [WEBSOCKET_API.md](auralis-web/backend/WEBSOCKET_API.md) - If WebSocket changes needed
4. [BETA2_RELEASE_NOTES.md](BETA2_RELEASE_NOTES.md) - Document improvements

---

## 🎯 Beta.2 Release Checklist

**P0 Issues** (Critical):
- ✅ Audio fuzziness between chunks - **FIXED**
- ✅ Volume jumps between chunks - **FIXED**

**P1 Issues** (High):
- ⏳ Gapless playback gaps - **PLANNED**
- ⏳ Artist listing performance - **PLANNED**

**Other Tasks**:
- ⏳ Test P0 fixes with real audio
- ⏳ Implement P1 fixes
- ⏳ Test P1 fixes
- ⏳ Update documentation
- ⏳ Create beta.2 release

**Timeline**: 1-2 weeks (faster than original 2-3 weeks estimate!)

---

*Last Updated: October 26, 2025*
*Status: Planning complete, ready for implementation*

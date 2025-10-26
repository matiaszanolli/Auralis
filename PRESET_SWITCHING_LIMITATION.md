# Preset Switching Limitation - Beta.2

**Date**: October 26, 2025
**Severity**: P2 (Medium - UX inconvenience, not a bug)
**Status**: Known Limitation - Requires architectural change

---

## 🎯 Issue Description

**User Report**: "I don't see the buffering fixes being applied. Every time I change presets I get forced to wait."

**Observed Behavior**:
- When user changes enhancement preset (e.g., adaptive → punchy → warm)
- Audio playback pauses for 2-5 seconds while new preset loads
- "Audio waiting for more data" messages appear in console
- User must wait for buffering even though multi-tier buffer system exists

**Expected Behavior** (ideal):
- Instant preset switching with no buffering delay
- Multi-tier buffer provides pre-processed audio for predicted presets
- Seamless listening experience when experimenting with presets

---

## 🔍 Root Cause Analysis

### Current Architecture

**Streaming Endpoint**: `/api/player/stream/{track_id}?enhanced=true&preset={preset}&intensity={intensity}`

**How It Works**:
1. Frontend loads audio via HTML5 `<audio>` element
2. Audio element requests: `http://localhost:8765/api/player/stream/39729?enhanced=true&preset=adaptive&intensity=1`
3. Backend processes entire track with `ChunkedAudioProcessor`
4. Backend serves complete processed WAV file via `FileResponse`
5. Frontend buffers and plays the file

**When Preset Changes**:
1. User clicks different preset button
2. Frontend generates NEW stream URL: `...?preset=punchy...`
3. Frontend calls `audio.load()` with new URL
4. HTML5 audio element **discards current buffer**
5. Backend processes **entire track** again with new preset
6. Frontend waits for buffering (~2-5 seconds)
7. Playback resumes from current position

### Why Multi-Tier Buffer Doesn't Help

The multi-tier buffer system **is working correctly** and pre-processing chunks for multiple presets. However, it's not being utilized because:

**Architectural Mismatch**:
```
Multi-Tier Buffer:
  - Pre-processes 30-second chunks for multiple presets
  - Stores in L1/L2/L3 cache tiers
  - Designed for progressive chunk-by-chunk delivery
  - Ready to serve chunks instantly on preset change

Streaming Endpoint:
  - Processes entire track to create complete WAV file
  - Serves via FileResponse (static file)
  - No progressive chunk delivery
  - New URL = complete reload
```

**The Problem**: The buffer has the data ready, but the streaming architecture can't use it because it serves complete files, not progressive chunks.

---

## 🛠️ Technical Details

### Current Code Flow

**File**: `auralis-web/backend/routers/player.py` (lines 200-208)

```python
# Current approach: Process ALL chunks to create full file
logger.info(f"Creating full processed audio (all chunks)...")
file_to_serve = processor.get_full_processed_audio_path()

# Serve as static file
return FileResponse(
    file_to_serve,
    media_type=media_type,
    headers={"Accept-Ranges": "bytes", ...}
)
```

**When preset changes**:
- Frontend requests new URL
- `get_full_processed_audio_path()` creates complete file (takes 2-5 seconds)
- HTML5 audio reloads entire file
- User waits

### What Was Intended

The multi-tier buffer system was designed for **progressive streaming**:

```python
# Intended flow (not implemented yet):
@router.get("/api/player/stream/{track_id}/chunk/{chunk_idx}")
async def stream_chunk(track_id, chunk_idx, preset):
    # Check multi-tier buffer
    chunk_data = await buffer_manager.get_chunk(track_id, preset, chunk_idx)

    if chunk_data:
        # Instant delivery from cache (0ms latency for L1)
        return chunk_data
    else:
        # Process on demand
        chunk_data = await process_chunk(...)
        return chunk_data
```

**With MSE (Media Source Extensions)**:
- Frontend uses MSE instead of `<audio src="...">`
- Frontend requests chunks progressively
- Preset change = switch to different chunk stream
- Buffer provides instant delivery from cache
- **No waiting, no reload!**

---

## ✅ Why This Isn't a Bug

This is a **design trade-off**, not a bug:

**Benefits of Current Approach**:
- ✅ Simple implementation (works with standard HTML5 audio)
- ✅ Reliable playback (complete file buffering)
- ✅ Easy seeking (file-based seeking)
- ✅ No MSE complexity
- ✅ Works on all browsers

**Limitation**:
- ⚠️ Preset changes require reload
- ⚠️ 2-5 second wait on preset change
- ⚠️ Multi-tier buffer not utilized for preset switching

**Design Decision**: We prioritized **simplicity and reliability** over **instant preset switching** for Beta.2.

---

## 📋 Workarounds for Beta.2

### For Users

**Recommendation**: Choose your preferred preset before starting playback

**Tips**:
1. **Preview presets on short tracks** to find your favorite
2. **Set default preset** in settings for your library
3. **Avoid frequent preset switching** during playback
4. **Pause before switching** to minimize disruption

### For Developers

The multi-tier buffer **is still valuable** because it:
- Pre-processes chunks in background
- Speeds up initial playback start
- Prepares for future MSE implementation
- Reduces CPU load during playback

---

## 🚀 Proper Solution (Future Implementation)

### Solution: MSE-Based Progressive Streaming

**Implementation Roadmap**:

**Phase 1**: Backend Chunk Streaming (1-2 days)
- Implement `/api/player/stream/{track_id}/chunk/{chunk_idx}` endpoint
- Integrate with multi-tier buffer manager
- Return WAV chunk data with proper headers

**Phase 2**: Frontend MSE Integration (2-3 days)
- Replace `<audio>` with MediaSource API
- Implement SourceBuffer management
- Handle chunk appending and transitions
- Implement preset switching without reload

**Phase 3**: Testing & Optimization (1-2 days)
- Test across browsers (Chrome, Firefox, Safari)
- Handle edge cases (seeking, network errors)
- Optimize buffer management
- Performance tuning

**Total Effort**: ~1 week of focused development

### Expected Results

After MSE implementation:
- ✅ **Instant preset switching** (< 100ms)
- ✅ **No buffering delays** when changing presets
- ✅ **Multi-tier buffer fully utilized**
- ✅ **Seamless user experience**
- ✅ **Lower memory usage** (stream chunks vs full files)

---

## 📊 Impact Assessment

### User Impact

**Frequency**: Medium
- Users experiment with presets during initial library setup
- Less frequent once preferred preset is chosen

**Severity**: Low-Medium
- 2-5 second wait is annoying but not blocking
- Playback resumes from correct position
- Audio quality not affected

**Workaround Available**: Yes (choose preset before playing)

### Priority Justification

**Why P2 (Medium)**:
- Not a bug, but a known architectural limitation
- Workaround exists (choose preset first)
- Affects UX, not core functionality
- Other Beta.2 fixes were higher priority (audio quality, crashes)
- Proper fix requires significant architectural change (~1 week)

**Why Not P0/P1**:
- Doesn't affect audio quality
- Doesn't cause crashes or data loss
- Users can work around it
- Multi-tier buffer still provides value elsewhere

---

## 📅 Roadmap

### Beta.2 (Current Release)
- ✅ Document limitation clearly
- ✅ Add to known issues
- ✅ Provide user workarounds
- ⏳ No code changes (accept limitation)

### Beta.3 or 1.0 Stable
- 🎯 Implement MSE-based progressive streaming
- 🎯 Full preset switch buffering
- 🎯 Instant preset switching UX
- 🎯 Remove this limitation

---

## 📝 Related Documentation

**Multi-Tier Buffer System**:
- [auralis-web/backend/multi_tier_buffer.py](auralis-web/backend/multi_tier_buffer.py) - Buffer implementation
- [docs/guides/MSE_PROGRESSIVE_STREAMING_PLAN.md](docs/guides/MSE_PROGRESSIVE_STREAMING_PLAN.md) - MSE implementation plan

**Streaming Architecture**:
- [auralis-web/backend/routers/player.py:101](auralis-web/backend/routers/player.py#L101) - Current streaming endpoint
- [auralis-web/backend/chunked_processor.py](auralis-web/backend/chunked_processor.py) - Chunked processing

**Roadmap**:
- [docs/roadmaps/NEXT_STEPS_ROADMAP.md](docs/roadmaps/NEXT_STEPS_ROADMAP.md) - Feature roadmap

---

## 🎯 Conclusion

**Status**: **Known Limitation** - Not a bug, requires architectural change

**For Beta.2**:
- Accept limitation and document clearly
- Provide user workarounds
- Focus on other critical fixes

**For Future Releases**:
- Implement MSE-based streaming
- Enable instant preset switching
- Fully utilize multi-tier buffer

**User Communication**:
> "Beta.2 offers high-quality adaptive audio processing with multiple presets. Due to the current streaming architecture, changing presets during playback requires a brief buffering pause (2-5 seconds). We recommend selecting your preferred preset before starting playback. Future updates will enable instant preset switching through progressive streaming technology."

---

**Last Updated**: October 26, 2025
**Status**: DOCUMENTED - Known limitation for Beta.2
**Priority**: P2 (Medium)
**Target Fix**: Beta.3 or 1.0 Stable


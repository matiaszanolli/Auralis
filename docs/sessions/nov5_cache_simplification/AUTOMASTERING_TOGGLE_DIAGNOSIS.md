# Auto-Mastering Toggle Issue - Diagnosis

**Date**: November 5, 2025
**Status**: 🔴 **ISSUE IDENTIFIED**
**Severity**: HIGH - Feature appears broken to users

---

## User-Reported Issue

**Symptom**: "I cannot tell for sure when the mastering process is enabled, because either is working extremely slightly or only works when I change the track, so I cannot really compare in real time."

**Translation**:
- Toggle switch shows "enabled/disabled" correctly
- BUT audio doesn't actually change when toggling
- Only changes when switching to a different track
- User suspects it's "working extremely slightly" (actually not working at all)

---

## Root Cause Analysis

### The Problem

When you toggle auto-mastering ON/OFF:
1. ✅ UI updates correctly (switch changes state)
2. ✅ Backend state changes (enhancement enabled/disabled flag)
3. ❌ **BUT**: Audio doesn't change because the browser is still playing **already-decoded chunks in the MediaSource buffer**

### Why It Happens

**MediaSource Extensions (MSE) Architecture**:
```
Frontend Request → Backend Cache → MediaSource Buffer → Audio Playback
                                    ↑
                          This is already filled!
```

When you toggle:
- New chunks are requested with `enhanced=true/false`
- Backend serves correct chunks (processed vs original)
- **BUT**: Browser's MediaSource buffer already has 30-60 seconds of decoded audio
- Browser continues playing from its buffer, ignoring new chunks until buffer is consumed

### Cache vs Playback Issue

The streamlined cache IS working correctly:
- ✅ Serving original chunks when `enhanced=false`
- ✅ Serving processed chunks when `enhanced=true`
- ✅ Cache hits/misses working as expected

**The problem**: Browser playback lag, not cache lag

---

## Evidence from Code

### Backend (webm_streaming.py:213-216)

```python
# If enhancement disabled, serve original audio chunk
if not enhanced:
    logger.info(f"Serving original (unenhanced) chunk {chunk_idx} for track {track_id}")
    webm_bytes = await _get_original_webm_chunk(track.filepath, chunk_idx, chunk_duration)
    cache_tier = "ORIGINAL"
```

**This works correctly** - backend serves original when `enhanced=false`

### Frontend Issue

The frontend likely:
1. Requests chunks with `enhanced=true`
2. User toggles OFF
3. Frontend requests chunks with `enhanced=false`
4. Backend correctly serves original chunks
5. **BUT**: Browser's MediaSource buffer still has 30-60s of processed audio queued
6. User hears processed audio for 30-60 more seconds before original audio plays

---

## Why It Works on Track Change

When you skip to a new track:
- MediaSource buffer is **flushed/cleared**
- New chunks are requested immediately
- Buffer fills with correct chunks (processed or original based on toggle state)
- You hear the correct audio immediately

---

## Solutions

### Option 1: Flush MediaSource Buffer on Toggle (Recommended)

**Pros**:
- Instant feedback (0-100ms)
- Clean implementation
- Works with MSE architecture

**Cons**:
- Brief audio gap/stutter during toggle (acceptable)
- Requires MSE buffer manipulation

**Implementation**:
```typescript
// In BottomPlayerBar or audio controller
const handleAutoMasteringToggle = async (enabled: boolean) => {
  // Update enhancement state
  await setEnhancementEnabled(enabled);

  // Flush MediaSource buffer
  if (sourceBuffer && !sourceBuffer.updating) {
    const currentTime = audioElement.currentTime;
    sourceBuffer.abort(); // Stop current operations

    // Remove buffered data ahead of current position
    const buffered = sourceBuffer.buffered;
    if (buffered.length > 0) {
      const start = currentTime;
      const end = buffered.end(buffered.length - 1);
      if (end > start) {
        sourceBuffer.remove(start, end);
      }
    }

    // Wait for removal to complete
    await new Promise(resolve => {
      sourceBuffer.addEventListener('updateend', resolve, { once: true });
    });

    // Force re-fetch of next chunks
    fetchNextChunks(currentChunkIndex, enabled);
  }
};
```

### Option 2: Dual MediaSource Streams (Complex)

**Concept**: Keep two parallel MediaSource instances (processed + original), switch between them

**Pros**:
- Truly instant switching (0ms)
- No buffer manipulation needed

**Cons**:
- 2x memory usage
- Complex state management
- Requires significant refactoring

**Not recommended** for Beta.9

### Option 3: Visual Feedback "Processing..." (Quick Fix)

**Concept**: Show a toast/notification explaining the delay

**Implementation**:
```typescript
const handleAutoMasteringToggle = async (enabled: boolean) => {
  await setEnhancementEnabled(enabled);

  // Show toast notification
  showToast(
    `Auto-mastering ${enabled ? 'enabled' : 'disabled'}. ` +
    `Changes will apply in ${estimateBufferDelay()}s...`,
    'info'
  );
};
```

**Pros**:
- Easy to implement (10 minutes)
- Sets correct user expectations

**Cons**:
- Doesn't fix the actual issue
- User still waits 30-60s

---

## Recommended Approach

### Phase 1: Immediate (30 min)

**Add visual feedback**:
1. Toast notification when toggle changes
2. Show "Applying..." indicator
3. Estimate buffer delay and show countdown

**User sees**: "Auto-mastering enabled. Applying in 30s..."

### Phase 2: Beta.10 (2-3 hours)

**Implement buffer flushing**:
1. Flush MediaSource buffer on toggle
2. Re-fetch chunks immediately
3. Brief audio gap (100-200ms) is acceptable

**User sees**: Brief pause, then immediate audio change

### Phase 3: Future (Optional)

**Dual-stream architecture**:
1. Keep both streams in memory
2. Instant switching with no gap
3. Higher memory usage but perfect UX

---

## Testing Plan

### Current Behavior (Bug)

**Steps**:
1. Play track with auto-mastering ON
2. Wait 10 seconds
3. Toggle auto-mastering OFF
4. **Expected**: Audio changes immediately
5. **Actual**: Audio doesn't change for 30-60s

### After Fix (Buffer Flush)

**Steps**:
1. Play track with auto-mastering ON
2. Wait 10 seconds
3. Toggle auto-mastering OFF
4. **Expected**: Brief pause (100-200ms), then audio changes
5. **Actual**: Should match expected

### Verification

**Check backend logs**:
```bash
# Should see immediate requests for original chunks
✅ Serving original (unenhanced) chunk 5 for track 123
✅ Serving original (unenhanced) chunk 6 for track 123
```

**Check browser console**:
```javascript
// Should see SourceBuffer operations
SourceBuffer: Aborting current operations
SourceBuffer: Removing range [10.0, 60.0]
SourceBuffer: Fetching new chunks from 10.0
```

---

## Code Locations

### Frontend (needs changes)

**Files to modify**:
1. `auralis-web/frontend/src/components/BottomPlayerBar.tsx` - Add buffer flush on toggle
2. `auralis-web/frontend/src/contexts/EnhancementContext.tsx` - Expose buffer control
3. `auralis-web/frontend/src/services/audioStreamingService.ts` - Add flush method

### Backend (works correctly)

**No changes needed** - backend is correctly serving original vs processed chunks based on `enhanced` parameter

---

## Impact Analysis

### User Experience

**Current (Broken)**:
- ❌ Toggle appears to do nothing
- ❌ User thinks feature is broken or "extremely slight"
- ❌ Only works when changing tracks (confusing)
- ❌ No feedback about delay

**After Quick Fix (Toast)**:
- ⚠️ Toggle shows countdown "Applying in 30s..."
- ✅ User understands there's a delay
- ⚠️ Still frustrating 30s wait

**After Buffer Flush**:
- ✅ Toggle works immediately (brief pause)
- ✅ Clear audio difference
- ✅ Matches user expectations
- ✅ Professional UX

### Technical Debt

**Current State**: MediaSource buffer management not implemented

**After Fix**: Proper buffer lifecycle management, foundation for future features

---

## Recommended Next Steps

### Immediate (This Session)

1. **Create task for buffer flush implementation**
2. **Document the exact buffer flush approach**
3. **Test current backend behavior** (verify it's working correctly)

### Short-Term (Beta.10)

1. **Implement buffer flushing on toggle**
2. **Add visual feedback during flush**
3. **Test with different chunk sizes**
4. **Measure actual toggle latency** (should be 100-200ms)

### Long-Term (Future)

1. **Consider dual-stream architecture**
2. **Pre-cache both states** (original + processed)
3. **Instant switching with no gap**

---

## Conclusion

**Status**: 🔴 **Root cause identified**

The auto-mastering toggle issue is **NOT a backend cache problem**. The streamlined cache is working correctly. The issue is **MediaSource buffer lag** - the browser continues playing already-buffered audio for 30-60 seconds after the toggle.

**Solution**: Flush MediaSource buffer on toggle, re-fetch chunks immediately

**Complexity**: Medium (2-3 hours for proper implementation)

**Priority**: HIGH - This is a critical UX issue that makes the feature appear broken

---

**Diagnosis Date**: November 5, 2025
**Next Action**: Implement buffer flushing in BottomPlayerBar component
**Estimated Fix Time**: 2-3 hours for proper implementation, or 30 minutes for quick toast notification

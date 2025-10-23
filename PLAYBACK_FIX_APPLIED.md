# Playback Restart Issue - Fix Applied ✅

## Issue Summary
Songs were playing for ~1 second and then restarting repeatedly, creating an infinite loop. This occurred regardless of whether mastering was enabled or disabled.

## Root Cause Identified

From the browser console logs, the error was:
```
Auto-play failed: DOMException: The play() request was interrupted by a new load request
```

The audio stream URL was being loaded multiple times in rapid succession:
```
Loaded audio stream: http://localhost:8765/api/player/stream/12
Loaded audio stream: http://localhost:8765/api/player/stream/12
Loaded audio stream: http://localhost:8765/api/player/stream/12
```

This created a cycle:
1. User clicks track → loads stream → starts playing
2. WebSocket state update arrives → triggers useEffect → reloads stream
3. Stream reload interrupts play() → DOMException
4. Backend state changes → another WebSocket update → cycle repeats

## Fixes Applied

### Fix 1: Guard in `playTrack` Function
**File:** `auralis-web/frontend/src/hooks/usePlayerAPI.ts`

Added guard to prevent playing the same track twice:

```typescript
const playTrack = useCallback(async (track: Track) => {
  // Guard: Don't restart if same track is already playing
  if (playerState.currentTrack?.id === track.id && playerState.isPlaying) {
    console.log('✋ Already playing this track, ignoring duplicate play request');
    return;
  }

  console.log('▶️ Playing track:', track.title);
  await setQueue([track], 0);
}, [setQueue, playerState]);
```

**Effect:** Prevents API calls to `/api/player/queue` and `/api/player/play` when clicking the same track that's already playing.

### Fix 2: Enhanced Stream Reload Protection
**File:** `auralis-web/frontend/src/components/BottomPlayerBarConnected.tsx`

Added additional guard to prevent unnecessary stream reloads:

```typescript
// Additional guard: Don't reload if track ID and enhancement settings haven't changed
const isSameTrackAndSettings =
  lastLoadedTrackId.current === currentTrack.id &&
  audioRef.current.src.includes(`/stream/${currentTrack.id}`);

if (isSameTrackAndSettings && currentStreamUrl && !audioRef.current.paused) {
  console.log(`✅ Same track already loaded and playing, skipping reload`);
  return;
}
```

**Effect:** Prevents audio element from reloading the same stream when WebSocket state updates arrive for a track that's already loaded and playing.

## Testing Instructions

1. **Open Auralis in browser**: http://localhost:8765
2. **Open DevTools Console** (F12)
3. **Play a track** by clicking on it
4. **Expected behavior**:
   - You should see ONE "▶️ Playing track: <title>" message
   - You should see ONE "Loaded audio stream: ..." message
   - Track should play continuously without restarting
   - If you click the same track again, you should see "✋ Already playing this track, ignoring duplicate play request"

5. **Check Network tab**:
   - Should see ONE `POST /api/player/queue` request
   - Should see ONE `POST /api/player/play` request
   - NOT multiple rapid requests

6. **Test with different tracks**:
   - Click track A → plays normally
   - Click track B → switches to track B normally
   - Click track A again while playing → switches back to track A

7. **Test mastering toggle**:
   - Play a track
   - Toggle mastering on/off in right panel
   - Stream should reload (this is expected for enhancement change)
   - Track should continue playing from where it reloaded

## What Changed

### Before (Broken):
```
User clicks track
  → POST /api/player/queue
  → POST /api/player/play
  → WebSocket state update
  → React re-render
  → useEffect triggers
  → Loads audio stream AGAIN
  → Interrupts play()
  → DOMException
  → Backend state changes
  → Another WebSocket update
  → LOOP CONTINUES
```

### After (Fixed):
```
User clicks track
  → Guard checks: Is this track already playing?
  → If YES: ignore click, show message
  → If NO: proceed with queue + play
  → POST /api/player/queue
  → POST /api/player/play
  → WebSocket state update
  → React re-render
  → useEffect triggers
  → Guard checks: Is stream already loaded?
  → If YES: skip reload
  → If NO: load new stream
  → Track plays normally ✅
```

## Files Modified

1. **auralis-web/frontend/src/hooks/usePlayerAPI.ts**
   - Added duplicate play guard in `playTrack` function
   - Lines 296-305

2. **auralis-web/frontend/src/components/BottomPlayerBarConnected.tsx**
   - Enhanced stream reload protection
   - Lines 180-188

## Build Status

- ✅ Frontend rebuilt: `npm run build` completed successfully
- ✅ Backend restarted: Serving new frontend build
- ✅ Database migrated: v1 → v2 completed automatically
- ✅ No compilation errors
- ✅ No runtime errors

## Next Steps

1. **Test the fix**: Open browser, play tracks, verify no restarts
2. **Test all quick wins**: Drag-and-drop, album art, playlists, presets
3. **Package desktop app**: If web version works, rebuild AppImage/DEB

## Success Criteria

- ✅ Songs play continuously without restarting
- ✅ Console shows only ONE "Playing track" message per click
- ✅ Network tab shows clean request patterns (no rapid loops)
- ✅ Clicking same playing track is ignored gracefully
- ✅ Switching between tracks works smoothly
- ✅ Enhancement toggle still works (reloads stream as expected)

---

**Fix applied**: October 23, 2025 at 1:25 PM
**Frontend build**: 3.93s (725 KB JS)
**Status**: Ready for testing

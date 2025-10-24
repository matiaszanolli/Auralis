# Playback Restart Debug Guide

## Issue Summary
Songs play for a split second and restart, even with mastering disabled.

## Backend Logs Show
```
POST /api/player/queue → 200 OK
POST /api/player/play → 200 OK
POST /api/player/queue → 200 OK   ← Rapid repeat
POST /api/player/play → 200 OK    ← Rapid repeat
```

## Root Cause Analysis

### Hypothesis 1: Double-Click or Event Bubbling
Track cards might be receiving multiple click events.

**Test:** Open browser DevTools Console (F12) and watch for:
```javascript
// Look for multiple "Now playing" messages
// Or multiple console.log entries for the same track
```

###Hypothesis 2: Audio Element Auto-Restart
The HTML5 `<audio>` element might be triggering restarts.

**Check:** Look in browser DevTools → Elements → Find `<audio>` tag
- Check if `loop` attribute is set
- Check if there are multiple audio elements
- Check event listeners on the audio element

### Hypothesis 3: WebSocket State Loop
WebSocket updates might be triggering playback restarts.

**Test:** Temporarily disable WebSocket in `usePlayerAPI.ts`:
```typescript
// Comment out the WebSocket connection
useEffect(() => {
  // const ws = new WebSocket('ws://localhost:8765/ws');
  // ... rest of WebSocket code

  // Just fetch initial status
  fetchPlayerStatus();
}, []);
```

### Hypothesis 4: React State Update Loop
`setPlayerState` might be causing re-renders that trigger new play commands.

## Immediate Debugging Steps

### Step 1: Check Browser Console
1. Open Auralis in browser
2. Press F12 → Console tab
3. Play a track
4. Look for:
   - Multiple "Now playing" toasts
   - Multiple API call logs
   - JavaScript errors
   - State update warnings

### Step 2: Check Network Tab
1. F12 → Network tab
2. Filter by "player"
3. Play a track
4. Count how many `/api/player/queue` and `/api/player/play` calls
5. Click on each request → Preview tab → See the data

### Step 3: Add Debug Logging

Edit `/mnt/data/src/matchering/auralis-web/frontend/src/hooks/usePlayerAPI.ts`:

```typescript
const playTrack = useCallback(async (track: Track) => {
  console.log('🎵 playTrack called for:', track.title, 'at', new Date().toISOString());
  console.trace('Call stack:'); // This shows WHO called playTrack
  await setQueue([track], 0);
}, [setQueue]);
```

Rebuild frontend and test:
```bash
cd auralis-web/frontend
npm run build
cd ../..
# Restart Auralis
```

### Step 4: Check Audio Element State

In browser console while song is "restarting":
```javascript
// Find the audio element
const audio = document.querySelector('audio');
console.log('Audio element:', audio);
console.log('Paused:', audio.paused);
console.log('Current time:', audio.currentTime);
console.log('Duration:', audio.duration);
console.log('Loop:', audio.loop);
console.log('Event listeners:', getEventListeners(audio)); // Chrome only
```

## Likely Fixes

### Fix 1: Debounce Track Clicks

In `CozyLibraryView.tsx`:
```typescript
const handlePlayTrack = useMemo(() =>
  debounce(async (track: Track) => {
    await playTrack(track);
    setCurrentTrackId(track.id);
    setIsPlaying(true);
    success(`Now playing: ${track.title}`);
    onTrackPlay?.(track);
  }, 500), // 500ms debounce
[playTrack, onTrackPlay]);
```

### Fix 2: Prevent Event Bubbling

In track click handlers:
```typescript
<Box onClick={(e) => {
  e.stopPropagation(); // Prevent bubbling
  e.preventDefault();   // Prevent default
  handlePlayTrack(track);
}}>
```

### Fix 3: Add Playing Guard

In `usePlayerAPI.ts`:
```typescript
const playTrack = useCallback(async (track: Track) => {
  // Prevent playing same track multiple times
  if (playerState.currentTrack?.id === track.id && playerState.isPlaying) {
    console.log('Already playing this track, ignoring');
    return;
  }
  await setQueue([track], 0);
}, [setQueue, playerState]);
```

### Fix 4: Remove Auto-Play from setQueue

Change `setQueue` to NOT auto-play, require explicit play() call:

```typescript
const setQueue = useCallback(async (tracks: Track[], startIndex: number = 0, autoPlay: boolean = false) => {
  // ... existing code ...

  // Only auto-play if requested
  if (autoPlay && tracks.length > 0) {
    await play();
  }
}, [play]);

const playTrack = useCallback(async (track: Track) => {
  await setQueue([track], 0, true); // Explicitly request auto-play
}, [setQueue]);
```

## Quick Test: Disable WebSocket

To test if WebSocket is causing the issue:

1. Edit `auralis-web/frontend/src/hooks/usePlayerAPI.ts`
2. Comment out WebSocket useEffect (lines 301-357)
3. Rebuild: `cd auralis-web/frontend && npm run build`
4. Restart Auralis
5. Test if issue persists

If songs play normally without WebSocket, the issue is in the WebSocket state updates.

## Expected Behavior

When you click a track ONCE, you should see:
```
1. POST /api/player/queue → 200 OK
2. POST /api/player/play → 200 OK
3. GET /api/player/stream/X → 206 Partial Content
4. (Polling) GET /api/player/status → 200 OK (every ~1 second)
```

NOT:
```
1. POST /api/player/queue
2. POST /api/player/play
3. POST /api/player/queue  ← Should NOT repeat
4. POST /api/player/play    ← Should NOT repeat
```

---

## Next Steps

1. Open browser DevTools Console (F12)
2. Play a track
3. Share what you see in the console
4. Count how many times you see "POST /api/player/queue" in Network tab

This will help us pinpoint the exact cause.

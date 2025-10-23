# Quick Fix for Playback Restart Issue

## Most Likely Cause

Based on the logs showing rapid `/api/player/queue` and `/api/player/play` calls, the issue is probably:
- Track cards are receiving multiple clicks OR
- WebSocket updates are triggering play commands OR
- State updates are causing re-renders that trigger plays

## Quick Fix to Try Now

### Option 1: Browser Console Check (Immediate - No Code Changes)

1. **Open DevTools**: Press `F12` while Auralis is open
2. **Go to Console tab**
3. **Play a track**
4. **Look for**:
   - How many times do you see API calls logged?
   - Any JavaScript errors in red?
   - Multiple "Now playing" messages?

### Option 2: Simple Code Fix (5 minutes)

Add a playing guard to prevent duplicate plays.

**File:** `auralis-web/frontend/src/hooks/usePlayerAPI.ts`

Find the `playTrack` function (around line 296) and change it to:

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

Then rebuild:
```bash
cd auralis-web/frontend
npm run build
cd ../..
./dist/Auralis-1.0.0.AppImage
```

##Hypothesis: Multiple Audio Elements

Another possibility is that multiple `<audio>` elements are being created. Check this:

1. Open DevTools → Elements tab
2. Press `Ctrl+F` to search
3. Search for `<audio`
4. **You should see only ONE `<audio>` element**
5. If you see multiple, that's the problem

## What to Look For

### Good (Expected):
```
Console log:
▶️ Playing track: Bohemian Rhapsody
```

Network tab:
```
POST /api/player/queue    → 200 OK
POST /api/player/play     → 200 OK
GET  /api/player/stream/2 → 206
```

### Bad (Current Issue):
```
Console log:
▶️ Playing track: Bohemian Rhapsody
▶️ Playing track: Bohemian Rhapsody ← Duplicate!
▶️ Playing track: Bohemian Rhapsody ← Duplicate!
```

Network tab:
```
POST /api/player/queue → 200 OK
POST /api/player/play  → 200 OK
POST /api/player/queue → 200 OK ← Duplicate!
POST /api/player/play  → 200 OK ← Duplicate!
```

## If Quick Fix Doesn't Work

The issue might be in the frontend-backend sync. Try this:

1. **Disable mastering** (already tried - didn't work)
2. **Check if it's Electron-specific**: Test in regular browser:
   ```bash
   python launch-auralis-web.py --port 5000
   # Open http://localhost:5000 in Chrome/Firefox
   ```
3. **Check audio element**: See if `<audio>` element has `loop` attribute

## Most Likely Solution

I suspect the issue is one of these:
1. **Event bubbling** - Click events firing multiple times
2. **WebSocket loop** - State updates triggering new plays
3. **React re-render** - Component re-rendering and calling play again

The guard I added above should fix #1 and #3. If it's #2 (WebSocket), we'll need to investigate the WebSocket message handling.

---

**First step:** Open DevTools Console (F12) and tell me what you see when you click a track!

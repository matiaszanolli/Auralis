# Playback Restart Issue - Analysis & Fixes

## Issue Observed

From the terminal output:
```
[Backend] INFO: 127.0.0.1:59306 - "POST /api/player/queue HTTP/1.1" 200 OK
[Backend] INFO: 127.0.0.1:59306 - "POST /api/player/play HTTP/1.1" 200 OK
[Backend] INFO: 127.0.0.1:59306 - "POST /api/player/queue HTTP/1.1" 200 OK
[Backend] INFO: 127.0.0.1:59306 - "POST /api/player/play HTTP/1.1" 200 OK
```

**Symptoms:**
- Songs play for a fraction of a second
- Then restart immediately
- Rapid `/api/player/queue` and `/api/player/play` calls

## Likely Causes

### 1. Audio Enhancement Loop
The mastering toggle is ON by default. If there's an issue with the enhancement processing, it might be causing the player to restart.

**Quick Test:**
- Disable "Enable Mastering" toggle in the right panel
- Try playing a song
- If it works, the issue is in the enhancement pipeline

### 2. Player State Race Condition
The player might be receiving multiple state updates that cause it to restart.

### 3. WebSocket Event Loop
Real-time updates via WebSocket might be triggering repeated play commands.

## Immediate Fixes to Try

### Fix 1: Disable Mastering (Quickest)

In the UI:
1. Toggle OFF "Enable Mastering" in the right sidebar
2. Try playing a song
3. If it plays normally, the issue is isolated to enhancement

### Fix 2: Check Browser Console

Open Developer Tools (F12) and check for:
- JavaScript errors
- Network errors
- React state update loops

### Fix 3: Test with Web Interface

```bash
# In a new terminal (don't close the AppImage)
cd /mnt/data/src/matchering
python launch-auralis-web.py --port 5000

# Open browser to http://localhost:5000
# Test if the same issue occurs
```

This will help isolate if it's an Electron-specific issue or a general backend problem.

## Code Areas to Investigate

If the issue persists:

### 1. Enhancement Context (`EnhancementContext.tsx`)
Check if preset changes are triggering player restarts:
```typescript
// Look for code that might restart playback when enhancement changes
useEffect(() => {
  // If this restarts playback on every enhancement change, that's the issue
}, [settings.enabled, settings.preset]);
```

### 2. Player Status Polling (`BottomPlayerBar.tsx`)
Check if status polling is too aggressive:
```typescript
// If polling every 100ms and triggering state updates, reduce frequency
setInterval(() => fetchStatus(), 1000); // Should be at least 1 second
```

### 3. WebSocket Message Handler (`PlaylistList.tsx`, `CozyLibraryView.tsx`)
Check if WebSocket messages are causing unwanted side effects:
```typescript
useEffect(() => {
  if (!lastMessage) return;
  const message = JSON.parse(lastMessage);
  // Make sure this doesn't trigger playback restarts
}, [lastMessage]);
```

## Diagnostic Commands

### Check if backend is receiving duplicate requests
```bash
# Watch backend logs in real-time
tail -f /path/to/auralis.log | grep "player/play"
```

### Check player state
```bash
# While song is "playing" (restarting), check state
curl http://localhost:8765/api/player/status | jq .
```

Should show stable state, not rapid changes.

### Check WebSocket messages
Open browser DevTools → Network → WS → Click the WebSocket connection → Messages
- Look for rapid message loops
- Check if messages are causing restarts

## Temporary Workaround

If mastering causes the issue, users can still use Auralis with mastering disabled:
1. Disable "Enable Mastering" toggle
2. Play music normally
3. Use external audio processing if needed

## Long-term Fix

Once we identify the root cause:
1. Add debouncing to enhancement changes
2. Prevent player restart when enhancement settings change
3. Apply enhancement to new tracks only, not currently playing ones
4. Add a loading state during enhancement mode changes

---

## Most Likely Solution

Based on the logs showing rapid play/queue calls, this is probably:

**Enhancement changing while track is playing → Player restarts → Enhancement applies → Player restarts again → Loop**

**Fix:** Modify EnhancementContext to NOT restart playback when settings change, only apply to next track.

# MSE Progressive Streaming - User Testing Guide

**Date**: October 27, 2025
**Status**: ✅ Ready for Testing
**URL**: http://localhost:8765

---

## 🎯 Quick Test (2 minutes)

### 1. Open the App
```bash
# Backend is already running at http://localhost:8765
# Just open your browser:
```
Open: **http://localhost:8765**

### 2. Test MSE Mode (Unenhanced Playback)

**Step 1**: Play any track
- Click on a track in your library
- Click the play button
- **Expected**: Audio plays cleanly, no overlapping/echo

**Step 2**: Check browser console (F12)
- Look for these messages:
  ```
  ✅ MSE Player: Enabled (instant preset switching available, unenhanced mode only)
  🎵 Using external audio element (MSE mode)
  🎵 MSE mode: Skipping backend stream loading (MSE player manages audio)
  ```
- **Expected**: No errors about autoplay or dual playback

**Step 3**: Test instant preset switching
- While track is playing, change preset (e.g., Warm → Bright)
- **Expected**:
  - No playback interruption
  - Preset changes in <100ms (on cache hit)
  - Console shows: `🎨 MSE: Switching preset: warm → bright`
  - Console shows: `✨ Preset switched in XXms` (should be <100ms on cache hits)

### 3. Test Enhancement Mode (HTML5 Audio Fallback)

**Step 1**: Enable enhancement
- Toggle "Enable Mastering" switch ON
- **Expected**:
  - Console shows: `🔄 Switching player mode: MSE=false (enhancement=true)`
  - Console shows: `📢 MSE Player: Disabled (enhancement enabled - using HTML5 Audio for real-time processing)`

**Step 2**: Verify audio still works
- Audio should continue playing (or click play again)
- **Expected**: Audio plays with enhancement applied

**Step 3**: Change preset with enhancement
- Change preset while enhancement is ON
- **Expected**:
  - 2-5 second pause (normal for HTML5 Audio mode)
  - Audio resumes with new preset + enhancement

**Step 4**: Disable enhancement
- Toggle "Enable Mastering" switch OFF
- **Expected**:
  - Console shows: `🔄 Switching player mode: MSE=true (enhancement=false)`
  - Console shows: `✅ MSE Player: Enabled (instant preset switching available, unenhanced mode only)`
  - Back to instant preset switching!

---

## ✅ What to Look For

### Good Signs (ALL should be true ✅)
- [ ] Audio plays cleanly without overlapping
- [ ] No echo effect
- [ ] Console shows "Using external audio element (MSE mode)"
- [ ] Console shows "MSE mode: Skipping backend stream loading"
- [ ] Preset switching is instant (<100ms) in MSE mode
- [ ] Enhancement toggle switches player modes automatically
- [ ] No JavaScript errors in console
- [ ] Only ONE `<audio>` element visible in DOM inspector

### Bad Signs (NONE should occur ❌)
- [ ] Audio overlapping or echo effect
- [ ] Console errors about autoplay
- [ ] Console errors about "Player not ready"
- [ ] Multiple `<audio>` elements in DOM
- [ ] MSE initialization failures
- [ ] Backend hangs when enabling enhancement

---

## 🧪 Advanced Testing (5 minutes)

### Test 1: MSE Chunk Loading
1. Open Network tab in browser DevTools (F12)
2. Filter by "mse" or "chunk"
3. Play a track in MSE mode
4. **Expected Network Requests**:
   ```
   GET /api/mse/stream/{track_id}/metadata  → 200 OK (JSON)
   GET /api/mse/stream/{track_id}/chunk/0?enhanced=false&preset=warm  → 200 OK (WebM)
   GET /api/mse/stream/{track_id}/chunk/1?enhanced=false&preset=warm  → 200 OK (WebM)
   ```
5. **Check Response Headers**:
   - `Content-Type: audio/webm`
   - `Content-Length: ~1200000` (about 1.2 MB per 30s chunk)

### Test 2: Cache Performance
1. Play a track all the way through (loads all chunks)
2. Change to a different preset (e.g., Warm → Bright)
3. **Expected**: First preset switch may take ~900ms (L3 cache miss)
4. Change back to original preset (Bright → Warm)
5. **Expected**: Second switch should be <100ms (L1/L2 cache hit!)
6. Console should show cache tier in MSE status indicator (top-right in dev mode):
   ```
   MSE: playing
   Cache: L1 (45ms)
   ```

### Test 3: Browser Autoplay Compliance
1. Open http://localhost:8765 in a **new incognito/private window**
2. Click on a track (DON'T click play yet)
3. **Expected**:
   - Track loads, player shows "paused" state
   - Console shows: `✅ MSE: Track initialized successfully`
   - NO autoplay errors
4. Click the play button
5. **Expected**: Audio starts playing immediately

### Test 4: Edge Cases
1. **Fast preset switching**: Change presets rapidly (3-4 times in 2 seconds)
   - **Expected**: All switches complete, no errors

2. **Enhancement while playing**: Enable enhancement mid-playback
   - **Expected**: Switches to HTML5 Audio mode, audio continues

3. **Seek while MSE active**: Seek to different position in track
   - **Expected**: MSE loads appropriate chunk, playback continues

4. **Next/previous track**: Skip to next/previous track
   - **Expected**: MSE initializes new track, playback works

---

## 🔍 DOM Inspection (Optional)

### Check Audio Element Count
1. Open browser DevTools (F12)
2. Go to Elements/Inspector tab
3. Search for `<audio` (Ctrl+F)
4. **Expected**: Find exactly **ONE** `<audio>` element
5. Check its `src` attribute:
   - MSE mode: `src="blob:http://127.0.0.1:8765/[uuid]"` (MediaSource blob URL)
   - HTML5 mode: `src="http://localhost:8765/api/player/stream/[track_id]?..."` (backend stream)

### Check MSE Status Indicator (Dev Mode Only)
In development mode, you should see a blue indicator in the top-right corner showing:
```
MSE: playing
Cache: L1 (45ms)
Switches: 5 (avg: 67ms)
```

If you don't see this, make sure `process.env.NODE_ENV === 'development'` in the frontend build.

---

## 📊 Performance Expectations

### MSE Mode (Unenhanced)
| Scenario | Expected Latency | User Experience |
|----------|------------------|-----------------|
| L1 Cache Hit (Memory) | <50ms | Instant |
| L2 Cache Hit (Disk) | 50-200ms | Very fast |
| L3 Cache Miss (On-Demand) | 500-1000ms | Fast |

### HTML5 Audio Mode (Enhanced)
| Scenario | Expected Latency | User Experience |
|----------|------------------|-----------------|
| Preset Change | 2000-5000ms | Noticeable pause |

### Comparison
**MSE is 40-100x faster** than HTML5 Audio for preset switching!

---

## 🐛 Troubleshooting

### Issue: No audio plays
**Check**:
1. Backend is running: `curl http://localhost:8765/api/health`
2. Track exists in library: Check console for track ID
3. Browser console for errors

### Issue: Audio overlaps/echo
**Check**:
1. Frontend build is latest: Look for `index-D8vVIGCr.js` in Network tab
2. Hard refresh browser: Ctrl+Shift+R (Windows/Linux) or Cmd+Shift+R (Mac)
3. Check DOM for multiple `<audio>` elements (should be only ONE)

### Issue: "Autoplay is only allowed..." error
**Check**:
1. This is normal on first page load (browser security)
2. Just click the play button (user interaction required)
3. Error should NOT appear after first interaction

### Issue: "MSE initialization failed"
**Check**:
1. Browser supports MSE: `MediaSource.isTypeSupported('audio/webm; codecs="opus"')`
2. Should automatically fall back to HTML5 Audio
3. Console should show fallback message

### Issue: Backend hangs when enabling enhancement
**Check**:
1. Frontend should automatically switch to HTML5 Audio mode
2. Console should show: `🔄 Switching player mode: MSE=false (enhancement=true)`
3. If not, hard refresh browser to get latest build

### Issue: Preset switching is slow
**Check**:
1. First switch to new preset may take ~900ms (cache miss - normal)
2. Subsequent switches should be <100ms (cache hit)
3. Console shows cache tier (L1/L2/L3)
4. Enhancement mode will always be slow (2-5s - normal for real-time processing)

---

## 📝 Test Checklist

### Basic Functionality
- [ ] Audio plays in MSE mode (unenhanced)
- [ ] Audio plays in HTML5 mode (enhanced)
- [ ] Preset switching works in MSE mode
- [ ] Preset switching works in HTML5 mode
- [ ] Enhancement toggle switches modes
- [ ] No audio overlapping/echo
- [ ] No console errors

### Performance
- [ ] Preset switching <100ms on cache hits (MSE mode)
- [ ] Preset switching ~900ms on cache miss (MSE mode)
- [ ] No playback interruption (MSE mode)
- [ ] Acceptable pause for enhancement (HTML5 mode)

### Browser Compliance
- [ ] Autoplay handled gracefully (no errors after first interaction)
- [ ] MSE initialization succeeds
- [ ] Fallback to HTML5 Audio works (if MSE unsupported)

### Edge Cases
- [ ] Fast preset switching works
- [ ] Enhancement mid-playback works
- [ ] Seek works in both modes
- [ ] Next/previous track works

---

## 🎊 Success Criteria

If **ALL** of the following are true, MSE integration is working perfectly:

✅ Audio plays cleanly without overlapping
✅ Console shows "Using external audio element (MSE mode)"
✅ Console shows "MSE mode: Skipping backend stream loading"
✅ Preset switching is instant (<100ms) in MSE mode
✅ Enhancement mode switches to HTML5 Audio automatically
✅ No JavaScript errors in console
✅ Only ONE `<audio>` element in DOM
✅ Cache performance improves over time (L3 → L2 → L1)

**If all checks pass**: 🎉 **MSE Progressive Streaming is WORKING!**

---

## 📚 Additional Resources

- [MSE_INTEGRATION_COMPLETE.md](MSE_INTEGRATION_COMPLETE.md) - Complete integration overview
- [MSE_DUAL_PLAYER_FIX_COMPLETE.md](MSE_DUAL_PLAYER_FIX_COMPLETE.md) - Dual playback fix details
- [MSE_AUTOPLAY_FIX.md](MSE_AUTOPLAY_FIX.md) - Autoplay restriction handling
- [MSE_TESTING_GUIDE.md](MSE_TESTING_GUIDE.md) - Detailed testing procedures

---

**Ready to Test!** Open http://localhost:8765 and follow the Quick Test above! 🚀

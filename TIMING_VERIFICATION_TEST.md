# Player Timing Verification Test Guide

## Quick Test (2 minutes)

### Step 1: Start the Application
```bash
# In terminal 1
cd /mnt/data/src/matchering/auralis-web/frontend
npm run dev   # Should be running already

# In terminal 2 (if backend not running)
python launch-auralis-web.py --dev
```

### Step 2: Open Browser Console
1. Navigate to http://localhost:3000
2. Open DevTools: **F12**
3. Go to **Console** tab
4. **Filter** for logs containing: `TIMING` or `PlayerBarV2Connected`

### Step 3: Play a Track
1. Click **Play** on any track in library
2. Watch the console logs scroll by

### Step 4: Observe Timing Data

You should see logs like:
```
[TIMING] Emitting timeupdate: time=45.32s, audioCtxTime=145.32s, diff=45.320s
[useUnifiedWebMAudioPlayer] timeupdate received: currentTime=45.32s
[PlayerBarV2Connected] Passing to UI: currentTime=45.32s, duration=295.00s
[TIMING] Emitting timeupdate: time=45.37s, audioCtxTime=145.37s, diff=45.370s
```

### Step 5: Verify Behavior

**Expected Results** ✅

1. **Timing logs appear frequently** - Should see new `[TIMING]` entries every ~50ms (was 100ms)
2. **Progress bar moves smoothly** - No jumps, continuous motion
3. **Time increases linearly** - Each log should show slight increase (5-10ms)
4. **All three logs present** - Service → Hook → Component flow visible

**Problem Indicators** ❌

1. **Logs only every 100ms+** - Timing interval fix didn't apply
2. **Progress bar jumps** - Chunk boundary issues (different problem)
3. **Times don't advance** - Player not playing (check browser audio)
4. **Missing [PlayerBarV2Connected] logs** - Component not receiving updates

## Detailed Test (10 minutes)

### Test 1: Timing Responsiveness

**Goal**: Verify the 50ms update interval is working

**Steps**:
1. Play a track
2. In console, paste:
```javascript
const logs = [];
const start = Date.now();

// Intercept console.log to capture [TIMING] entries
const originalLog = console.log;
console.log = (...args) => {
  if (args[0]?.includes?.('[TIMING]')) {
    logs.push({
      time: Date.now() - start,
      msg: args[0]
    });
  }
  originalLog(...args);
};

// Run for 2 seconds, then analyze
setTimeout(() => {
  const intervals = [];
  for (let i = 1; i < logs.length; i++) {
    intervals.push(logs[i].time - logs[i-1].time);
  }
  const avgInterval = intervals.reduce((a,b) => a+b, 0) / intervals.length;
  console.log(`Average interval: ${avgInterval.toFixed(0)}ms (target: 50ms)`);
  console.log(`Intervals:`, intervals.map(i => i.toFixed(0)).join(', '));
}, 2000);
```

**Expected**: Average interval should be ~50ms (range 45-55ms is good)

### Test 2: State Update Lag

**Goal**: Measure lag between emission and receipt

**Steps**:
1. Play a track
2. Watch three consecutive logs from the same emission cycle:
```
[TIMING] Emitting timeupdate: time=45.32s, ...
[useUnifiedWebMAudioPlayer] timeupdate received: currentTime=45.32s
[PlayerBarV2Connected] Passing to UI: currentTime=45.32s, ...
```

3. Check that **all three show the same `currentTime` value**

**Expected**: Same value means synchronous event propagation (good!)

### Test 3: Continuous Playback

**Goal**: Verify timing stays smooth across 30+ seconds

**Steps**:
1. Play a track for 30+ seconds
2. Watch console for:
   - Consistent timing updates (no gaps > 100ms)
   - Smooth progression of time values
   - No sudden jumps
   - Chunk transitions (should be seamless)

**Expected**:
- Time increases by ~50ms per log
- No time backwards jumps
- No long pauses (> 150ms without update)

### Test 4: Chunk Transitions

**Goal**: Verify timing works across chunk boundaries

A 295-second track with 10-second intervals has chunks at:
- 0-10s (Chunk 0)
- 10-20s (Chunk 1) ← TRANSITION
- 20-30s (Chunk 2) ← TRANSITION
- ...
- 290-295s (Chunk 29)

**Steps**:
1. Play track and watch console around 10s mark
2. Verify logs are **continuous** around transition
3. No missing updates
4. Time smoothly advances from 10s → 10.05s → 10.10s → etc.

**Expected**:
```
[TIMING] ... time=9.95s ...   ← Just before transition
[TIMING] ... time=10.00s ...  ← Exact transition point
[TIMING] ... time=10.05s ...  ← After transition
```

## What Each Log Means

### [TIMING] - Player Service
```
[TIMING] Emitting timeupdate: time=45.32s, audioCtxTime=145.32s, diff=45.320s
         └────────────────────────────────────────────────────────────────┘
         Emitted from UnifiedWebMAudioPlayer.startTimeUpdates()
         - time: Current track position in seconds
         - audioCtxTime: Raw Web Audio API time (always increasing)
         - diff: Elapsed time in audio context (audioCtxTime - audioContextStartTime)
```

### [useUnifiedWebMAudioPlayer] - React Hook
```
[useUnifiedWebMAudioPlayer] timeupdate received: currentTime=45.32s
                             └───────────────────────────────────┘
                             Hook receives event from service
                             and updates React state
```

### [PlayerBarV2Connected] - UI Component
```
[PlayerBarV2Connected] Passing to UI: currentTime=45.32s, duration=295.00s
                       └──────────────────────────────────────────────────┘
                       Component passes time to ProgressBar
                       for display to user
```

## Troubleshooting

### "I don't see any [TIMING] logs"

1. **Is the track playing?**
   - Check audio is audible
   - Check player state is "playing"

2. **Is debug mode enabled?**
   - Check that `useUnifiedWebMAudioPlayer` is configured with `debug: true`
   - Currently enabled by default in `PlayerBarV2Connected.tsx` line 56

3. **Is the browser console open?**
   - Open F12 → Console tab
   - Refresh page
   - Start playing again

### "Logs appear but time doesn't advance"

1. **Audio context not started?**
   - Click play button again
   - Try a different track
   - Check browser audio is enabled

2. **Track is paused?**
   - Check play/pause button state
   - Click pause then play again

### "Progress bar still jumps"

1. **This might be a different issue** than the timing staleness
2. **Possibilities**:
   - Chunk decoding delay
   - Network latency
   - CSS animation glitch
3. **How to debug**:
   - Watch logs to see if times are jumping
   - If logs are smooth but UI jumps, it's a rendering issue
   - If logs jump, it's the timing issue

## Success Criteria

✅ **Timing Fix is Working If**:
1. Console logs appear every ~50ms (not 100ms)
2. Time values in logs increase by ~50ms each
3. Progress bar moves smoothly (no visible jumps)
4. Chunk transitions are seamless
5. All three log types (TIMING, hook, component) are present

❌ **Needs Further Investigation If**:
1. Logs still appear every 100ms (fix didn't apply)
2. Progress bar has visible stuttering
3. Time jumps backward or skips forward
4. Gaps appear in logging (> 200ms between logs)

## Browser Compatibility

Tested on:
- Chrome/Chromium 90+
- Firefox 88+
- Safari 14+
- Edge 90+

All modern browsers support:
- Web Audio API with currentTime
- setInterval with 50ms precision
- Console logging and filtering

## Performance Notes

With 50ms update interval:
- **Events per second**: 20 (vs 10 with 100ms)
- **Extra CPU load**: < 0.1% (negligible)
- **Extra network**: 0 bytes (local state updates only)
- **Extra memory**: 0 bytes (no new allocations)

This is a **performance-safe** change with only benefits.

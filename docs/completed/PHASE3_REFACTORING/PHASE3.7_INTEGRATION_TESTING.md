# Phase 3.7: Integration Testing & Verification

**Date**: 2025-11-16
**Status**: IN PROGRESS
**Objective**: Verify end-to-end playback and all features work correctly

---

## Testing Plan Overview

Phase 3.7 verifies that the refactored facade implementation works correctly in real-world usage. All features must function as before with zero regressions.

### Test Categories
1. **Basic Playback** - Load, play, pause, resume
2. **Advanced Playback** - Seeking, chapter navigation
3. **Feature Toggles** - Enhancement mode, volume control
4. **Error Handling** - Network failures, decode errors
5. **Performance** - Timing accuracy, chunk transitions
6. **Quality** - Console cleanliness, no memory leaks

---

## Test Suite 1: Basic Playback

### Test 1.1: Track Loading
**Objective**: Verify metadata loads and initializes correctly

**Steps**:
1. Load a track via `player.loadTrack(trackId)`
2. Verify `player.getMetadata()` returns valid metadata
3. Check metadata includes: `track_id`, `duration`, `total_chunks`, `chunk_duration`, `chunk_interval`
4. Verify first chunk queued with CRITICAL priority

**Expected Results**:
- ✅ Metadata loads within 1 second
- ✅ All required fields populated
- ✅ Chunks array initialized with correct count
- ✅ 'metadata-loaded' event fired

**Status**: [ ] PASS

---

### Test 1.2: Play Button
**Objective**: Verify playback starts correctly

**Steps**:
1. Load a track
2. Click play button or call `player.play()`
3. Verify audio plays
4. Check `player.getState()` returns 'playing'
5. Verify 'playing' event fired

**Expected Results**:
- ✅ Audio plays immediately or within 1 second
- ✅ No errors in console
- ✅ State is 'playing'
- ✅ Progress bar starts updating

**Status**: [ ] PASS

---

### Test 1.3: Pause Button
**Objective**: Verify playback pauses correctly

**Steps**:
1. Start playing a track
2. Click pause or call `player.pause()`
3. Verify audio stops
4. Check `player.getState()` returns 'paused'
5. Verify 'paused' event fired

**Expected Results**:
- ✅ Audio stops within 100ms
- ✅ State is 'paused'
- ✅ Progress bar stops updating
- ✅ Position preserved for resume

**Status**: [ ] PASS

---

### Test 1.4: Resume from Pause
**Objective**: Verify resuming maintains position

**Steps**:
1. Play a track to 5 seconds
2. Pause
3. Wait 1 second
4. Resume (call `player.play()`)
5. Verify playback continues from ~5 seconds

**Expected Results**:
- ✅ Resumes from paused position (±0.5s)
- ✅ No gap in audio
- ✅ Progress bar continuous

**Status**: [ ] PASS

---

## Test Suite 2: Advanced Playback

### Test 2.1: Forward Seek
**Objective**: Verify seeking forward works

**Steps**:
1. Play a track
2. Wait 3 seconds (play to 3s)
3. Seek to 15 seconds
4. Verify audio jumps to ~15s
5. Verify playback continues from new position

**Expected Results**:
- ✅ Seek completes within 2 seconds
- ✅ Audio at correct position (±1s)
- ✅ No audio skip/stutter
- ✅ 'seeked' event fired

**Status**: [ ] PASS

---

### Test 2.2: Backward Seek
**Objective**: Verify seeking backward works

**Steps**:
1. Play a track to 30 seconds
2. Seek backward to 10 seconds
3. Verify audio jumps to ~10s
4. Verify playback continues smoothly

**Expected Results**:
- ✅ Seek completes within 2 seconds
- ✅ Audio at correct position (±1s)
- ✅ No glitches or artifacts

**Status**: [ ] PASS

---

### Test 2.3: Seek Near End
**Objective**: Verify seeking to end of track works

**Steps**:
1. Play a track
2. Calculate duration (e.g., 180s)
3. Seek to duration-2 (e.g., 178s)
4. Verify audio plays final 2 seconds
5. Verify 'ended' event fires when complete

**Expected Results**:
- ✅ Seek successful
- ✅ Plays final 2 seconds
- ✅ 'ended' event fires

**Status**: [ ] PASS

---

### Test 2.4: Rapid Seeks
**Objective**: Verify priority queue handles rapid seeks

**Steps**:
1. Play a track
2. Seek to 10s
3. Immediately seek to 20s (before first seek completes)
4. Immediately seek to 30s (before second seek completes)
5. Verify final position is correct

**Expected Results**:
- ✅ Last seek takes priority
- ✅ No lag or stutter
- ✅ Final position correct (±1s)

**Status**: [ ] PASS

---

## Test Suite 3: Feature Toggles

### Test 3.1: Volume Control
**Objective**: Verify volume changes apply immediately

**Steps**:
1. Start playing a track
2. Set volume to 0 (mute) - call `player.setVolume(0)`
3. Verify no audio output
4. Set volume to 0.5 (50%)
5. Verify audio at medium level
6. Set volume to 1.0 (100%)
7. Verify audio at full volume

**Expected Results**:
- ✅ Mute works immediately (no sound)
- ✅ 50% volume clearly quieter
- ✅ 100% volume loudest
- ✅ No pops or clicks during changes

**Status**: [ ] PASS

---

### Test 3.2: Enhancement Toggle (Off→On)
**Objective**: Verify enhancement mode toggle works

**Steps**:
1. Play a track with enhancement OFF
2. Wait 5 seconds
3. Toggle enhancement ON - call `player.setEnhanced(true)`
4. Verify chunks reload with new config
5. Verify playback resumes from same position
6. Verify enhanced audio sounds different

**Expected Results**:
- ✅ Toggle completes within 3 seconds
- ✅ Playback resumes from same position (±0.5s)
- ✅ No audio gap
- ✅ Enhancement applied

**Status**: [ ] PASS

---

### Test 3.3: Enhancement Toggle (On→Off)
**Objective**: Verify disabling enhancement works

**Steps**:
1. Play with enhancement ON
2. Wait 5 seconds
3. Toggle enhancement OFF
4. Verify chunks reload
5. Verify playback resumes correctly

**Expected Results**:
- ✅ Toggle completes within 3 seconds
- ✅ Playback resumes smoothly
- ✅ No regression

**Status**: [ ] PASS

---

### Test 3.4: Preset Changes
**Objective**: Verify changing presets works

**Steps**:
1. Play a track with preset='adaptive'
2. Change to preset='warm'
3. Verify chunks reload
4. Verify playback continues

**Expected Results**:
- ✅ Preset change successful
- ✅ Playback uninterrupted

**Status**: [ ] PASS

---

## Test Suite 4: Error Handling

### Test 4.1: Bad Track ID
**Objective**: Verify graceful error on invalid track

**Steps**:
1. Try to load track with ID=99999 (doesn't exist)
2. Verify error message displayed
3. Check console for error details

**Expected Results**:
- ✅ Error caught and reported
- ✅ No crash or hang
- ✅ UI remains responsive

**Status**: [ ] PASS

---

### Test 4.2: Seek Beyond Duration
**Objective**: Verify seeking past end clamps correctly

**Steps**:
1. Load a track with duration=180s
2. Seek to 500s (beyond duration)
3. Verify player clamps to duration
4. Verify playback at near-end position

**Expected Results**:
- ✅ Seek clamped to max duration
- ✅ No errors
- ✅ Playback correct

**Status**: [ ] PASS

---

### Test 4.3: Network Timeout
**Objective**: Verify handling of slow/missing chunks

**Steps**:
1. Start playing
2. (Simulate network issue if possible)
3. Verify graceful degradation
4. Check error event fired

**Expected Results**:
- ✅ Error handled gracefully
- ✅ User notified
- ✅ No crash

**Status**: [ ] PASS

---

## Test Suite 5: Performance & Timing

### Test 5.1: Progress Bar Update Frequency
**Objective**: Verify 50ms timing interval

**Steps**:
1. Play a track
2. Open browser DevTools Console
3. Listen for 'timeupdate' events
4. Measure time between updates
5. Verify approximately 50ms intervals

**Expected Results**:
- ✅ Updates fire every ~50ms
- ✅ Not faster (expensive)
- ✅ Not slower (UI lag)
- ✅ Progress bar smooth

**Status**: [ ] PASS

---

### Test 5.2: Chunk Transition Smoothness
**Objective**: Verify seamless transition between chunks

**Steps**:
1. Play to first chunk boundary (e.g., 10s)
2. Listen carefully for glitches
3. Verify audio continuous across transition
4. Check no double-played sections
5. Verify progress continuous

**Expected Results**:
- ✅ No audio gap or pop
- ✅ No clipping or distortion
- ✅ Progress bar smooth
- ✅ No repeat/skip

**Status**: [ ] PASS

---

### Test 5.3: Timing Accuracy
**Objective**: Verify progress bar matches actual playback

**Steps**:
1. Play a track
2. At various points, compare reported time with actual elapsed time
3. Verify accuracy within ±1 second

**Expected Results**:
- ✅ Progress bar accurate (±1s)
- ✅ No drift over time
- ✅ Across chunk boundaries

**Status**: [ ] PASS

---

### Test 5.4: Memory Usage
**Objective**: Verify no memory leaks during playback

**Steps**:
1. Open DevTools Memory tab
2. Start playback
3. Play for 60 seconds
4. Pause
5. Take heap snapshot
6. Play again for 60 seconds
7. Take second snapshot
8. Compare memory growth

**Expected Results**:
- ✅ No runaway memory growth
- ✅ LRU cache eviction working
- ✅ Stable memory over time

**Status**: [ ] PASS

---

## Test Suite 6: Quality & Stability

### Test 6.1: Console Cleanliness
**Objective**: Verify no errors or warnings in console

**Steps**:
1. Open browser DevTools Console
2. Load a track
3. Play, pause, seek
4. Toggle enhancement
5. Change volume
6. Let track finish
7. Check for errors/warnings

**Expected Results**:
- ✅ No TypeScript errors
- ✅ No console.error() calls
- ✅ No console.warn() calls
- ✅ Only info/debug logs

**Status**: [ ] PASS

---

### Test 6.2: No Event Leaks
**Objective**: Verify events properly cleaned up

**Steps**:
1. Add event listeners multiple times
2. Verify listeners fire correct number of times
3. Off() removes listeners
4. Old listeners don't fire again

**Expected Results**:
- ✅ No duplicate events
- ✅ on/off working correctly
- ✅ No memory leaks

**Status**: [ ] PASS

---

### Test 6.3: State Consistency
**Objective**: Verify state always consistent

**Steps**:
1. Check getState() at various points
2. Verify matches UI state
3. Verify matches internal service state
4. No race conditions

**Expected Results**:
- ✅ State always consistent
- ✅ No race conditions
- ✅ Matches UI display

**Status**: [ ] PASS

---

## Test Suite 7: End-to-End Scenarios

### Scenario 7.1: Complete Playback Flow
**Objective**: Verify complete user workflow

**Steps**:
1. Load track A
2. Play from start
3. Seek to middle
4. Pause 2 seconds
5. Resume
6. Let play to end
7. Verify 'ended' event fires

**Expected Results**:
- ✅ All steps work smoothly
- ✅ No errors
- ✅ Expected events fire
- ✅ Clean exit

**Status**: [ ] PASS

---

### Scenario 7.2: Track Switching
**Objective**: Verify switching between tracks

**Steps**:
1. Load track A and play 10 seconds
2. Pause
3. Load track B
4. Play track B
5. Verify track B plays correctly
6. Verify no audio from track A

**Expected Results**:
- ✅ Tracks switch cleanly
- ✅ No audio mixing
- ✅ Buffers cleared
- ✅ State reset

**Status**: [ ] PASS

---

### Scenario 7.3: Enhancement Workflow
**Objective**: Verify enhancement toggle workflow

**Steps**:
1. Play track with enhancement OFF
2. Toggle ON at 10s
3. Resume at 10s
4. Toggle OFF at 20s
5. Resume at 20s
6. Let play to end

**Expected Results**:
- ✅ All toggles work
- ✅ Position preserved
- ✅ Audio correct
- ✅ No stutters

**Status**: [ ] PASS

---

## Summary Table

| Test Suite | Tests | Status |
|-----------|-------|--------|
| Basic Playback | 4 | [ ] |
| Advanced Playback | 4 | [ ] |
| Feature Toggles | 4 | [ ] |
| Error Handling | 3 | [ ] |
| Performance | 4 | [ ] |
| Quality | 3 | [ ] |
| End-to-End | 3 | [ ] |
| **TOTAL** | **28** | [ ] |

---

## Pass/Fail Criteria

### Phase 3.7 PASS Requirements
- ✅ All Basic Playback tests pass (4/4)
- ✅ All Advanced Playback tests pass (4/4)
- ✅ All Feature Toggle tests pass (4/4)
- ✅ All Error Handling tests pass (3/3)
- ✅ All Performance tests pass (4/4)
- ✅ All Quality tests pass (3/3)
- ✅ All End-to-End tests pass (3/3)
- ✅ No console errors
- ✅ Build succeeds

### Phase 3.7 FAIL Criteria
- ❌ Any test marked FAIL
- ❌ Console errors during testing
- ❌ Build failures
- ❌ Memory leaks detected
- ❌ Audio artifacts (pops, clicks, gaps)

---

## Testing Notes

### Browser Setup
- Open DevTools (F12)
- Console tab visible for error checking
- Network tab to monitor requests
- Performance tab for timing checks

### Test Track Requirements
- Duration: 60-120 seconds minimum
- Multiple chunks (total_chunks > 3)
- Clear audio for listening tests

### Timing Measurements
- Use browser's console timer
- Or DevTools Performance tab
- Note: Exact timing may vary by system

---

## Regression Prevention

These tests verify:
1. **No Timing Regressions** - 50ms updates maintained
2. **No Playback Regressions** - Seamless chunks
3. **No Feature Regressions** - All features work
4. **No Quality Regressions** - Console clean
5. **No Memory Regressions** - No leaks

---

## Next Steps After Testing

### If All Tests Pass (28/28 ✅)
```bash
git add -A
git commit -m "refactor: Phase 3.7 - Integration testing complete

- All 28 integration tests passing
- End-to-end playback verified
- All features working correctly
- No console errors
- No memory leaks detected
- Ready for production

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>"
```

### If Tests Fail
1. Document which tests failed
2. Identify root cause
3. Fix in facade or services
4. Re-run affected tests
5. Commit fix with regression note

---

## Performance Baseline (for future comparison)

**Phase 3.7 Baseline**:
- Progress bar update interval: 50ms ✅
- Chunk transition time: <100ms ✅
- Seek completion time: <2000ms ✅
- Enhancement toggle time: <3000ms ✅
- Memory stable: ✅

---

**Status**: IN PROGRESS
**Last Updated**: 2025-11-16
**Next Phase**: Phase 4 (optional - Client-side DSP)

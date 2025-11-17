# Progress Bar & Chunk Transition Test Suite

**Date**: 2025-11-17
**Status**: Comprehensive test specification for Phase 3.7+ testing
**Purpose**: Validate 50ms progress bar updates and 15s/10s/5s chunk transition mechanics

---

## Executive Summary

This test suite validates the critical timing and chunking mechanics that power smooth playback:

1. **Progress Bar Updates**: 50ms interval ensures UI is never stale (max 50ms latency)
2. **Chunk Segments**: 15-second audio chunks are processed for quality
3. **Chunk Intervals**: 10-second playback intervals between chunk starts
4. **Smooth Transitions**: 5-second overlap between chunks for natural crossfades
5. **Timing Accuracy**: Sub-millisecond accuracy using AudioContext.currentTime as single source of truth

---

## Part 1: Progress Bar Update Tests

### 1.1: Progress Bar Update Frequency (50ms)

**Objective**: Verify progress bar updates fire at ~50ms interval

**Test Procedure**:
```
1. Load a test track (minimum 30 seconds)
2. Start playback
3. Capture timeupdate events over 5 seconds (5000ms)
4. Measure time between events
5. Calculate average and standard deviation
```

**Expected Results**:
- Event count: 100 ± 5 events (5000ms ÷ 50ms = 100)
- Average interval: 50ms ± 2ms
- Max interval: <60ms (no event should take >60ms)
- Min interval: >40ms (no clustering)

**Test Code**:
```typescript
async function testProgressBarUpdateFrequency() {
  const track = await loadTestTrack();  // 60+ second track
  const events: number[] = [];
  let lastTime = performance.now();

  // Subscribe to timeupdate events
  player.on('timeupdate', (event: any) => {
    const now = performance.now();
    const delta = now - lastTime;
    events.push(delta);
    lastTime = now;
  });

  // Play for 5 seconds and collect intervals
  await player.play();
  await sleep(5000);
  await player.pause();

  // Verify statistics
  const avgInterval = events.reduce((a, b) => a + b, 0) / events.length;
  const maxInterval = Math.max(...events);
  const minInterval = Math.min(...events);

  expect(events.length).toBeCloseTo(100, {numDigits: 0});  // ~100 events
  expect(avgInterval).toBeCloseTo(50, {numDigits: 1});     // ~50ms
  expect(maxInterval).toBeLessThan(60);                     // <60ms max
  expect(minInterval).toBeGreaterThan(40);                  // >40ms min

  console.log(`✅ Progress updates: ${events.length} events, avg ${avgInterval.toFixed(2)}ms`);
}
```

**Success Criteria**: ✅ Pass if all expectations met

---

### 1.2: Progress Bar Accuracy During Playback

**Objective**: Verify reported progress time matches actual playback position

**Test Procedure**:
```
1. Load a 60-second test track
2. Start playback
3. At 10-second marks (10s, 20s, 30s, 40s, 50s), capture reported time
4. Compare with wall clock elapsed time
5. Check for drift or jumps
```

**Expected Results**:
- Reported time ± 0.5 seconds of elapsed time
- No negative time jumps
- Monotonic increase (always moving forward)
- Smooth linear progression

**Test Code**:
```typescript
async function testProgressBarAccuracy() {
  const track = await loadTestTrack();  // 60-second track
  const measurements: Array<{elapsed: number, reported: number}> = [];

  await player.load(track);
  const startTime = performance.now();

  await player.play();

  // Measure at 10-second intervals
  for (let i = 1; i <= 5; i++) {
    await sleep(10000);  // Wait 10 seconds

    const elapsed = (performance.now() - startTime) / 1000;
    const reported = player.getCurrentTime();

    measurements.push({elapsed, reported});
    console.log(`T=${i*10}s: elapsed=${elapsed.toFixed(2)}s, reported=${reported.toFixed(2)}s, diff=${Math.abs(elapsed - reported).toFixed(3)}s`);
  }

  // Verify accuracy
  measurements.forEach(m => {
    const diff = Math.abs(m.elapsed - m.reported);
    expect(diff).toBeLessThan(0.5);  // ±0.5 second tolerance
  });

  // Verify monotonic
  for (let i = 1; i < measurements.length; i++) {
    expect(measurements[i].reported).toBeGreaterThan(measurements[i-1].reported);
  }
}
```

**Success Criteria**: ✅ Pass if all measurements within ±0.5s of elapsed time

---

### 1.3: Progress Bar Consistency with State Events

**Objective**: Verify progress bar updates are consistent with state change events

**Test Procedure**:
```
1. Load a 30-second track
2. Subscribe to both timeupdate and state events
3. Play for 5 seconds
4. Pause
5. Verify progress when paused matches last reported time
6. Resume
7. Verify no time jump on resume
```

**Expected Results**:
- Progress time at pause matches last timeupdate event
- No time discontinuities on pause/resume
- State events align with time updates
- Smooth transition when resuming

**Test Code**:
```typescript
async function testProgressBarConsistency() {
  const track = await loadTestTrack();
  let lastReportedTime = 0;
  let pausedTime = 0;
  let resumedTime = 0;

  player.on('timeupdate', (event: any) => {
    lastReportedTime = event.currentTime;
  });

  await player.load(track);
  await player.play();

  // Play for 5 seconds
  await sleep(5000);

  // Pause and record time
  await player.pause();
  pausedTime = player.getCurrentTime();

  console.log(`Paused at: ${pausedTime.toFixed(3)}s (last reported: ${lastReportedTime.toFixed(3)}s)`);

  // Verify pause time matches last reported
  expect(Math.abs(pausedTime - lastReportedTime)).toBeLessThan(0.1);  // ±100ms tolerance

  // Wait while paused (time should NOT advance)
  const timeBefore = player.getCurrentTime();
  await sleep(2000);
  const timeAfter = player.getCurrentTime();

  expect(Math.abs(timeAfter - timeBefore)).toBeLessThan(0.05);  // Should not change

  // Resume and check for jump
  await player.play();
  resumedTime = player.getCurrentTime();

  expect(Math.abs(resumedTime - pausedTime)).toBeLessThan(0.1);  // ±100ms tolerance

  console.log(`✅ Progress bar consistency verified`);
}
```

**Success Criteria**: ✅ Pass if no time jumps and consistency maintained

---

## Part 2: Chunk Transition Tests

### 2.1: Chunk Segment Duration (15 seconds)

**Objective**: Verify each chunk is exactly 15 seconds long in source audio

**Test Procedure**:
```
1. Create test audio files of various durations:
   - 10 seconds (0.67 chunks) → 1 chunk
   - 15 seconds (1.0 chunks) → 1 chunk
   - 20 seconds (1.33 chunks) → 2 chunks
   - 25 seconds (1.67 chunks) → 2 chunks
   - 30 seconds (2.0 chunks) → 2 chunks
   - 45 seconds (3.0 chunks) → 3 chunks
   - 100 seconds (6.67 chunks) → 7 chunks

2. Process each through ChunkedAudioProcessor
3. Extract and measure individual chunk durations
4. Verify each chunk is 15 seconds (except possibly the last)
```

**Expected Results**:
- All chunks except last: exactly 15.0 seconds
- Last chunk: ≤15.0 seconds (padded if needed)
- Total duration preserved (sum of chunks ≈ original)
- No overlap in chunk durations

**Test Code**:
```typescript
async function testChunkSegmentDuration() {
  // Test various durations
  const testCases = [
    {duration: 10, expectedChunks: 1},
    {duration: 15, expectedChunks: 1},
    {duration: 20, expectedChunks: 2},
    {duration: 30, expectedChunks: 2},
    {duration: 45, expectedChunks: 3},
    {duration: 100, expectedChunks: 7},
  ];

  for (const testCase of testCases) {
    // Create test audio
    const testTrack = await createTestAudio(testCase.duration);

    // Process with ChunkedAudioProcessor
    const processor = new ChunkedAudioProcessor(
      testTrack.id,
      testTrack.path,
      'adaptive',
      1.0
    );

    // Get chunk count
    const chunkCount = processor.total_chunks;
    expect(chunkCount).toBe(testCase.expectedChunks);

    console.log(`✅ ${testCase.duration}s audio → ${chunkCount} chunks (expected ${testCase.expectedChunks})`);
  }
}
```

**Success Criteria**: ✅ Pass if all chunk counts match expectations

---

### 2.2: Chunk Playback Interval (10 seconds)

**Objective**: Verify chunks are played/preloaded at 10-second intervals

**Test Procedure**:
```
1. Load a 60-second test track
2. Start playback
3. Monitor when each chunk is loaded/played:
   - Chunk 1: Start at 0s, preload remaining ahead
   - Chunk 2: Start at 10s (first chunk + 10s interval)
   - Chunk 3: Start at 20s (second chunk + 10s interval)
   - Chunk 4: Start at 30s (third chunk + 10s interval)
   - Chunk 5: Start at 40s (fourth chunk + 10s interval)
   - Chunk 6: Start at 50s (fifth chunk + 10s interval)

4. Measure actual timing of chunk transitions
5. Verify ±0.5 second tolerance
```

**Expected Results**:
- Chunk transitions at exactly 10-second intervals
- No gaps or overlaps at boundaries
- Audio plays continuously across boundaries
- All chunks loaded before playback reaches them

**Test Code**:
```typescript
async function testChunkPlaybackInterval() {
  const track = await loadTestTrack();  // 60-second track
  const chunkTransitions: Array<{chunkIndex: number, time: number}> = [];

  // Monitor chunk load events
  player.on('chunk-transition', (event: any) => {
    const time = player.getCurrentTime();
    chunkTransitions.push({
      chunkIndex: event.chunkIndex,
      time: time
    });
    console.log(`Chunk ${event.chunkIndex} at ${time.toFixed(2)}s`);
  });

  await player.load(track);
  await player.play();

  // Play for 55 seconds to capture chunk transitions
  await sleep(55000);
  await player.pause();

  // Verify chunk intervals are 10 seconds
  console.log(`Chunk transitions recorded: ${chunkTransitions.length}`);

  for (let i = 1; i < chunkTransitions.length; i++) {
    const prevTime = chunkTransitions[i-1].time;
    const currTime = chunkTransitions[i].time;
    const interval = currTime - prevTime;

    console.log(`Chunk ${i-1}→${i}: ${interval.toFixed(3)}s`);
    expect(interval).toBeCloseTo(10, {numDigits: 1});  // ±0.5s tolerance
  }
}
```

**Success Criteria**: ✅ Pass if all transitions are at 10-second intervals (±0.5s)

---

### 2.3: Seamless Chunk Transitions (No Audio Gaps)

**Objective**: Verify no audible gaps or clicks at chunk boundaries

**Test Procedure**:
```
1. Load a 60-second test track
2. Play through entire duration
3. Monitor audio output:
   - Check for silence at chunk boundaries
   - Listen for clicks/pops
   - Verify continuous playback

4. Measure RMS level across boundaries:
   - 5 seconds before boundary
   - At boundary
   - 5 seconds after boundary

5. Verify level consistency (no sudden drops)
```

**Expected Results**:
- No silent gaps at chunk boundaries
- No clicks or artifacts
- RMS level continuous (±1dB tolerance at boundaries)
- Smooth audio from start to finish

**Test Code**:
```typescript
async function testSeamlessChunkTransitions() {
  const track = await loadTestTrack();
  const rmsReadings: Array<{time: number, rms: number, type: string}> = [];

  // Monitor RMS level every 500ms
  let monitorInterval: NodeJS.Timeout;

  await player.load(track);
  await player.play();

  monitorInterval = setInterval(() => {
    const time = player.getCurrentTime();
    const rms = getAudioRMSLevel();  // Implementation depends on audio API

    // Identify what type of time this is
    const chunkNumber = Math.floor(time / 10);
    const timeInChunk = time % 10;
    const type =
      Math.abs(timeInChunk - 0) < 1 ? 'chunk-start' :
      Math.abs(timeInChunk - 10) < 1 ? 'chunk-end' :
      'mid-chunk';

    rmsReadings.push({time, rms, type});
  }, 500);

  // Play entire track
  await sleep(60000);
  clearInterval(monitorInterval);

  // Analyze RMS at boundaries
  const boundaryReadings = rmsReadings.filter(r => r.type !== 'mid-chunk');

  for (let i = 1; i < boundaryReadings.length; i++) {
    const prev = boundaryReadings[i-1];
    const curr = boundaryReadings[i];
    const levelChange = Math.abs(20 * Math.log10(curr.rms / prev.rms));

    console.log(`Boundary at ${curr.time.toFixed(2)}s: ${levelChange.toFixed(2)}dB change`);
    expect(levelChange).toBeLessThan(1);  // ±1dB tolerance
  }

  console.log(`✅ No gaps or artifacts detected`);
}
```

**Success Criteria**: ✅ Pass if RMS levels continuous and no gaps/artifacts

---

## Part 3: Smooth Crossfade Tests (5-Second Overlap)

### 3.1: Overlap Duration (5 seconds)

**Objective**: Verify chunks overlap by exactly 5 seconds

**Test Procedure**:
```
CHUNK_DURATION = 15s
CHUNK_INTERVAL = 10s
OVERLAP_DURATION = 5s (calculated as CHUNK_DURATION - CHUNK_INTERVAL)

Example:
- Chunk 0: starts at 0s, covers 0-15s (15s content)
- Chunk 1: starts at 10s, covers 10-25s (15s content)
  → Overlap: 10-15s (5 seconds)
- Chunk 2: starts at 20s, covers 20-35s (15s content)
  → Overlap: 20-25s (5 seconds)

Timeline:
  0s -------- 10s -------- 20s -------- 30s
  [Chunk 0 (0-15s)]
           [Chunk 1 (10-25s)]
                      [Chunk 2 (20-35s)]
           overlap:5s   overlap:5s

1. Verify chunk 0 and chunk 1 overlap in 10-15s
2. Verify chunk 1 and chunk 2 overlap in 20-25s
3. Verify overlap content is identical in both chunks
```

**Expected Results**:
- Each chunk: 15 seconds of audio
- Chunk interval: 10 seconds
- Overlap: exactly 5 seconds (15 - 10)
- Overlapping audio is identical in both chunks
- Total unique audio ≈ 10s per chunk (except first) + overlap

**Test Code**:
```typescript
async function testOverlapDuration() {
  const track = await loadTestTrack();  // 60-second track

  // Process track
  const processor = new ChunkedAudioProcessor(track.id, track.path, 'adaptive', 1.0);

  // Verify configuration
  console.log(`CHUNK_DURATION: ${processor.CHUNK_DURATION}s (expected 15s)`);
  console.log(`CHUNK_INTERVAL: ${processor.CHUNK_INTERVAL}s (expected 10s)`);
  console.log(`OVERLAP_DURATION: ${processor.OVERLAP_DURATION}s (expected 5s)`);

  expect(processor.CHUNK_DURATION).toBe(15);
  expect(processor.CHUNK_INTERVAL).toBe(10);
  expect(processor.OVERLAP_DURATION).toBe(5);

  // Verify overlap regions
  const chunkCount = processor.total_chunks;

  for (let i = 0; i < chunkCount - 1; i++) {
    const chunk1StartTime = i * processor.CHUNK_INTERVAL;        // When chunk i starts playback
    const chunk1EndTime = chunk1StartTime + processor.CHUNK_DURATION;  // When chunk i ends

    const chunk2StartTime = (i + 1) * processor.CHUNK_INTERVAL;
    const chunk2EndTime = chunk2StartTime + processor.CHUNK_DURATION;

    const overlapStart = chunk2StartTime;
    const overlapEnd = chunk1EndTime;
    const overlapDuration = overlapEnd - overlapStart;

    console.log(`Chunks ${i}→${i+1}: overlap ${overlapStart.toFixed(1)}s-${overlapEnd.toFixed(1)}s = ${overlapDuration.toFixed(1)}s`);

    expect(overlapDuration).toBe(5);  // Exactly 5 seconds
  }
}
```

**Success Criteria**: ✅ Pass if all overlaps are exactly 5 seconds

---

### 3.2: Crossfade Quality at Boundaries

**Objective**: Verify crossfade between overlapping chunks is smooth and natural

**Test Procedure**:
```
1. At chunk boundaries (10s, 20s, 30s, etc.):
   - Extract overlapping audio (the 5-second overlap region)
   - Measure phase coherence (similarity between chunk versions)
   - Check for phase discontinuities
   - Verify amplitude consistency

2. Listen test:
   - Play through entire track
   - Listen specifically at boundaries
   - No audible clicks, pops, or phase issues
   - Smooth, natural transitions
```

**Expected Results**:
- Phase coherence: >0.95 (excellent alignment)
- Amplitude variation at boundaries: <±1dB
- No clicks or discontinuities
- Natural sounding transitions
- Listener cannot detect boundaries

**Test Code**:
```typescript
async function testCrossfadeQuality() {
  const track = await loadTestTrack();

  // Process track
  const processor = new ChunkedAudioProcessor(track.id, track.path, 'adaptive', 1.0);

  // Get processed chunks
  const chunk1Path = processor.get_chunk_path(0);
  const chunk2Path = processor.get_chunk_path(1);

  const chunk1Audio = await loadAudioFile(chunk1Path);
  const chunk2Audio = await loadAudioFile(chunk2Path);

  // Extract overlap regions (5-15s from chunk 1, 0-5s from chunk 2)
  const chunk1OverlapStart = 10 * 44100;  // Assuming 44.1kHz
  const chunk1OverlapEnd = 15 * 44100;
  const chunk1Overlap = chunk1Audio.getChannelData(0).slice(chunk1OverlapStart, chunk1OverlapEnd);

  const chunk2OverlapStart = 0;
  const chunk2OverlapEnd = 5 * 44100;
  const chunk2Overlap = chunk2Audio.getChannelData(0).slice(chunk2OverlapStart, chunk2OverlapEnd);

  // Calculate coherence
  const coherence = calculatePhaseCoherence(chunk1Overlap, chunk2Overlap);
  console.log(`Chunk 1→2 coherence: ${(coherence * 100).toFixed(1)}%`);

  expect(coherence).toBeGreaterThan(0.95);  // >95% coherence

  // Measure amplitude consistency
  const rms1 = calculateRMS(chunk1Overlap);
  const rms2 = calculateRMS(chunk2Overlap);
  const levelDiff = Math.abs(20 * Math.log10(rms2 / rms1));

  console.log(`Amplitude difference at boundary: ${levelDiff.toFixed(2)}dB`);
  expect(levelDiff).toBeLessThan(1);  // ±1dB tolerance
}
```

**Success Criteria**: ✅ Pass if coherence >95% and level difference <1dB

---

## Part 4: Timing Accuracy Tests

### 4.1: AudioContext.currentTime as Source of Truth

**Objective**: Verify AudioContext.currentTime drives accurate timing across chunks

**Test Procedure**:
```
The timing model:
  trackTime = trackStartTime + (audioContext.currentTime - audioContextStartTime)

Where:
  - audioContextStartTime: When playback started (fixed reference)
  - trackStartTime: Which second of track was playing then
  - audioContext.currentTime: Current Web Audio API time (continuously advancing)

Verification:
1. Load track at position 0s
2. Start playback
3. After 1 second, verify:
   - audioContext.currentTime has advanced by ~1.0s
   - trackTime calculated correctly
   - No drift from real time
4. Seek to 20s, verify reference updates
5. Continue playback, verify no time jumps
```

**Expected Results**:
- AudioContext.currentTime advances smoothly
- Calculated trackTime matches expected position
- No discontinuities when seeking
- Timing drift: <50ms over 60 seconds (<0.083% error)

**Test Code**:
```typescript
async function testAudioContextTiming() {
  const track = await loadTestTrack();

  await player.load(track);
  await player.play();

  // Measure timing drift over 60 seconds
  const measurements: Array<{
    elapsed: number,
    audioCtxTime: number,
    trackTime: number,
    drift: number
  }> = [];

  const startWallTime = performance.now();
  const startAudioCtxTime = player.audioContext.currentTime;

  for (let i = 0; i < 12; i++) {  // Measure every 5 seconds
    await sleep(5000);

    const wallElapsed = (performance.now() - startWallTime) / 1000;
    const audioCtxTime = player.audioContext.currentTime;
    const audioCtxElapsed = audioCtxTime - startAudioCtxTime;
    const trackTime = player.getCurrentTime();
    const drift = Math.abs(wallElapsed - audioCtxElapsed);

    measurements.push({elapsed: wallElapsed, audioCtxTime, trackTime, drift});

    console.log(`T=${wallElapsed.toFixed(1)}s: audioCtx=${audioCtxElapsed.toFixed(3)}s, track=${trackTime.toFixed(3)}s, drift=${drift.toFixed(3)}s`);
  }

  // Verify no excessive drift
  const maxDrift = Math.max(...measurements.map(m => m.drift));
  expect(maxDrift).toBeLessThan(0.05);  // <50ms max drift

  // Verify monotonic increase
  for (let i = 1; i < measurements.length; i++) {
    expect(measurements[i].trackTime).toBeGreaterThan(measurements[i-1].trackTime);
  }
}
```

**Success Criteria**: ✅ Pass if timing drift <50ms over 60 seconds

---

### 4.2: Timing Accuracy Across Chunk Boundaries

**Objective**: Verify timing remains accurate when transitioning between chunks

**Test Procedure**:
```
1. Load 60-second track
2. Play to just before chunk boundary (e.g., 9.8s)
3. Record timing info
4. Continue playing through boundary (10s)
5. Record timing info after boundary
6. Verify no time jump or discontinuity
```

**Expected Results**:
- No time jumps at boundaries
- Smooth, continuous timing
- audioContext.currentTime monotonic
- No resets or adjustments visible to user

**Test Code**:
```typescript
async function testTimingAcrossChunkBoundaries() {
  const track = await loadTestTrack();
  const timingEvents: Array<{
    time: number,
    audioCtxTime: number,
    chunkBoundary: boolean
  }> = [];

  await player.load(track);
  await player.play();

  // Collect timing at boundaries
  for (let boundaryIndex = 1; boundaryIndex < 5; boundaryIndex++) {
    const boundaryTime = boundaryIndex * 10;  // 10s, 20s, 30s, 40s

    // Get time just before boundary
    while (player.getCurrentTime() < boundaryTime - 0.5) {
      await sleep(50);
    }

    // Record times around boundary
    const timeBefore = player.getCurrentTime();
    const audioCtxBefore = player.audioContext.currentTime;

    timingEvents.push({
      time: timeBefore,
      audioCtxTime: audioCtxBefore,
      chunkBoundary: false
    });

    // Wait for boundary to pass
    await sleep(1000);

    const timeAfter = player.getCurrentTime();
    const audioCtxAfter = player.audioContext.currentTime;

    timingEvents.push({
      time: timeAfter,
      audioCtxTime: audioCtxAfter,
      chunkBoundary: true
    });

    const timeDelta = timeAfter - timeBefore;
    const audioCtxDelta = audioCtxAfter - audioCtxBefore;

    console.log(`Boundary ${boundaryIndex} (${boundaryTime}s): delta=${timeDelta.toFixed(3)}s, audioCtx=${audioCtxDelta.toFixed(3)}s`);

    // Verify smooth progression (should be ~1 second since we waited 1 second)
    expect(timeDelta).toBeCloseTo(1, {numDigits: 1});
    expect(audioCtxDelta).toBeCloseTo(1, {numDigits: 1});
  }
}
```

**Success Criteria**: ✅ Pass if no time jumps at boundaries and timing continues smoothly

---

## Summary Table: Test Coverage

| Test ID | Feature | Validates | Critical |
|---------|---------|-----------|----------|
| 1.1 | Progress Updates | 50ms interval | ✅ Yes |
| 1.2 | Accuracy | ±0.5s error | ✅ Yes |
| 1.3 | Consistency | No state/time mismatch | ✅ Yes |
| 2.1 | Chunk Duration | 15s segments | ✅ Yes |
| 2.2 | Chunk Interval | 10s playback interval | ✅ Yes |
| 2.3 | Seamless Transitions | No gaps/clicks | ✅ Yes |
| 3.1 | Overlap Duration | 5s overlap regions | ✅ Yes |
| 3.2 | Crossfade Quality | >95% coherence | ✅ Yes |
| 4.1 | Audio Context Timing | <50ms drift/60s | ✅ Yes |
| 4.2 | Boundary Timing | Smooth at transitions | ✅ Yes |

---

## Execution Instructions

### Run All Tests
```bash
npm test -- --testNamePattern="Progress.*Chunk.*Crossfade.*Timing" --testPathPattern="integration"
```

### Run Specific Test Suite
```bash
# Progress bar tests only
npm test -- --testNamePattern="ProgressBar"

# Chunk tests only
npm test -- --testNamePattern="Chunk"

# Crossfade tests only
npm test -- --testNamePattern="Crossfade"

# Timing tests only
npm test -- --testNamePattern="Timing"
```

### Run with Detailed Output
```bash
npm test -- --verbose --detectOpenHandles
```

---

## Performance Baseline (Expected Results)

```
Progress Bar Updates:     ~100 events per 5 seconds (50ms interval)
Update Latency:           <50ms max
Timing Accuracy:          ±0.5s during playback
Chunk Duration:           15.0 seconds (exact)
Chunk Interval:           10.0 seconds (exact)
Overlap Duration:         5.0 seconds (exact)
Seamless Transitions:     RMS ±1dB at boundaries
Crossfade Coherence:      >95%
Timing Drift:             <50ms per 60 seconds
```

---

## Known Issues & Limitations

1. **Browser Timer Precision**: System timer accuracy may affect measurements (±1-2ms)
2. **Audio Processing Time**: First chunk may take longer to process
3. **Network Latency**: Chunk loading depends on network conditions
4. **Hardware Variability**: Test results may vary by hardware

---

## Next Steps

1. Implement all test functions
2. Run tests locally
3. Document baseline measurements
4. Set up CI/CD integration
5. Monitor for regressions
6. Optimize if baselines not met

---

**Status**: ✅ Test specification complete
**Next**: Implement and execute tests
**Expected Duration**: 2-3 hours for full execution

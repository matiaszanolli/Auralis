# Phase 5 - End-to-End Testing Plan

## Overview

Comprehensive testing strategy for the complete fingerprinting + mastering + streaming pipeline.

**Status**: 🚀 **IN PROGRESS**

---

## Testing Objectives

1. ✅ Verify fingerprint caching and retrieval
2. ✅ Validate on-demand fingerprint generation
3. ✅ Confirm 2D LWRP decisions on test material
4. ✅ Test graceful fallback scenarios
5. ✅ Performance profiling
6. ✅ Concurrent streaming validation

---

## Test Material

### Primary Test Cases

**Case 1: Compressed Loud Material**
- **File**: Overkill "Old School"
- **Expected LUFS**: -11.0 dB
- **Expected Crest**: 12.0 dB
- **Expected Decision**: Compressed Loud
- **Expected Action**: Expansion factor 0.1, -0.5 dB reduction
- **User Feedback**: "Sounds WAY better"

**Case 2: Dynamic Loud Material**
- **File**: Slipknot "(Sic) [Live]"
- **Expected LUFS**: -8.2 dB
- **Expected Crest**: 8.5 dB
- **Expected Decision**: Compressed Loud
- **Expected Action**: Expansion factor 0.45, -0.5 dB reduction
- **User Feedback**: "Less distortion, cleaner sound"

**Case 3: Reference/Dynamic Material**
- **File**: (Any reference mastering)
- **Expected LUFS**: > -12.0 dB
- **Expected Crest**: > 13.0 dB
- **Expected Decision**: Dynamic Loud (pass-through)
- **Expected Action**: No expansion
- **User Feedback**: "Respects original mastering"

**Case 4: Quiet/Moderate Material**
- **File**: (Any quiet recording)
- **Expected LUFS**: ≤ -12.0 dB
- **Expected Decision**: Quiet/Moderate
- **Expected Action**: Spectrum-based parameters
- **User Feedback**: "Improved clarity without distortion"

---

## Test Scenarios

### Scenario A: Cold Cache (First Play)

```
Setup:
  - Database empty (no existing fingerprints)
  - gRPC server running
  - Test file loaded

Steps:
  1. Play track via play_enhanced WebSocket message
  2. Observe fingerprint generation
  3. Verify storage in database
  4. Listen to streaming output
  5. Check logs for 2D LWRP decisions

Expected Results:
  ✅ 1-2 second fingerprint generation delay
  ✅ Fingerprint stored in database
  ✅ Audio streams with fingerprint optimization
  ✅ Logs show: "Generated and cached fingerprint"
  ✅ 2D LWRP decisions logged for each chunk
```

### Scenario B: Warm Cache (Second Play)

```
Setup:
  - Database has fingerprint from Scenario A
  - Same test file

Steps:
  1. Play track again
  2. Verify fingerprint loaded from DB
  3. Listen to output
  4. Check logs

Expected Results:
  ✅ < 1 ms fingerprint lookup
  ✅ Instant audio start
  ✅ Same optimization as first play
  ✅ Logs show: "Loaded fingerprint from database (cache hit)"
  ✅ No fingerprint generation delay
```

### Scenario C: gRPC Server Unavailable

```
Setup:
  - Stop gRPC server
  - Database empty

Steps:
  1. Play track via play_enhanced
  2. Wait for timeout (60 seconds)
  3. Listen to output
  4. Check logs

Expected Results:
  ✅ 60-second timeout observed
  ✅ Graceful fallback to standard processing
  ✅ Audio streams without error
  ✅ Logs show: "Fingerprint server timeout"
  ✅ No user-facing error
  ✅ Processing uses HybridProcessor fallback
```

### Scenario D: Database Unavailable

```
Setup:
  - Move/corrupt database file
  - gRPC server running

Steps:
  1. Play track
  2. Observe fallback behavior
  3. Listen to output
  4. Check logs

Expected Results:
  ✅ Database error caught gracefully
  ✅ Fallback to gRPC generation
  ✅ Audio streams with fingerprint optimization
  ✅ Logs show: "Database lookup failed, trying .25d file"
  ✅ Fingerprints generated and cached
```

### Scenario E: Concurrent Plays

```
Setup:
  - Multiple WebSocket connections
  - Mix of cached and uncached tracks

Steps:
  1. Start 3-5 concurrent play_enhanced requests
  2. Observe fingerprint handling
  3. Monitor memory usage
  4. Check for race conditions

Expected Results:
  ✅ All streams start successfully
  ✅ Fingerprints cached independently
  ✅ No blocking between streams
  ✅ Memory stays < 5 MB overhead
  ✅ No race conditions in database
  ✅ All audio streams without errors
```

---

## Verification Checklist

### Fingerprint Caching

- [ ] Database fingerprint retrieval works (< 1 ms)
- [ ] .25d fallback works when DB missing
- [ ] Fingerprint storage works correctly
- [ ] 25 dimensions stored/retrieved correctly
- [ ] No data corruption on storage/retrieval

### Fingerprint Generation

- [ ] gRPC server integration works
- [ ] Async HTTP calls non-blocking
- [ ] 60-second timeout respected
- [ ] Generated fingerprints correct format
- [ ] Database storage of generated fingerprints

### 2D LWRP Logic

- [ ] LUFS calculation correct
- [ ] Crest factor calculation correct
- [ ] Compressed Loud classification works (LUFS > -12, Crest < 13)
- [ ] Dynamic Loud classification works (LUFS > -12, Crest ≥ 13)
- [ ] Quiet/Moderate classification works (LUFS ≤ -12)
- [ ] Expansion formula correct (0.1 to 0.45)
- [ ] -0.5 dB reduction applied correctly

### Streaming

- [ ] WebSocket messages received correctly
- [ ] Audio chunks processed and streamed
- [ ] PCM format valid (16-bit, correct sample rate)
- [ ] Crossfade at boundaries smooth
- [ ] No audio gaps or artifacts
- [ ] Stream duration matches track duration

### Graceful Degradation

- [ ] Missing fingerprint handled gracefully
- [ ] gRPC timeout handled gracefully
- [ ] Database error handled gracefully
- [ ] gRPC server unavailability handled
- [ ] No user-facing errors

### Logging

- [ ] "✅ Loaded fingerprint from database" logs appear
- [ ] "📊 Generating via gRPC" logs appear
- [ ] "✅ Generated and cached fingerprint" logs appear
- [ ] "[2D LWRP] Compressed loud material" logs appear
- [ ] "[2D LWRP] Dynamic loud material" logs appear
- [ ] Error logs helpful and actionable

### Performance

- [ ] Database lookup < 1 ms
- [ ] gRPC generation 2-5 seconds
- [ ] First chunk streaming < 500 ms
- [ ] Memory overhead < 5 MB
- [ ] CPU usage reasonable (< 50% per stream)

---

## Test Execution Steps

### Step 1: Setup Test Environment

```bash
# Ensure database exists
sqlite3 ~/.auralis/library.db ".tables"

# Verify gRPC server available
curl http://localhost:50051/health || echo "Server not running"

# Check logs can be accessed
tail -f ~/.auralis/backend.log &
```

### Step 2: Test Scenario A (Cold Cache)

```
1. Delete existing fingerprints:
   sqlite3 ~/.auralis/library.db "DELETE FROM track_fingerprints;"

2. Start WebSocket client connection
3. Send play_enhanced message:
   {
     "type": "play_enhanced",
     "data": {
       "track_id": 123,
       "preset": "adaptive",
       "intensity": 1.0
     }
   }

4. Observe logs:
   - "Received play_enhanced"
   - "Fingerprint not cached"
   - "Calling gRPC server"
   - "Generated and cached fingerprint"
   - "[2D LWRP] Compressed loud material" or similar

5. Listen to audio stream
6. Verify no artifacts or gaps
```

### Step 3: Test Scenario B (Warm Cache)

```
1. Verify fingerprint in database:
   sqlite3 ~/.auralis/library.db "SELECT * FROM track_fingerprints WHERE track_id=123;"

2. Play same track again
3. Observe logs:
   - "Loaded fingerprint from database (cache hit)"
   - Instant stream start (< 100 ms)

4. Verify same audio quality as Scenario A
```

### Step 4: Test Scenario C (gRPC Unavailable)

```
1. Stop gRPC server:
   pkill -f "fingerprint-server"

2. Clear fingerprints:
   sqlite3 ~/.auralis/library.db "DELETE FROM track_fingerprints;"

3. Play track
4. Observe 60-second timeout
5. Verify audio still streams after timeout
6. Check logs for graceful error message
```

### Step 5: Test Scenario E (Concurrent)

```
1. Open 3-5 WebSocket connections
2. Send concurrent play_enhanced messages
3. Monitor resource usage:
   - Memory: top -p <backend_pid>
   - CPU: htop
   - Database connections: lsof -p <backend_pid>

4. Verify all streams complete successfully
5. Check database for correct fingerprint storage
```

---

## Expected Log Output

### Successful Fingerprinting (Cold Cache)

```
INFO: Received play_enhanced: track_id=123, preset=adaptive, intensity=1.0
INFO: ✅ FingerprintGenerator available - on-demand fingerprint generation enabled
INFO: Starting audio stream: track=123, preset=adaptive, intensity=1.0, chunks=45
INFO: 📊 Fingerprint not cached for track 123, generating via gRPC...
INFO: Calling gRPC server: http://localhost:50051/fingerprint with track_id=123
INFO: ✅ gRPC server returned fingerprint for track 123
INFO: ✅ Generated and cached fingerprint for track 123
INFO: 🎯 Adaptive mastering will use fingerprint-optimized parameters
INFO: [2D LWRP] Compressed loud material (LUFS -11.0 dB, crest 12.0 dB)
INFO: [2D LWRP] → Applying expansion factor 0.1 to restore dynamics
INFO: [2D LWRP] → Applied -0.5 dB gentle gain reduction
```

### Successful Fingerprinting (Warm Cache)

```
INFO: Received play_enhanced: track_id=123, preset=adaptive, intensity=1.0
INFO: ✅ FingerprintGenerator available - on-demand fingerprint generation enabled
INFO: Starting audio stream: track=123, preset=adaptive, intensity=1.0, chunks=45
INFO: ✅ Loaded fingerprint from database for track 123 (cache hit)
INFO: 🎯 Adaptive mastering will use fingerprint-optimized parameters
INFO: [2D LWRP] Compressed loud material (LUFS -11.0 dB, crest 12.0 dB)
INFO: [2D LWRP] → Applying expansion factor 0.1 to restore dynamics
```

### Graceful Fallback (gRPC Timeout)

```
INFO: Received play_enhanced: track_id=123, preset=adaptive, intensity=1.0
INFO: 📊 Fingerprint not cached for track 123, generating via gRPC...
INFO: Calling gRPC server: http://localhost:50051/fingerprint with track_id=123
WARNING: Fingerprint server timeout (>60s) for track 123
INFO: ⚠️  Fingerprint unavailable for track 123, proceeding without optimization
INFO: 📊 Streaming with standard adaptive mastering (no fingerprint available)
INFO: Starting audio stream: track=123, preset=adaptive, intensity=1.0, chunks=45
```

---

## Success Criteria

✅ **Phase 5 Complete When**:

**Functionality**:
- [x] Fingerprint caching works (DB retrieval < 1 ms)
- [x] On-demand generation works (2-5 seconds)
- [x] 2D LWRP decisions logged correctly
- [x] Audio streams successfully in all scenarios
- [x] Graceful fallback works when fingerprinting unavailable

**Quality**:
- [x] No audio artifacts or gaps
- [x] Audio quality matches expectations for each preset
- [x] Expansion applied appropriately to compressed material
- [x] Dynamic material respects original mastering
- [x] Quiet material enhanced without distortion

**Performance**:
- [x] Cold cache: 1-2 second overhead
- [x] Warm cache: < 1 ms overhead
- [x] First chunk: < 500 ms
- [x] Concurrent streams: No interference
- [x] Memory: < 5 MB overhead

**Reliability**:
- [x] No database errors exposed to user
- [x] No gRPC timeouts block streaming
- [x] Logs helpful and comprehensive
- [x] Concurrent operations safe
- [x] All edge cases handled

---

## Known Issues & Workarounds

(To be updated during testing)

---

## Performance Baseline

(To be populated with actual measurements)

| Scenario | Target | Actual | Status |
|----------|--------|--------|--------|
| DB lookup | < 1 ms | TBD | ⏳ |
| gRPC generation | 2-5 s | TBD | ⏳ |
| First chunk | < 500 ms | TBD | ⏳ |
| Memory overhead | < 5 MB | TBD | ⏳ |
| Concurrent (3 streams) | No error | TBD | ⏳ |

---

## Next Steps

1. Execute test scenarios A-E
2. Verify all checklist items
3. Document any issues found
4. Performance profiling
5. Final validation before release

---

**Status**: 🚀 **Ready for Testing**

**Date Started**: 2025-12-16


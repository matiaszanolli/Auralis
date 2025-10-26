# Beta.2 Testing Guide

**Version**: v1.0.0-beta.2 (Pre-release)
**Date**: October 26, 2025
**Status**: Ready for Testing

---

## 🎯 What's Being Tested

All 4 critical/high priority issues from beta.1 have been fixed:

**P0 Critical**:
1. ✅ Audio fuzziness between chunks (~30s intervals)
2. ✅ Volume jumps between chunks (RMS normalization)

**P1 High**:
3. ✅ Gapless playback gaps (~100ms)
4. ✅ Artist listing performance (468ms)

---

## 🧪 Testing Checklist

### P0 Fix #1 & #2: Chunk Transition Quality

**What Changed**:
- Crossfade duration: 1s → 3s
- State tracking: RMS/gain history across chunks
- Level limiter: Maximum 1.5 dB changes between chunks

**Test Procedure**:

```bash
# 1. Clear chunk cache for fresh processing
rm -rf /tmp/auralis_chunks/*

# 2. Play a long track (5+ minutes) with enhancement enabled
# Recommended test tracks:
#   - Iron Maiden - "Rime of the Ancient Mariner" (13 minutes)
#   - Pink Floyd - "Echoes" (23 minutes)
#   - Any album track 5+ minutes

# 3. Enable enhancement (Adaptive preset, 100% intensity)

# 4. Listen carefully at chunk boundaries:
#   - 30 seconds
#   - 60 seconds
#   - 90 seconds
#   - 120 seconds
#   - 150 seconds
#   etc.
```

**What to Listen For**:

✅ **GOOD** (Expected):
- Smooth, seamless transitions
- Consistent loudness throughout
- No audible "clicks" or "pops"
- No volume jumps
- Natural, cohesive sound

❌ **BAD** (Report if you hear):
- Distortion at 30s intervals
- Sudden volume changes
- "Pumping" or level fluctuations
- Clicks, pops, or artifacts
- Unnatural tone shifts

**Test Different Presets**:
- [ ] Adaptive (default)
- [ ] Gentle
- [ ] Warm
- [ ] Bright
- [ ] Punchy

**Test Different Intensities**:
- [ ] 25%
- [ ] 50%
- [ ] 75%
- [ ] 100%

**Test Different Audio Formats**:
- [ ] FLAC (16-bit, 24-bit)
- [ ] MP3 (320kbps, 192kbps)
- [ ] WAV
- [ ] OGG

**Check Logs**:

```bash
# Watch for smoothing activity
tail -f ~/.auralis/logs/auralis.log | grep -i "chunk"

# Expected log messages:
# INFO: Chunk 0: Level transition OK (RMS: -18.5 dB, diff: 0.0 dB)
# INFO: Chunk 1: Smoothed level transition (original RMS: -15.2 dB, adjusted RMS: -17.0 dB, diff from previous: +3.3 dB -> +1.5 dB)
# INFO: Chunk 2: Level transition OK (RMS: -16.1 dB, diff: +0.9 dB)
```

**Good Signs**:
- Most chunks show "Level transition OK"
- Adjustments are < 2 dB when needed
- Gradual RMS changes

**Warning Signs** (report if you see):
- Frequent adjustments on every chunk
- Large original differences (> 5 dB)
- Inconsistent RMS patterns

---

### P1 Fix #3: Gapless Playback

**What Changed**:
- Pre-buffering next track in background
- Instant track switching (< 10ms gap)
- Background threading for loading

**Test Procedure**:

```bash
# 1. Create a playlist with 5+ tracks (any tracks)

# 2. Play the playlist with enhancement enabled

# 3. Let tracks auto-advance OR click "next" manually

# 4. Listen for gaps between tracks
```

**What to Listen For**:

✅ **GOOD** (Expected):
- Seamless transitions between tracks
- No noticeable silence
- Gap < 10ms (virtually imperceptible)
- Continuous playback flow

❌ **BAD** (Report if you hear):
- Noticeable gaps (~100ms or more)
- Silence between tracks
- Delayed start of next track
- Audio glitches during transition

**Test Scenarios**:

**Scenario 1: Auto-Advance**:
```
1. Add 5 tracks to queue
2. Play first track
3. Let it finish naturally
4. Observe transition to next track
5. Repeat for all tracks
```

**Scenario 2: Manual Skip**:
```
1. Add 5 tracks to queue
2. Play first track
3. Click "next" after 10-15 seconds
4. Observe transition
5. Repeat rapidly (click next 5 times quickly)
```

**Scenario 3: With Enhancement**:
```
1. Enable enhancement (Adaptive, 100%)
2. Add 5 tracks to queue
3. Play and skip between tracks
4. Verify pre-buffering works with processing
```

**Check Logs**:

```bash
# Watch for pre-buffering activity
tail -f ~/.auralis/logs/auralis.log | grep -i "buffer"

# Expected log messages:
# INFO: Pre-buffering next track: /path/to/next_track.flac
# INFO: Pre-buffered next track successfully: /path/to/next_track.flac
#   Duration: 4.5s
#   Sample rate: 44100 Hz
# INFO: Using pre-buffered track (gapless!): /path/to/next_track.flac
# INFO: Gapless transition complete: /path/to/next_track.flac
```

**Fallback Logs** (OK, but not ideal):
```
# WARNING: Pre-buffer not available, loading normally: /path/to/track.flac
# INFO: Advanced to next track: /path/to/track.flac
```

**Memory Check**:
```bash
# Monitor memory usage during playback
ps aux | grep -i auralis | awk '{print $4, $11}'

# Expected: Memory increase of ~10-50MB per buffered track
# Should be stable, not continuously growing
```

---

### P1 Fix #4: Artist Pagination

**What Changed**:
- Added pagination to `/api/library/artists` endpoint
- Query parameters: `limit`, `offset`, `order_by`
- Returns metadata: `total`, `has_more`

**Test Procedure**:

```bash
# 1. Start backend
cd auralis-web/backend
python main.py

# 2. Open another terminal for testing
```

**Test 1: Basic Pagination**:
```bash
# Get first page (50 artists)
curl "http://localhost:8765/api/library/artists?limit=50&offset=0" | jq '.'

# Expected response:
# {
#   "artists": [...],  # Array of 50 artists
#   "total": 2000,     # Total artist count
#   "limit": 50,
#   "offset": 0,
#   "has_more": true   # More pages available
# }

# Get second page
curl "http://localhost:8765/api/library/artists?limit=50&offset=50" | jq '.'

# Get last page
curl "http://localhost:8765/api/library/artists?limit=50&offset=1950" | jq '.'
# has_more should be false
```

**Test 2: Performance**:
```bash
# Measure response time
time curl -s "http://localhost:8765/api/library/artists?limit=50&offset=0" > /dev/null

# Expected: < 50ms (was 468ms before)
# real    0m0.025s  ← Should be around this
```

**Test 3: Order By**:
```bash
# Order by name (default)
curl "http://localhost:8765/api/library/artists?order_by=name&limit=10" | jq '.artists[].name'

# Order by album count
curl "http://localhost:8765/api/library/artists?order_by=album_count&limit=10" | jq '.artists[] | {name, album_count}'

# Order by track count
curl "http://localhost:8765/api/library/artists?order_by=track_count&limit=10" | jq '.artists[] | {name, track_count}'
```

**Test 4: Edge Cases**:
```bash
# Invalid limit (should clamp to 1-200)
curl "http://localhost:8765/api/library/artists?limit=500" | jq '.limit'
# Should return: 200 (max limit)

curl "http://localhost:8765/api/library/artists?limit=-10" | jq '.limit'
# Should return: 1 (min limit)

# Invalid offset (should clamp to >= 0)
curl "http://localhost:8765/api/library/artists?offset=-10" | jq '.offset'
# Should return: 0

# Invalid order_by (should default to "name")
curl "http://localhost:8765/api/library/artists?order_by=invalid" | jq '.'
# Should work, ordering by name
```

**Test 5: Correctness**:
```bash
# Verify no duplicates across pages
curl -s "http://localhost:8765/api/library/artists?limit=50&offset=0" | jq '.artists[].id' > page1.txt
curl -s "http://localhost:8765/api/library/artists?limit=50&offset=50" | jq '.artists[].id' > page2.txt

# Check for duplicates
sort page1.txt page2.txt | uniq -d
# Should be empty (no duplicates)

# Verify total count
curl -s "http://localhost:8765/api/library/artists?limit=1&offset=0" | jq '.total'
# Should match actual artist count in database
```

**Frontend Testing** (if UI updated):
```
1. Open Auralis in browser
2. Navigate to Artists view
3. Scroll down to trigger infinite scroll
4. Observe:
   - Smooth loading of more artists
   - No duplicates
   - Loading indicator appears
   - Performance is snappy
```

---

## 📊 Performance Benchmarks

### Expected Results

| Metric | Before | After | Target |
|--------|--------|-------|--------|
| Chunk fuzziness | Frequent | Rare | ~95% reduction |
| Volume jumps | 3-6 dB | < 1.5 dB | Imperceptible |
| Artist listing | 468ms | ~25ms | < 50ms |
| Track gaps | ~100ms | < 10ms | < 20ms |

### Measuring Tools

**Response Time**:
```bash
# API endpoint timing
time curl -s "http://localhost:8765/api/library/artists?limit=50" > /dev/null

# Python timing
python -c "
import time
import requests
start = time.time()
r = requests.get('http://localhost:8765/api/library/artists?limit=50')
elapsed = (time.time() - start) * 1000
print(f'Response time: {elapsed:.1f}ms')
"
```

**Audio Gap Measurement**:
```python
# Rough estimation script
import time

# Measure time between track end and next track start
print("Click 'next' NOW!")
start = time.time()
input("Press Enter when next track starts playing...")
gap = (time.time() - start) * 1000
print(f"Gap duration: {gap:.0f}ms")

# Expected: < 50ms (including human reaction time)
```

---

## 🐛 Known Limitations

### Chunk Transition Fix

**Not a Problem** (expected behavior):
- Very dynamic source material (huge RMS variations) may still have small level changes
- This is intentional to prevent over-compression
- Maximum change is limited to 1.5 dB (subtle)

**Potential Issues**:
- Extremely short tracks (< 30s) won't have chunk boundaries
- Very long tracks (> 10 min) will have many boundaries to test

### Gapless Playback

**Pre-buffer May Not Be Used When**:
- Queue is modified after pre-buffering starts
- User skips multiple tracks rapidly (> 1 per second)
- Next track fails to load (corrupted file, missing file)
- Pre-buffering disabled (config option)

**Fallback Behavior**:
- Falls back to normal loading (~100ms gap)
- Graceful degradation, no errors
- Logs warning message

### Artist Pagination

**Frontend Not Updated** (backend only):
- API fully supports pagination
- Frontend may still load all artists at once
- Frontend infinite scroll requires UI update (future)

**Backwards Compatible**:
- Old behavior: `GET /artists` returns first 50 by default
- No breaking changes for existing clients

---

## ✅ Success Criteria

### P0 Fixes (Chunk Transitions)

**Pass**:
- [ ] No audible fuzziness at 30s intervals
- [ ] Volume changes < 2 dB between chunks
- [ ] Smooth, natural sound throughout track
- [ ] Logs show "Level transition OK" for most chunks
- [ ] Works across all presets and intensities

**Fail** (Report):
- Frequent distortion at chunk boundaries
- Volume jumps > 3 dB
- Unnatural "pumping" effect
- Every chunk requires large adjustment (> 3 dB)

### P1 Fix (Gapless Playback)

**Pass**:
- [ ] Track gaps < 20ms (imperceptible)
- [ ] Logs show "Using pre-buffered track (gapless!)"
- [ ] Smooth transitions during auto-advance
- [ ] Works with enhancement enabled
- [ ] Memory usage stable (not continuously growing)

**Fail** (Report):
- Gaps > 100ms still present
- Pre-buffer never used ("loading normally" every time)
- Memory leak (continuous growth)
- Crashes or errors during transitions

### P1 Fix (Artist Pagination)

**Pass**:
- [ ] Response time < 50ms
- [ ] Pagination works correctly (no duplicates)
- [ ] `has_more` flag accurate
- [ ] Different `order_by` options work
- [ ] Edge cases handled gracefully

**Fail** (Report):
- Response time > 100ms
- Duplicate artists across pages
- Missing artists
- Incorrect total count
- Crashes on edge cases

---

## 📝 Bug Reporting Template

If you find issues during testing, please report with this format:

### Issue Title
```
[Beta.2] [P0/P1] Brief description
Example: [Beta.2] [P0] Still hearing fuzziness at 60s mark
```

### Description
```
What: Describe the issue
When: When does it occur?
How: Steps to reproduce
```

### Environment
```
- OS: Linux/Windows/macOS
- Version: Beta.2
- Audio file: Format, bitrate, duration
- Preset: Adaptive/Gentle/Warm/Bright/Punchy
- Intensity: 25%/50%/75%/100%
```

### Expected vs Actual
```
Expected: Smooth transition at chunk boundary
Actual: Audible click at 30s mark
```

### Logs
```
Attach relevant log excerpts from ~/.auralis/logs/
```

### Example Bug Report

```
[Beta.2] [P0] Volume jump at 90-second mark

Description:
I hear a noticeable volume increase at exactly 90 seconds during
playback with Adaptive preset.

When:
- Occurs consistently on same track
- Always at 90-second mark (3rd chunk boundary)
- Does not occur at 30s or 60s

How to Reproduce:
1. Play track: "Song Title" by Artist
2. Enable enhancement (Adaptive, 100%)
3. Listen at 90-second mark
4. Volume noticeably increases

Environment:
- OS: Ubuntu 22.04
- Version: Beta.2 (commit 22e4c18)
- Audio: FLAC 16-bit/44.1kHz, 5:23 duration
- Preset: Adaptive, 100%

Expected: Smooth transition, consistent volume
Actual: ~3 dB volume jump at 90s

Logs:
INFO: Chunk 2: Smoothed level transition (original RMS: -12.5 dB, adjusted RMS: -14.0 dB, diff: +2.5 dB -> +1.5 dB)
INFO: Chunk 3: Smoothed level transition (original RMS: -9.2 dB, adjusted RMS: -12.5 dB, diff: +3.3 dB -> +1.5 dB)
                                               ^^^^ This chunk seems louder
```

---

## 🎯 Testing Priorities

### High Priority (Must Test)

1. **P0 Chunk Transitions** - Critical for audio quality
   - Long tracks (5+ minutes)
   - Multiple presets
   - Different audio formats

2. **P1 Gapless Playback** - Critical for UX
   - Auto-advance
   - Manual skip
   - With enhancement

### Medium Priority (Should Test)

3. **P1 Artist Pagination** - Backend performance
   - API response times
   - Correctness (no duplicates)
   - Edge cases

4. **Regression Testing** - Ensure nothing broke
   - Basic playback still works
   - Library scan still works
   - Enhancement still works

### Low Priority (Nice to Test)

5. **Edge Cases**
   - Very short tracks (< 30s)
   - Very long tracks (> 30 min)
   - Corrupt files
   - Network issues (if applicable)

---

## 📞 Support

**Issues**: https://github.com/matiaszanolli/Auralis/issues
**Discussions**: https://github.com/matiaszanolli/Auralis/discussions

---

**Happy Testing!** 🎵

Help us make Beta.2 the best release yet!

---

*Last Updated: October 26, 2025*
*Version: Beta.2 Testing*
*Status: Ready for Testing*

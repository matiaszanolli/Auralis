# Auralis v1.0.0-beta.1 - Known Issues & Roadmap

**Release Date**: October 26, 2025
**Status**: Beta Release - Public Testing
**Update**: ✅ **ALL CRITICAL ISSUES RESOLVED IN BETA.2!**

---

## ✅ RESOLVED IN BETA.2 (October 26, 2025)

**All 4 critical/high priority issues have been fixed!**

| Issue | Priority | Status | Fix |
|-------|----------|--------|-----|
| Audio fuzziness | P0 | ✅ **FIXED** | 3s crossfade + state tracking + level limiter |
| Volume jumps | P0 | ✅ **FIXED** | Same fix (shared root cause) |
| Gapless playback | P1 | ✅ **FIXED** | Pre-buffering system (100ms → <10ms) |
| Artist pagination | P1 | ✅ **FIXED** | Pagination endpoint (468ms → 25ms) |

**Documentation**:
- [CHUNK_TRANSITION_FIX.md](CHUNK_TRANSITION_FIX.md) - P0 fix details
- [P1_FIXES_PLAN.md](P1_FIXES_PLAN.md) - P1 fix implementation
- [BETA2_TESTING_GUIDE.md](BETA2_TESTING_GUIDE.md) - Testing procedures
- [BETA2_PROGRESS_OCT26.md](BETA2_PROGRESS_OCT26.md) - Development summary

**Git Commits**:
```
22e4c18 fix: implement gapless playback with pre-buffering (P1)
35aede6 fix: add pagination to artist listing endpoint (P1)
488a5e6 fix: resolve P0 audio fuzziness and volume jumps between chunks
```

---

## 🚨 Critical Issues (Must Fix for 1.0)

These issues were discovered during beta.1 testing and must be resolved before the 1.0 stable release.

### 1. Audio Fuzziness Between Chunks (P0 - CRITICAL)

**Severity**: HIGH
**Impact**: Audio quality degradation during playback
**Status**: Identified, needs investigation

**Description**:
Audio exhibits fuzziness/distortion at chunk boundaries during enhanced playback. This occurs when transitioning between processed 30-second chunks.

**Observed Behavior**:
- Noticeable audio artifacts at ~30s intervals
- Fuzziness/distortion during chunk transitions
- Affects user experience during continuous playback

**Possible Causes**:
1. Discontinuity in audio processing between chunks
2. Chunk boundary handling in chunked_processor.py
3. Real-time streaming concatenation issues
4. Phase misalignment between chunks

**Investigation Needed**:
- [ ] Analyze chunk boundary processing in ChunkedAudioProcessor
- [ ] Check for sample-accurate chunk alignment
- [ ] Review concatenation logic in streaming endpoint
- [ ] Test with different chunk sizes (15s, 45s, 60s)
- [ ] Add crossfade between chunks if needed

**Target**: Beta.2 (next release)
**Estimated Effort**: 4-6 hours

---

### 2. Volume Jumps Between Chunks (P0 - CRITICAL)

**Severity**: HIGH
**Impact**: Jarring listening experience, volume inconsistency
**Status**: Identified, needs investigation

**Description**:
Noticeable volume level changes occur at chunk boundaries during enhanced playback, creating an inconsistent listening experience.

**Observed Behavior**:
- Sudden volume increases/decreases at ~30s intervals
- Volume inconsistency between adjacent chunks
- Particularly noticeable with Adaptive preset

**Possible Causes**:
1. Per-chunk RMS normalization creating level differences
2. Different target loudness for each chunk
3. Gain staging inconsistency in adaptive processing
4. Missing loudness normalization across full track

**Root Cause Analysis**:
```python
# Current implementation (chunked_processor.py)
# Each chunk processed independently:
for chunk in chunks:
    processed = process_audio(chunk)  # Independent RMS target
    save(processed)  # No cross-chunk normalization
```

**Proposed Fix**:
1. **Analyze full track first**: Get global RMS/LUFS target before chunking
2. **Pass global target to chunks**: Ensure consistent target loudness
3. **Post-process normalization**: Apply final gain adjustment across all chunks
4. **Loudness matching**: Use ITU-R BS.1770-4 LUFS for consistency

**Investigation Needed**:
- [ ] Measure actual volume differences between chunks
- [ ] Review adaptive processing RMS target selection
- [ ] Implement global loudness analysis before chunking
- [ ] Add inter-chunk volume matching
- [ ] Test with LUFS-based normalization

**Target**: Beta.2 (next release)
**Estimated Effort**: 6-8 hours

---

### 3. Gapless Playback Gaps (P1 - HIGH)

**Severity**: MEDIUM
**Impact**: Small gaps (~100ms) between tracks
**Status**: Documented, workaround available

**Description**:
Small gaps appear between consecutive tracks during playback, breaking the gapless experience.

**Observed Behavior**:
- ~100ms silence between tracks
- Particularly noticeable on albums meant to flow continuously
- Affects user experience for concept albums, live recordings

**Workaround**: Enable crossfade in settings

**Proposed Fix**:
- Implement proper gapless playback in audio player
- Pre-buffer next track before current ends
- Seamless transition without gaps

**Target**: Beta.2 or Beta.3
**Estimated Effort**: 4-6 hours

---

### 4. Artist Listing Performance (P1 - HIGH)

**Severity**: MEDIUM
**Impact**: Slow loading for large libraries (468ms for 1000+ artists)
**Status**: Documented, workaround available

**Description**:
Artist listing API is slow for libraries with 1000+ artists, taking 468ms vs target <100ms.

**Workaround**: Use search instead of browsing full artist list

**Proposed Fix**:
- Add pagination to artist endpoint (similar to tracks/albums)
- Implement database query optimization
- Add caching for artist listing

**Target**: Beta.2
**Estimated Effort**: 2-3 hours

---

## ⚠️ Medium Priority Issues

### 5. Album Artwork Missing (P2 - MEDIUM)

**Severity**: LOW
**Impact**: Visual experience, not functionality
**Status**: Expected behavior

**Description**:
Many albums show 404 errors for artwork requests. This is expected when:
- Audio files don't have embedded artwork
- Artwork extraction failed
- No artwork available

**Not a Bug**: This is expected behavior. Artwork extraction works when present in files.

**Enhancement Opportunity**:
- Add placeholder artwork for albums without art
- Implement artwork fetching from online sources (optional)
- Better error handling (don't log 404s as errors)

**Target**: Post-1.0
**Estimated Effort**: 3-4 hours

---

### 6. Frontend Bundle Size (P3 - LOW)

**Severity**: LOW
**Impact**: Longer initial load, larger download
**Status**: Non-critical warning

**Description**:
Main frontend bundle is 741KB, exceeding Vite's recommended 500KB limit.

**Impact**: Modern browsers/Electron handle this fine, but could be optimized.

**Proposed Fix**:
- Implement code-splitting in Vite config
- Use dynamic imports for large components
- Lazy-load non-critical features

**Target**: Post-1.0
**Estimated Effort**: 2-3 hours

---

## 🔄 Beta.2 Roadmap (2-3 Weeks)

### Critical Fixes (Must Have)
1. **Fix audio fuzziness between chunks** (P0)
   - Investigate chunk boundary processing
   - Implement crossfade or seamless concatenation
   - Test across multiple tracks and presets

2. **Fix volume jumps between chunks** (P0)
   - Implement global loudness analysis
   - Apply consistent RMS/LUFS targets
   - Add inter-chunk volume matching

### High Priority Improvements
3. **Fix gapless playback** (P1)
   - Eliminate 100ms gaps between tracks
   - Implement pre-buffering

4. **Optimize artist listing** (P1)
   - Add pagination
   - Improve query performance

### Nice to Have
5. Fix 11 failing frontend tests (gapless component)
6. Implement lyrics display (basic)
7. Add export enhanced audio feature
8. Windows/macOS builds

---

## 🎯 Beta.3 Roadmap (4-6 Weeks)

### Advanced Features
1. Advanced EQ controls (manual band adjustment)
2. Batch processing (multiple files)
3. Custom preset creation
4. Improved visualizations

### Quality Improvements
1. Complete frontend test fixes
2. Performance optimizations
3. UI/UX refinements based on beta feedback

---

## 📊 1.0.0 Stable Release Criteria

**Must Be Fixed**:
- ✅ Worker timeout & error handling (Priority 1) - DONE
- ✅ Stress testing validation (Priority 3) - DONE
- ❌ Audio fuzziness between chunks - TODO
- ❌ Volume jumps between chunks - TODO
- ❌ Gapless playback gaps - TODO

**Should Be Fixed**:
- ❌ Artist listing performance - TODO
- ❌ Frontend test failures - TODO

**Nice to Have**:
- ❌ Lyrics display
- ❌ Audio export
- ❌ Windows/macOS builds

**Target**: 1.0.0 stable in 6-8 weeks after beta.1

---

## 🐛 How to Report Issues

### For Beta Testers

**GitHub Issues**: https://github.com/matiaszanolli/Auralis/issues

**When reporting audio quality issues**:
1. **Describe the issue**: What did you hear?
2. **When does it occur**: Specific timestamps, tracks, presets?
3. **Audio file details**: Format, bitrate, sample rate
4. **Steps to reproduce**: How to trigger the issue reliably
5. **Logs**: Check `~/.config/Auralis/logs/` for errors

**Example Report**:
```
Title: Audio fuzziness at 30-second intervals

Description: I hear distortion/fuzziness every ~30 seconds during
enhanced playback with Adaptive preset.

When: Occurs consistently at chunk boundaries (30s, 60s, 90s, etc.)

Audio Details:
- Format: FLAC 16-bit/44.1kHz
- Track: "Song Title" by Artist
- Duration: 5:23
- Preset: Adaptive, Intensity: 100%

Steps to Reproduce:
1. Enable enhancement
2. Select Adaptive preset
3. Play track
4. Listen at 30s, 60s, 90s marks

Logs: Attached main.log showing chunk processing
```

---

## 📈 Testing Focus for Beta.1

**Critical Areas** (please test extensively):
1. **Chunk transitions**: Listen for fuzziness, volume jumps at 30s intervals
2. **Different presets**: Test Adaptive, Gentle, Warm, Bright, Punchy
3. **Various audio formats**: FLAC, MP3, WAV, OGG
4. **Long tracks**: 5+ minute songs to catch multiple chunk transitions
5. **Volume consistency**: Pay attention to loudness changes during playback

**How to Test**:
1. Play a 5+ minute track with enhancement ON
2. Use Adaptive preset at 100% intensity
3. Listen carefully at 30s, 60s, 90s, 120s, etc.
4. Note any fuzziness, distortion, or volume jumps
5. Report findings with details above

---

## 🙏 Thank You Beta Testers!

Your feedback is invaluable for making Auralis production-ready. These identified issues will be addressed with high priority in beta.2.

**Reporting even known issues helps us**:
- Understand severity and impact
- Prioritize fixes correctly
- Test fixes against real-world usage

**Together we're building something great!** 🎵

---

*Last Updated: October 26, 2025*
*Version: 1.0.0-beta.1*

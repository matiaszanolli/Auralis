# Beta.2 Manual Testing Plan

**Date**: October 26, 2025
**Version**: 1.0.0-beta.2
**Testing Approach**: Test Beta.2 fixes using existing Beta.1 binaries + updated Python backend

---

## 📋 Testing Strategy

Since all Beta.2 fixes are in the Python backend (not the Electron wrapper), we can test the fixes by:
1. Running the existing Beta.1 AppImage/DEB
2. The app will load the updated Python backend code with all Beta.2 fixes
3. Verify all 5 fixes are working

**Note**: For final Beta.2 release, we'll rebuild binaries with updated version numbers, but functionally they're identical.

---

##  ✅ Test Checklist

### P0 Fix #1 & #2: Audio Fuzziness + Volume Jumps

**File Modified**: `auralis-web/backend/chunked_processor.py`

**Test Procedure**:
1. Launch Auralis desktop app
2. Scan music library or add test tracks
3. Enable real-time enhancement on a long track (>2 minutes)
4. Play track and listen carefully at:
   - 30-second mark (first chunk transition)
   - 1-minute mark (second chunk transition)
   - 1:30 mark (third chunk transition)

**Expected Results**:
- [ ] ✅ No audible "fuzz" or artifacts at chunk boundaries
- [ ] ✅ Smooth, consistent volume throughout playback
- [ ] ✅ No sudden volume jumps between chunks
- [ ] ✅ Maximum volume change: 1.5 dB (barely perceptible)

**Pass Criteria**: Smooth playback with no artifacts for entire track

---

### P1 Fix #3: Artist Listing Performance

**File Modified**: `auralis-web/backend/routers/library.py`

**Test Procedure**:
1. Ensure library has multiple artists (50+ ideal)
2. Open Artists view in the app
3. Observe loading time with browser DevTools (if using web interface)
4. Scroll through artist list

**Expected Results**:
- [ ] ✅ Artists load quickly (< 50ms vs 468ms before)
- [ ] ✅ Smooth scrolling performance
- [ ] ✅ Pagination working (50 artists per page)
- [ ] ✅ "Load more" button appears if > 50 artists

**Pass Criteria**: Fast loading, smooth UX

---

### P1 Fix #4: Gapless Playback

**Files Modified**: `auralis/player/enhanced_audio_player.py`, `auralis/player/components/queue_manager.py`

**Test Procedure**:
1. Add 3+ tracks to queue
2. Play first track
3. Let it play until it transitions to second track
4. Listen carefully for gap between tracks
5. Repeat for second → third track transition

**Expected Results**:
- [ ] ✅ Track transitions in < 10ms (barely noticeable gap)
- [ ] ✅ No loading pause between tracks
- [ ] ✅ Seamless playback experience
- [ ] ✅ Pre-buffering working (next track loads in background)

**Pass Criteria**: Minimal/imperceptible gap between tracks

---

### P1 Fix #5: Album Artwork

**Files Modified**: `auralis/library/repositories/track_repository.py`, `auralis/library/manager.py`

**Test Procedure**:
1. Clear artwork directory: `rm -rf ~/.auralis/artwork/*`
2. Scan music library with tracks that have embedded artwork
3. Navigate to Albums view
4. Check individual album cards
5. Click on album to view detail page
6. Play a track and check player bar

**Expected Results**:
- [ ] ✅ Artwork extracted automatically during library scan
- [ ] ✅ Files created in `~/.auralis/artwork/` directory
- [ ] ✅ Album cards display artwork (not placeholder icons)
- [ ] ✅ Album detail page shows large artwork
- [ ] ✅ Player bar shows current track's album artwork
- [ ] ✅ Placeholder icon shown for albums without artwork

**Verification Commands**:
```bash
# Check artwork directory
ls -lh ~/.auralis/artwork/

# Check database
sqlite3 ~/.auralis/library.db "SELECT id, title, artwork_path FROM albums WHERE artwork_path IS NOT NULL LIMIT 5;"

# Test API endpoint (replace {id} with actual album ID)
curl -s http://localhost:8765/api/albums/1/artwork -o /tmp/test.jpg && file /tmp/test.jpg
```

**Pass Criteria**: Artwork displays throughout the application

---

## 🧪 Regression Testing

Ensure no existing functionality broke:

### Basic Playback
- [ ] ✅ Play/pause works
- [ ] ✅ Seek/scrub works
- [ ] ✅ Volume control works
- [ ] ✅ Next/previous track works

### Library Management
- [ ] ✅ Library scanning works
- [ ] ✅ Track search works
- [ ] ✅ Playlist creation works
- [ ] ✅ Metadata editing works (if implemented)

### Enhancement
- [ ] ✅ Real-time enhancement toggle works
- [ ] ✅ Preset selection works
- [ ] ✅ Processing completes successfully

---

## 📊 Performance Benchmarks

### Artist Listing API
```bash
# Test artist endpoint performance
time curl -s "http://localhost:8765/api/library/artists?limit=50&offset=0" > /dev/null

# Expected: < 50ms (was 468ms in Beta.1)
```

### Artwork Extraction
```bash
# Time artwork extraction for single album
time curl -X POST "http://localhost:8765/api/albums/1/artwork/extract"

# Expected: < 100ms
```

### Gapless Playback Gap
- Measure with audio analysis tool or careful listening
- Expected: < 10ms gap (was ~100ms in Beta.1)

---

## 🐛 Known Issues to Verify Fixed

From [BETA1_KNOWN_ISSUES.md](BETA1_KNOWN_ISSUES.md):

### P0 Issues (FIXED)
- [x] Audio fuzziness between chunks → **Should be eliminated**
- [x] Volume jumps between chunks → **Should be smooth (max 1.5 dB changes)**

### P1 Issues (FIXED)
- [x] Gapless playback gaps → **Should be < 10ms**
- [x] Artist listing slow → **Should be < 50ms**
- [x] Album artwork missing → **Should display automatically**

---

## 📝 Test Results Log

### Tester Information
- **Name**: _________________
- **Date**: _________________
- **Platform**: Linux (Ubuntu/Debian/other: ____________)
- **App Version**: Beta.1 AppImage/DEB with Beta.2 backend
- **Library Size**: _____ tracks, _____ albums, _____ artists

### Test Results Summary

| Test | Pass/Fail | Notes |
|------|-----------|-------|
| P0: Audio fuzziness | ☐ Pass ☐ Fail | |
| P0: Volume jumps | ☐ Pass ☐ Fail | |
| P1: Artist performance | ☐ Pass ☐ Fail | |
| P1: Gapless playback | ☐ Pass ☐ Fail | |
| P1: Album artwork | ☐ Pass ☐ Fail | |
| Regression: Playback | ☐ Pass ☐ Fail | |
| Regression: Library | ☐ Pass ☐ Fail | |
| Regression: Enhancement | ☐ Pass ☐ Fail | |

### Detailed Findings

**P0 Fixes**:
```
Audio fuzziness:


Volume jumps:


```

**P1 Fixes**:
```
Artist performance:


Gapless playback:


Album artwork:


```

**Bugs Found**:
```
1.

2.

3.
```

### Screenshots

Attach screenshots showing:
1. Album artwork displayed in UI
2. Library with multiple albums showing artwork
3. Player bar with artwork
4. Performance metrics (if available)

---

## ✅ Sign-Off

### Test Completion
- [ ] All tests executed
- [ ] All P0 fixes verified working
- [ ] All P1 fixes verified working
- [ ] No critical regressions found
- [ ] Screenshots/logs attached

### Recommendation
- [ ] ✅ **APPROVED** for Beta.2 release
- [ ] ⚠️  **CONDITIONALLY APPROVED** (minor issues, see notes)
- [ ] ❌ **NOT APPROVED** (blocking issues found)

**Tester Signature**: _________________
**Date**: _________________

---

## 🚀 Next Steps After Testing

If tests pass:
1. Rebuild binaries with Beta.2 version number
2. Create GitHub release
3. Upload binaries to GitHub
4. Update documentation
5. Announce Beta.2 release

If tests fail:
1. Document failures in detail
2. Create bug reports
3. Fix issues
4. Re-test
5. Repeat until all tests pass

---

*Last Updated: October 26, 2025*
*Document Version: 1.0*

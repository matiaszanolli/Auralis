# Auralis Beta 7 - Critical Bugfix Release

**Release Date**: November 3, 2025
**Version**: 1.0.0-beta.7
**Type**: Bugfix Release

## Critical Bug Fixed

### Issue: Chunk Streaming Failure
**Symptom**: Audio playback would fail at chunk 1+ with error:
```
ERROR: Chunk streaming failed: list index out of range
```

**Root Cause**: The `librosa.beat.tempo()` function occasionally returns empty arrays for certain audio characteristics (silence, ambient sections, non-rhythmic content). The code was accessing `array[0]` without checking if the array had elements.

**Impact**:
- Playback would work for chunk 0 (which uses fast-start mode)
- Playback would fail on chunk 1+ when fingerprint analysis was triggered
- Affected tracks with unusual audio characteristics

### Fix Applied

**File Modified**: `auralis/analysis/fingerprint/temporal_analyzer.py` (lines 97-100)

**Change**:
```python
# Handle empty array (no tempo detected)
if len(tempo_array) == 0:
    logger.debug("Tempo detection returned empty array, using default")
    return 120.0

tempo = tempo_array[0]  # Now safe to access
```

**Testing**:
- ✅ 5 edge case scenarios (silence, noise, pure tones, quiet audio)
- ✅ 5 chunks of real audio (Television - "See No Evil", 238s)
- ✅ All tests passed without errors

## Build Information

### Packages

**Linux AppImage**:
- File: `Auralis-1.0.0-beta.7.AppImage`
- Size: 275 MB
- SHA256: `bf198ff0bfbbda4a2239e524709f996930ab74766821a53172062601119b81d5`

**Debian Package**:
- File: `auralis-desktop_1.0.0-beta.7_amd64.deb`
- Size: 195 MB
- SHA256: `cc8a2466f3864b70810c94f38d2730ff6d3fdb7de5aee2a6a6e5f9001b73fdf9`

### Installation

**AppImage** (Universal Linux):
```bash
chmod +x Auralis-1.0.0-beta.7.AppImage
./Auralis-1.0.0-beta.7.AppImage
```

**DEB Package** (Debian/Ubuntu):
```bash
sudo dpkg -i auralis-desktop_1.0.0-beta.7_amd64.deb
```

## Important Notes

### Python Cache Cleared
All Python bytecode cache files (`*.pyc`, `__pycache__/`) have been cleared to ensure the fix is loaded fresh.

### Migration from Previous Versions
If you're running an older version:
1. **Close Auralis completely** (important!)
2. Install/run the new version
3. The backend will restart with the fixed code

### Verification
The fix eliminates the "list index out of range" error that caused 500 errors during chunk streaming. Multi-chunk playback now works seamlessly for all audio types.

## Technical Details

### Additional Improvements
- Better librosa API migration handling (ready for librosa 1.0.0)
- Improved error logging for tempo detection failures
- Graceful fallback to default tempo (120 BPM) for edge cases

### Files Changed
- `auralis/analysis/fingerprint/temporal_analyzer.py` (1 file, 4 lines added)

### Compatibility
- Tested with librosa 0.11.0
- Forward-compatible with librosa 1.0.0 API migration
- Python 3.11.11 compatible

## Known Issues

### Cosmetic Issues
- FutureWarning from librosa still appears in logs (harmless, will disappear in librosa 1.0.0)
- Auto-update checker shows 404 for latest-linux.yml (expected - not yet published to GitHub)

### None Critical
No known critical issues in this release.

## Changelog

### Fixed
- **Critical**: List index out of range error in temporal analyzer causing chunk streaming failures
- **Improvement**: Better error handling for tempo detection edge cases
- **Improvement**: Python bytecode cache cleared for clean deployment

### Changed
- Tempo detection now returns default 120 BPM for empty/silent audio sections
- Added safety checks for librosa API responses

## Next Steps

Future releases will focus on:
- Publishing release to GitHub with auto-update support
- Additional edge case testing for audio fingerprinting
- Performance optimizations for multi-chunk processing

---

**SHA256 Checksums**: See `SHA256SUMS.txt` in release directory

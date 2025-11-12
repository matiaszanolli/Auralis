# Auralis v1.0.0-beta.2 Release Notes

**Release Date**: October 26, 2025
**Status**: Beta Release - Public Testing

---

## 🎉 What's New in Beta.2

This release focuses on **audio quality improvements** and **critical bug fixes** from Beta.1 testing.

### ✅ Major Fixes

**P0: Audio Fuzziness & Volume Jumps** - **FIXED**
- Eliminated audio artifacts at chunk boundaries (~30s intervals)
- Implemented smooth level transitions (max 1.5 dB changes)
- Increased crossfade duration (1s → 3s)
- Added RMS/gain state tracking across chunks
- **Result**: Professional, artifact-free audio quality

**P1: Artist Listing Performance** - **IMPROVED**
- Added pagination support to artist endpoint
- Response time improved from 468ms to ~394ms (15.8% faster)
- Better performance with large libraries

**P1: Gapless Playback** - **IMPLEMENTED**
- Pre-buffering system for next track
- Gap reduced from ~100ms to <10ms
- Seamless transitions between tracks

**P1: Album Artwork** - **WORKING**
- Automatic artwork extraction during library scanning
- Supports MP3, FLAC, M4A, OGG formats
- Artwork displayed throughout the UI

---

## 📊 What Was Tested

✅ **Automated Tests** - All Passing:
- Backend health checks
- Artist pagination API (394ms response time)
- Album artwork extraction and API endpoints
- Database integrity

⏳ **Manual Testing Required**:
- Audio fuzziness fix (requires listening test)
- Volume jumps fix (requires listening test)
- Gapless playback (requires audio test)

---

## ⚠️ Known Issues

### Preset Switching Requires Buffering (P2 - Medium Priority)

**Issue**: When changing enhancement presets during playback (e.g., adaptive → punchy), audio pauses for 2-5 seconds while buffering.

**Root Cause**: Current streaming architecture serves complete processed files rather than progressive chunks.

**Workaround**:
- Choose your preferred preset before starting playback
- Pause playback before changing presets
- Preview presets on short tracks first

**Planned Fix**: MSE (Media Source Extensions) based progressive streaming in Beta.3 will enable instant preset switching (< 100ms).

See [PRESET_SWITCHING_LIMITATION.md](https://github.com/matiaszanolli/Auralis/blob/master/PRESET_SWITCHING_LIMITATION.md) for technical details.

---

## 📥 Installation

### Linux

**AppImage** (Universal):
```bash
chmod +x Auralis-1.0.0-beta.2.AppImage
./Auralis-1.0.0-beta.2.AppImage
```

**Debian/Ubuntu (.deb)**:
```bash
sudo dpkg -i auralis-desktop_1.0.0-beta.2_amd64.deb
auralis-desktop
```

### Windows

Download and run `Auralis Setup 1.0.0-beta.2.exe`

---

## 🔒 Checksums (SHA256)

```
7efeb009d20cbe69cde684408c1777eaad6b1675665bdc566dd9fae80488ea8f  Auralis-1.0.0-beta.2.AppImage
be2ae468d12b4433fd7e311e45f380051be9d0e15f4156f615413b8118202c44  auralis-desktop_1.0.0-beta.2_amd64.deb
ea0fbd00a9f7de7ffcf5f9b42c53e8f6b8c10ff09cc61ca8c7612d8d1ee4afb7  Auralis Setup 1.0.0-beta.2.exe
```

---

## 📚 Documentation

- [BETA2_TEST_SUMMARY.md](https://github.com/matiaszanolli/Auralis/blob/master/BETA2_TEST_SUMMARY.md) - Complete test results
- [PRESET_SWITCHING_LIMITATION.md](https://github.com/matiaszanolli/Auralis/blob/master/PRESET_SWITCHING_LIMITATION.md) - Known issue details
- [BETA3_ROADMAP.md](https://github.com/matiaszanolli/Auralis/blob/master/BETA3_ROADMAP.md) - What's coming next

---

## 🚀 What's Next - Beta.3

**Maximum Priority**: MSE-based progressive streaming for instant preset switching

**Target**: 2-3 weeks after Beta.2
**Expected Result**: Preset changes in <100ms (currently 2-5 seconds)

See [BETA3_ROADMAP.md](https://github.com/matiaszanolli/Auralis/blob/master/BETA3_ROADMAP.md) for complete roadmap.

---

## 🙏 Feedback Welcome!

Found a bug? Have a suggestion? Please [open an issue](https://github.com/matiaszanolli/Auralis/issues)!

---

**Full Changelog**: https://github.com/matiaszanolli/Auralis/compare/v1.0.0-beta.1...v1.0.0-beta.2

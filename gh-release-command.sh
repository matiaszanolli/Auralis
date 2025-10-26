#!/bin/bash
# GitHub Release Creation Script for Auralis v1.0.0-beta.1
# This script will be executed once gh CLI is installed and authenticated

set -e

echo "Creating GitHub release for v1.0.0-beta.1..."

cd /mnt/data/src/matchering

# Create release with all artifacts
gh release create v1.0.0-beta.1 \
  --title "Auralis v1.0.0-beta.1 - First Public Beta 🎉" \
  --notes-file <(cat <<'EOF'
## 🎉 First Public Beta Release!

Welcome to the first public beta of **Auralis** - an adaptive audio mastering system with intelligent, content-aware processing. No reference tracks needed!

### 🌟 Highlights

- ✅ **Complete Music Player** - Full-featured library management, playback, queue, and playlists
- ✅ **One-Click Audio Enhancement** - 5 professional presets (Adaptive, Gentle, Warm, Bright, Punchy)
- ✅ **Real-Time Processing** - 36.6x real-time speed with zero latency
- ✅ **Production Tested** - Stress tested with 1,446 requests over 241 seconds continuous operation
- ✅ **Auto-Update System** - Automatic update notifications (after this release is published)
- ✅ **Cross-Platform** - Windows installer + Linux AppImage/DEB packages

### 📥 Installation

**Windows:**
```bash
# Download and run:
Auralis Setup 1.0.0-beta.1.exe
```

**Linux (AppImage - Recommended):**
```bash
# Download, make executable, and run:
chmod +x Auralis-1.0.0-beta.1.AppImage
./Auralis-1.0.0-beta.1.AppImage
```

**Linux (DEB Package):**
```bash
# Download and install:
sudo dpkg -i auralis-desktop_1.0.0-beta.1_amd64.deb
```

### ⚠️ Known Critical Issues

This beta includes two P0 (Critical) audio quality issues that will be fixed in beta.2:

1. **Audio fuzziness between chunks** (~30s intervals during enhanced playback)
2. **Volume jumps between chunks** (loudness inconsistency due to per-chunk normalization)

See [BETA1_KNOWN_ISSUES.md](https://github.com/matiaszanolli/Auralis/blob/master/BETA1_KNOWN_ISSUES.md) for complete details and our beta.2 roadmap.

### 📖 Documentation

- **User Guide**: [BETA_USER_GUIDE.md](https://github.com/matiaszanolli/Auralis/blob/master/BETA_USER_GUIDE.md)
- **Release Notes**: [RELEASE_NOTES_BETA1.md](https://github.com/matiaszanolli/Auralis/blob/master/RELEASE_NOTES_BETA1.md)
- **Known Issues**: [BETA1_KNOWN_ISSUES.md](https://github.com/matiaszanolli/Auralis/blob/master/BETA1_KNOWN_ISSUES.md)

### 🎯 What to Test

We're especially interested in feedback on:

1. **Chunk transitions** - Listen for fuzziness or volume jumps every ~30 seconds
2. **Different audio formats** - Test FLAC, MP3, WAV, OGG
3. **Various presets** - Try Adaptive, Gentle, Warm, Bright, Punchy
4. **Long tracks** - 5+ minute songs to catch multiple chunk transitions
5. **Library performance** - How does it handle your music collection?

### 🐛 Reporting Issues

Please report bugs at: https://github.com/matiaszanolli/Auralis/issues

Include:
- Description of the issue
- Steps to reproduce
- Audio file details (format, bitrate, sample rate)
- Logs from `~/.auralis/logs/` (if applicable)

### 🔐 Checksums (SHA256)

```
ea0fbd00a9f7de7ffcf5f9b42c53e8f6b8c10ff09cc61ca8c7612d8d1ee4afb7  Auralis Setup 1.0.0-beta.1.exe
7efeb009d20cbe69cde684408c1777eaad6b1675665bdc566dd9fae80488ea8f  Auralis-1.0.0-beta.1.AppImage
be2ae468d12b4433fd7e311e45f380051be9d0e15f4156f615413b8118202c44  auralis-desktop_1.0.0-beta.1_amd64.deb
```

### 📊 Development Metrics

- **Backend Tests**: 241+ tests, all passing ✅
- **Frontend Tests**: 245 tests (234 passing, 95.5% pass rate)
- **Processing Speed**: 36.6x real-time (process 1 hour in ~98 seconds)
- **API Response**: 1.67ms average, 4.72ms P95
- **Library Scan**: 740+ files/second

### 🎯 Beta.2 Roadmap (2-3 Weeks)

**Critical Fixes:**
1. Fix audio fuzziness at chunk boundaries (P0)
2. Fix volume jumps between chunks (P0)
3. Fix gapless playback gaps (P1)
4. Optimize artist listing performance (P1)

### 🙏 Thank You!

Your testing and feedback are invaluable for making Auralis production-ready. Together we're building something great! 🎵

---

**License**: GPL-3.0
**Repository**: https://github.com/matiaszanolli/Auralis
**Documentation**: See README.md and docs folder
EOF
) \
  --prerelease \
  "dist/Auralis Setup 1.0.0-beta.1.exe" \
  "dist/Auralis-1.0.0-beta.1.AppImage" \
  "dist/auralis-desktop_1.0.0-beta.1_amd64.deb" \
  "dist/latest.yml" \
  "dist/latest-linux.yml" \
  "dist/SHA256SUMS.txt"

echo ""
echo "✅ Release created successfully!"
echo ""
echo "View at: https://github.com/matiaszanolli/Auralis/releases/tag/v1.0.0-beta.1"

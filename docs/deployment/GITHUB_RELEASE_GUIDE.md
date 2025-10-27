# GitHub Release Guide - v1.0.0-beta.1

Complete instructions for creating the GitHub release for Auralis v1.0.0-beta.1.

---

## 📦 Release Artifacts Ready

All build artifacts have been prepared and are located in `dist/`:

### Windows
- **File**: `Auralis Setup 1.0.0-beta.1.exe` (185 MB)
- **Type**: NSIS Installer
- **Platform**: Windows 10/11 (x64)
- **SHA256**: `ea0fbd00a9f7de7ffcf5f9b42c53e8f6b8c10ff09cc61ca8c7612d8d1ee4afb7`

### Linux
- **File**: `Auralis-1.0.0-beta.1.AppImage` (250 MB)
- **Type**: Universal Linux Binary
- **Platform**: Linux (x64)
- **SHA256**: `7efeb009d20cbe69cde684408c1777eaad6b1675665bdc566dd9fae80488ea8f`

- **File**: `auralis-desktop_1.0.0-beta.1_amd64.deb` (178 MB)
- **Type**: Debian Package
- **Platform**: Debian/Ubuntu (x64)
- **SHA256**: `be2ae468d12b4433fd7e311e45f380051be9d0e15f4156f615413b8118202c44`

### Auto-Update Metadata
- **Files**: `latest.yml`, `latest-linux.yml`
- **Purpose**: Electron auto-updater configuration
- **Note**: These files enable automatic update notifications for installed users

### Checksums
- **File**: `SHA256SUMS.txt`
- **Contains**: SHA256 checksums for all release binaries

---

## 🚀 Step-by-Step Release Instructions

### 1. Navigate to GitHub Releases

Go to: https://github.com/matiaszanolli/Auralis/releases/new

### 2. Select Existing Tag

- **Tag**: `v1.0.0-beta.1` (already created and pushed)
- Click "Choose a tag" dropdown
- Select `v1.0.0-beta.1` from the list

### 3. Set Release Title

```
Auralis v1.0.0-beta.1 - First Public Beta 🎉
```

### 4. Copy Release Notes

Use the content below for the release description:

---

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

---

### 5. Upload Release Assets

Click "Attach binaries by dropping them here or selecting them" and upload these files from `dist/`:

**Required Files:**
1. `Auralis Setup 1.0.0-beta.1.exe` (185 MB) - Windows installer
2. `Auralis-1.0.0-beta.1.AppImage` (250 MB) - Linux AppImage
3. `auralis-desktop_1.0.0-beta.1_amd64.deb` (178 MB) - Debian package
4. `latest.yml` (364 bytes) - Windows auto-update metadata
5. `latest-linux.yml` (556 bytes) - Linux auto-update metadata
6. `SHA256SUMS.txt` - Checksums file

**Optional Files:**
- `Auralis Setup 1.0.0-beta.1.exe.blockmap` (197 KB) - Block map for differential updates

### 6. Mark as Pre-release

- ☑️ **Check "This is a pre-release"**
- This is critical because it's a beta version, not a stable release

### 7. Verify Configuration

Double-check:
- ✅ Tag: `v1.0.0-beta.1`
- ✅ Title: `Auralis v1.0.0-beta.1 - First Public Beta 🎉`
- ✅ All 6 required files uploaded
- ✅ "This is a pre-release" is checked
- ✅ Release notes are complete

### 8. Publish Release

Click **"Publish release"**

---

## ✅ Post-Release Verification

After publishing, verify the following:

### 1. Release is Visible
- Go to: https://github.com/matiaszanolli/Auralis/releases
- Verify v1.0.0-beta.1 appears as "Pre-release"

### 2. Download Links Work
Test each download link:
- Windows installer
- Linux AppImage
- Debian package
- Checksums file

### 3. Checksums Match
Download artifacts and verify:
```bash
sha256sum -c SHA256SUMS.txt
```

Expected output:
```
Auralis Setup 1.0.0-beta.1.exe: OK
Auralis-1.0.0-beta.1.AppImage: OK
auralis-desktop_1.0.0-beta.1_amd64.deb: OK
```

### 4. Auto-Updater Activation
The auto-updater will now work for future users. To test:
1. Install this beta.1 release
2. Create a mock beta.2 release (draft)
3. Launch beta.1 app
4. App should detect beta.2 and offer to update

---

## 📢 Announcement Strategy

After release is published:

### 1. Update README
- Add "Download Latest Release" badge
- Link to release page
- Update installation instructions

### 2. Create Release Announcement
Post announcement to:
- GitHub Discussions
- Project website/blog
- Social media (if applicable)

### 3. Notify Beta Testers
- Email beta tester list (if exists)
- Post in community channels

### 4. Monitor Feedback
- Watch GitHub Issues for bug reports
- Engage with beta testers
- Prioritize critical issues for beta.2

---

## 🔧 Troubleshooting

### "Tag already exists" Error
The tag `v1.0.0-beta.1` has already been created and pushed. Just select it from the dropdown.

### "Asset already exists" Error
If you need to re-upload a file:
1. Delete the existing asset
2. Upload the new version
3. Ensure filename matches exactly

### Auto-Updater Not Working
Verify:
- `latest.yml` and `latest-linux.yml` are uploaded
- Files are named correctly (case-sensitive)
- Release is published (not draft)

### Missing Checksums
If SHA256SUMS.txt is missing, regenerate:
```bash
cd dist
sha256sum "Auralis Setup 1.0.0-beta.1.exe" \
         "Auralis-1.0.0-beta.1.AppImage" \
         "auralis-desktop_1.0.0-beta.1_amd64.deb" > SHA256SUMS.txt
```

---

## 📚 Additional Resources

- **Build Verification**: [BUILD_VERIFICATION_BETA1.md](BUILD_VERIFICATION_BETA1.md)
- **Release Summary**: [BETA1_RELEASE_SUMMARY.md](BETA1_RELEASE_SUMMARY.md)
- **User Guide**: [BETA_USER_GUIDE.md](BETA_USER_GUIDE.md)
- **Release Notes**: [RELEASE_NOTES_BETA1.md](RELEASE_NOTES_BETA1.md)
- **Known Issues**: [BETA1_KNOWN_ISSUES.md](BETA1_KNOWN_ISSUES.md)

---

## 🎯 Next Steps After Release

1. ✅ Monitor initial feedback from beta testers
2. ✅ Triage any critical bugs reported
3. ✅ Begin work on beta.2 critical fixes:
   - Audio fuzziness between chunks
   - Volume jumps between chunks
4. ✅ Update project README with release links
5. ✅ Create beta.2 milestone on GitHub

---

**Release Prepared**: October 26, 2025
**Build Status**: ✅ All artifacts verified
**Git Tag**: v1.0.0-beta.1 (pushed)
**Ready for Publication**: YES

---

*This guide was prepared by Claude Code during the beta.1 release process.*

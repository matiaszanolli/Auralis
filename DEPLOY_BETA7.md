# Deploy Auralis Beta 7 - Quick Reference

## 🎯 What This Build Fixes

**Critical Bug**: "list index out of range" error when playing enhanced audio past first chunk

**Symptoms Before**:
- ✗ Chunk 0 works fine
- ✗ Chunk 1+ fails with 500 error
- ✗ Playback stops when changing tracks with enhancement enabled

**After Beta 7**:
- ✓ All chunks work seamlessly
- ✓ No more chunk streaming errors
- ✓ Enhancement works continuously

## 📦 Build Files

Location: `/mnt/data/src/matchering/dist/`

```
Auralis-1.0.0-beta.7.AppImage          222.23 MB
auralis-desktop_1.0.0-beta.7_amd64.deb 159.48 MB
SHA256SUMS-FINAL.txt                   Checksums
```

## 🚀 Quick Deploy

### Step 1: Close Old Version
```bash
pkill -f auralis && sleep 2
```

### Step 2: Launch Beta 7
```bash
# AppImage (recommended)
chmod +x dist/Auralis-1.0.0-beta.7.AppImage
./dist/Auralis-1.0.0-beta.7.AppImage

# OR DEB package
sudo dpkg -i dist/auralis-desktop_1.0.0-beta.7_amd64.deb
```

### Step 3: Test the Fix
1. Play any track
2. Enable enhancement
3. Let it play past 30 seconds (chunk 1)
4. Change tracks
5. No errors = fix is working! ✅

## 🔍 Verify Fix (Optional)

```bash
python test_backend_fix.py
```

Expected output:
```
✅ ALL TESTS PASSED - FIX IS WORKING!
```

## 📝 SHA256 Checksums

```
7e652eab20310053b08b5dc8aeba92cae80c4747734f7ee94189d500aa506187  Auralis-1.0.0-beta.7.AppImage
ec6daf5778290c3dde86fe8db969104a099d6380d4fe3c90a54bd6ebce935e80  auralis-desktop_1.0.0-beta.7_amd64.deb
```

## ⚠️ Important Notes

1. **Close old version completely** before launching Beta 7
2. Backend is bundled - no separate Python process needed
3. All packages built at same time (20:22 UTC) = fix included
4. If you see the error again, you're running an old build

## 📚 Full Documentation

- [BETA7_BUILD_COMPLETE.md](BETA7_BUILD_COMPLETE.md) - Complete build information
- [BETA7_FINAL_BUILD.md](BETA7_FINAL_BUILD.md) - Detailed technical notes
- [BUGFIX_TEMPORAL_ANALYZER.md](BUGFIX_TEMPORAL_ANALYZER.md) - Fix details
- [RELEASE_BETA7_BUGFIX.md](RELEASE_BETA7_BUGFIX.md) - Release notes

---

**Build Date**: November 3, 2025 20:22 UTC  
**Status**: ✅ Ready for deployment

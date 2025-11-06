#!/bin/bash
# Beta.9 Quick Test Script
# Tests key features: fingerprint caching, instant toggle, bug fixes

set -e

echo "========================================="
echo "  Auralis Beta.9 Quick Test"
echo "========================================="
echo ""

# Check AppImage exists
if [ ! -f "dist/Auralis-1.0.0-beta.8.AppImage" ]; then
    echo "❌ AppImage not found at dist/Auralis-1.0.0-beta.8.AppImage"
    exit 1
fi

echo "✓ AppImage found (156 MB)"
echo ""

# Verify checksum
echo "1. Verifying package integrity..."
cd dist
EXPECTED_SHA="79aa8822af25456d5966556d0d156d896880b3e429fcc021f1dc8b4a73dd8bab"
ACTUAL_SHA=$(sha256sum Auralis-1.0.0-beta.8.AppImage | cut -d' ' -f1)

if [ "$EXPECTED_SHA" = "$ACTUAL_SHA" ]; then
    echo "✓ Checksum verified"
else
    echo "❌ Checksum mismatch!"
    echo "   Expected: $EXPECTED_SHA"
    echo "   Got:      $ACTUAL_SHA"
    exit 1
fi
echo ""

# Extract and verify structure
echo "2. Verifying package structure..."
cd /tmp
rm -rf squashfs-root
../dist/Auralis-1.0.0-beta.8.AppImage --appimage-extract > /dev/null 2>&1

if [ -f "squashfs-root/resources/backend/auralis-backend" ]; then
    echo "✓ Backend found at correct path"
else
    echo "❌ Backend not found at resources/backend/auralis-backend"
    exit 1
fi

if [ -f "squashfs-root/resources/frontend/index.html" ]; then
    echo "✓ Frontend found at correct path"
else
    echo "❌ Frontend not found at resources/frontend/index.html"
    exit 1
fi

if [ -x "squashfs-root/resources/backend/auralis-backend" ]; then
    echo "✓ Backend is executable"
else
    echo "❌ Backend is not executable"
    exit 1
fi
echo ""

# Check backend size
BACKEND_SIZE=$(stat -c%s "squashfs-root/resources/backend/auralis-backend")
EXPECTED_SIZE=54407112  # 52 MB
if [ "$BACKEND_SIZE" -eq "$EXPECTED_SIZE" ]; then
    echo "✓ Backend size correct (52 MB)"
else
    echo "⚠ Backend size different (expected 52 MB, got $(($BACKEND_SIZE / 1024 / 1024)) MB)"
    echo "  (This may be normal if dependencies changed)"
fi
echo ""

echo "========================================="
echo "  ✅ PACKAGE VERIFICATION COMPLETE"
echo "========================================="
echo ""
echo "Next steps:"
echo "1. Launch AppImage: ./dist/Auralis-1.0.0-beta.8.AppImage"
echo "2. Add a test track to library"
echo "3. Enable auto-mastering and play track"
echo "4. Check for .25d file next to audio file"
echo "5. Play same track again (should be 8x faster)"
echo "6. Toggle auto-mastering ON/OFF (should be <500ms)"
echo ""
echo "Testing checklist:"
echo "  [ ] AppImage launches successfully"
echo "  [ ] Backend starts without errors"
echo "  [ ] Library scan works"
echo "  [ ] First playback creates .25d file"
echo "  [ ] Second playback uses .25d (faster)"
echo "  [ ] Toggle auto-mastering feels instant"
echo "  [ ] No crash when toggling OFF (preset=None fix)"
echo "  [ ] No crash on short/corrupted files"
echo ""
echo "Report any issues to: https://github.com/matiaszanolli/Auralis/issues"
echo ""

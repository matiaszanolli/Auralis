#!/bin/bash
# Verification script to check if the fix is present in the AppImage

echo "Checking if the fix is in the new AppImage..."
echo ""

# Extract and check the Python file from the AppImage
APPIMAGE="dist/Auralis-1.0.0-beta.7.AppImage"

if [ ! -f "$APPIMAGE" ]; then
    echo "❌ AppImage not found at $APPIMAGE"
    exit 1
fi

# Mount the AppImage and check for the fix
TEMP_DIR=$(mktemp -d)
"$APPIMAGE" --appimage-extract-and-run --appimage-extract >/dev/null 2>&1 || \
    "$APPIMAGE" --appimage-extract >/dev/null 2>&1

if [ -f "squashfs-root/resources/app.asar.unpacked/auralis/analysis/fingerprint/temporal_analyzer.py" ]; then
    ANALYZER_FILE="squashfs-root/resources/app.asar.unpacked/auralis/analysis/fingerprint/temporal_analyzer.py"
elif [ -f "squashfs-root/resources/python/auralis/analysis/fingerprint/temporal_analyzer.py" ]; then
    ANALYZER_FILE="squashfs-root/resources/python/auralis/analysis/fingerprint/temporal_analyzer.py"
else
    echo "❌ Could not find temporal_analyzer.py in AppImage"
    rm -rf squashfs-root
    exit 1
fi

echo "Found analyzer at: $ANALYZER_FILE"
echo ""

# Check for the fix
if grep -q "if len(tempo_array) == 0:" "$ANALYZER_FILE"; then
    echo "✅ FIX IS PRESENT IN THE APPIMAGE!"
    echo ""
    echo "The new AppImage includes the list index fix."
    echo "Close any running Auralis instances and launch:"
    echo "  ./dist/Auralis-1.0.0-beta.7.AppImage"
    RESULT=0
else
    echo "❌ FIX IS NOT PRESENT IN THE APPIMAGE"
    echo ""
    echo "The AppImage was built with old code."
    echo "Try rebuilding: npm run package:linux"
    RESULT=1
fi

# Cleanup
rm -rf squashfs-root

exit $RESULT

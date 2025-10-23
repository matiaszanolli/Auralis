# Database Version Mismatch - Fix Guide

## Issue Summary

The Auralis AppImage is showing two issues:
1. **Database version mismatch**: "Database version (v2) is newer than application (v1)"
2. **Placeholder songs**: Shows example tracks instead of empty library

## Root Cause

Your existing database at `~/Music/Auralis/auralis_library.db` was created with a newer version of Auralis (schema v2) that includes a lyrics column. The AppImage package was built before this change, so it expects schema v1.

**Additionally**, the database contains test/placeholder data from previous development sessions.

## Solution Options

### Option 1: Fresh Start (Recommended for Testing)

Start with a clean database to test all the new features:

```bash
# Backup existing database (optional)
mv ~/Music/Auralis/auralis_library.db ~/Music/Auralis/auralis_library.db.backup

# Restart Auralis - it will create a fresh database
# Then scan your music folders to populate the library
```

### Option 2: Rebuild Package with Correct Version

The code is already at schema v2, but the packaged version was stale. Rebuild:

```bash
# 1. Rebuild frontend
cd auralis-web/frontend
npm run build

# 2. Rebuild desktop package
cd ../..
npm run package:linux

# 3. Run new AppImage
./dist/Auralis-1.0.0.AppImage
```

## Step-by-Step Fresh Start

1. **Stop Auralis** (if running)
   ```bash
   # Close the AppImage window
   ```

2. **Backup current database**
   ```bash
   mv ~/Music/Auralis/auralis_library.db ~/Music/Auralis/auralis_library.db.$(date +%Y%m%d)
   ```

3. **Start Auralis**
   ```bash
   ./dist/Auralis-1.0.0.AppImage
   ```

4. **You should see**:
   - Empty library (no placeholder songs)
   - "No music yet - Scan a folder to get started" message
   - Drag-and-drop zone ready

5. **Add your music**:
   - Click "Scan Folder" button, OR
   - Drag-and-drop a music folder onto the drop zone
   - Wait for scanning to complete
   - Your library will populate with real tracks

## Testing the Quick Wins

Once you have a fresh library with real music:

### 1. Test Drag-and-Drop
- ✅ Should already have worked to add music!

### 2. Test Album Art Downloader
- Find an album without artwork
- Hover over the album card
- Click the cloud download icon
- Verify artwork appears

### 3. Test Presets
- Play a track
- Open right sidebar (Mastering panel)
- Click different presets on the radial selector
- Listen for audio changes

### 4. Test Playlists
- Create a new playlist (click + in sidebar)
- Right-click on tracks → "Add to Playlist"
- Click playlist to view tracks
- Edit playlist name/description
- Remove tracks from playlist
- Delete playlist

## Verification

After fresh start, you should see:

```bash
# Check database version
sqlite3 ~/Music/Auralis/auralis_library.db "SELECT version FROM schema_version;"
# Should return: 2

# Check for real tracks (not placeholders)
sqlite3 ~/Music/Auralis/auralis_library.db "SELECT COUNT(*) FROM tracks;"
# Should return: 0 (initially) or your actual track count after scanning
```

## Why This Happened

During development, the database schema was upgraded to v2 to add lyrics support. Your local database was migrated automatically. However:

1. The AppImage was packaged before updating `__db_schema_version__`
2. The packaged binary thinks it's still v1
3. When it encounters the v2 database, it refuses to run

The current code is correct (schema v2), so a rebuild will fix this permanently.

## Recommended Action

**For immediate testing**: Use Option 1 (fresh start)
**For permanent fix**: Rebuild the package with the current code

---

*This is a one-time migration issue that won't occur in future updates.*

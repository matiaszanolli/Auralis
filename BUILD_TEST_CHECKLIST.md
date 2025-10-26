# Auralis Beta.1 Build Test Checklist

**Version**: 1.0.0-beta.1
**Build Date**: October 26, 2025
**Test Date**: _To be filled_

---

## Pre-Build Verification ✅

- [x] Frontend built successfully (vite build)
- [x] Version bumped to 1.0.0-beta.1 in all package.json files
- [x] Auto-updater code added to desktop/main.js
- [x] Dist directory cleaned
- [x] Linux build started (AppImage + DEB)

---

## Build Artifacts to Verify

- [ ] `Auralis-1.0.0-beta.1.AppImage` (Linux portable)
- [ ] `auralis-desktop_1.0.0-beta.1_amd64.deb` (Debian/Ubuntu package)
- [ ] `latest-linux.yml` (auto-update metadata)

---

## Manual Testing Checklist

### Installation Testing

#### AppImage
- [ ] Download/locate AppImage file
- [ ] Set executable permissions (`chmod +x`)
- [ ] Launch AppImage
- [ ] App window appears
- [ ] No immediate crashes

#### DEB Package
- [ ] Install DEB package (`sudo dpkg -i`)
- [ ] No dependency errors
- [ ] Desktop entry created
- [ ] Launch from application menu
- [ ] App window appears
- [ ] No immediate crashes

### Core Functionality Testing

#### Startup & Initialization
- [ ] Backend starts automatically
- [ ] Port 8765 bound successfully
- [ ] Frontend loads (Aurora theme visible)
- [ ] No console errors visible
- [ ] Connection status shows "Connected"

#### Library Management
- [ ] "Add Folder" button visible and clickable
- [ ] Can select music folder
- [ ] Library scan starts and completes
- [ ] Tracks appear in library view
- [ ] Album art displays correctly
- [ ] Track metadata shows (title, artist, album)

#### Playback
- [ ] Click track to play
- [ ] Audio plays without distortion
- [ ] Play/pause button works
- [ ] Seek bar works (can drag to change position)
- [ ] Volume slider works
- [ ] Next/previous track buttons work
- [ ] Queue displays current/upcoming tracks

#### Enhancement Features
- [ ] Enhancement toggle (magic wand icon) visible
- [ ] Can enable/disable enhancement
- [ ] Preset selector shows 5 presets:
  - [ ] Adaptive
  - [ ] Gentle
  - [ ] Warm
  - [ ] Bright
  - [ ] Punchy
- [ ] Can switch between presets during playback
- [ ] Intensity slider works (0-100%)
- [ ] Audio quality changes with preset/intensity

#### UI/UX
- [ ] Album view: Click album shows album detail
- [ ] Artist view: Click artist shows artist detail
- [ ] Playlist: Can create new playlist
- [ ] Playlist: Can add tracks to playlist
- [ ] Search: Global search finds tracks/albums/artists
- [ ] Theme: Theme toggle button visible
- [ ] Settings: Settings dialog opens
- [ ] Navigation: All sidebar items work

### Auto-Update Testing

#### Development Mode (Not Packaged)
- [ ] Auto-update disabled (expected in dev mode)
- [ ] No update check errors in logs

#### Production Mode (Packaged App)
- [ ] App checks for updates on startup (3s delay)
- [ ] Log shows "Checking for updates..." message
- [ ] No errors in update check
- [ ] **Note**: Actual update won't be available until release is published

### Performance Testing

#### Responsiveness
- [ ] UI remains responsive during library scan
- [ ] No lag when switching views
- [ ] Smooth scrolling in track list
- [ ] Fast search results (< 1 second)

#### Memory Usage
- [ ] Check memory usage: `ps aux | grep auralis`
- [ ] Should be ~200-300 MB for app
- [ ] No significant growth over 5-10 minutes of use

#### CPU Usage
- [ ] Check CPU usage during idle: `top -p $(pgrep -f auralis)`
- [ ] Should be < 5% when idle
- [ ] Should be < 20% during playback with enhancement

### Stress Testing

#### Rapid Interactions
- [ ] Rapidly switch presets (5x in 10 seconds)
- [ ] No audio glitches
- [ ] No UI freezes
- [ ] No crashes

#### Long Session
- [ ] Play music continuously for 5-10 minutes
- [ ] Try different tracks, presets, intensities
- [ ] No crashes
- [ ] No memory leaks (check with `ps`)
- [ ] Audio remains stable

### Error Handling

#### Invalid Operations
- [ ] Try to play non-existent file (if possible)
- [ ] App doesn't crash, shows error gracefully
- [ ] Try extreme intensity values (if possible)
- [ ] App clamps to valid range

#### Edge Cases
- [ ] Empty library handling (before adding folders)
- [ ] Large library (1000+ tracks if available)
- [ ] Network drive (if available)
- [ ] Corrupt audio file (if available)

---

## Known Issues to Verify

These are expected issues documented in release notes:

### Expected Behaviors
- [ ] **Gapless Playback**: Small gap (~100ms) between tracks
  - **Status**: Known issue, workaround is crossfade
- [ ] **Artist Listing**: Slow for 1000+ artists (468ms)
  - **Status**: Known issue, use search instead
- [ ] **Wayland**: Window may not show on first launch
  - **Status**: Restart app if needed

### Unexpected Issues (Report if Found)
- [ ] Crashes: _______________
- [ ] Audio issues: _______________
- [ ] UI bugs: _______________
- [ ] Performance problems: _______________
- [ ] Other: _______________

---

## Logs & Debugging

### Log Locations
- **Electron Logs**: `~/.config/Auralis/logs/`
- **Auto-Update Logs**: Check electron-log output
- **Backend Logs**: Console output during development

### Useful Commands

```bash
# Check if backend is running
lsof -ti:8765

# View process memory/CPU
ps aux | grep -i auralis

# Real-time resource monitoring
top -p $(pgrep -f auralis)

# View logs
tail -f ~/.config/Auralis/logs/main.log

# Kill app processes (if needed)
killall auralis
lsof -ti:8765 | xargs kill -9
```

---

## Test Results Summary

**Build Version**: 1.0.0-beta.1
**Tested By**: _______________
**Test Date**: _______________
**Platform**: Linux (specify distro: _______________)
**Test Duration**: _______________

### Overall Status
- [ ] ✅ PASS - Ready for beta release
- [ ] ⚠️ PASS WITH MINOR ISSUES - Can release with notes
- [ ] ❌ FAIL - Blocking issues found, needs fixes

### Critical Issues Found
1. _______________
2. _______________
3. _______________

### Minor Issues Found
1. _______________
2. _______________
3. _______________

### Recommendations
1. _______________
2. _______________
3. _______________

---

## Sign-Off

**Tester Name**: _______________
**Signature**: _______________
**Date**: _______________

**Build Approved for Release**: [ ] YES [ ] NO

---

*This checklist should be completed before publishing the beta.1 release.*

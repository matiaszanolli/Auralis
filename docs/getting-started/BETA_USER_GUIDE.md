# Auralis Beta User Guide

Welcome to the Auralis Beta! 🎵

Thank you for helping us test and improve Auralis, the professional adaptive audio mastering system.

## Table of Contents

- [What is Auralis?](#what-is-auralis)
- [Installation](#installation)
- [Getting Started](#getting-started)
- [Features](#features)
- [Known Issues](#known-issues)
- [Providing Feedback](#providing-feedback)
- [FAQ](#faq)

---

## What is Auralis?

Auralis is an intelligent music player with professional-grade audio enhancement built-in. Unlike traditional mastering tools that require reference tracks, Auralis uses adaptive processing to automatically enhance your music based on its content.

**Key Features:**
- 🎵 Music player with library management
- ✨ One-click audio enhancement (no reference tracks needed)
- 🎚️ 5 enhancement presets (Adaptive, Gentle, Warm, Bright, Punchy)
- 📊 Real-time audio visualization
- 🎨 Beautiful Aurora-themed UI
- 🔒 100% local processing (complete privacy)
- ⚡ Lightning-fast performance (36.6x real-time)

---

## Installation

### Linux

#### Option 1: AppImage (Recommended)
1. Download `Auralis-1.0.0-beta.1.AppImage`
2. Make it executable:
   ```bash
   chmod +x Auralis-1.0.0-beta.1.AppImage
   ```
3. Double-click to run, or:
   ```bash
   ./Auralis-1.0.0-beta.1.AppImage
   ```

#### Option 2: DEB Package (Debian/Ubuntu)
1. Download `auralis-desktop_1.0.0-beta.1_amd64.deb`
2. Install:
   ```bash
   sudo dpkg -i auralis-desktop_1.0.0-beta.1_amd64.deb
   sudo apt-get install -f  # Fix dependencies if needed
   ```
3. Launch from application menu or:
   ```bash
   auralis
   ```

### Windows

1. Download `Auralis-Setup-1.0.0-beta.1.exe`
2. Run the installer
3. Follow installation prompts
4. Launch from Start Menu or desktop shortcut

### macOS

1. Download `Auralis-1.0.0-beta.1.dmg`
2. Open the DMG file
3. Drag Auralis to Applications folder
4. Launch from Applications

**Note**: macOS may show a security warning. Go to System Preferences → Security & Privacy → Allow.

---

## Getting Started

### First Launch

1. **Start Auralis**: Launch the application
2. **Add Music**: Click "Add Folder" or use Settings → Library → Add Folder
3. **Wait for Scan**: Auralis will scan your music (740+ files/second)
4. **Start Listening**: Click any track to play!

### Adding Your Music Library

#### Method 1: Folder Selection Dialog
1. Click "Add Folder" button (or Settings → Library → Add Folder)
2. Select your music folder
3. Wait for scan to complete
4. Your tracks appear in the library

#### Method 2: Settings Panel
1. Click the gear icon (⚙️) in the sidebar
2. Go to "Library" tab
3. Click "Add Folder to Library"
4. Select folder and wait for scan

### Basic Playback

- **Play Track**: Click any track in your library
- **Pause/Resume**: Click play/pause button in player bar
- **Next/Previous**: Use arrow buttons or keyboard shortcuts
- **Seek**: Click anywhere on the progress bar
- **Volume**: Use volume slider or mouse wheel

### Keyboard Shortcuts

- `Space`: Play/Pause
- `→`: Next track
- `←`: Previous track (or restart current if >3s)
- `↑/↓`: Volume up/down
- `Ctrl/Cmd + F`: Focus search

---

## Features

### 1. Audio Enhancement

**What it does**: Intelligently enhances your music without requiring reference tracks.

**How to use**:
1. Play any track
2. Toggle enhancement ON (magic wand icon ✨)
3. Choose a preset (right panel)
4. Adjust intensity slider (0-100%)

**Presets**:
- **Adaptive** (Default): Intelligent content-aware mastering
- **Gentle**: Subtle enhancement, minimal processing
- **Warm**: Adds warmth and smoothness
- **Bright**: Enhances clarity and presence
- **Punchy**: Increases impact and dynamics

**Performance**: Processes audio in real-time with zero latency!

### 2. Library Management

**Features**:
- Automatic metadata extraction (artist, album, year, genre)
- Album artwork display
- Fast search (sub-5ms response time)
- Sort by title, artist, album, date added
- Favorite tracks
- Recently played tracking
- Smart pagination (handles 50k+ tracks)

**Views**:
- **Songs**: All tracks in your library
- **Albums**: Browse by album with artwork
- **Artists**: Browse by artist
- **Favorites**: Your starred tracks
- **Recently Played**: Your listening history

### 3. Playlists

**Create Playlists**:
1. Click "+ New Playlist" in sidebar
2. Give it a name
3. Right-click tracks → "Add to Playlist"

**Manage Playlists**:
- Reorder tracks (drag & drop)
- Remove tracks (right-click → Remove)
- Play entire playlist
- Edit playlist name/description

### 4. Search

**Global Search** (top bar):
- Searches tracks, albums, and artists
- Real-time results as you type
- Click result to navigate

**Filter** (within views):
- Filter current view
- Works in Songs, Albums, Artists views

### 5. Queue Management

**Add to Queue**:
- Right-click track → "Play Next" or "Add to Queue"
- Click "Play Album" to queue entire album

**View Queue**:
- Click queue icon in player bar
- Reorder, remove, or clear queue
- Shuffle and repeat controls

### 6. Album/Artist Details

**Album View**:
- Click any album card
- See all tracks, play album, add to queue
- View album metadata

**Artist View**:
- Click any artist
- See all albums and tracks by artist
- Play artist radio

### 7. Theme

**Toggle Theme**:
- Click sun/moon icon in sidebar
- Switches between dark and aurora themes
- Theme persists across sessions

### 8. Settings

**Access**: Click gear icon (⚙️) in sidebar

**Tabs**:
- **Enhancement**: Default preset, intensity
- **Library**: Add/remove folders, rescan
- **Playback**: Crossfade, repeat, shuffle defaults
- **About**: Version info, check for updates

---

## Known Issues

### Beta Limitations

#### High Priority (Will Fix Before 1.0)
1. **Gapless Playback**: Small gap between tracks (~100ms)
   - Workaround: Use crossfade in settings
2. **Large Library Load**: First load of 50k+ tracks takes ~5 seconds
   - Subsequent loads are instant (cached)
3. **Artist Listing**: Slow for libraries with 1000+ artists (468ms)
   - Workaround: Use search instead

#### Medium Priority (Post-1.0)
1. **Lyrics Display**: Not yet implemented
2. **Visualizer Performance**: Can lag on older hardware with enhancement enabled
   - Workaround: Disable visualizer in settings
3. **Metadata Editing**: Basic fields only (advanced editing coming soon)

#### Low Priority (Nice to Have)
1. **Cloud Sync**: Not available
2. **Mobile App**: Not planned for 1.0
3. **Plugin System**: Future consideration

### Platform-Specific Issues

**Linux**:
- Wayland: Window may not show on first launch (restart app)
- AppImage: May need to allow execution permissions

**macOS**:
- Security warning on first launch (allow in System Preferences)
- arm64 (M1/M2): Runs via Rosetta 2 (native build coming)

**Windows**:
- Windows Defender may flag installer (false positive)
- Older Windows versions (<10) not tested

---

## Providing Feedback

We value your feedback! Here's how to help:

### Reporting Bugs

**Use GitHub Issues**: https://github.com/matiaszanolli/Auralis/issues

**Include**:
1. **Description**: What happened?
2. **Expected**: What should happen?
3. **Steps to Reproduce**: How to trigger the bug?
4. **System**: OS, version, hardware
5. **Logs**: Check `~/.auralis/logs/` for error logs

**Example**:
```
Title: Audio cuts out when switching presets

Description: When I switch from Adaptive to Warm preset during playback,
the audio cuts out for ~2 seconds before resuming.

Steps:
1. Play any track
2. Enable enhancement
3. Switch preset from Adaptive to Warm
4. Audio cuts out briefly

System: Ubuntu 22.04, AMD Ryzen 5, 16GB RAM
Version: 1.0.0-beta.1
```

### Feature Requests

**Use GitHub Discussions**: https://github.com/matiaszanolli/Auralis/discussions

**Provide**:
- Clear use case
- Why it's valuable
- How you'd use it

### Beta Feedback Form

**Quick Feedback**: [Google Form Link]

**Questions**:
- Overall experience (1-5 stars)
- Most useful feature
- Most frustrating issue
- Would you recommend? (0-10)
- Open comments

---

## FAQ

### General

**Q: Is Auralis free?**
A: Yes! Auralis is open-source (GPL-3.0) and completely free.

**Q: Does it phone home or collect data?**
A: No. All processing is 100% local. Zero telemetry, zero tracking.

**Q: What audio formats are supported?**
A: Input: WAV, FLAC, MP3, OGG, M4A, AAC, WMA
Output (if exporting): WAV, FLAC

**Q: Can I use it for commercial projects?**
A: Yes, GPL-3.0 allows commercial use.

**Q: How is this different from traditional mastering?**
A: Traditional tools require reference tracks. Auralis uses adaptive processing to enhance based on content analysis.

### Performance

**Q: How fast is the processing?**
A: 36.6x real-time. That means processing 1 hour of audio takes ~98 seconds.

**Q: Does it work in real-time during playback?**
A: Yes! Zero latency real-time processing.

**Q: Will it slow down my computer?**
A: No. CPU usage is minimal (<5% on modern hardware).

**Q: How much RAM does it use?**
A: ~200-300 MB for the app, plus ~50 MB per 10k tracks in library.

### Library

**Q: How many tracks can it handle?**
A: Tested with 50k+ tracks. Performance remains excellent with proper pagination.

**Q: Does it modify my original files?**
A: No. Enhancement is applied during playback only. Original files are never touched.

**Q: Can I use it with streaming services?**
A: No. Auralis works with local files only.

**Q: Does it support network/NAS drives?**
A: Yes, but scan performance depends on network speed.

### Audio Enhancement

**Q: Will it make my music sound better?**
A: Depends! Try different presets. Some tracks benefit more than others.

**Q: Can I export enhanced audio?**
A: Not yet. Planned for 1.1.0.

**Q: Does it work with all genres?**
A: Yes. Adaptive mode analyzes content and adjusts accordingly.

**Q: Can I tweak individual parameters?**
A: Not in beta. Advanced controls coming in 1.1.0.

### Technical

**Q: Is the backend written in Python?**
A: Yes. FastAPI backend + React frontend + Electron wrapper.

**Q: Can I run just the backend as a server?**
A: Yes! `python launch-auralis-web.py` runs the web interface.

**Q: Does it support Raspberry Pi?**
A: Not officially, but users report it works (albeit slowly).

**Q: Can I contribute code?**
A: Yes! See CONTRIBUTING.md in the repo.

### Updates

**Q: How do I update?**
A: Auto-update system will notify you when updates are available.

**Q: Can I stay on beta releases?**
A: Yes. Set update channel to "beta" in settings.

**Q: What's the release schedule?**
A: Beta: Every 2-4 weeks. Stable (1.0): When bugs are ironed out.

---

## Support

### Getting Help

**Documentation**: https://github.com/matiaszanolli/Auralis/wiki
**Discussions**: https://github.com/matiaszanolli/Auralis/discussions
**Issues**: https://github.com/matiaszanolli/Auralis/issues

### Community

**Discord**: [Coming Soon]
**Reddit**: r/Auralis [Coming Soon]

---

## Beta Testing Tips

### What to Focus On

1. **Test Different Music**: Try various genres, quality levels
2. **Large Libraries**: Add 1000+ tracks if possible
3. **Rapid Interactions**: Click fast, switch presets quickly
4. **Long Sessions**: Leave it running for hours
5. **Edge Cases**: Corrupt files, weird metadata, huge files

### How to Help Most

1. **Report Bugs**: Even if already reported, +1 helps prioritize
2. **Suggest Improvements**: UI, features, workflows
3. **Share on Social Media**: Help us reach more beta testers
4. **Be Specific**: "Slow" is less useful than "Takes 5s to load 1000 tracks"

---

## Credits

**Lead Developer**: Matias Zanolli
**Contributors**: [See CONTRIBUTORS.md]
**Special Thanks**: Beta testers, open-source community

**Built With**:
- Python, NumPy, SciPy, Numba (audio processing)
- FastAPI (backend)
- React, TypeScript, Material-UI (frontend)
- Electron (desktop wrapper)

---

## License

Auralis is licensed under GPL-3.0. See LICENSE file for details.

---

**Thank you for being part of the Auralis beta! Your feedback shapes the future of this project.** 🎵

*Last Updated: October 26, 2025*
*Version: 1.0.0-beta.1*

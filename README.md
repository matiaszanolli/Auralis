# 🎵 Auralis - Your Music Player with Magical Audio Enhancement

**A beautiful music player that makes your music sound better - automatically.**

Simple like iTunes. Smart like a mastering studio. No complicated settings.

[![License](https://img.shields.io/badge/license-GPL--3.0-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20macOS%20%7C%20Windows-lightgrey.svg)]()
[![Status](https://img.shields.io/badge/status-Beta-orange.svg)]()

📚 **[Complete Documentation](DOCS.md)** | 🏗️ **[Architecture Guide](CLAUDE.md)** | 📊 **[Project Status](PROJECT_STATUS.md)**

---

## ✨ What is Auralis?

Auralis is a **local music player** with professional audio enhancement built-in. Play your music collection with a simple toggle to make it sound better.

**Think:** iTunes meets audio mastering - but simple enough for anyone to use.

### Key Features

- 🎵 **Beautiful Music Player** - Clean, modern interface inspired by Spotify and iTunes
- ✨ **Magical Audio Enhancement** - One-click toggle for professional audio mastering
- 📁 **Library Management** - Scan folders, organize your collection, search instantly
- 🎨 **Audio Visualizer** - Watch your music come alive with real-time visualization
- 🖥️ **Desktop & Web** - Native Electron app or run in your browser
- 🔒 **100% Private** - Your music, your computer, no cloud required
- ⚡ **Blazing Fast** - 52.8x real-time audio processing, 740+ files/second scanning

---

## 🚀 Quick Start

### Option 1: Web Interface (Easiest)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Launch Auralis
python launch-auralis-web.py

# 3. Open browser
http://localhost:8000
```

### Option 2: Desktop App (Recommended)

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Install Node.js dependencies
cd desktop && npm install

# 3. Launch desktop app
npm run dev
```

---

## 📸 Screenshots

### Your Music Collection
Beautiful grid or list view of your library with smart search and filtering.

### Simple Magic Toggle
Play any song → Toggle "Magic" switch → Hear the difference. That's it!

### Audio Visualizer
Watch your music with real-time waveform and spectrum visualization.

---

## 🎯 How to Use

### 1. Add Your Music

**Desktop App:**
- Click the **📁 Scan Folder** button
- Native folder picker opens
- Browse to your music folder
- Click "Select Folder"
- Done! ✅

**Web Interface:**
- Click the **📁 Scan Folder** button
- Type your music folder path (e.g., `/home/user/Music`)
- Press OK
- Done! ✅

### 2. Play Music

- Browse your library (grid or list view)
- Click any track to play
- Use player controls at bottom
- That's it!

### 3. Enable Magic Enhancement

- While playing any song
- Look at bottom-right of player
- Toggle the **✨ Magic** switch
- Hear instant audio enhancement!

**No settings, no presets, no complexity. Just better sound.**

---

## 🎛️ What Makes It Different?

### vs. iTunes/Music.app
- ✅ Works with your local files (no cloud required)
- ✅ Built-in audio enhancement (no plugins needed)
- ✅ Cross-platform (Linux, macOS, Windows)
- ❌ No streaming service (local files only)

### vs. Spotify Desktop
- ✅ Owns your music (no subscription needed)
- ✅ Better sound quality (lossless local files)
- ✅ Audio enhancement built-in
- ❌ No online streaming (your files only)

### vs. VLC/foobar2000
- ✅ Modern, beautiful interface
- ✅ Simple to use (no learning curve)
- ✅ One-click audio enhancement
- ❌ Less advanced customization

**Perfect for:** People who care about sound quality but don't want complexity.

---

## 🔧 Supported Audio Formats

### Input (Playback)
WAV, FLAC, MP3, OGG, M4A, AAC, WMA

### Output (Export)
WAV (16-bit/24-bit PCM), FLAC (16-bit/24-bit PCM)

---

## 🏗️ Architecture

### Simple Two-Tab Interface
1. **Your Music** - Library browser with search and grid/list view
2. **Visualizer** - Real-time audio visualization

### Technology Stack

**Backend (Python):**
- FastAPI for REST API
- SQLite for library database
- Professional DSP algorithms
- Real-time audio processing

**Frontend (React):**
- Material-UI components
- WebSocket for live updates
- Responsive design
- Modern UX

**Desktop (Electron):**
- Native OS integration
- System tray support
- Auto-updates ready

```
auralis/                    # Core audio processing engine
├── core/                   # Mastering algorithms
├── dsp/                    # Digital signal processing
├── analysis/               # Audio analysis tools
├── library/                # SQLite library management
├── player/                 # Audio playback engine
└── io/                     # Multi-format audio I/O

auralis-web/               # Web & Desktop UI
├── backend/               # FastAPI server
│   └── main.py           # API endpoints
└── frontend/              # React app
    └── src/
        └── components/
            ├── CozyLibraryView.tsx      # Library browser
            ├── MagicalMusicPlayer.tsx   # Music player
            └── ClassicVisualizer.tsx    # Visualizer

desktop/                   # Electron wrapper
├── main.js               # Main process
├── preload.js            # IPC bridge
└── package.json          # Desktop config
```

---

## 🧪 Development

### Run Tests

```bash
# Full stack test (backend + frontend + APIs)
python test_full_stack.py

# Backend tests (96 tests, 74% coverage)
python -m pytest tests/backend/ -v

# Core audio processing tests (26 tests)
python -m pytest tests/test_adaptive_processing.py -v

# All tests with coverage
python -m pytest --cov=auralis --cov-report=html tests/
```

### Build Desktop App

```bash
cd desktop

# Development mode
npm run dev

# Build for all platforms
npm run package

# Build for specific platform
npm run package:linux
npm run package:win
npm run package:mac
```

### Frontend Development

```bash
cd auralis-web/frontend

# Install dependencies
npm install

# Development server (hot reload)
npm start

# Build for production
npm run build
```

---

## 📚 Documentation

### Essential Docs
- **[NEXT_STEPS.md](NEXT_STEPS.md)** - Development roadmap and testing guide
- **[UI_SIMPLIFICATION.md](UI_SIMPLIFICATION.md)** - UI design philosophy
- **[LIBRARY_MANAGEMENT_ADDED.md](LIBRARY_MANAGEMENT_ADDED.md)** - Library features
- **[NATIVE_FOLDER_PICKER.md](NATIVE_FOLDER_PICKER.md)** - Native OS integration
- **[CRITICAL_FIXES_APPLIED.md](CRITICAL_FIXES_APPLIED.md)** - Recent bug fixes

### Technical Docs
- **[VERSION_MIGRATION_ROADMAP.md](VERSION_MIGRATION_ROADMAP.md)** - Version management plan
- **[CLAUDE.md](CLAUDE.md)** - Full technical reference (for developers)

---

## 🎯 Roadmap

### ✅ Completed (v0.9)
- [x] Simplified UI (2 tabs instead of 6)
- [x] Library management with folder scanning
- [x] Native OS folder picker (Electron)
- [x] Real-time audio enhancement toggle
- [x] Beautiful music player interface
- [x] Audio visualizer
- [x] WebSocket live updates

### 🔄 In Progress
- [ ] End-to-end testing on clean systems
- [ ] Version management system
- [ ] Auto-update for Electron app

### 📋 Planned (v1.0)
- [ ] Playlist creation and management UI (backend complete)
- [ ] Enhancement presets UI (backend complete: Adaptive, Gentle, Warm, Bright, Punchy)
- [ ] Album art downloader (automatic artwork fetching)
- [ ] Dark/light theme toggle
- [ ] Drag-and-drop folder import
- [ ] Queue management UI (backend complete)

### 🎨 Future Ideas
- [ ] Lyrics display
- [ ] Smart collections (auto-playlists)
- [ ] Keyboard shortcuts
- [ ] Mini player mode
- [ ] Crossfade between tracks
- [ ] Gapless playback

---

## ❓ FAQ

### Q: Is Auralis free?
**A:** Yes! Open source under GPL-3.0 license.

### Q: Does it work offline?
**A:** Yes, 100% local. No internet required after installation.

### Q: What does "Magic" enhancement do?
**A:** Professional audio mastering - balances levels, enhances dynamics, improves clarity. All automatic.

### Q: Will it modify my original files?
**A:** No! Enhancement is applied in real-time during playback only. Your files are never changed.

### Q: Can I export enhanced versions?
**A:** Not yet, but planned for v1.0.

### Q: Why is it called Auralis?
**A:** "Aura" (atmosphere/feeling) + "Audio" = Auralis. The magical aura of your music.

### Q: How is this different from EQ?
**A:** Much more sophisticated - dynamic range optimization, frequency balancing, psychoacoustic EQ, intelligent limiting. Think mastering studio, not just treble/bass knobs.

---

## 🐛 Known Issues

### Backend Connection
**Issue:** "Connecting..." status doesn't turn green
**Fix:** Make sure backend is running first:
```bash
python launch-auralis-web.py
```

### Blank Screen in Electron
**Status:** Fixed in latest version
**If still occurs:** Check DevTools console (F12) for errors

### Large Library Scanning
**Status:** Works but may be slow for 10,000+ files
**Workaround:** Scan smaller folders at a time

---

## 🤝 Contributing

We welcome contributions! Here's how:

1. **Fork** the repository
2. **Create** a feature branch: `git checkout -b feature/amazing-feature`
3. **Commit** your changes: `git commit -m 'Add amazing feature'`
4. **Push** to the branch: `git push origin feature/amazing-feature`
5. **Open** a Pull Request

### Development Guidelines
- Keep it simple (music player first, not a DAW)
- Maintain the clean 2-tab UI
- Write tests for new features
- Update documentation

---

## 📄 License

This project is licensed under the **GPL-3.0 License** - see the [LICENSE](LICENSE) file for details.

### What This Means
- ✅ Free to use, modify, and distribute
- ✅ Can use in commercial projects
- ✅ Must keep source code open if distributed
- ✅ Must use same license for derivatives

---

## 🙏 Acknowledgments

- **Matchering 2.0** - Original audio processing algorithms
- **FastAPI** - Modern Python web framework
- **React & Material-UI** - Beautiful UI components
- **Electron** - Cross-platform desktop apps
- **All contributors** - Making Auralis better every day

---

## 💬 Community

- **Issues:** [GitHub Issues](https://github.com/matiaszanolli/Auralis/issues)
- **Discussions:** [GitHub Discussions](https://github.com/matiaszanolli/Auralis/discussions)
- **Email:** [Project Maintainer](mailto:matiaszanolli@gmail.com)

---

## 🎵 Philosophy

> **"The best music player is the one you actually enjoy using."**

We believe:
- Music should sound great without complicated settings
- Beautiful design matters
- Privacy is important (your music, your computer)
- Simple is better than complex
- Open source builds trust

---

**Made with ❤️ by music lovers, for music lovers.**

**🎵 Rediscover the magic in your music.**

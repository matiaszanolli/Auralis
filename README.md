# 🎵 Auralis - Your Music Player with Magical Audio Enhancement

**A beautiful music player that makes your music sound better - automatically.**

Simple like iTunes. Smart like a mastering studio. No complicated settings.

[![License](https://img.shields.io/badge/license-GPL--3.0-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20Windows%20%7C%20macOS-lightgrey.svg)]()
[![Release](https://img.shields.io/badge/release-v1.2.0--beta.1-green.svg)](https://github.com/matiaszanolli/Auralis/releases/tag/v1.2.0-beta.1)
[![Backend Tests](https://img.shields.io/badge/backend%20tests-850%2B%20total-brightgreen.svg)]()
[![Frontend Tests](https://img.shields.io/badge/frontend%20tests-1084%20passing%2F1425%20total-orange.svg)]()
[![Component Tests](https://img.shields.io/badge/component%20tests-450%2B%20new-brightgreen.svg)]()
[![Status](https://img.shields.io/badge/Phase-A%20Complete-brightgreen.svg)]()

## 📦 Current Version: 1.2.0-beta.1

**🎵 First Desktop Release with Binary Installers (December 2025)**

This release includes **pre-built binaries** for all major platforms:

### Downloads

| Platform | Download | Notes |
|----------|----------|-------|
| **Linux** | [AppImage](https://github.com/matiaszanolli/Auralis/releases/tag/v1.2.0-beta.1) | Universal, make executable and run |
| **Linux** | [.deb](https://github.com/matiaszanolli/Auralis/releases/tag/v1.2.0-beta.1) | Debian/Ubuntu: `sudo dpkg -i <file>` |
| **Windows** | [.exe](https://github.com/matiaszanolli/Auralis/releases/tag/v1.2.0-beta.1) | Run installer |
| **macOS** | [.dmg](https://github.com/matiaszanolli/Auralis/releases/tag/v1.2.0-beta.1) | Drag to Applications |

### Highlights

- ✅ **macOS Support** - First release with native macOS binaries (.dmg)
- ✅ **High-Performance Rust DSP** - 2-5x faster audio analysis via PyO3 bindings
  - HPSS (Harmonic/Percussive Separation), YIN pitch detection, Chroma analysis
  - 25D audio fingerprinting in ~500ms per track
- ✅ **Improved Mastering Algorithm** - Energy-adaptive LUFS targeting
  - Content-aware processing adapts to source characteristics
  - 5 enhancement presets: Adaptive, Gentle, Warm, Bright, Punchy
- ✅ **Enhanced Playback Mode** - Real-time audio enhancement during streaming
- ✅ **Audio Streaming Stability** - Fixed position jumps, buffer underruns, and corruption
- ✅ **Automated CI/CD** - GitHub Actions builds for Linux, Windows, macOS

📖 **[Release Notes](docs/releases/CHANGELOG.md)** | 🔗 **[Development Roadmap](DEVELOPMENT_ROADMAP_1_1_0.md)**

### 🎯 Previous Releases

- **[v1.1.0-beta.5](https://github.com/matiaszanolli/Auralis/releases/tag/v1.1.0-beta.5)** - Audio mastering refinement (Dec 2024)
- **[v1.1.0-beta.3](https://github.com/matiaszanolli/Auralis/releases/tag/v1.1.0-beta.3)** - DRY refactoring & code quality (Nov 2024)
- **[v1.0.0-beta.12](https://github.com/matiaszanolli/Auralis/releases/tag/v1.0.0-beta.12)** - Previous stable release with binaries

---

📚 **[Master Roadmap](docs/MASTER_ROADMAP.md)** | 🏗️ **[Architecture Guide](CLAUDE.md)** | ⚡ **[Performance Optimizations](CRITICAL_OPTIMIZATIONS_IMPLEMENTED.md)** | 📊 **[Test Guidelines](docs/development/TESTING_GUIDELINES.md)** | 🚀 **[Development Roadmap](docs/roadmaps/DEVELOPMENT_ROADMAP_1_1_0.md)**

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
- ⚡ **Blazing Fast** - 36.6x real-time audio processing, 740+ files/second scanning
- ✅ **Well Tested** - 850+ automated tests, production-ready quality, comprehensive test suite

---

## 🚀 Quick Start

### Option 1: Download Binary (Recommended)

Download the latest release from [GitHub Releases](https://github.com/matiaszanolli/Auralis/releases/tag/v1.2.0-beta.1):

**Windows:**
```bash
# 1. Download Auralis-Setup-1.2.0-beta.1.exe
# 2. Run the installer
# 3. Launch Auralis from Start Menu
```

**Linux (AppImage):**
```bash
# 1. Download Auralis-1.2.0-beta.1.AppImage
chmod +x Auralis-1.2.0-beta.1.AppImage
./Auralis-1.2.0-beta.1.AppImage
```

**Linux (Debian/Ubuntu):**
```bash
# 1. Download auralis_1.2.0-beta.1_amd64.deb
sudo dpkg -i auralis_1.2.0-beta.1_amd64.deb
auralis
```

**macOS:**
```bash
# 1. Download Auralis-1.2.0-beta.1.dmg
# 2. Open the DMG and drag Auralis to Applications
# 3. First launch: Right-click → Open (to bypass Gatekeeper)
```

### Option 2: Run from Source (Development)

**Web Interface:**
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Launch Auralis
python launch-auralis-web.py

# 3. Open browser at http://localhost:8765
```

**Desktop App:**
```bash
# 1. Install Python + Node.js dependencies
pip install -r requirements.txt
cd desktop && npm install

# 2. Launch desktop app
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

## 🧪 Testing & Quality

**850+ automated tests** ensure production-ready quality:

- **Backend (Python):** 850+ tests covering audio processing, API, security
- **Frontend (React):** Component and integration tests with Vitest
- **Security:** OWASP Top 10 coverage (SQL injection, XSS, etc.)

### Run Tests

```bash
# Backend tests
python -m pytest tests/ -v

# Skip slow tests
python -m pytest -m "not slow" -v

# Frontend tests
cd auralis-web/frontend
npm test

# With coverage
python -m pytest tests/ --cov=auralis --cov-report=html
```

See [TESTING_GUIDELINES.md](docs/development/TESTING_GUIDELINES.md) for testing philosophy and standards.

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
- **[MASTER_ROADMAP.md](docs/MASTER_ROADMAP.md)** - Complete project roadmap
- **[CLAUDE.md](CLAUDE.md)** - Full technical reference (for developers)
- **[User Guide](docs/getting-started/BETA_USER_GUIDE.md)** - Complete user guide

### Testing Documentation
- **[TESTING_GUIDELINES.md](docs/development/TESTING_GUIDELINES.md)** - **MANDATORY** - Test quality principles
- **[TEST_IMPLEMENTATION_ROADMAP.md](docs/development/TEST_IMPLEMENTATION_ROADMAP.md)** - Path to 2,500+ tests
- **[PHASE1_WEEK3_PROGRESS.md](docs/development/PHASE1_WEEK3_PROGRESS.md)** - Current boundary test progress

### Release Notes
- **[Beta 9.1](docs/archive/releases/RELEASE_NOTES_BETA9.1.md)** - Latest release (Testing Infrastructure)
- **[Beta 9.0](docs/archive/releases/RELEASE_NOTES_BETA9.0.md)** - Previous release
- **[All Releases](docs/archive/releases/)** - Complete release history

---

## 🎯 Roadmap

### ✅ Recently Completed

**v1.2.0-beta.1** (December 2025):
- [x] macOS binaries (.dmg) - First macOS release
- [x] High-performance Rust DSP via PyO3 (2-5x faster)
- [x] Energy-adaptive LUFS mastering algorithm
- [x] Enhanced playback mode with real-time streaming
- [x] Audio streaming stability fixes
- [x] Automated CI/CD for all platforms

**v1.1.x Series** (Oct-Dec 2025):
- [x] 25D audio fingerprinting system
- [x] 850+ automated tests
- [x] Unified streaming architecture
- [x] Query caching (136x speedup)

### 🔄 In Progress

**v1.2.0 Stable:**
- [ ] macOS code signing for Gatekeeper
- [ ] Enhancement presets UI (5 presets ready in backend)
- [ ] Export enhanced audio to file

### 📋 Planned

**v1.3.0:**
- [ ] Album art downloader
- [ ] Dark/light theme toggle
- [ ] Lyrics display
- [ ] Mini player mode

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
**A:** Not yet, but planned for v1.2.0 stable.

### Q: Why is it called Auralis?
**A:** "Aura" (atmosphere/feeling) + "Audio" = Auralis. The magical aura of your music.

### Q: How is this different from EQ?
**A:** Much more sophisticated - dynamic range optimization, frequency balancing, psychoacoustic EQ, intelligent limiting. Think mastering studio, not just treble/bass knobs.

---

## 🐛 Known Issues (v1.2.0-beta.1)

### ⚠️ Current Limitations

**macOS Code Signing**
- macOS builds trigger Gatekeeper warnings (not code-signed)
- **Workaround:** Right-click → Open on first launch
- **Status:** Code signing planned for v1.2.0 stable

**Preset Switching Delay**
- 2-5 second pause when changing presets during playback
- **Workaround:** Select preset before starting playback

### ✅ Recently Fixed

- **Audio position jumps** - Buffer management improvements
- **Buffer underruns** - Health monitoring prevents cascades
- **Backward audio jumps** - Chunk overlap bug resolved
- **WebSocket disconnects** - Proper state cleanup on reconnection

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

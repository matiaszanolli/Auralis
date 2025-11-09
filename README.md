# 🎵 Auralis - Your Music Player with Magical Audio Enhancement

**A beautiful music player that makes your music sound better - automatically.**

Simple like iTunes. Smart like a mastering studio. No complicated settings.

[![License](https://img.shields.io/badge/license-GPL--3.0-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20Windows-lightgrey.svg)]()
[![Release](https://img.shields.io/badge/release-v1.0.0--beta.11.2-orange.svg)](https://github.com/matiaszanolli/Auralis/releases/tag/v1.0.0-beta.11.2)
[![Backend Tests](https://img.shields.io/badge/backend%20tests-850%2B%20total-brightgreen.svg)]()
[![Frontend Tests](https://img.shields.io/badge/frontend%20tests-234%20passing-brightgreen.svg)]()
[![Phase 1](https://img.shields.io/badge/Phase%201%20Week%203-30%2F150%20boundary%20tests-blue.svg)]()

## 📥 Download Beta 11.2

**🎯 Latest Release: Quick Wins - Performance & UX**

| Platform | Download | Size |
|----------|----------|------|
| 🪟 **Windows** | [Auralis Setup 1.0.0-beta.11.2.exe](https://github.com/matiaszanolli/Auralis/releases/download/v1.0.0-beta.11.2/Auralis.Setup.1.0.0-beta.11.2.exe) | 246 MB |
| 🐧 **Linux (AppImage)** | [Auralis-1.0.0-beta.11.2.AppImage](https://github.com/matiaszanolli/Auralis/releases/download/v1.0.0-beta.11.2/Auralis-1.0.0-beta.11.2.AppImage) | 274 MB |
| 🐧 **Linux (DEB)** | [auralis-desktop_1.0.0-beta.11.2_amd64.deb](https://github.com/matiaszanolli/Auralis/releases/download/v1.0.0-beta.11.2/auralis-desktop_1.0.0-beta.11.2_amd64.deb) | 242 MB |

📖 **[User Guide](docs/getting-started/BETA_USER_GUIDE.md)** | 📝 **[Release Notes](RELEASE_NOTES_BETA11.2.md)** | 🔗 **[Full Changelog](https://github.com/matiaszanolli/Auralis/releases)**

### 📚 What's New in Beta 11.2

**⚡ Processing Speed Indicator**

Users can now see the impressive real-time processing performance during audio enhancement!
- **36.6x real-time factor** displayed during audio analysis
- ProcessingToast shows processing speed in bottom-right corner
- Better perception of system capabilities

**🚀 Instant Preset Switching**

Preset switching is now **near-instant** (< 1 second) instead of the previous 2-5 second delay.
- Removed cache-clearing logic that forced reprocessing
- Keep all presets cached for instant toggling
- Background proactive buffering system now works as designed
- Switch between presets smoothly without audio interruption

**Plus all Beta 11.1 features:**
- ✅ **14 Keyboard Shortcuts** restored (Space, ←→, ↑↓, M, 1-4, /, Esc, ?, Ctrl/Cmd+,)
- ✅ **Service-based architecture** - Minification-safe production builds
- ✅ **Zero breaking changes** - All previous features preserved

See [RELEASE_NOTES_BETA11.2.md](RELEASE_NOTES_BETA11.2.md) for complete details.

---

📚 **[Master Roadmap](MASTER_ROADMAP.md)** | 🏗️ **[Architecture Guide](CLAUDE.md)** | 📊 **[Test Guidelines](docs/development/TESTING_GUIDELINES.md)** | 📈 **[Phase 1 Week 3 Progress](docs/development/PHASE1_WEEK3_PROGRESS.md)**

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
- ✅ **Well Tested** - 850+ automated tests, production-ready quality, comprehensive test suite

---

## 🚀 Quick Start

### Option 1: Download Beta Release (Recommended)

**Windows:**
```bash
# 1. Download Auralis Setup 1.0.0-beta.8.exe
# 2. Run the installer
# 3. Launch Auralis from Start Menu
```

**Linux (AppImage):**
```bash
# 1. Download Auralis-1.0.0-beta.8.AppImage
chmod +x Auralis-1.0.0-beta.8.AppImage
./Auralis-1.0.0-beta.8.AppImage
```

**Linux (Debian/Ubuntu):**
```bash
# 1. Download auralis-desktop_1.0.0-beta.8_amd64.deb
sudo dpkg -i auralis-desktop_1.0.0-beta.8_amd64.deb
auralis-desktop
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

### Test Coverage (850+ Tests)

**Current Status (Phase 1 Week 3):**
- **850+ total tests** across comprehensive test suites
- **30 boundary tests** for chunked processing (100% pass rate)
- **Critical invariant tests** (305 tests) - Properties that must always hold
- **Advanced integration tests** (85 tests) - Boundary & integration coverage
- **API security tests** (67 tests) - SQL injection, XSS, authentication
- **Production bug discovery** - Boundary tests caught P1 bug on Day 1

**Backend (Python):**
- **850+ tests** across all test categories
- Invariant testing (critical properties verification)
- Boundary testing (edge cases and limits)
- Integration testing (cross-component behavior)
- Security testing (OWASP Top 10 coverage)
- All critical audio processing paths tested

**Frontend (React/TypeScript):**
- **245 tests** with Vitest + React Testing Library
- **95.5% pass rate** (234 passing, 11 edge cases)
- Component testing with full provider context
- WebSocket integration tests

**Testing Philosophy:**
- **Coverage ≠ Quality** - 100% coverage doesn't mean tests catch bugs
- **Test invariants, not implementation** - Focus on properties that must always hold
- **Test behavior, not code** - What the system does, not how it does it
- See [TESTING_GUIDELINES.md](docs/development/TESTING_GUIDELINES.md) for complete philosophy

### Run Tests

```bash
# Phase 1 Week 1: Critical Invariant Tests (305 tests)
python -m pytest tests/invariants/ -v                  # All critical invariants
python -m pytest -m invariant -v                       # Run by marker

# Phase 1 Week 2: Integration Tests (85 tests)
python -m pytest tests/integration/ -v                 # All integration tests
python -m pytest -m integration -v                     # Run by marker

# Phase 1 Week 3: Boundary Tests (30/150 complete)
python -m pytest tests/boundaries/ -v                  # All boundary tests
python -m pytest tests/boundaries/test_chunked_processing_boundaries.py -v  # Chunked processing (30 tests)

# Backend API tests
python -m pytest tests/backend/ -v
python -m pytest tests/backend/ --cov=auralis-web/backend --cov-report=html

# Core audio processing tests
python -m pytest tests/test_adaptive_processing.py -v

# Frontend tests (245 tests, 95.5% pass rate)
cd auralis-web/frontend
npm test                    # Interactive watch mode
npm run test:run           # Single run
npm run test:coverage      # With coverage report

# Full test suite (850+ tests)
python -m pytest tests/ -v

# Run tests by type
python -m pytest -m unit          # Unit tests only
python -m pytest -m integration   # Integration tests only
python -m pytest -m boundary      # Boundary tests only
python -m pytest -m "not slow"    # Skip slow tests
```

**Test Roadmap:**
- [TEST_IMPLEMENTATION_ROADMAP.md](docs/development/TEST_IMPLEMENTATION_ROADMAP.md) - Path to 2,500+ tests
- [TESTING_GUIDELINES.md](docs/development/TESTING_GUIDELINES.md) - **MANDATORY** quality standards
- [PHASE1_WEEK3_PROGRESS.md](docs/development/PHASE1_WEEK3_PROGRESS.md) - Current boundary test progress

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
- **[MASTER_ROADMAP.md](MASTER_ROADMAP.md)** - Complete project roadmap
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

### ✅ Completed

**Beta.9.1 - Testing Infrastructure** (November 8, 2025):
- [x] **Phase 1 Week 3** - 30/150 boundary tests complete (100% pass rate)
- [x] **Production bug discovery** - P1 bug found by boundary tests on Day 1
- [x] **Comprehensive testing guidelines** - 1,342 lines of mandatory standards
- [x] **Test implementation roadmap** - Path from 445 to 2,500+ tests

**Beta.9.0 - Test Quality Foundation** (November 2025):
- [x] **Phase 1 Week 1** - 305 critical invariant tests
- [x] **Phase 1 Week 2** - 85 advanced integration tests
- [x] **Testing philosophy** - Coverage ≠ Quality
- [x] **850+ total tests** - Comprehensive test suite

**Beta.6 - Enhanced Interactions** (October 30, 2025):
- [x] **Drag-and-drop system** - Playlist and queue management
- [x] **Keyboard shortcuts** - 15+ shortcuts (temporarily disabled)
- [x] **Batch operations** - Multi-select with bulk actions
- [x] **Bug fixes** - Backend imports, deprecations, frontend artwork

**Beta.5 - Audio Fingerprints** (October 28, 2025):
- [x] **25D Audio Fingerprint System** - Cross-genre discovery
- [x] **6 REST API Endpoints** - Similarity search
- [x] **500x Performance** - K-NN graph optimization

**Beta.4 - Unified Streaming** (October 27, 2025):
- [x] **MSE + Multi-Tier Buffer** - Progressive streaming
- [x] **Unified player architecture** - 67% code reduction
- [x] **WebM/Opus encoding** - Efficient streaming

**Beta.1-3 - Foundation** (October 25-26, 2025):
- [x] Simplified UI (2 tabs instead of 6)
- [x] Library management with folder scanning
- [x] Native OS folder picker (Electron)
- [x] Real-time audio enhancement toggle
- [x] Beautiful music player interface
- [x] Audio visualizer
- [x] WebSocket live updates
- [x] Albums & Artists REST APIs with pagination
- [x] Infinite scroll for large libraries (10k+ tracks)
- [x] Query caching (136x speedup)
- [x] Cross-platform builds (Windows + Linux)

### 🔄 In Progress (Phase 1 Week 3)
- [x] **Chunked Processing Boundaries** - 30/30 tests (100% passing)
- [ ] **Pagination Boundaries** - 0/30 tests (next up)
- [ ] **Audio Processing Boundaries** - 0/30 tests
- [ ] **Library Operations Boundaries** - 0/30 tests
- [ ] **String Input Boundaries** - 0/30 tests

### 📋 Planned (v1.0.0 Stable)
- [ ] Enhancement presets UI (backend complete: Adaptive, Gentle, Warm, Bright, Punchy)
- [ ] Export enhanced audio feature
- [ ] Album art downloader (automatic artwork fetching)
- [ ] Dark/light theme toggle
- [ ] macOS build
- [ ] Undo system for batch operations

### 🎨 Future Ideas
- [ ] Lyrics display
- [ ] Mini player mode
- [ ] Advanced crossfade (audio analysis for optimal points)
- [ ] Music similarity graphs
- [ ] Batch metadata editor

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

## 🐛 Known Issues (Beta.6)

### ⚠️ Current Limitations

**Keyboard Shortcuts Temporarily Disabled** (P0)
- **Issue:** Circular dependency in production build minification
- **Status:** Feature complete, disabled for Beta.6 release
- **Fix:** Re-enable in Beta.7 with refactored architecture
- **Details:** See [BETA6_KEYBOARD_SHORTCUTS_DISABLED.md](docs/troubleshooting/BETA6_KEYBOARD_SHORTCUTS_DISABLED.md)

**Playlist Track Order Persistence**
- **Issue:** Drag-reordered tracks may not persist across restarts
- **Status:** Database migration planned for Beta.7
- **Workaround:** Use queue for temporary ordering

**Preset Switching Buffering**
- **Issue:** 2-5 second pause when changing presets during playback
- **Status:** Ongoing optimization
- **Workaround:** Select preset before starting playback

### ✅ Recently Fixed (Beta.2-6)

**Audio fuzziness between chunks** - ✅ FIXED in Beta.2
- Fixed with 3s crossfade and state tracking

**Volume jumps between chunks** - ✅ FIXED in Beta.2
- Fixed with global LUFS analysis

**Gapless playback gaps** - ✅ FIXED in Beta.2
- Pre-buffering reduced gaps from 100ms to <10ms

**Artist listing performance** - ✅ FIXED in Beta.2
- Pagination reduced response from 468ms to 25ms

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

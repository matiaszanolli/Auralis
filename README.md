# 🎵 Auralis - Your Music Player with Magical Audio Enhancement

**A beautiful music player that makes your music sound better - automatically.**

Simple like iTunes. Smart like a mastering studio. No complicated settings.

[![License](https://img.shields.io/badge/license-AGPL--3.0-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20Windows%20%7C%20macOS-lightgrey.svg)]()
[![Release](https://img.shields.io/badge/release-v1.5.0-green.svg)](https://github.com/matiaszanolli/Auralis/releases)
[![Backend Tests](https://img.shields.io/badge/backend%20tests-~5%2C400-brightgreen.svg)]()
[![Frontend Tests](https://img.shields.io/badge/frontend%20tests-~3%2C500-brightgreen.svg)]()
[![Python](https://img.shields.io/badge/python-3.14%2B-blue.svg)]()
[![Node](https://img.shields.io/badge/node-24%2B-blue.svg)]()

## 📦 Current Version: 1.5.0 — First Stable Release

**🎵 Auralis is now stable.** v1.5.0 consolidates everything built since the last binary release (v1.2.0-beta.2, Dec 2025) — two source-only pre-release tags plus a mastering-quality refinement pass, all folded into one stable line.

### Downloads

> ⚠️ **No v1.5.0 binaries yet.** The last release with downloadable binaries is **v1.2.0-beta.2** (Dec 2025) — several months behind current `master`. For all the fixes described below, **build from source** (see Option 2 below); a fresh v1.5.0 binary build is planned as a near-term follow-up.

| Platform | Download (v1.2.0-beta.2) | Notes |
|----------|----------|-------|
| **Linux** | [AppImage](https://github.com/matiaszanolli/Auralis/releases/tag/v1.2.0-beta.2) | Universal, make executable and run |
| **Linux** | [.deb](https://github.com/matiaszanolli/Auralis/releases/tag/v1.2.0-beta.2) | Debian/Ubuntu: `sudo dpkg -i <file>` |
| **Windows** | [.exe](https://github.com/matiaszanolli/Auralis/releases/tag/v1.2.0-beta.2) | Run installer |
| **macOS** | [.dmg](https://github.com/matiaszanolli/Auralis/releases/tag/v1.2.0-beta.2) | Drag to Applications |

### Highlights (since v1.2.0-beta.2)

- ✅ **First stable release** — no longer beta; production-ready quality bar
- ✅ **Mastering pipeline refinement** — Linkwitz-Riley LR4 crossovers for phase-coherent stereo band splitting, fixed headroom calculation for quiet/loud-peak tracks, cosine-interpolated smooth processing curves (intensity, stereo expansion, bass enhancement)
- 🔒 **Concurrency hardening** — resolved a hard deadlock between seek/load/next-track and playback-info reads; fixed resource leaks in the processing engine and cache workers; guarded database-migration races
- ✅ **Large audit-remediation effort** — dozens of concurrency, data-integrity, API-contract, DSP, and security issues resolved (issues #2299–#2472 and beyond)
- ✅ **High-Performance Rust DSP** — 2-5x faster audio analysis via PyO3 bindings (HPSS, YIN pitch detection, Chroma analysis); 25D audio fingerprinting in ~500ms per track
- ✅ **Comprehensive Test Suite** — ~5,400 backend tests, ~3,500 frontend tests

📖 **[Full Changelog](docs/releases/CHANGELOG.md)** | 🔗 **[Roadmap](docs/MASTER_ROADMAP.md)**

### 🎯 Previous Releases

- **[v1.2.0-beta.2](https://github.com/matiaszanolli/Auralis/releases/tag/v1.2.0-beta.2)** - Last binary release; AppImage size optimization (Dec 2025)
- **[v1.1.0-beta.5](https://github.com/matiaszanolli/Auralis/releases/tag/v1.1.0-beta.5)** - Audio mastering refinement (Dec 2025)
- **[v1.1.0-beta.3](https://github.com/matiaszanolli/Auralis/releases/tag/v1.1.0-beta.3)** - DRY refactoring & code quality (Nov 2025)
- **[v1.0.0-beta.12](https://github.com/matiaszanolli/Auralis/releases/tag/v1.0.0-beta.12)** - Previous stable release with binaries

---

📚 **[Master Roadmap](docs/MASTER_ROADMAP.md)** | 🏗️ **[Architecture Guide](CLAUDE.md)** | ⚡ **[Performance Optimizations](docs/optimization/CRITICAL_OPTIMIZATIONS_IMPLEMENTED.md)** | 📊 **[Test Guidelines](docs/development/TESTING_GUIDELINES.md)** | 📖 **[Developer Docs](docs/README.md)**

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
- ✅ **Well Tested** - ~5,400 automated backend tests, ~3,500 frontend tests, production-ready quality

---

## 🚀 Quick Start

### Option 1: Download Binary (last binary release: v1.2.0-beta.2)

Several months behind `master` — see the note above. Download from [GitHub Releases](https://github.com/matiaszanolli/Auralis/releases):

**Windows:**
```bash
# 1. Download Auralis.Setup.1.2.0-beta.2.exe
# 2. Run the installer
# 3. Launch Auralis from Start Menu
```

**Linux (AppImage):**
```bash
# 1. Download Auralis-1.2.0-beta.2.AppImage
chmod +x Auralis-1.2.0-beta.2.AppImage
./Auralis-1.2.0-beta.2.AppImage
```

**Linux (Debian/Ubuntu):**
```bash
# 1. Download auralis-desktop_1.2.0-beta.2_amd64.deb
sudo dpkg -i auralis-desktop_1.2.0-beta.2_amd64.deb
auralis
```

**macOS:**
```bash
# 1. Download Auralis-1.2.0-beta.2.dmg (or -arm64.dmg for Apple Silicon)
# 2. Open the DMG and drag Auralis to Applications
# 3. First launch: Right-click → Open (to bypass Gatekeeper)
```

### Option 2: Run from Source (Recommended — current v1.5.0)

**Web Interface:**
```bash
# 1. Install dependencies (uv manages the Python interpreter + venv)
uv venv && source .venv/bin/activate
uv pip install -r requirements.txt

# 2. Build the Rust DSP module (required)
cd vendor/auralis-dsp && maturin develop && cd ../..

# 3. Launch Auralis
python launch-auralis-web.py

# 4. Open browser at http://localhost:8765
```

**Desktop App:**
```bash
# 1. Install Python + Node.js dependencies
uv venv && source .venv/bin/activate
uv pip install -r requirements.txt
cd vendor/auralis-dsp && maturin develop && cd ../..
cd desktop && npm install

# 2. Launch desktop app
npm run dev
```

---

## 📸 Screenshots

### Album Detail View
View album details with track listings, metadata, and integrated audio enhancement controls.

![Album Detail View](docs/images/screenshots/album-detail.png)

### Albums Grid View
Beautiful grid layout of your music collection with album artwork and metadata.

![Albums Grid View](docs/images/screenshots/albums-grid.png)

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
- FastAPI for REST API + WebSocket streaming
- SQLite for library database
- Professional DSP algorithms (Rust via PyO3 + NumPy)
- Real-time audio processing

**Frontend (React):**
- Material-UI components + a custom design-token system
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
├── backend/               # FastAPI server (REST + WebSocket, :8765)
│   ├── main.py           # App entry point
│   └── routers/          # 18 route handlers
└── frontend/              # React app
    └── src/
        ├── components/    # UI components (library, player, visualizer)
        ├── hooks/         # Domain hooks (player, library, enhancement, websocket)
        ├── store/         # Redux slices
        └── design-system/ # Design tokens (single source of truth)

desktop/                   # Electron wrapper
├── main.js               # Main process
├── preload.js            # IPC bridge
└── package.json          # Desktop config
```

---

## 🧪 Testing & Quality

**~5,400 automated backend tests + ~3,500 frontend tests** ensure production-ready quality:

- **Backend (Python):** ~5,400 tests covering audio processing, API, security
- **Frontend (React):** ~3,500 component and integration tests with Vitest
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
- **[MASTER_ROADMAP.md](docs/MASTER_ROADMAP.md)** - Complete project roadmap and what's actually shipped
- **[CLAUDE.md](CLAUDE.md)** - Full technical reference (for developers)
- **[User Guide](docs/getting-started/BETA_USER_GUIDE.md)** - Complete user guide

### Testing Documentation
- **[TESTING_GUIDELINES.md](docs/development/TESTING_GUIDELINES.md)** - **MANDATORY** - Test quality principles
- **[AUTOMATED_TESTING_GUIDE.md](docs/development/AUTOMATED_TESTING_GUIDE.md)** - Automated testing workflow
- **[TEST_EXECUTION_GUIDE.md](docs/development/TEST_EXECUTION_GUIDE.md)** - How to run the test suites

### Release Notes
- **[CHANGELOG](docs/releases/CHANGELOG.md)** - Full version history
- **[All Release Notes](docs/releases/)** - Per-release notes archive

---

## 🎯 Roadmap

This section is a brief summary — **[MASTER_ROADMAP.md](docs/MASTER_ROADMAP.md)** is the detailed, actively-maintained source of truth (current state, open backlog, longer-term vision).

### ✅ Recently Completed (v1.5.0)

- [x] **First stable release** — production-ready, no longer beta
- [x] Mastering-pipeline refinement (Linkwitz-Riley crossovers, headroom fix, smooth processing curves)
- [x] Large concurrency/data-integrity/security audit-remediation effort (#2299–#2472 and beyond)
- [x] Enhancement presets UI (5 presets: Adaptive, Gentle, Warm, Bright, Punchy)
- [x] Album art downloader (MusicBrainz/iTunes)
- [x] Dark/light theme toggle

### 🔄 Open Backlog

- [ ] macOS code signing for Gatekeeper (binaries currently unsigned)
- [ ] `response_model=` coverage for ~28 backend endpoints (#3838)
- [ ] Rust LUFS measurement → full BS.1770 K-weighting (#4123)
- [ ] Export enhanced audio to file (playback enhancement is real-time only today)

### 📋 Planned

- [ ] Lyrics display (storage exists; no viewer UI yet)
- [ ] Mini player mode (setting exists in Preferences; not yet wired to window behavior)
- [ ] "Find songs like this" discovery UX (similarity API already shipped)
- [ ] Intelligent/flow playlist generation (recommendation engine already shipped)

See **[MASTER_ROADMAP.md §5](docs/MASTER_ROADMAP.md#5-open-backlog-real-tracked)** for the full, current backlog.

---

## ❓ FAQ

### Q: Is Auralis free?
**A:** Yes! Open source under AGPL-3.0 for personal, research, and open-source use. A commercial license is available for proprietary/closed-source use — see [COMMERCIAL_LICENSE.md](COMMERCIAL_LICENSE.md).

### Q: Does it work offline?
**A:** Yes, 100% local. No internet required after installation.

### Q: What does "Magic" enhancement do?
**A:** Professional audio mastering - balances levels, enhances dynamics, improves clarity. All automatic.

### Q: Will it modify my original files?
**A:** No! Enhancement is applied in real-time during playback only. Your files are never changed.

### Q: Can I export enhanced versions?
**A:** Not yet — tracked on the [roadmap](docs/MASTER_ROADMAP.md).

### Q: Why is it called Auralis?
**A:** "Aura" (atmosphere/feeling) + "Audio" = Auralis. The magical aura of your music.

### Q: How is this different from EQ?
**A:** Much more sophisticated - dynamic range optimization, frequency balancing, psychoacoustic EQ, intelligent limiting. Think mastering studio, not just treble/bass knobs.

---

## 🐛 Known Issues (v1.5.0)

### ⚠️ Current Limitations

**macOS Code Signing**
- macOS builds are unsigned (no Gatekeeper certificate) — triggers a Gatekeeper warning
- **Workaround:** Right-click → Open on first launch
- **Status:** Tracked on the roadmap

**No v1.5.0 Binaries Yet**
- The last binary release is v1.2.0-beta.2 (Dec 2025); see Downloads above
- **Workaround:** Build from source to run current v1.5.0

### ✅ Recently Fixed

**v1.5.0** (July 2026):
- **Playback concurrency deadlock** - Fixed a hard deadlock between seek/load/next-track and playback-info reads
- **Resource leaks** - Processing engine and cache workers no longer leak threads/state after failures
- **Database migration concurrency (CRITICAL)** - Inter-process locking prevents corruption
- **Mastering correctness** - Whole-song-peak makeup gain, NaN/Inf guards, smoother processing curves

**v1.2.0-beta.1** (December 2025):
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

Auralis is dual-licensed:

- **Open Source:** [AGPL-3.0](LICENSE) — free for personal use, research, education, and open-source projects.
- **Commercial:** For proprietary, embedded, or closed-source commercial use, a commercial license is required. See [COMMERCIAL_LICENSE.md](COMMERCIAL_LICENSE.md) or contact contacto@matiaszanolli.com.

### What This Means for Open-Source Users
- ✅ Free to use, modify, and distribute
- ✅ Can use in open-source commercial projects
- ✅ Must keep source code open if distributed or deployed as a network service
- ✅ Must use same license (AGPL-3.0) for derivatives

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
- **Email:** [Project Maintainer](mailto:contacto@matiaszanolli.com)

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

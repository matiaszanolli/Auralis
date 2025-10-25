# Auralis - Start Here

**Version**: 1.0.0-alpha.1
**Status**: Working POC (Proof of Concept)
**Last Updated**: October 25, 2025

---

## 🎯 What is Auralis?

Auralis is a professional **adaptive audio mastering system** with desktop and web interfaces. It provides intelligent, content-aware audio processing without requiring reference tracks.

**What makes it unique**:
- ✅ No reference tracks needed (adaptive processing)
- ✅ **36.6x real-time processing speed** (optimized with Numba JIT)
- ✅ Simple UI for end users, powerful API for developers
- ✅ 100% local processing (complete privacy)

---

## 🚀 Quick Start

### For End Users

**Run the desktop app** (Linux):
```bash
# Download and run
./dist/Auralis-1.0.0-alpha.1.AppImage

# Or install the .deb package
sudo dpkg -i dist/auralis-desktop_1.0.0-alpha.1_amd64.deb
```

**Or run the web interface**:
```bash
python launch-auralis-web.py --dev
# Open: http://localhost:8765
```

### For Developers

1. **Read the developer guide**: [CLAUDE.md](CLAUDE.md)
2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   cd desktop && npm install
   ```
3. **Run development environment**:
   ```bash
   npm run dev  # Starts backend + frontend + Electron
   ```

### For Contributors

1. **Understand the architecture**: [CLAUDE.md](CLAUDE.md) - Architecture Overview
2. **Check the roadmap**: [docs/sessions/oct25_alpha1_release/ALPHA_1_BUILD_SUMMARY.md](docs/sessions/oct25_alpha1_release/ALPHA_1_BUILD_SUMMARY.md)
3. **Follow code style**: [CLAUDE.md](CLAUDE.md) - Code Style and Best Practices

---

## 📚 Essential Documentation

### Main Guides
- **[CLAUDE.md](CLAUDE.md)** - Complete developer guide (architecture, setup, best practices)
- **[README.md](README.md)** - User-facing documentation (what is Auralis, installation)
- **[DOCUMENTATION_INDEX.md](DOCUMENTATION_INDEX.md)** - Master navigation hub (find anything)

### Latest Work
- **[docs/sessions/oct25_alpha1_release/](docs/sessions/oct25_alpha1_release/)** - October 25 session
  - Alpha 1 build summary
  - Critical bug fixes (gain pumping, window display)
  - Complete session documentation

### Performance
- **[PERFORMANCE_OPTIMIZATION_QUICK_START.md](PERFORMANCE_OPTIMIZATION_QUICK_START.md)**
  - Installation for optimal speed
  - 36.6x real-time processing
  - Benchmark validation

### Version & Release
- **[docs/versions/RELEASE_GUIDE.md](docs/versions/RELEASE_GUIDE.md)** - How to release
- **[docs/versions/CHANGELOG.md](docs/versions/CHANGELOG.md)** - Release history

---

## 🎵 What Can It Do?

### Current Features (Alpha 1)
- ✅ **Real-time audio mastering** with 4 presets (balanced, warm, bright, punchy)
- ✅ **Desktop application** (Linux AppImage + .deb)
- ✅ **Library management** (tracks, albums, artists, playlists)
- ✅ **High-performance processing** (36.6x real-time speed)
- ✅ **WebSocket real-time updates**
- ✅ **Pagination support** for large libraries (50k+ tracks)

### Coming Soon (Beta 1)
- [ ] Library scan UI (backend complete)
- [ ] Frontend test coverage
- [ ] Windows and macOS builds
- [ ] UI/UX polish

---

## 🔧 Project Status

**Current Release**: 1.0.0-alpha.1 (Working POC)

### What's Working ✅
- Core audio processing (36.6x real-time)
- Desktop application (Linux)
- Real-time mastering (all presets)
- Library management
- API server (74% test coverage)

### Known Rough Edges 📝
- UI/UX needs polish
- Library scan UI not implemented (backend ready)
- Frontend tests need expansion

### Recent Achievements (October 2025)
- ✅ **Performance optimization** - 36.6x real-time (Oct 24)
- ✅ **Version management** - Complete semantic versioning (Oct 24)
- ✅ **Critical bug fixes** - Gain pumping, window display, soft limiting (Oct 25)
- ✅ **Desktop build** - Working Linux AppImage (Oct 25)

---

## 📊 Performance Highlights

From the October 24 optimization session:
- **36.6x real-time processing** (process 1 hour in ~98 seconds)
- **40-70x envelope speedup** (Numba JIT vectorization)
- **1.7x EQ speedup** (NumPy vectorization)
- **Optional dependencies** (graceful fallbacks)

See: [PERFORMANCE_OPTIMIZATION_QUICK_START.md](PERFORMANCE_OPTIMIZATION_QUICK_START.md)

---

## 🐛 Recent Bug Fixes (Oct 25)

### 1. Gain Pumping Fix
**Problem**: Audio degraded after 30 seconds of playback
**Fix**: Replaced stateless compression with proper `AdaptiveCompressor`
**Impact**: Clean audio throughout entire song
**Details**: [docs/sessions/oct25_alpha1_release/GAIN_PUMPING_FIX.md](docs/sessions/oct25_alpha1_release/GAIN_PUMPING_FIX.md)

### 2. Window Display Fix
**Problem**: Backend started but no UI window on Linux
**Fix**: Added timeout fallback for Electron `ready-to-show` event
**Impact**: Application now displays properly on Linux/Wayland
**Details**: [docs/sessions/oct25_alpha1_release/ELECTRON_WINDOW_FIX.md](docs/sessions/oct25_alpha1_release/ELECTRON_WINDOW_FIX.md)

---

## 🎓 Learning Resources

### Architecture Deep-Dives
- [CLAUDE.md](CLAUDE.md) - Complete architecture section
- Two-tier architecture (Web + Desktop)
- Modular DSP system
- Analysis framework

### Audio Processing
- [PROCESSING_BEHAVIOR_GUIDE.md](PROCESSING_BEHAVIOR_GUIDE.md) - All processing modes
- [docs/sessions/oct25_alpha1_release/GAIN_PUMPING_FIX.md](docs/sessions/oct25_alpha1_release/GAIN_PUMPING_FIX.md) - Real-time processing

### Code Organization
- [docs/guides/REFACTORING_QUICK_START.md](docs/guides/REFACTORING_QUICK_START.md) - Refactoring patterns
- [docs/completed/BACKEND_REFACTORING_ROADMAP.md](docs/completed/BACKEND_REFACTORING_ROADMAP.md) - Modular architecture

---

## 🤝 Contributing

### Before You Start
1. Read [CLAUDE.md](CLAUDE.md) - Code style and best practices
2. Check [docs/versions/CHANGELOG.md](docs/versions/CHANGELOG.md) - "Unreleased" section
3. Review recent session docs: [docs/sessions/](docs/sessions/)

### Development Workflow
```bash
# 1. Install dependencies
pip install -r requirements.txt
cd desktop && npm install

# 2. Run tests
python -m pytest tests/backend/ -v        # Backend (fastest)
cd auralis-web/frontend && npm test       # Frontend

# 3. Run development environment
npm run dev  # Backend + Frontend + Electron
```

### Release Process
See: [docs/versions/RELEASE_GUIDE.md](docs/versions/RELEASE_GUIDE.md)

---

## 📞 Support & Community

### Documentation
- **Questions about architecture?** → [CLAUDE.md](CLAUDE.md)
- **How do I...?** → [DOCUMENTATION_INDEX.md](DOCUMENTATION_INDEX.md) - "I want to..." section
- **What's new?** → [docs/versions/CHANGELOG.md](docs/versions/CHANGELOG.md)
- **What's broken?** → [docs/troubleshooting/](docs/troubleshooting/)

### Git Info
- **Repository**: https://github.com/matiaszanolli/Auralis
- **Current Branch**: `master`
- **Main Branch**: `master` (use this for PRs)
- **License**: GPL-3.0

---

## 🎯 Common Tasks

### Run the Application
```bash
# Desktop (Linux)
./dist/Auralis-1.0.0-alpha.1.AppImage

# Web interface (development)
python launch-auralis-web.py --dev

# Full development environment
npm run dev
```

### Build Desktop App
```bash
cd desktop
npm run build:linux    # Linux (AppImage + .deb)
npm run build:win      # Windows (requires VM)
npm run build:mac      # macOS (native)
```

### Run Tests
```bash
# Backend API tests (96 tests, fastest)
python -m pytest tests/backend/ -v

# Core processing tests (26 tests)
python -m pytest tests/test_adaptive_processing.py -v

# Frontend tests
cd auralis-web/frontend
npm test
```

### Performance Benchmarks
```bash
# Quick validation (~30s)
python test_integration_quick.py

# Comprehensive benchmark (~2-3 min)
python benchmark_performance.py
```

---

## 🗺️ Find Your Way

### "I want to..."

**...get started developing**
1. [CLAUDE.md](CLAUDE.md) - "Quick Start for Developers"
2. Install: `pip install -r requirements.txt`
3. Run: `npm run dev`

**...understand the architecture**
1. [CLAUDE.md](CLAUDE.md) - "Architecture Overview"
2. [docs/completed/BACKEND_REFACTORING_ROADMAP.md](docs/completed/BACKEND_REFACTORING_ROADMAP.md)

**...build the desktop app**
1. `cd desktop && npm run build:linux`
2. Find artifacts in `dist/`

**...release a new version**
1. [docs/versions/RELEASE_GUIDE.md](docs/versions/RELEASE_GUIDE.md)
2. `python scripts/sync_version.py <version>`

**...debug an audio issue**
1. [docs/sessions/oct25_alpha1_release/GAIN_PUMPING_FIX.md](docs/sessions/oct25_alpha1_release/GAIN_PUMPING_FIX.md)
2. [PROCESSING_BEHAVIOR_GUIDE.md](PROCESSING_BEHAVIOR_GUIDE.md)

---

## 📈 Project Roadmap

### Alpha → Beta (16-25 hours)
1. Library Scan UI (8-12h)
2. Frontend Tests (4-6h)
3. Multi-platform Builds (2-4h)
4. Documentation Polish (2-3h)

### Beta → 1.0 (TBD)
- Production stability testing
- User documentation
- Performance validation
- Security audit

---

## ⭐ Key Files

### Must-Read Documentation
- **[CLAUDE.md](CLAUDE.md)** - Developer bible
- **[DOCUMENTATION_INDEX.md](DOCUMENTATION_INDEX.md)** - Navigation hub
- **[docs/sessions/oct25_alpha1_release/COMPLETE_SESSION_SUMMARY_OCT25.md](docs/sessions/oct25_alpha1_release/COMPLETE_SESSION_SUMMARY_OCT25.md)** - Latest work

### Core Code
- `auralis/core/hybrid_processor.py` - Main processing engine
- `auralis-web/backend/main.py` - Backend API (614 lines, modular)
- `auralis-web/frontend/src/components/ComfortableApp.tsx` - Main UI
- `desktop/main.js` - Electron wrapper

### Configuration
- `auralis/version.py` - Version info (single source of truth)
- `auralis/core/unified_config.py` - Processing configuration

---

**Welcome to Auralis!** 🎵

**Next Steps**:
1. Choose your path: End User, Developer, or Contributor
2. Read the appropriate documentation
3. Start coding or using Auralis!

**Have questions?** Check [DOCUMENTATION_INDEX.md](DOCUMENTATION_INDEX.md) - it has answers organized by topic and use case.

---

**Last Updated**: October 25, 2025
**Version**: 1.0.0-alpha.1
**Status**: Working POC - Ready for testing and feedback

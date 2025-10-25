# Auralis Documentation Master Index

**Project**: Auralis - Adaptive Audio Mastering System
**Version**: 1.0.0-alpha.1
**Last Updated**: October 25, 2025

---

## 🚀 Quick Start Guides

### For Developers
- **[CLAUDE.md](CLAUDE.md)** - **START HERE** - Complete developer guide
  - Project overview and architecture
  - Setup instructions and key commands
  - Code organization and best practices
  - API documentation and examples

### For End Users
- **[README.md](README.md)** - User-facing documentation
  - What is Auralis?
  - Installation instructions
  - Basic usage guide

### Performance Optimization
- **[PERFORMANCE_OPTIMIZATION_QUICK_START.md](PERFORMANCE_OPTIMIZATION_QUICK_START.md)** - Performance guide
  - Installation for optimal speed (Numba)
  - 36.6x real-time processing
  - Benchmark validation

---

## 📁 Documentation Structure

```
/
├── CLAUDE.md                          # Main developer guide
├── README.md                          # User documentation
├── CHANGELOG.md → docs/versions/      # Release history
├── DOCUMENTATION_INDEX.md             # This file
│
├── docs/
│   ├── README.md                      # Documentation navigator
│   │
│   ├── sessions/                      # Session-specific documentation
│   │   ├── oct24_performance/         # Oct 24: Performance & versioning
│   │   │   └── (See DOCS_INDEX_OCT24.md)
│   │   └── oct25_alpha1_release/      # Oct 25: Alpha 1 build & fixes
│   │       ├── SESSION_OCT25_INDEX.md # **Session overview**
│   │       ├── ALPHA_1_BUILD_SUMMARY.md
│   │       ├── GAIN_PUMPING_FIX.md
│   │       └── ELECTRON_WINDOW_FIX.md
│   │
│   ├── versions/                      # Version management
│   │   ├── VERSIONING_STRATEGY.md
│   │   ├── VERSIONING_IMPLEMENTATION_COMPLETE.md
│   │   ├── RELEASE_GUIDE.md
│   │   ├── CHANGELOG.md
│   │   └── ALPHA_RELEASE_READY.md
│   │
│   ├── completed/                     # Completed features
│   │   ├── BACKEND_REFACTORING_ROADMAP.md
│   │   ├── LARGE_LIBRARY_OPTIMIZATION.md
│   │   ├── PHASE_4_1_COMPLETE.md
│   │   └── TECHNICAL_DEBT_RESOLUTION.md
│   │
│   ├── guides/                        # Implementation guides
│   │   ├── PRESET_ARCHITECTURE_RESEARCH.md
│   │   ├── WEBSOCKET_CONSOLIDATION_PLAN.md
│   │   ├── CHUNKED_STREAMING_DESIGN.md
│   │   └── REFACTORING_QUICK_START.md
│   │
│   ├── troubleshooting/               # Debug and issue resolution
│   │
│   ├── roadmaps/                      # Future planning
│   │   └── VERSION_MIGRATION_ROADMAP.md
│   │
│   └── archive/                       # Historical documentation
│
├── Performance Docs (root level - Oct 24):
│   ├── PERFORMANCE_OPTIMIZATION_QUICK_START.md  # **Quick start**
│   ├── BENCHMARK_RESULTS_FINAL.md
│   ├── PERFORMANCE_REVAMP_FINAL_COMPLETE.md
│   ├── VECTORIZATION_INTEGRATION_COMPLETE.md
│   ├── VECTORIZATION_RESULTS.md
│   ├── PHASE_2_EQ_RESULTS.md
│   └── PERFORMANCE_REVAMP_INDEX.md
│
└── Session Docs (Oct 24 - root level):
    ├── README_OCT24_SESSION.md
    ├── DOCS_INDEX_OCT24.md
    ├── DYNAMICS_EXPANSION_COMPLETE.md
    ├── PROCESSING_BEHAVIOR_GUIDE.md
    ├── RMS_BOOST_FIX.md
    ├── LIBRARY_SCAN_IMPLEMENTATION.md
    ├── BUILD_COMPLETE_OCT24.md
    ├── SESSION_SUMMARY_OCT24.md
    └── IMPORT_FIX.md
```

---

## 📚 Documentation by Topic

### 🏗️ Architecture & Design

**Core Architecture**:
- [CLAUDE.md](CLAUDE.md) - Complete architecture overview
  - Two-tier architecture (Web + Desktop)
  - Processing engine (`auralis/core/`)
  - DSP system (`auralis/dsp/`)
  - Analysis framework (`auralis/analysis/`)

**API Design**:
- [CLAUDE.md](CLAUDE.md) - Backend API section
- `auralis-web/backend/WEBSOCKET_API.md` - WebSocket protocol
- [docs/guides/WEBSOCKET_CONSOLIDATION_PLAN.md](docs/guides/WEBSOCKET_CONSOLIDATION_PLAN.md)
- [docs/guides/CHUNKED_STREAMING_DESIGN.md](docs/guides/CHUNKED_STREAMING_DESIGN.md)

**UI/UX Design**:
- [CLAUDE.md](CLAUDE.md) - UI/UX Design Philosophy section
- Design aesthetic, color palette, component guidelines

---

### ⚡ Performance Optimization

**Quick Start**: [PERFORMANCE_OPTIMIZATION_QUICK_START.md](PERFORMANCE_OPTIMIZATION_QUICK_START.md)

**Detailed Results**:
- [BENCHMARK_RESULTS_FINAL.md](BENCHMARK_RESULTS_FINAL.md) - Complete benchmark data
- [VECTORIZATION_RESULTS.md](VECTORIZATION_RESULTS.md) - Numba JIT deep dive (40-70x)
- [PHASE_2_EQ_RESULTS.md](PHASE_2_EQ_RESULTS.md) - EQ optimization analysis

**Complete Story**:
- [PERFORMANCE_REVAMP_FINAL_COMPLETE.md](PERFORMANCE_REVAMP_FINAL_COMPLETE.md) - All 5 phases
- [VECTORIZATION_INTEGRATION_COMPLETE.md](VECTORIZATION_INTEGRATION_COMPLETE.md) - Integration
- [PERFORMANCE_REVAMP_INDEX.md](PERFORMANCE_REVAMP_INDEX.md) - Navigation guide

**Key Achievements**:
- 36.6x real-time processing speed
- 40-70x envelope follower speedup (Numba JIT)
- 1.7x EQ speedup (NumPy vectorization)
- Optional Numba dependency with graceful fallbacks

---

### 🎵 Audio Processing

**Processing Behaviors**:
- [PROCESSING_BEHAVIOR_GUIDE.md](PROCESSING_BEHAVIOR_GUIDE.md) - All 4 behaviors explained
- [DYNAMICS_EXPANSION_COMPLETE.md](DYNAMICS_EXPANSION_COMPLETE.md) - Expansion implementation

**Critical Fixes**:
- [docs/sessions/oct25_alpha1_release/GAIN_PUMPING_FIX.md](docs/sessions/oct25_alpha1_release/GAIN_PUMPING_FIX.md) - Stateless compression bug
- [RMS_BOOST_FIX.md](RMS_BOOST_FIX.md) - Overdrive fix

**Real-time Processing**:
- [docs/sessions/oct25_alpha1_release/GAIN_PUMPING_FIX.md](docs/sessions/oct25_alpha1_release/GAIN_PUMPING_FIX.md) - Chunk-based processing
- [CLAUDE.md](CLAUDE.md) - Real-time processor architecture

---

### 💾 Library Management

**Core Features**:
- [docs/completed/LARGE_LIBRARY_OPTIMIZATION.md](docs/completed/LARGE_LIBRARY_OPTIMIZATION.md) - Performance optimization
  - Pagination system
  - Database indexes
  - Query result caching (136x speedup)
  - Supports 50k+ tracks

**Metadata Editing**:
- [docs/completed/PHASE_4_1_COMPLETE.md](docs/completed/PHASE_4_1_COMPLETE.md) - CRUD implementation
- 14 editable fields with Mutagen

**Library Scanning**:
- [LIBRARY_SCAN_IMPLEMENTATION.md](LIBRARY_SCAN_IMPLEMENTATION.md) - Backend + frontend plan
- 740+ files/second scanning speed

---

### 🖥️ Desktop Application

**Building**:
- [CLAUDE.md](CLAUDE.md) - Build commands section
- [BUILD_COMPLETE_OCT24.md](BUILD_COMPLETE_OCT24.md) - Build validation
- [docs/sessions/oct25_alpha1_release/ALPHA_1_BUILD_SUMMARY.md](docs/sessions/oct25_alpha1_release/ALPHA_1_BUILD_SUMMARY.md)

**Platform-Specific Issues**:
- [docs/sessions/oct25_alpha1_release/ELECTRON_WINDOW_FIX.md](docs/sessions/oct25_alpha1_release/ELECTRON_WINDOW_FIX.md) - Linux/Wayland fix
- `ELECTRON_BUILD_FIXED.md` - Previous build troubleshooting

---

### 📦 Version Management & Releases

**Versioning System**: [docs/versions/](docs/versions/)
- [VERSIONING_STRATEGY.md](docs/versions/VERSIONING_STRATEGY.md) - Complete strategy
- [VERSIONING_IMPLEMENTATION_COMPLETE.md](docs/versions/VERSIONING_IMPLEMENTATION_COMPLETE.md) - Implementation
- [RELEASE_GUIDE.md](docs/versions/RELEASE_GUIDE.md) - Step-by-step release process

**Release Notes**:
- [CHANGELOG.md](docs/versions/CHANGELOG.md) - All releases (Keep a Changelog format)
- [ALPHA_RELEASE_READY.md](docs/versions/ALPHA_RELEASE_READY.md) - Alpha 1 preparation

**Current Release**:
- [docs/sessions/oct25_alpha1_release/ALPHA_1_BUILD_SUMMARY.md](docs/sessions/oct25_alpha1_release/ALPHA_1_BUILD_SUMMARY.md)
- Version: 1.0.0-alpha.1
- Status: Working POC

---

### 🔧 Backend Development

**Refactoring**:
- [docs/completed/BACKEND_REFACTORING_ROADMAP.md](docs/completed/BACKEND_REFACTORING_ROADMAP.md)
- Modular router architecture (614 lines, down from 1,960)

**Code Organization**:
- [docs/guides/REFACTORING_QUICK_START.md](docs/guides/REFACTORING_QUICK_START.md)
- Module refactoring patterns
- 13 modules refactored, 60% size reduction

**Technical Debt**:
- [docs/completed/TECHNICAL_DEBT_RESOLUTION.md](docs/completed/TECHNICAL_DEBT_RESOLUTION.md)

---

### 🧪 Testing

**Test Coverage**:
- Backend: 74% (96 tests, 100% passing)
- Frontend: Needs expansion (noted in technical debt)

**Performance Testing**:
- [BENCHMARK_RESULTS_FINAL.md](BENCHMARK_RESULTS_FINAL.md)
- Real-world validation with Iron Maiden track

**Test Files**:
- `tests/backend/` - Backend API tests (fastest, most comprehensive)
- `tests/test_adaptive_processing.py` - Core processing (26 tests)
- `test_e2e_processing.py` - End-to-end validation
- `benchmark_performance.py` - Performance benchmarks

---

## 📅 Session Documentation

### October 25, 2025 - Alpha 1 Build & Critical Fixes
**Index**: [docs/sessions/oct25_alpha1_release/SESSION_OCT25_INDEX.md](docs/sessions/oct25_alpha1_release/SESSION_OCT25_INDEX.md)

**Focus**: Desktop application build and bug fixes
**Outcome**: Working POC with 3 critical bugs fixed

**Key Documents**:
- [ALPHA_1_BUILD_SUMMARY.md](docs/sessions/oct25_alpha1_release/ALPHA_1_BUILD_SUMMARY.md)
- [GAIN_PUMPING_FIX.md](docs/sessions/oct25_alpha1_release/GAIN_PUMPING_FIX.md)
- [ELECTRON_WINDOW_FIX.md](docs/sessions/oct25_alpha1_release/ELECTRON_WINDOW_FIX.md)

### October 24, 2025 - Performance & Version Management
**Index**: [DOCS_INDEX_OCT24.md](DOCS_INDEX_OCT24.md)

**Focus**: Performance optimization and versioning system
**Outcome**: 36.6x real-time processing, complete version management

**Key Documents**:
- [README_OCT24_SESSION.md](README_OCT24_SESSION.md) - Session overview
- [PERFORMANCE_OPTIMIZATION_QUICK_START.md](PERFORMANCE_OPTIMIZATION_QUICK_START.md)
- [DYNAMICS_EXPANSION_COMPLETE.md](DYNAMICS_EXPANSION_COMPLETE.md)
- [BUILD_COMPLETE_OCT24.md](BUILD_COMPLETE_OCT24.md)

---

## 🎯 Documents by Use Case

### "I want to get started developing"
1. [CLAUDE.md](CLAUDE.md) - Read "Quick Start for Developers" section
2. Install dependencies: `pip install -r requirements.txt`
3. Run dev environment: `npm run dev`

### "I want to understand the architecture"
1. [CLAUDE.md](CLAUDE.md) - "Architecture Overview" section
2. [docs/completed/BACKEND_REFACTORING_ROADMAP.md](docs/completed/BACKEND_REFACTORING_ROADMAP.md)
3. Browse module structure in `auralis/`

### "I want to optimize performance"
1. [PERFORMANCE_OPTIMIZATION_QUICK_START.md](PERFORMANCE_OPTIMIZATION_QUICK_START.md)
2. Install Numba: `pip install numba`
3. Run benchmarks: `python benchmark_performance.py`

### "I want to build the desktop app"
1. [CLAUDE.md](CLAUDE.md) - "Launch Applications" section
2. `cd desktop && npm run build:linux` (or `:win`, `:mac`)
3. Find artifacts in `dist/`

### "I want to release a new version"
1. [docs/versions/RELEASE_GUIDE.md](docs/versions/RELEASE_GUIDE.md) - Step-by-step guide
2. [docs/versions/VERSIONING_STRATEGY.md](docs/versions/VERSIONING_STRATEGY.md) - Strategy
3. Run: `python scripts/sync_version.py <new-version>`

### "I want to understand what's new"
1. [docs/versions/CHANGELOG.md](docs/versions/CHANGELOG.md) - All releases
2. [docs/sessions/oct25_alpha1_release/ALPHA_1_BUILD_SUMMARY.md](docs/sessions/oct25_alpha1_release/ALPHA_1_BUILD_SUMMARY.md) - Current release
3. [CLAUDE.md](CLAUDE.md) - "Project Status" section

### "I need to debug an audio issue"
1. [docs/sessions/oct25_alpha1_release/GAIN_PUMPING_FIX.md](docs/sessions/oct25_alpha1_release/GAIN_PUMPING_FIX.md) - Common issues
2. [PROCESSING_BEHAVIOR_GUIDE.md](PROCESSING_BEHAVIOR_GUIDE.md) - Processing modes
3. [RMS_BOOST_FIX.md](RMS_BOOST_FIX.md) - Overdrive issues

### "I want to contribute"
1. [CLAUDE.md](CLAUDE.md) - "Code Style and Best Practices"
2. [docs/guides/REFACTORING_QUICK_START.md](docs/guides/REFACTORING_QUICK_START.md)
3. Check [CHANGELOG.md](docs/versions/CHANGELOG.md) for "Unreleased" section

---

## 🔍 Finding Documentation

### By File Type
- **Quick References**: CLAUDE.md, README.md, PERFORMANCE_OPTIMIZATION_QUICK_START.md
- **Complete Guides**: Files ending in `_COMPLETE.md` or `_GUIDE.md`
- **Session Summaries**: Files in `docs/sessions/` or `SESSION_SUMMARY_*.md`
- **Implementation Details**: Files in `docs/completed/`
- **Future Planning**: Files in `docs/roadmaps/`

### By Date
- **Latest**: docs/sessions/oct25_alpha1_release/
- **October 24**: Root level and docs/sessions/oct24_performance/
- **Older**: docs/archive/ and docs/completed/

### By Topic
Use the "Documentation by Topic" section above

---

## 📝 Documentation Standards

### File Naming
- `ALL_CAPS_WITH_UNDERSCORES.md` for important standalone docs
- `lowercase-with-dashes.md` for general documentation
- `YYYY-MM-DD_description.md` for dated documents

### Location
- **Root level**: Most important quick-start docs (CLAUDE.md, README.md)
- **docs/sessions/**: Session-specific work
- **docs/versions/**: Version management
- **docs/completed/**: Finished features
- **docs/guides/**: Implementation guides
- **docs/archive/**: Historical documentation

### Content Structure
All major docs should include:
1. Title and metadata (date, status, version)
2. Quick summary/TL;DR
3. Detailed content with clear sections
4. Code examples where applicable
5. Related documentation links
6. Status/completion indicators

---

## 🔄 Maintenance

### When to Update This Index
- New session completed
- Major documentation reorganization
- New documentation category added
- Significant docs moved or renamed

### Documentation Health Checks
- [ ] All links in this index are valid
- [ ] CLAUDE.md is up to date with latest features
- [ ] CHANGELOG.md includes latest release
- [ ] Session indexes are complete
- [ ] No duplicate documentation

---

**Last Updated**: October 25, 2025
**Maintained By**: Development team
**Next Review**: Before beta.1 release

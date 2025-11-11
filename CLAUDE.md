# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Project-Specific Guidance**: This CLAUDE.md contains Auralis-specific development guidelines. For user-specific preferences across all projects, see `~/.claude/CLAUDE.md`.

**Key Project Principles:**
- Always prioritize improving existing code rather than duplicating logic
- Coverage ≠ Quality: Test behavior and invariants, not implementation
- Modular design: Keep modules under 300 lines, use facade pattern for backward compatibility

---

## ⚡ Quick Start (30 seconds)

```bash
# Install and run
pip install -r requirements.txt
python launch-auralis-web.py --dev    # http://localhost:8765

# Run all tests
python -m pytest tests/ -v

# Run specific test suite
python -m pytest tests/backend/ -v     # API tests
python -m pytest tests/auralis/ -v     # Core audio processing
python -m pytest tests/boundaries/ -v  # Edge cases & boundaries
```

---

## 🎯 Common Development Tasks

### Running the Application
```bash
# Web interface (recommended for development)
python launch-auralis-web.py --dev    # Dev mode, http://localhost:8765
python launch-auralis-web.py           # Production mode

# Desktop application (from root directory)
npm run dev                            # Starts backend + frontend + Electron

# Just the backend API server
cd auralis-web/backend && python -m uvicorn main:app --reload --port 8765

# Frontend only (requires backend running separately)
cd auralis-web/frontend && npm start   # Proxies to http://localhost:8765
```

### Running Tests
```bash
# All tests
python -m pytest tests/ -v

# Specific categories
python -m pytest tests/backend/ -v                    # API endpoints (96 tests)
python -m pytest tests/auralis/ -v                    # Audio processing (24 tests)
python -m pytest tests/boundaries/ -v                 # Boundary conditions (151 tests)
python -m pytest tests/integration/ -v                # Integration tests (85 tests)
python -m pytest tests/invariants/ -v                 # Critical invariants (305 tests)
python -m pytest tests/mutation/ -v                   # Mutation tests (quality validation)

# Run with coverage
python -m pytest tests/ --cov=auralis --cov=auralis-web --cov-report=html

# Run single test file
python -m pytest tests/backend/test_player.py -v

# Run single test
python -m pytest tests/backend/test_player.py::test_play_track -v

# Run tests matching pattern
python -m pytest -k "test_enhance" -v

# Run tests by marker
python -m pytest -m "invariant" -v     # Invariant tests only
python -m pytest -m "boundary" -v      # Boundary tests only
python -m pytest -m "not slow" -v      # Skip slow tests
```

### Making Code Changes

**Backend API (FastAPI):**
```bash
# 1. Edit endpoint in auralis-web/backend/routers/*.py
# 2. Run affected tests
python -m pytest tests/backend/ -v
# 3. Test manually at http://localhost:8765/api/docs (Swagger UI)
# 4. Backend auto-reloads with --reload flag
```

**Core Audio Processing:**
```bash
# 1. Edit in auralis/core/ or auralis/dsp/
# 2. Run core tests
python -m pytest tests/auralis/ -v
# 3. Run validation tests
python -m pytest tests/validation/ -v
# 4. Check performance impact
python benchmark_performance.py
```

**Frontend (React/TypeScript):**
```bash
# 1. Edit in auralis-web/frontend/src/
# 2. Dev server auto-reloads
cd auralis-web/frontend
npm test                               # Interactive test mode
npm run test:run                       # Single test run
npm run build                          # Production build
```

### Code Quality
```bash
# Type checking
mypy auralis/ auralis-web/backend/

# Linting
python -m lint auralis/ auralis-web/backend/

# Code formatting (if set up)
black auralis/ auralis-web/backend/
```

### Building & Packaging
```bash
# Build desktop app for all platforms
make build                  # Runs tests + builds (see Makefile for details)

# Build without tests (faster)
make build-fast

# Package only (for distribution)
make package

# Platform-specific builds
make build-linux
make build-windows          # Windows only
make build-macos            # macOS only

# Clean build artifacts
make clean
```

---

## 📁 Project Structure

**Core Audio Engine** (`auralis/`):
- `core/` - Main processing engine (adaptive mastering, reference mode, hybrid mode)
- `dsp/` - Digital signal processing modules (EQ, dynamics, filtering)
  - `eq/` - 26-band psychoacoustic EQ system
  - `dynamics/` - Compression, limiting, envelope following
  - `utils/` - Audio utilities (normalization, gain, stereo processing)
- `analysis/` - Audio analysis framework (spectrum, loudness, quality metrics)
  - `fingerprint/` - 25D audio fingerprint system (NEW)
  - `ml/` - Machine learning genre classification
  - `quality/` - Quality metrics (frequency response, dynamic range, etc.)
- `library/` - Library management with SQLite backend
  - `repositories/` - Data access layer with pagination support
  - `cache.py` - Query result caching (136x speedup on cache hits)
- `player/` - Audio playback engine with real-time processing
- `io/` - Audio file I/O and format handling
- `optimization/` - Performance optimizations (Numba JIT, NumPy vectorization)

**Web Interface** (`auralis-web/`):
- `backend/` - FastAPI server (614 lines, modular routers)
  - `main.py` - FastAPI app initialization and routes
  - `routers/` - Modular endpoint handlers (player, library, enhancement, etc.)
  - `chunked_processor.py` - Streaming audio processor (30s chunks)
  - `streaming/` - MSE + Multi-Tier Buffer streaming system
- `frontend/` - React/TypeScript UI
  - `components/` - Main UI components (player, library, enhancement panel)
  - `hooks/` - Custom React hooks (player logic, library data, etc.)
  - `services/` - API communication layer
  - `design-system/` - Design tokens and reusable UI primitives

**Desktop Application** (`desktop/`):
- `main.js` - Electron main process (spawns backend, loads frontend)
- `preload.js` - IPC bridge for native file selection

**Tests** (`tests/`):
- `backend/` - API endpoint tests (96 tests, 74% coverage)
- `auralis/` - Audio processing tests (24 tests)
- `boundaries/` - Edge case and boundary tests (151 tests, 101% of target)
- `integration/` - Cross-component integration tests (85 tests)
- `invariants/` - Critical invariant tests (305 tests)
- `mutation/` - Mutation testing for test quality validation
- `validation/` - End-to-end validation tests
- `conftest.py` - Pytest fixtures and configuration

---

## 🏗️ Architecture Patterns & Key Interdependencies

### Data Flow: Library → Processor → Player → WebSocket
1. **LibraryManager** scans folders → SQLite database with caching
2. **HybridProcessor** loads audio → applies DSP pipeline → returns processed frames
3. **EnhancedAudioPlayer** queues tracks → plays with real-time processing
4. **FastAPI backend** exposes REST endpoints + WebSocket for live updates

### Key Classes & Their Relationships
- **LibraryManager** (`auralis/library/manager.py`): Singleton managing SQLite, caching queries via LRU
- **HybridProcessor** (`auralis/core/hybrid_processor.py`): Orchestrates DSP pipeline with pluggable stages
- **ChunkedProcessor** (`auralis-web/backend/chunked_processor.py`): Streams audio in 30s chunks with MSE encoding
- **PlayerStateManager** (`auralis-web/backend/state_manager.py`): Thread-safe WebSocket state synchronization
- **PsychoacousticEQ** (`auralis/dsp/eq/`): 26-band EQ with genre-specific curves

### Critical Performance Patterns
1. **Query Caching**: LibraryManager caches `albums()`, `artists()`, `tracks()` → 136x speedup
2. **Chunked Processing**: Backend splits audio into 30s chunks, processes in parallel
3. **NumPy Vectorization**: DSP operations use np.array broadcasting (1.7x EQ speedup)
4. **Numba JIT** (optional): Envelope follower compilation → 40-70x speedup
5. **MSE Streaming**: Chunks encoded as WebM/Opus for efficient browser playback

### Backend Router Pattern
All API endpoints are modular routers in `auralis-web/backend/routers/`:
- Each router handles a domain (player, library, enhancement, etc.)
- Routers use FastAPI dependency injection for shared state
- Automatically included in `main.py` via `app.include_router()`
- Each router test file mirrors the router directory structure

---

## 🔑 Key Files You'll Modify Most

**Audio Processing:**
- [auralis/core/hybrid_processor.py](auralis/core/hybrid_processor.py) - Main processing orchestrator
- [auralis/dsp/stages.py](auralis/dsp/stages.py) - Processing pipeline stages
- [auralis/core/unified_config.py](auralis/core/unified_config.py) - Processing configuration

**Backend API:**
- [auralis-web/backend/main.py](auralis-web/backend/main.py) - FastAPI app and routes (614 lines)
- [auralis-web/backend/routers/](auralis-web/backend/routers/) - Modular endpoint handlers
- [auralis-web/backend/chunked_processor.py](auralis-web/backend/chunked_processor.py) - Streaming processor

**Frontend UI:**
- [auralis-web/frontend/src/components/ComfortableApp.tsx](auralis-web/frontend/src/components/ComfortableApp.tsx) - Main app layout
- [auralis-web/frontend/src/components/CozyLibraryView.tsx](auralis-web/frontend/src/components/CozyLibraryView.tsx) - Library view (407 lines, refactored)
- [auralis-web/frontend/src/components/BottomPlayerBarUnified.tsx](auralis-web/frontend/src/components/BottomPlayerBarUnified.tsx) - Player controls
- [auralis-web/frontend/src/design-system/](auralis-web/frontend/src/design-system/) - Design tokens (required for all new UI)

**Desktop:**
- [desktop/main.js](desktop/main.js) - Electron process

**Database:**
- [auralis/library/manager.py](auralis/library/manager.py) - Library manager with caching
- [auralis/library/cache.py](auralis/library/cache.py) - Query result caching (136x speedup)
- [auralis/library/repositories/](auralis/library/repositories/) - Data access layer with pagination

---

## ⚠️ Important Gotchas & Common Mistakes

### Port Numbers
- **Backend API**: Port **8765** (NOT 8000)
- **Frontend dev**: Port 3000 (proxies to backend)
- Check with `lsof -ti:8765` if port is in use

### Audio Processing Invariants
These MUST always hold - test them!

```python
# Output sample count must equal input sample count
assert len(output_audio) == len(input_audio), "Sample count changed!"

# Audio arrays are NumPy, not Python lists
processed = processor.process(audio)  # Returns np.ndarray
assert isinstance(processed, np.ndarray)

# Never modify audio in-place
output = audio.copy()  # NOT audio directly
output *= gain  # Then modify the copy
```

### Testing Philosophy (Read First!)
- **Coverage ≠ Quality**: 100% coverage doesn't catch all bugs (proven by overlap bug)
- **Test invariants**: Properties that must always hold
- **Test behavior**: What the system does, not how it does it
- **Test edge cases**: Boundary conditions, empty inputs, maximum values
- **MANDATORY**: Read [docs/development/TESTING_GUIDELINES.md](docs/development/TESTING_GUIDELINES.md)

### API Changes
When adding backend endpoints:
1. Use the modular router pattern (in `routers/` directory)
2. Router is automatically included in `main.py`
3. Use dependency injection for shared state (player, library)
4. Document in [WEBSOCKET_API.md](auralis-web/backend/WEBSOCKET_API.md) if WebSocket
5. Add tests in `tests/backend/`

### Import Patterns
**Use new modular imports:**
```python
from auralis.dsp.eq import PsychoacousticEQ, generate_genre_eq_curve
from auralis.dsp.utils import spectral_centroid, to_db, adaptive_gain_calculation
from auralis.dsp.dynamics import AdaptiveCompressor
from auralis.analysis.quality import QualityMetrics
from auralis.library.repositories import TrackRepository
```

**Legacy imports still work but are deprecated:**
```python
from auralis.dsp.unified import spectral_centroid  # OLD - don't use
from auralis.dsp.psychoacoustic_eq import PsychoacousticEQ  # OLD
```

### Database Operations
- Always use repository pattern (in `auralis/library/repositories/`)
- Use pagination for large result sets
- Queries are automatically cached (configure TTL in `LibraryManager`)
- Default database location: `~/.auralis/library.db`

### Frontend UI Development
**MANDATORY**: Read [docs/guides/UI_DESIGN_GUIDELINES.md](docs/guides/UI_DESIGN_GUIDELINES.md)
- ✅ Use design system tokens (no hardcoded colors/spacing)
- ✅ One component per purpose (no duplicates)
- ✅ Keep components under 300 lines
- ✅ Extract subcomponents if needed
- ❌ Don't create "Enhanced" or variant versions of existing components

### Common Testing Gotchas
1. **AsyncIO Tests**: Use `@pytest.mark.asyncio` for async functions; backend tests may need `await` handling
2. **WebSocket State**: ChunkedProcessor maintains state; tests must initialize PlayerStateManager properly
3. **Audio Fixtures**: Use fixtures from `conftest.py` (sample_audio, test_audio_file); don't create inline
4. **Library Transactions**: Tests may need isolation; check if test needs new LibraryManager instance
5. **Boundary Tests**: When writing boundaries, test both minimum (0, empty, None) and maximum values
6. **Invariant Tests**: If modifying core processors, update invariant tests in `tests/invariants/`

---

## 🧪 Testing Patterns

### Test Structure (Arrange-Act-Assert)
```python
def test_processor_preserves_sample_count():
    """Invariant: Output sample count == input sample count"""
    # Arrange
    audio = np.random.randn(44100)
    processor = AudioProcessor()

    # Act
    output = processor.process(audio)

    # Assert
    assert len(output) == len(audio), "Sample count must be preserved"
```

### Test Markers
```python
@pytest.mark.boundary
def test_maximum_audio_duration():
    """Boundary: Test at extreme values"""
    pass

@pytest.mark.invariant
def test_compression_ratio_invariant():
    """Invariant: Properties that must always hold"""
    pass

@pytest.mark.integration
def test_end_to_end_processing_pipeline():
    """Integration: Test across components"""
    pass

@pytest.mark.mutation
def test_quality_metric_catches_subtle_bugs():
    """Mutation: Designed to catch specific code mutations"""
    pass

@pytest.mark.slow
def test_large_audio_file_processing():
    """Slow test: Skip with -m "not slow" """
    pass
```

### Fixtures for Common Setup
```python
# Available in conftest.py:
@pytest.fixture
def sample_audio():
    """16-bit PCM 44.1kHz audio"""
    pass

@pytest.fixture
def test_audio_file():
    """Path to test WAV file"""
    pass

@pytest.fixture
def hybrid_processor():
    """Configured HybridProcessor instance"""
    pass
```

See [tests/conftest.py](tests/conftest.py) for all available fixtures.

---

## 📊 Test Organization (850+ tests)

**Phase 1 - Complete (541 tests):**
- ✅ Week 1: 305 critical invariant tests
- ✅ Week 2: 85 advanced integration tests
- ✅ Week 3: 151 boundary tests (101% of target)

**Key Test Files:**
- `tests/backend/` - API tests (96 tests)
- `tests/auralis/` - Audio processing (24 tests)
- `tests/boundaries/` - Edge cases (151 tests)
- `tests/integration/` - Cross-component (85 tests)
- `tests/invariants/` - Critical invariants (305 tests)
- `tests/mutation/` - Test quality validation
- `tests/validation/` - End-to-end validation

**Running Test Suites:**
```bash
python -m pytest tests/boundaries/ -v              # All 151 boundary tests
python -m pytest tests/boundaries/test_chunked_processing_boundaries.py -v  # Just chunked (31)
python -m pytest tests/boundaries/test_pagination_boundaries.py -v          # Just pagination (30)
python -m pytest -m "invariant" -v                  # All invariant tests
python -m pytest -m "not slow" -v                   # Skip slow tests
```

---

## 🔧 Performance & Optimization

### Performance Metrics
- **Real-time factor**: 36.6x (process 1 hour in ~98 seconds)
- **Envelope follower**: 40-70x speedup with Numba JIT
- **EQ processing**: 1.7x speedup with NumPy vectorization
- **Cache hits**: 136x faster queries with LRU cache

### Optimizations Used
```bash
# 1. Numba JIT compilation (optional, ~2-3x overall speedup)
pip install numba

# 2. NumPy vectorization (included, 1.7x EQ speedup)
# 3. Query result caching (included, 136x speedup)
# 4. Memory pools and SIMD (included)
```

### Checking Performance
```bash
# Quick validation (~30 seconds)
python tests/validation/test_integration_quick.py

# Comprehensive benchmark (~2-3 minutes)
python benchmark_performance.py
```

---

## 🎵 Key Processing Concepts

### Processing Modes
1. **Adaptive** (default): Intelligent mastering without reference tracks
2. **Reference**: Traditional reference-based mastering
3. **Hybrid**: Combines reference guidance with adaptive intelligence

### Processing Presets
- Adaptive, Gentle, Warm, Bright, Punchy

### Audio Fingerprint System (NEW)
25-dimensional acoustic fingerprint for intelligent processing:
- **Frequency** (7D): Bass, mids, treble distribution
- **Dynamics** (3D): Loudness, crest factor, compression
- **Temporal** (4D): Tempo, rhythm, transients
- **Spectral** (3D): Tonal characteristics
- **Harmonic** (3D): Vocals vs drums detection
- **Variation** (3D): Loudness dynamics
- **Stereo** (2D): Width and phase

Automatically used by `HybridProcessor` for intelligent parameter selection.

---

## 📚 Documentation References

**Development Guidelines:**
- [TESTING_GUIDELINES.md](docs/development/TESTING_GUIDELINES.md) - **MANDATORY** test quality
- [TEST_IMPLEMENTATION_ROADMAP.md](docs/development/TEST_IMPLEMENTATION_ROADMAP.md) - Testing roadmap

**Architecture & Design:**
- [docs/guides/UI_DESIGN_GUIDELINES.md](docs/guides/UI_DESIGN_GUIDELINES.md) - UI requirements
- [docs/guides/MULTI_TIER_BUFFER_ARCHITECTURE.md](docs/guides/MULTI_TIER_BUFFER_ARCHITECTURE.md) - Streaming architecture
- [docs/guides/AUDIO_FINGERPRINT_GRAPH_SYSTEM.md](docs/guides/AUDIO_FINGERPRINT_GRAPH_SYSTEM.md) - Fingerprint system

**Performance:**
- [PERFORMANCE_OPTIMIZATION_QUICK_START.md](PERFORMANCE_OPTIMIZATION_QUICK_START.md) - Optimization guide
- [LARGE_LIBRARY_OPTIMIZATION.md](docs/completed/LARGE_LIBRARY_OPTIMIZATION.md) - Library performance

**Complete Index:**
- [docs/README.md](docs/README.md) - Documentation index (all 55 files)

---

## 🚀 Release & Version Management

**Version File**: [auralis/version.py](auralis/version.py)

```bash
# Check current version
python -c "from auralis.version import get_version; print(get_version())"

# Bump version (updates all files)
python scripts/sync_version.py 1.0.0-beta.13

# Git workflow for releases
git commit -am "chore: bump version to X.Y.Z"
git tag -a vX.Y.Z -m "Release vX.Y.Z"
git push origin master && git push origin vX.Y.Z
```

**Current Version**: 1.0.0-beta.12 (see README.md for latest)

---

## 🐛 Troubleshooting

### Backend Won't Start
```bash
# Check port is free
lsof -ti:8765 | xargs kill -9

# Check dependencies
pip install -r requirements.txt

# Run directly to see errors
cd auralis-web/backend && python -m uvicorn main:app --reload
```

### Tests Failing
```bash
# Run with verbose output
python -m pytest tests/ -vv --tb=long

# Check test dependencies
pip install -r requirements.txt
pip install pytest pytest-cov pytest-asyncio

# Run single test to isolate issue
python -m pytest tests/backend/test_player.py::test_play_track -vv

# Run only fast tests (skip slow ones)
python -m pytest -m "not slow" -v
```

### Audio Files Not Found
```bash
# Check test file location
ls test_files/
cd tests && python -m pytest test_*.py
```

### Frontend Won't Build
```bash
cd auralis-web/frontend
rm -rf node_modules package-lock.json
npm install
npm run build
```

### Database Errors
```bash
# Reset database (WARNING: deletes all library data)
rm ~/.auralis/library.db
# Will be recreated on next app launch
```

### Performance Debugging
```bash
# Profile audio processing
python -m cProfile -s cumtime -o profile.stats auralis/core/hybrid_processor.py
python -m pstats profile.stats

# Check memory usage during library scan
watch -n 1 'ps aux | grep python'

# Benchmark specific operation
python benchmark_performance.py

# Check query cache effectiveness
python -c "from auralis.library import LibraryManager; m = LibraryManager(); print(m.cache_info())"
```

---

## 💾 Repository Info

- **Git Status**: Current branch `master`
- **Main Branch**: `master` (use for PRs)
- **License**: GPL-3.0
- **Project Name**: Auralis (matchering-player)

---

## 🔗 Useful Links

- **GitHub**: https://github.com/matiaszanolli/Auralis
- **API Docs**: http://localhost:8765/api/docs (when running)
- **WebSocket Protocol**: [auralis-web/backend/WEBSOCKET_API.md](auralis-web/backend/WEBSOCKET_API.md)
- **Release Downloads**: https://github.com/matiaszanolli/Auralis/releases

---

## Notes from ~/.claude/CLAUDE.md

- Always prioritize improving existing code rather than duplicating logic
- In this computer, the worker project lives in ../worker_aithentia relative to this project
- The backend is properly deployed at https://api.test.aithentia.com:8000/

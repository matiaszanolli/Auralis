# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick Start for Developers

**First time here? Start with:**
```bash
# 1. Install dependencies
pip install -r requirements.txt
cd desktop && npm install

# 2. Run the development environment
npm run dev                           # Starts backend + frontend + Electron

# 3. Or launch web interface only
python launch-auralis-web.py --dev   # http://localhost:8765
```

**Key files to know:**
- [auralis/core/hybrid_processor.py](auralis/core/hybrid_processor.py) - Main audio processing engine
- [auralis-web/backend/main.py](auralis-web/backend/main.py) - Backend API server (614 lines, modular routers)
- [auralis-web/backend/routers/](auralis-web/backend/routers/) - API endpoint routers (player, library, enhancement, etc.)
- [auralis-web/frontend/src/components/ComfortableApp.tsx](auralis-web/frontend/src/components/ComfortableApp.tsx) - Main UI component
- [desktop/main.js](desktop/main.js) - Electron main process

**Running tests:**
```bash
# Backend Python tests (850+ tests across all categories)
python -m pytest tests/backend/ -v                    # API tests (96 tests, 74% coverage)
python -m pytest tests/auralis/ -v                    # Real-time processing tests (24 tests, all passing ✅)
python -m pytest tests/test_adaptive_processing.py -v  # Core processing (26 tests)

# Phase 1 Week 1: Critical Invariant Tests (305 tests)
python -m pytest tests/invariants/ -v                 # All critical invariants
python -m pytest -m invariant -v                      # Run by marker

# Phase 1 Week 2: Advanced Integration Tests (85 tests)
python -m pytest tests/integration/ -v                # All integration tests
python -m pytest -m integration -v                    # Run by marker

# Phase 1 Week 3: Boundary Tests (151/150 complete - 101%)
python -m pytest tests/boundaries/ -v                 # All boundary tests (151 tests)
python -m pytest tests/boundaries/test_chunked_processing_boundaries.py -v  # Chunked processing (31 tests)
python -m pytest tests/boundaries/test_pagination_boundaries.py -v          # Pagination (30 tests)
python -m pytest tests/boundaries/test_audio_processing_boundaries.py -v    # Audio processing (30 tests)
python -m pytest tests/boundaries/test_library_operations_boundaries.py -v  # Library operations (30 tests)
python -m pytest tests/boundaries/test_string_input_boundaries.py -v        # String inputs (30 tests)

# Validation tests (preset validation, E2E testing)
python -m pytest tests/validation/ -v                 # All validation tests
python -m pytest tests/validation/test_preset_integration.py -v  # Preset integration
python -m pytest tests/auralis/analysis/test_fingerprint_integration.py -v  # 25D fingerprint (4 tests)

# Mutation Testing (Beta 9+)
python -m pytest tests/mutation/ -v                   # Mutation test suite
mutmut run --paths-to-mutate=auralis/library/cache.py  # Run mutation testing

# Run all tests (from root directory)
npm test                                 # Runs Python pytest suite
npm run test:coverage                    # With coverage report

# Frontend tests (245 tests, 234 passing, 11 failing)
# ⚠️ KNOWN ISSUES:
# - Gapless playback: 11 tests failing (needs investigation)
cd auralis-web/frontend
npm test                                 # Interactive Vitest
npm run test:run                         # Single run
npm run test:coverage                   # Coverage report
```

**🎯 MANDATORY: Test Quality Guidelines**
- **Read**: [docs/development/TESTING_GUIDELINES.md](docs/development/TESTING_GUIDELINES.md) - **REQUIRED** for all contributors
- **Roadmap**: [docs/development/TEST_IMPLEMENTATION_ROADMAP.md](docs/development/TEST_IMPLEMENTATION_ROADMAP.md)
- **Key Principle**: Test **behavior** and **invariants**, not implementation details
- **Coverage ≠ Quality**: 100% coverage doesn't mean tests catch bugs (see overlap bug case study)

## Project Overview

**Auralis** is a professional adaptive audio mastering system with both desktop (Electron) and web (FastAPI + React) interfaces. The system provides intelligent, content-aware audio processing without requiring reference tracks.

**Target Users:**
- **End Users**: Music lovers who want a simple music player with one-click audio enhancement
- **Developers**: Audio engineers, researchers integrating audio processing APIs

**What makes it unique:**
- No reference tracks needed (adaptive processing)
- **High-performance processing** (36.6x real-time, optimized with Numba JIT + vectorization)
- Simple UI for end users, powerful API for developers
- 100% local processing (no cloud, complete privacy)

## Essential Commands

### Launch Applications
```bash
# Web interface (recommended for development and production)
python launch-auralis-web.py           # Production mode (http://localhost:8765)
python launch-auralis-web.py --dev     # Development mode with hot reload

# Electron desktop application (from desktop/ directory)
cd desktop && npm run dev              # Development mode (starts backend + frontend + Electron)
cd desktop && npm run build            # Build desktop application

# Simplified workflow from root directory (requires desktop dependencies installed)
npm run dev                            # Alias for desktop dev mode (via scripts/dev.js)
npm run build                          # Alias for desktop build (via scripts/build.js)
npm run package                        # Package for current platform (via scripts/package.js)
npm run package:linux                  # Package for Linux (.AppImage, .deb)
npm run package:win                    # Package for Windows
npm run package:mac                    # Package for macOS
```

### Testing
```bash
# Backend tests (850+ tests across all categories)
python -m pytest tests/backend/ -v                     # API endpoint tests (96 tests)
python -m pytest tests/auralis/ -v                     # Real-time processing (24 tests, all passing ✅)
python -m pytest tests/test_adaptive_processing.py -v  # Core processing tests (26 tests)

# Phase 1 Week 1: Critical Invariant Tests (305 tests)
python -m pytest tests/invariants/ -v                  # All critical invariants
python -m pytest -m invariant -v                       # Run by marker

# Phase 1 Week 2: Advanced Integration Tests (85 tests)
python -m pytest tests/integration/ -v                 # All integration tests
python -m pytest -m integration -v                     # Run by marker

# Phase 1 Week 3: Boundary Tests (151/150 complete - 101%)
python -m pytest tests/boundaries/ -v                  # All boundary tests (151 tests)
python -m pytest tests/boundaries/test_chunked_processing_boundaries.py -v  # Chunked processing (31 tests)
python -m pytest tests/boundaries/test_pagination_boundaries.py -v          # Pagination (30 tests)
python -m pytest tests/boundaries/test_audio_processing_boundaries.py -v    # Audio processing (30 tests)
python -m pytest tests/boundaries/test_library_operations_boundaries.py -v  # Library operations (30 tests)
python -m pytest tests/boundaries/test_string_input_boundaries.py -v        # String inputs (30 tests)

# Validation tests (organized Oct 27, 2025)
python -m pytest tests/validation/ -v                  # All validation tests
python -m pytest tests/validation/test_preset_integration.py -v  # Preset integration
python -m pytest tests/validation/test_comprehensive_presets.py  # Comprehensive preset validation
python -m pytest tests/validation/test_e2e_processing.py         # End-to-end processing
python -m pytest tests/auralis/analysis/test_fingerprint_integration.py -v  # 25D fingerprint (4 tests)

# Mutation Testing (Beta 9+)
python -m pytest tests/mutation/ -v                    # Mutation test suite
mutmut run --paths-to-mutate=auralis/library/cache.py  # Run mutation testing

# Run tests by marker (see pytest.ini for all markers)
python -m pytest -m unit          # Unit tests only
python -m pytest -m integration   # Integration tests only
python -m pytest -m invariant     # Critical invariant tests
python -m pytest -m boundary      # Boundary tests
python -m pytest -m mutation      # Mutation tests
python -m pytest -m "not slow"    # Skip slow tests
python -m pytest -m audio         # Audio processing tests only

# See TEST_FIX_COMPLETE.md for details on fixed real-time processing tests
# See TEST_ORGANIZATION_COMPLETE.md for test structure details
# ⚠️ TODO: Add regression tests for Oct 25 bug fixes (gain pumping, soft limiter)
# ⚠️ TODO: Fix 11 failing frontend tests (gapless playback component)

# Frontend tests (245 tests, 234 passing, 11 failing)
cd auralis-web/frontend
npm test                    # Interactive Vitest
npm run test:run            # Single run
npm run test:coverage       # Generate coverage report

# Coverage reports
python -m pytest tests/backend/ --cov=auralis-web/backend --cov-report=html
python -m pytest tests/auralis/ --cov=auralis/player/realtime --cov-report=html

# Performance benchmarks and optimization tests
python tests/validation/test_integration_quick.py    # Quick optimization validation (~30s)
python benchmark_performance.py                      # Comprehensive performance benchmark (~2-3 min)
python benchmark_vectorization.py                    # Envelope follower benchmark (40-70x speedup)
python benchmark_eq_parallel.py                      # EQ optimization benchmark (1.7x speedup)
```

**Test Markers** (defined in [pytest.ini](pytest.ini)):
- `@pytest.mark.unit` - Unit tests for individual components
- `@pytest.mark.integration` - Integration tests across components
- `@pytest.mark.invariant` - Critical invariant tests (properties that must always hold)
- `@pytest.mark.boundary` - Boundary tests (edge cases at input domain limits)
- `@pytest.mark.exact` - Exact boundary tests (at precise limits)
- `@pytest.mark.empty` - Empty input tests
- `@pytest.mark.single` - Single item tests
- `@pytest.mark.mutation` - Mutation tests (validate test effectiveness)
- `@pytest.mark.slow` - Long-running tests (skip with `-m "not slow"`)
- `@pytest.mark.audio` - Tests requiring audio processing
- `@pytest.mark.performance` - Performance benchmarks
- `@pytest.mark.security` - Security tests (SQL injection, XSS, etc.)
- `@pytest.mark.load` - Load and stress tests
- `@pytest.mark.edge_case` - Edge case tests
- See [pytest.ini](pytest.ini) for complete list

**Critical Invariants to Test** (Examples):

When adding features with chunking, pagination, or streaming, always test these invariants:

```python
# Chunked Processing Invariants
def test_overlap_is_appropriate_for_chunk_duration():
    """Invariant: Overlap < CHUNK_DURATION / 2 prevents duplicate audio"""
    assert OVERLAP_DURATION < CHUNK_DURATION / 2, \
        f"Overlap {OVERLAP_DURATION}s too large for {CHUNK_DURATION}s chunks"

def test_chunks_cover_entire_duration_no_gaps():
    """Invariant: Sum(chunks) = original audio duration"""
    chunks = [processor.process_chunk(i) for i in range(total_chunks)]
    concatenated = np.concatenate(chunks)
    assert len(concatenated) == len(original_audio), "Gap/overlap detected"

# Pagination Invariants
def test_pagination_returns_all_items_exactly_once():
    """Invariant: All items returned, no duplicates"""
    all_ids = set()
    offset = 0
    while True:
        items = get_items(limit=50, offset=offset)
        if not items: break
        assert not (all_ids & {i.id for i in items}), "Duplicate found"
        all_ids.update(i.id for i in items)
        offset += 50
    assert len(all_ids) == get_total_count()

# Audio Processing Invariants
def test_processing_preserves_sample_count():
    """Invariant: Output sample count == input sample count"""
    processed = processor.process(audio)
    assert len(processed) == len(audio), "Sample count changed"
```

See [TESTING_GUIDELINES.md](docs/development/TESTING_GUIDELINES.md) for complete testing philosophy and case studies.

### Testing Roadmap & Progress

**Current Focus (Phase 1)**: ✅ **COMPLETE** - All 3 weeks finished
- **Week 1**: ✅ 305 invariant tests (100% passing)
- **Week 2**: ✅ 85 integration tests (100% passing)
- **Week 3**: ✅ 151 boundary tests (100% passing)
- **Total Phase 1**: 541 tests complete
- **Next**: Phase 2 Week 4 - Performance Tests (100 tests planned)

**Phase 1 Completed**:
- ✅ Week 1 (305 invariant tests) - Properties that must always hold
- ✅ Week 2 (85 integration tests) - Cross-component behavior
- ✅ Week 3 (151 boundary tests) - Edge cases and limits (COMPLETE - 101% of target)

**Testing Documentation**:
- [TESTING_GUIDELINES.md](docs/development/TESTING_GUIDELINES.md) - **MANDATORY** - Test quality principles
- [TEST_IMPLEMENTATION_ROADMAP.md](docs/development/TEST_IMPLEMENTATION_ROADMAP.md) - Path to 2,500+ tests
- [PHASE1_WEEK3_PLAN.md](docs/testing/PHASE1_WEEK3_PLAN.md) - Boundary testing plan (150 tests)
- [PHASE1_WEEK3_COMPLETE.md](docs/testing/PHASE1_WEEK3_COMPLETE.md) - Boundary testing completion (151 tests, 100% passing)
- [MUTATION_TESTING_GUIDE.md](docs/testing/MUTATION_TESTING_GUIDE.md) - Mutation testing framework
- [PHASE3_WEEK9_COMPLETE.md](docs/testing/PHASE3_WEEK9_COMPLETE.md) - Mutation testing results

**Key Learnings**:
- ✅ **Production bug found**: Boundary tests caught P1 chunked processing bug on Day 1
- ✅ **Coverage ≠ Quality**: Overlap bug had 100% coverage but zero detection
- ✅ **Invariants work**: Testing "overlap < chunk_duration/2" would have caught the bug

### Mutation Testing (Beta 9+)

**Purpose**: Validate that tests actually catch bugs by intentionally introducing code mutations.

**Framework**: mutmut + pytest

**Quick Start**:
```bash
# Run mutation testing on cache module
mutmut run --paths-to-mutate=auralis/library/cache.py

# View results
mutmut results

# Show specific mutant
mutmut show 1
```

**Current Results**:
- **Cache module**: 13/13 mutants killed (100% mutation score)
- **Iteration 3**: All critical paths validated
- **Test effectiveness**: ✅ Confirmed (tests catch real bugs)

**Documentation**: See [MUTATION_TESTING_GUIDE.md](docs/testing/MUTATION_TESTING_GUIDE.md)

### Supported Audio Formats
- **Input**: WAV, FLAC, MP3, OGG, M4A, AAC, WMA
- **Output**: WAV (16-bit/24-bit PCM), FLAC (16-bit/24-bit PCM)

## Architecture Overview

### Two-Tier Architecture
The project has two parallel UI implementations sharing the same Python audio processing backend:

1. **Web Stack**: FastAPI backend + React frontend + optional Electron wrapper
2. **Python Core**: Unified audio processing engine (`auralis/`) used by both interfaces

### Core Processing Engine (`auralis/core/`)

**Main Components:**
- **`hybrid_processor.py`** - Main processing engine with three modes:
  - **Adaptive Mode** (primary): Intelligent mastering without reference tracks
  - **Reference Mode**: Traditional reference-based mastering
  - **Hybrid Mode**: Combines reference guidance with adaptive intelligence
- **`unified_config.py`** - Configuration system with genre profiles and adaptive settings

**Analysis Components (`core/analysis/`):**
- `content_analyzer.py` - ContentAnalyzer for adaptive processing
- `target_generator.py` - Adaptive parameter generation based on content analysis

**Processing Components (`core/processors/`):**
- `reference_mode.py` - Traditional reference-based matching algorithm

### Advanced DSP System (`auralis/dsp/`)

Professional-grade digital signal processing with modular architecture:

**Core Modules:**
- `basic.py` - Basic DSP utilities (RMS, normalize, amplify, mid-side processing)
- `advanced_dynamics.py` - Dynamics processing orchestrator (facade for modular components)
- `realtime_adaptive_eq.py` - Real-time EQ adaptation (0.28ms processing time)
- `stages.py` - Processing stages orchestration (EQ, compression, limiting)

**Modular Subsystems:**
- `dsp/eq/` - 26-band psychoacoustic EQ system (critical bands, masking, filters, genre curves)
  - **`parallel_eq_processor.py`** - Vectorized EQ processing (1.7x speedup with NumPy)
- `dsp/dynamics/` - Dynamics processing (envelope follower, compressor, limiter with ISR/true peak)
  - **`vectorized_envelope.py`** - Numba JIT envelope follower (40-70x speedup)
- `dsp/utils/` - Organized utilities (audio info, conversion, spectral analysis, adaptive processing, stereo)

**Legacy Compatibility:**
- `unified.py` and `psychoacoustic_eq.py` (root) - Backward compatibility wrappers re-exporting from new modular structure

### Analysis Framework (`auralis/analysis/`)

**Core Modules:**
- `spectrum_analyzer.py` - Professional FFT analysis with A/C/Z weighting
- `loudness_meter.py` - ITU-R BS.1770-4 compliant LUFS measurement
- `phase_correlation.py` - Stereo correlation analysis
- `dynamic_range.py` - EBU R128 dynamic range calculation

**Modular Subsystems:**
- `analysis/content/` - Feature extraction, genre/mood analysis, processing recommendations
- `analysis/ml/` - Machine learning genre classification (RandomForest with MFCC/chroma/spectral features)
- `analysis/quality/` - Quality metrics (frequency, dynamic range, stereo, distortion, loudness standards)
- **`parallel_spectrum_analyzer.py`** - Parallel FFT processing (3.4x speedup for long audio)
- **`analysis/fingerprint/`** - 25D audio fingerprint system for music similarity and cross-genre discovery

**Audio Fingerprint System (`auralis/analysis/fingerprint/`):** ✨ NEW (Oct 26, 2025)
- **`audio_fingerprint_analyzer.py`** - Main 25D fingerprint extraction (combines all analyzers)
- `temporal_analyzer.py` - Tempo, rhythm stability, transient density, silence ratio (4D)
- `spectral_analyzer.py` - Spectral centroid, rolloff, flatness (3D)
- `harmonic_analyzer.py` - Harmonic ratio, pitch stability, chroma energy (3D)
- `variation_analyzer.py` - Dynamic range variation, loudness variation, peak consistency (3D)
- `stereo_analyzer.py` - Stereo width, phase correlation (2D)
- **Purpose**: Extract acoustic fingerprints for cross-genre music discovery, similarity analysis, and recommendation
- **25 Dimensions**: Frequency (7D), Dynamics (3D), Temporal (4D), Spectral (3D), Harmonic (3D), Variation (3D), Stereo (2D)
- **Use Case**: `from auralis.analysis.fingerprint import AudioFingerprintAnalyzer`
- **Documentation**: See [docs/sessions/oct26_fingerprint_system/](docs/sessions/oct26_fingerprint_system/) for complete implementation details

**Research Tools (`research/`):** ✨ NEW (Oct 26-28, 2025)
- **Analysis scripts** for track fingerprinting and batch processing
- **Preset validation** tools to verify processing behavior
- **Album studies** with detailed frequency analysis
- **Usage**: `python research/scripts/analyze_track.py <audio_file>` outputs JSON fingerprint

### Other Key Systems

**Library Management (`auralis/library/`):**
- Repository pattern for data access (track, album, artist, playlist repositories)
- Intelligent folder scanning (740+ files/second)
- SQLite database with SQLAlchemy models (schema v3 with performance indexes)
- **Query result caching** with 136x speedup on cache hits
- **Pagination support** for large libraries (10k+ tracks)
- Database migration system for schema versioning

**Audio Player (`auralis/player/`):**
- Enhanced player with real-time processing
- Queue management with shuffle/repeat support

**Performance Optimization (`auralis/optimization/`):**
- **Numba JIT compilation** - 40-70x envelope speedup (vectorized_envelope.py)
- **NumPy vectorization** - 1.7x EQ speedup (parallel_eq_processor.py)
- **Parallel processing framework** - Infrastructure for batch operations (parallel_processor.py)
- **Real-time factor**: 36.6x on real-world audio (processes 1 hour in ~98 seconds)
- Memory pools, smart caching, SIMD acceleration

**Web Interface (`auralis-web/`):**
- `backend/main.py` - FastAPI server (614 lines, refactored with modular routers)
- `backend/chunked_processor.py` - Chunked audio streaming processor (30s chunks with overlap handling)
- `backend/routers/` - Modular API routers (14 routers: player, library, albums, artists, streaming, etc.)
- `backend/processing_engine.py` - Background job queue for async audio processing
- `backend/streaming/` - **NEW (Beta.4)** - Unified MSE + Multi-Tier Buffer streaming system
  - Progressive WebM/Opus encoding for instant preset switching
  - Combined buffer management for seamless playback
  - See [docs/sessions/oct27_mse_integration/](docs/sessions/oct27_mse_integration/) for architecture details
- `backend/WEBSOCKET_API.md` - WebSocket message documentation
- `frontend/` - React app with Material-UI components
  - `BottomPlayerBarUnified.tsx` - **NEW (Beta.4)** - Unified player component (67% code reduction)
  - `CozyLibraryView.tsx` - Main library orchestrator (refactored from 958 lines using extracted hooks)

**Desktop Application (`desktop/`):**
- Electron wrapper that spawns Python backend and loads React UI
- IPC for native file/folder selection

## Frequently Modified Files

### Adding New Audio Processing Features
- [auralis/core/hybrid_processor.py](auralis/core/hybrid_processor.py) - Main processing pipeline
- [auralis/dsp/stages.py](auralis/dsp/stages.py) - Processing stages (EQ, compression, limiting)
- [auralis/core/unified_config.py](auralis/core/unified_config.py) - Processing configuration

### Research and Analysis
- [research/scripts/](research/scripts/) - Analysis scripts for audio fingerprinting and preset validation
  - `analyze_track.py` - Extract fingerprints and analyze individual tracks
  - `batch_analyze_*.sh` - Batch analysis scripts for albums
  - `validate_preset_fix.py` - Validate preset processing behavior
- [research/data/](research/data/) - Analysis results and fingerprint data
  - `analysis/` - Track-level fingerprint JSON files
  - `batch/` - Batch analysis results

### Modifying the Web UI
- [auralis-web/frontend/src/components/ComfortableApp.tsx](auralis-web/frontend/src/components/ComfortableApp.tsx) - Main app layout
- [auralis-web/frontend/src/components/CozyLibraryView.tsx](auralis-web/frontend/src/components/CozyLibraryView.tsx) - Library view orchestrator (407 lines, refactored)
  - Uses extracted hooks: `useLibraryData`, `useTrackSelection`, `usePlayerAPI`
  - Delegates to sub-components: `LibraryViewRouter`, `TrackListView`, `LibraryEmptyState`
  - Handles search/filter, batch operations, keyboard shortcuts
- [auralis-web/frontend/src/components/BottomPlayerBar.tsx](auralis-web/frontend/src/components/BottomPlayerBar.tsx) - Player controls
- **Beta.6 Interaction Features:**
  - [auralis-web/frontend/src/components/drag-drop/](auralis-web/frontend/src/components/drag-drop/) - Drag-and-drop system (5 components)
  - [auralis-web/frontend/src/hooks/useKeyboardShortcuts.tsx](auralis-web/frontend/src/hooks/useKeyboardShortcuts.tsx) - Keyboard shortcuts (⚠️ disabled in Beta.6)
  - [auralis-web/frontend/src/components/BatchOperationsToolbar.tsx](auralis-web/frontend/src/components/BatchOperationsToolbar.tsx) - Multi-select batch operations

### Adding Backend API Endpoints

The backend uses a **modular router architecture** (FastAPI best practice):

- [auralis-web/backend/main.py](auralis-web/backend/main.py) - Main FastAPI app and startup (614 lines)
- [auralis-web/backend/routers/](auralis-web/backend/routers/) - Modular endpoint routers:
  - `player.py` - Playback control (play, pause, seek, queue, volume)
  - `library.py` - Library management (tracks) with **pagination support**
  - `albums.py` - Album browsing and management
  - `artists.py` - Artist browsing and management
  - `metadata.py` - Track metadata editing (14 editable fields)
  - `enhancement.py` - Audio enhancement settings
  - `playlists.py` - Playlist CRUD operations
  - `files.py` - File upload and format handling
  - `artwork.py` - Album artwork management
  - `cache.py` - Cache management and statistics
  - `mse_streaming.py` - Media Source Extensions streaming (Beta.4)
  - `unified_streaming.py` - Unified streaming orchestration (Beta.4)
  - `system.py` - Health checks, version info
- [auralis-web/backend/processing_engine.py](auralis-web/backend/processing_engine.py) - Background job queue
- [auralis-web/backend/WEBSOCKET_API.md](auralis-web/backend/WEBSOCKET_API.md) - WebSocket message types

**When adding new endpoints:**
1. Identify the appropriate router (or create a new one if needed)
2. Add endpoint to the router file
3. Router is automatically included in main.py
4. Use dependency injection for shared state (player, library manager)
5. Follow async/await pattern for I/O operations

### Library Management Changes
- [auralis/library/manager.py](auralis/library/manager.py) - Library manager orchestrator with caching
- [auralis/library/cache.py](auralis/library/cache.py) - Query result caching system (136x speedup)
- [auralis/library/scanner.py](auralis/library/scanner.py) - Folder scanning logic
- [auralis/library/repositories/](auralis/library/repositories/) - Repository pattern data access with pagination
- [auralis/library/migrations/](auralis/library/migrations/) - Database schema migrations
- [auralis/library/metadata_editor.py](auralis/library/metadata_editor.py) - Track metadata editing (Mutagen)

## Key Processing Workflows

### Adaptive Mode (Primary Use Case)
Intelligent mastering without reference tracks:

```python
from auralis.core.hybrid_processor import HybridProcessor
from auralis.core.unified_config import UnifiedConfig
from auralis.io.unified_loader import load_audio
from auralis.io.saver import save

# Load audio
audio, sr = load_audio("input.wav")

# Create processor
config = UnifiedConfig()
config.set_processing_mode("adaptive")  # Default mode
processor = HybridProcessor(config)

# Process audio - no reference needed
processed_audio = processor.process(audio)

# Save output
save("output.wav", processed_audio, sr, subtype='PCM_16')
```

### Available Processing Presets
- **Adaptive** (default): Intelligent content-aware mastering
- **Gentle**: Subtle mastering with minimal processing
- **Warm**: Adds warmth and smoothness
- **Bright**: Enhances clarity and presence
- **Punchy**: Increases impact and dynamics

### Audio Fingerprint-Driven Processing (NEW - Oct 27, 2025)

**Status**: ✅ **INTEGRATED AS CORE COMPONENT** - Phase 1 Complete

The 25D audio fingerprint system is now integrated into the processing pipeline, enabling intelligent, content-aware parameter selection.

**Automatic Usage** (No code changes required):
```python
from auralis.core.hybrid_processor import HybridProcessor
from auralis.core.unified_config import UnifiedConfig
from auralis.io.unified_loader import load_audio

# Load audio
audio, sr = load_audio("song.flac")

# Create processor (fingerprint analysis enabled by default)
config = UnifiedConfig()
config.set_processing_mode("adaptive")
processor = HybridProcessor(config)

# Process audio - fingerprint automatically extracted and used!
processed = processor.process(audio)

# Inspect fingerprint (optional)
if "fingerprint" in processor.last_content_profile:
    fp = processor.last_content_profile["fingerprint"]
    print(f"Bass%: {fp['bass_pct']:.1f}%")
    print(f"LUFS: {fp['lufs']:.1f}dB")
    print(f"Crest: {fp['crest_db']:.1f}dB")
```

**Manual Fingerprint Extraction**:
```python
from auralis.analysis.fingerprint import AudioFingerprintAnalyzer

# Initialize analyzer
analyzer = AudioFingerprintAnalyzer()

# Extract complete 25D fingerprint
fingerprint = analyzer.analyze(audio, sr)

# 25 dimensions available:
# - Frequency (7D): sub_bass_pct, bass_pct, low_mid_pct, mid_pct, upper_mid_pct, presence_pct, air_pct
# - Dynamics (3D): lufs, crest_db, bass_mid_ratio
# - Temporal (4D): tempo_bpm, rhythm_stability, transient_density, silence_ratio
# - Spectral (3D): spectral_centroid, spectral_rolloff, spectral_flatness
# - Harmonic (3D): harmonic_ratio, pitch_stability, chroma_energy
# - Variation (3D): dynamic_range_variation, loudness_variation_std, peak_consistency
# - Stereo (2D): stereo_width, phase_correlation
```

**Intelligent Processing Enabled**:
1. **Frequency-aware EQ** (7D): Precise adjustments based on actual bass/mid/treble distribution (not spectral centroid guessing)
2. **Dynamics-aware compression** (3D): Respects high dynamic range, detects brick-walled material, adapts to loudness
3. **Temporal-aware processing** (4D): Preserves transients and rhythm stability
4. **Harmonic-aware intensity** (3D): Gentle on vocals/strings (high harmonic ratio), aggressive on percussion
5. **Stereo-aware width** (2D): Expands narrow mixes, checks phase correlation for mono compatibility
6. **Variation-aware dynamics** (3D): Preserves intentional loudness variation (quiet/loud sections)

**Disable Fingerprints** (if needed):
```python
from auralis.core.analysis import ContentAnalyzer

# Disable at analyzer level
analyzer = ContentAnalyzer(use_fingerprint_analysis=False)
```

**Future Use Cases** (Planned):
- Cross-genre music discovery based on acoustic similarity
- "Find songs like this" recommendation system
- Music similarity graphs and clustering
- Continuous enhancement space (interpolate between characteristics)
- Real-time adaptive processing

**Documentation**: See [docs/completed/FINGERPRINT_CORE_INTEGRATION.md](docs/completed/FINGERPRINT_CORE_INTEGRATION.md)

## Performance Optimization

Auralis includes comprehensive performance optimizations for real-time audio processing:

### Core Optimizations (Oct 24, 2025)

**Numba JIT Compilation** (40-70x speedup):
- Envelope following in dynamics processing
- Sequential operations with dependencies
- Automatic activation when Numba is installed

**NumPy Vectorization** (1.7x speedup):
- Psychoacoustic EQ processing (26-band)
- Element-wise operations
- SIMD-optimized array operations

**Parallel Processing** (3.4x for long audio):
- Spectrum analysis with multiple FFT windows
- Only beneficial for audio > 60 seconds
- Automatic threshold-based activation

### Performance Metrics

**Real-World Performance** (Iron Maiden - 232.7s track):
- Processing time: 6.35 seconds
- **Real-time factor: 36.6x**
- Meaning: Process 1 hour of audio in ~98 seconds

**Component Performance**:
- Dynamics Processing: 150-323x real-time
- Psychoacoustic EQ: 72-74x real-time
- Content Analysis: 98-129x real-time
- Spectrum Analysis: 54-55x real-time

### Installation for Optimal Performance

```bash
# Standard installation (works, but slower)
pip install numpy scipy

# Recommended: Install Numba for 2-3x overall speedup
pip install numpy scipy numba
```

**Graceful Fallbacks**: All optimizations are optional. Without Numba, the system falls back to standard implementations (still ~18-20x real-time).

### Verification

```bash
# Quick validation (~30 seconds)
python test_integration_quick.py

# Comprehensive benchmark (~2-3 minutes)
python benchmark_performance.py
```

**Documentation**: See [PERFORMANCE_OPTIMIZATION_QUICK_START.md](PERFORMANCE_OPTIMIZATION_QUICK_START.md) for detailed information.

## Large Library Performance Optimization

Auralis is optimized for handling large music libraries (10k+ tracks) with 4-layer performance architecture:

### 1. Pagination System
- **Backend**: Offset-based pagination in all repository methods
- **Frontend**: Infinite scroll with Intersection Observer (50 tracks per page)
- **API**: `GET /api/library/tracks?limit=50&offset=0` returns `{tracks, total, has_more}`
- **Impact**: Initial load only fetches 50 tracks (~100ms)

### 2. Database Indexes (Schema v3)
- **12 performance indexes** on frequently queried columns
- Indexed columns: `created_at`, `title`, `play_count`, `favorite`, `last_played`, `album_id`, `year`
- Composite index for favorite tracks ordered by title
- Related tables: `artists.name`, `albums.title`, `genres.name`
- **Impact**: Faster ORDER BY and WHERE queries on large datasets

### 3. Query Result Caching
- **LRU cache** with TTL expiration (256 entries, configurable)
- Cache durations:
  - Recent tracks: 3 minutes
  - Popular tracks: 2 minutes
  - Favorites: 3 minutes
  - All tracks: 5 minutes
  - Search: 1 minute
- **Automatic invalidation** on data changes (play count, favorites, library scanning)
- **Impact**: 136x speedup on cache hits (6ms → 0.04ms)

### 4. Cache Management API
```python
from auralis.library.manager import LibraryManager

manager = LibraryManager()

# Get cache statistics
stats = manager.get_cache_stats()
# Returns: {size, max_size, hits, misses, hit_rate, total_requests}

# Clear all caches
manager.clear_cache()

# Invalidate specific caches after batch operations
manager.invalidate_track_caches()
```

**Combined Performance**: Initial load fast, subsequent queries 136x faster, supports 50k+ track libraries

**Documentation**: See [LARGE_LIBRARY_OPTIMIZATION.md](LARGE_LIBRARY_OPTIMIZATION.md) for implementation details

## Development Workflow

### Common Development Tasks

**Setting up a new development environment:**
```bash
# 1. Clone and install dependencies
git clone https://github.com/matiaszanolli/Auralis.git
cd Auralis
pip install -r requirements.txt

# 2. Install frontend and desktop dependencies
cd auralis-web/frontend && npm install && cd ../..
cd desktop && npm install && cd ..

# 3. Launch development server
python launch-auralis-web.py --dev
# OR for desktop development
npm run dev
```

**Making changes to the backend API:**
```bash
# 1. Make changes to routers in auralis-web/backend/routers/
# 2. Test with pytest
python -m pytest tests/backend/ -v

# 3. Test manually with Swagger UI
python launch-auralis-web.py --dev
# Visit http://localhost:8765/api/docs
```

**Making changes to audio processing:**
```bash
# 1. Edit files in auralis/core/ or auralis/dsp/
# 2. Run core processing tests
python -m pytest tests/test_adaptive_processing.py -v

# 3. Run validation tests
python -m pytest tests/validation/ -v

# 4. Benchmark performance if optimization-related
python benchmark_performance.py
```

**Analyzing audio with fingerprint system:**
```bash
# Analyze a single track
python research/scripts/analyze_track.py /path/to/track.flac

# Batch analyze an album (creates script first)
ls "/path/to/album/"*.flac > /tmp/tracklist.txt
python research/scripts/batch_analyze.py /tmp/tracklist.txt
```

**Working with Beta.6 interaction features:**
```bash
# Drag-and-drop components (5 components, 724 lines)
# Location: auralis-web/frontend/src/components/drag-drop/
# - DraggableTrack.tsx - Individual draggable track
# - DroppablePlaylist.tsx - Playlist drop target
# - DroppableQueue.tsx - Queue drop target
# - DragPreview.tsx - Visual drag feedback
# - useDragAndDrop.tsx - Drag-and-drop logic hook

# Keyboard shortcuts (⚠️ temporarily disabled in Beta.6)
# Location: auralis-web/frontend/src/hooks/useKeyboardShortcuts.tsx
# Status: Complete but disabled due to minification issue
# Re-enable planned for Beta.7 with refactored architecture

# Batch operations
# Location: auralis-web/frontend/src/components/BatchOperationsToolbar.tsx
# Features: Multi-select, bulk add to queue, toggle favorites, remove tracks
```

### Code Organization Principles
- **Modular Design**: Large modules (400+ lines) refactored into focused sub-modules
- **Facade Pattern**: Original files become re-export wrappers for backward compatibility
- **Repository Pattern**: Data access layer for database operations
- **Configuration-Driven**: All processing controlled via `UnifiedConfig`
- **Maximum file size**: Keep modules under 300 lines (guideline, not strict rule)

### Module Refactoring Pattern
When refactoring large modules, follow this established pattern:

1. **Create sub-package**: `mkdir auralis/<subsystem>/<module_name>/`
2. **Split by responsibility**: Create focused modules (100-200 lines each)
3. **Main orchestrator**: Keep main class in `<module_name>/<module_name>.py`
4. **Public API**: Export all public classes/functions in `<module_name>/__init__.py`
5. **Backward compatibility**: Original file becomes re-export wrapper
6. **Verify tests**: Ensure all existing tests pass without modification

**Successfully refactored modules (13 total, 50+ new focused modules):**
- `auralis/dsp/eq/` - Psychoacoustic EQ (623→123 lines, -80%)
- `auralis/dsp/utils/` - DSP utilities (1158→150 lines, -87%)
- `auralis/dsp/dynamics/` - Dynamics processing (718→293 lines, -59%)
- `auralis/analysis/quality/` - Quality metrics (889→249 lines, -72%)
- `auralis/analysis/content/` - Content analysis (723→227 lines, -69%)
- `auralis/analysis/ml/` - ML genre classifier (623→29 lines, -95%)
- Plus: `core/analysis/`, `core/processors/`, `library/repositories/`, `learning/components/`, `player/components/`

**Results:** Average 60% size reduction, 100% backward compatibility, 100% test pass rate

### Import Patterns

**Recommended imports (new modular structure):**
```python
# Use these for new code
from auralis.dsp.utils import spectral_centroid, to_db, adaptive_gain_calculation
from auralis.dsp.eq import PsychoacousticEQ, generate_genre_eq_curve
from auralis.dsp.dynamics import AdaptiveCompressor, AdaptiveLimiter
from auralis.analysis.quality import QualityMetrics, FrequencyResponseAssessor
from auralis.analysis.content import FeatureExtractor, GenreAnalyzer
from auralis.analysis.ml import MLGenreClassifier, extract_ml_features
from auralis.library.repositories import TrackRepository, AlbumRepository
```

**Legacy imports (still supported):**
```python
# These still work but are deprecated
from auralis.dsp.unified import spectral_centroid, to_db
from auralis.dsp.psychoacoustic_eq import PsychoacousticEQ
from auralis.analysis.quality_metrics import QualityMetrics
```

### Important API Notes
- **HybridProcessor.process()**: Returns numpy array directly (not a result object)
- **Audio Player Methods**: Use `seek_to_position()` not `seek()`, `next_track()` not `next()`, `previous_track()` not `previous()`
- **Processing Endpoints**: Volume parameter is `volume` not `level`
- **Library Manager**: Database location is `~/.auralis/library.db` by default

## UI/UX Design Philosophy

### 🚨 MANDATORY: UI Design Guidelines

**ALL UI development MUST follow [docs/guides/UI_DESIGN_GUIDELINES.md](docs/guides/UI_DESIGN_GUIDELINES.md)**

These are **strict requirements**, not suggestions. PRs that violate these guidelines will be rejected.

**Key Rules:**
1. ✅ **One Component Rule** - Only one component per purpose (no duplicates)
2. ✅ **No "Enhanced" Versions** - Refactor existing, don't create variants
3. ✅ **Design Tokens Only** - No hardcoded colors, spacing, or typography
4. ✅ **< 300 Lines** - Extract subcomponents if exceeded
5. ✅ **Performance Budget** - 60fps, virtual scrolling, code splitting

**Before creating ANY new UI component:**
- Read [UI_DESIGN_GUIDELINES.md](docs/guides/UI_DESIGN_GUIDELINES.md)
- Check if existing component can be extended
- Use design system primitives from `src/design-system/`

### Current UI Status (Beta 9.0)

⚠️ **Known Issues:**
- **92 components, 46k lines** - Too much bloat
- **Multiple duplicates** - AudioPlayer, EnhancedAudioPlayer, MagicalMusicPlayer...
- **Bootstrap-clone feel** - Needs professional polish

**Beta 10.0 Target:**
- **~45 components** (50% reduction)
- **~20k lines** (56% reduction)
- **Professional UI** with design system
- See [docs/roadmaps/UI_OVERHAUL_PLAN.md](docs/roadmaps/UI_OVERHAUL_PLAN.md)

### Design Aesthetic (Target State)

Auralis combines classic library-based player experience (iTunes, Rhythmbox) with modern touches from Spotify and Cider:

**Visual Style:**
- **Dark theme**: Deep navy/black backgrounds (#0A0E27, #1a1f3a)
- **Aurora gradient branding**: Flowing purple/blue/pink waves (signature visual element)
- **Neon accents**: Vibrant retro-futuristic elements
- **Album art grid**: Large, prominent artwork cards (160x160px minimum)
- **Smooth animations**: Subtle transitions, gradient progress bars

**Layout Structure:**
```
┌─────────────┬──────────────────────────────┬───────────────┐
│  Sidebar    │      Main Content Area       │  Remastering  │
│  (240px)    │         (flexible)           │   (280-320px) │
├─────────────┼──────────────────────────────┴───────────────┤
│             │        Player Bar (80-100px)                  │
└─────────────┴───────────────────────────────────────────────┘
```

**Design System Tokens:**
All components must use tokens from `src/design-system/tokens.ts`:
- **Colors**: `bg`, `accent`, `text` palettes
- **Spacing**: `xs`, `sm`, `md`, `lg`, `xl`, `xxl`
- **Typography**: Font sizes, weights, families
- **Shadows**: `sm`, `md`, `lg`
- **Transitions**: `fast`, `normal`, `slow`

See [UI_DESIGN_GUIDELINES.md](docs/guides/UI_DESIGN_GUIDELINES.md) for complete design system specification.

## Code Style and Best Practices

### Python Backend
- **Type hints**: Use for function parameters and return values
- **Docstrings**: All public classes and functions
- **NumPy arrays**: Preferred over lists for audio processing
- **Async/await**: Use for I/O operations in FastAPI endpoints
- **Repository pattern**: For all database operations (no direct SQLAlchemy queries in business logic)

### React Frontend
- **TypeScript**: Always use TypeScript, no plain JavaScript
- **Functional components**: Use hooks instead of class components
- **Material-UI**: Use MUI components for consistency
- **Service layer**: Use for API calls (e.g., `processingService.ts`)

### Testing

**⚠️ CRITICAL: Read [TESTING_GUIDELINES.md](docs/development/TESTING_GUIDELINES.md) before writing tests**

**Test Quality Principles:**
- **Coverage ≠ Quality**: 100% coverage doesn't mean tests catch bugs
- **Test invariants, not implementation**: Focus on properties that must always hold
- **Test behavior, not code**: What the system does, not how it does it
- **Integration tests matter**: Unit tests alone won't catch configuration bugs

**Test Structure:**
- **File naming**: `test_<module_name>.py`
- **Function naming**: `test_<function>_<scenario>()` - Be descriptive
- **Structure**: Arrange-Act-Assert pattern
- **Fixtures**: Use pytest fixtures for common setup
- **Mock sparingly**: Prefer real dependencies in integration tests

**Quality Metrics:**
- **Minimum coverage**: 85% backend, 80% frontend
- **Mutation score target**: >80% (tests must catch intentional bugs)
- **Test-to-code ratio**: Target 1.0+ (equal or more test files than source files)

### Common Pitfalls to Avoid
- ❌ Don't modify audio files in place (always create new outputs)
- ❌ Don't use blocking I/O in FastAPI endpoints (use async)
- ❌ Don't hardcode file paths (use Path objects and configuration)
- ❌ Don't access database directly from UI components (use API)
- ❌ Don't use `print()` for logging (use Python `logging` module)

### Performance Considerations
- ✅ Use NumPy vectorized operations instead of loops
- ✅ Cache expensive computations with `@lru_cache`
- ✅ Profile before optimizing (use `cProfile` or `py-spy`)
- ✅ Use memory pools for repeated array allocations
- ✅ Batch database operations when possible

## Version Management

Auralis uses **Semantic Versioning 2.0.0** with automated version management.

### Version Commands
```bash
# Check current version
python -c "from auralis.version import get_version; print(get_version())"

# Bump to new version (updates all files)
python scripts/sync_version.py 1.0.0-alpha.2

# Get detailed version info (JSON)
python auralis/version.py
```

### Release Process
```bash
# 1. Bump version
python scripts/sync_version.py 1.0.0-alpha.2

# 2. Update CHANGELOG.md with release notes

# 3. Commit and tag
git commit -am "chore: bump version to 1.0.0-alpha.2"
git push origin master
git tag -a v1.0.0-alpha.2 -m "Release v1.0.0-alpha.2"
git push origin v1.0.0-alpha.2  # Triggers CI/CD builds
```

**Documentation**: See [VERSIONING_STRATEGY.md](VERSIONING_STRATEGY.md) and [RELEASE_GUIDE.md](RELEASE_GUIDE.md)

## Web Interface Access Points

When web interface is running:
- **Main UI**: http://localhost:3000 (dev mode) or http://localhost:8765 (production)
- **Backend API**: http://localhost:8765/api/
- **API Documentation**: http://localhost:8765/api/docs (Swagger UI)
- **WebSocket**: ws://localhost:8765/ws (real-time updates)
- **Health Check**: http://localhost:8765/api/health
- **Version Info**: http://localhost:8765/api/version

**Note**: Default backend port is **8765** (not 8000). Frontend dev server uses port **3000**.

## Troubleshooting

### Common Development Issues

**"Module not found" errors:**
```bash
pip install -r requirements.txt
pip install pytest pytest-cov soundfile scikit-learn mutagen
```

**Frontend build errors:**
```bash
cd auralis-web/frontend
rm -rf node_modules package-lock.json
npm install
npm run build
```

**Database errors:**
```bash
# Reset database (WARNING: deletes all library data)
./RESET_DATABASE.sh              # Uses provided script
# OR manually:
rm ~/.auralis/library.db         # Will be recreated on next launch
rm ~/.auralis/auralis_library.db # Alternative location
```

**WebSocket connection fails:**
- Ensure backend is running before loading frontend
- Check CORS settings in [auralis-web/backend/main.py](auralis-web/backend/main.py)
- Verify port 8765 is not blocked by firewall

**Port conflicts:**
```bash
lsof -ti:8765 | xargs kill -9  # Backend
lsof -ti:3000 | xargs kill -9  # Frontend dev server
```

### Electron Build Issues

**AppImage startup error:**
```bash
lsof -ti:8765 | xargs kill -9           # Kill process on port 8765
./dist/Auralis-1.0.0.AppImage           # Run from terminal to see logs
```

**DEB package installation:**
```bash
sudo dpkg -i dist/auralis-desktop_1.0.0_amd64.deb
sudo apt-get install -f  # Fix dependencies if needed
```

See `ELECTRON_BUILD_FIXED.md` for detailed build troubleshooting.

## Important Notes

### Git Workflow
- **Current branch**: `master`
- **Main branch**: `master` (use this for PRs)
- **Repository**: https://github.com/matiaszanolli/Auralis
- **License**: GPL-3.0

### Project Status
- **Version**: 1.0.0-beta.10 (Beta stage - Mutation testing and quality improvements)
- **Roadmap**: See [docs/roadmaps/MASTER_ROADMAP.md](docs/roadmaps/MASTER_ROADMAP.md) for complete roadmap
- **Current Focus**: Boundary testing (30/150 tests), mutation testing framework
- **Next Major**: Beta 11.0 (Complete Phase 1 testing) - December 2025

**Beta.10 - Mutation Testing** (November 2025):
- [x] **Mutation testing framework** - mutmut integration for test quality validation
- [x] **Cache module validation** - 8 cache tests passing mutation testing
- [x] **Iteration 3 complete** - 13/13 mutants killed (100% mutation score)
- [x] **Documentation** - Complete mutation testing guide

**Beta.9.1 - Testing Infrastructure** (November 8, 2025):
- [x] **Comprehensive testing guidelines** - 1,342 lines of mandatory standards
- [x] **Test implementation roadmap** - Path from 445 to 2,500+ tests (868 lines)
- [x] **Enhanced CLAUDE.md** - Improved developer documentation
- [x] **Phase 1 Week 3 plan** - 150 boundary tests specification

**Beta.9.0 - Test Quality Foundation** (November 2025):
- [x] **Phase 1 Week 1** - 305 critical invariant tests
- [x] **Phase 1 Week 2** - 85 advanced integration tests
- [x] **Testing philosophy** - Coverage ≠ Quality
- [x] **850+ total tests** - Comprehensive test suite
- **Beta.6 Enhanced Interactions**: ✅ **COMPLETE PHASE 2** (Oct 30, 2025)
  - Drag-and-drop system for playlist and queue management (724 lines)
  - Keyboard shortcuts (15+ shortcuts, ⚠️ temporarily disabled due to minification issue)
  - Batch operations with multi-select (589 lines)
  - 2,037 lines of new feature code
  - Bug fixes for backend imports, deprecations, and frontend artwork
  - See [RELEASE_NOTES_BETA6.md](RELEASE_NOTES_BETA6.md) for complete details
- **Beta.4 Unified Streaming**: ✅ **MAJOR ARCHITECTURE OVERHAUL** (Oct 27, 2025)
  - Unified MSE + Multi-Tier Buffer system (eliminates dual playback conflicts)
  - Progressive WebM/Opus streaming for instant preset switching
  - 4,518 lines of new code across 15 components
  - 67% player UI code reduction (970→320 lines)
  - 75% test coverage on new components (50+ comprehensive tests)
  - See [docs/sessions/oct27_mse_integration/](docs/sessions/oct27_mse_integration/) for complete technical details
- **Beta.1 Critical Fixes**: ✅ **ALL P0/P1 ISSUES RESOLVED** (Oct 26, 2025)
  - Audio fuzziness between chunks - ✅ FIXED (3s crossfade + state tracking)
  - Volume jumps between chunks - ✅ FIXED (same fix, shared root cause)
  - Gapless playback - ✅ FIXED (pre-buffering: 100ms → <10ms)
  - Artist pagination - ✅ FIXED (pagination: 468ms → 25ms)
- **Core Processing**: ✅ Production-ready (**52.8x real-time speed** with optimizations, E2E validated)
- **Performance Optimization**: ✅ COMPLETE - Numba JIT + vectorization (Oct 24, 2025)
  - **40-70x envelope speedup** (Numba JIT compilation)
  - **1.7x EQ speedup** (NumPy vectorization)
  - **2-3x overall pipeline improvement** (real-world validated)
  - Optional Numba dependency, graceful fallbacks, zero breaking changes
- **Version Management**: ✅ COMPLETE - Semantic versioning system (Oct 24, 2025)
  - Single source of truth (`auralis/version.py`)
  - Automated version sync script
  - API endpoint (`/api/version`)
  - CI/CD workflow for releases
- **Dynamics Expansion**: ✅ COMPLETE - All 4 Matchering behaviors working (Oct 24, 2025)
  - Heavy Compression, Light Compression, Preserve Dynamics, **Expand Dynamics (de-mastering)**
  - Average 0.67 dB crest error, 1.30 dB RMS error across all behaviors
- **RMS Boost Fix**: ✅ FIXED - No more overdrive on loud material (Oct 24, 2025)
- **Real-time Processing Fixes**: ✅ CRITICAL BUGS FIXED (Oct 25, 2025)
  - **Gain pumping bug** - Fixed stateless compression causing audio degradation after 30s
  - **Soft limiter** - Replaced harsh brick-wall with tanh() saturation
  - **Electron window** - Fixed window not showing on Linux/Wayland
- **Testing**: ✅ **850+ comprehensive tests** - See [TEST_FIX_COMPLETE.md](TEST_FIX_COMPLETE.md)
  - Backend: 850+ tests across all categories
    - API tests: 96 tests, 74% coverage
    - Real-time processing: 24 tests, all passing ✅ (fixed Oct 25)
    - Core processing: 26 tests
    - Invariant tests: 305 tests (Phase 1 Week 1) ✅
    - Integration tests: 85 tests (Phase 1 Week 2) ✅
    - Boundary tests: 151 tests (Phase 1 Week 3 - COMPLETE - 101% of target) ✅
    - Mutation tests: 13/13 mutants killed (100% score) ✅
    - **Total Phase 1**: 541 tests complete
  - Frontend: 245 tests (234 passing, 11 failing - 95.5% pass rate)
    - ⚠️ Known issue: 11 gapless playback tests failing
  - **Test Quality Initiative** (Beta 9.0 → Beta 11.0):
    - Phase 1 Week 1: ✅ 305 critical invariant tests (COMPLETE)
    - Phase 1 Week 2: ✅ 85 advanced integration tests (COMPLETE)
    - Phase 1 Week 3: ✅ 151 boundary tests (COMPLETE - 101% of target)
    - **Phase 1 Total**: ✅ 541 tests complete (100% pass rate)
    - Mutation testing: ✅ Framework complete, 100% cache module score
    - **Next**: Phase 2 Week 4 - Performance Tests (100 tests planned)
    - See [TEST_IMPLEMENTATION_ROADMAP.md](docs/development/TEST_IMPLEMENTATION_ROADMAP.md)
  - **Critical Learning**: Overlap bug had 100% coverage but zero detection - coverage ≠ quality
- **Library Management Quality Improvements**: ✅ **PHASE 2 COMPLETE** (Nov 7, 2025)
  - **Pattern-based cache invalidation** - 80%+ cache hit rate after mutations (was 0%)
  - **API standardization** - 100% consistent return types for paginated queries (was 20%)
  - **Comprehensive documentation** - 9,500+ lines of API design guidelines
  - **Performance impact** - 70% fewer database queries, 100% type hint coverage
  - **Test coverage** - 13 comprehensive cache tests, 142 passing tests total (93.3% pass rate)
  - See [docs/development/PHASE2_COMPLETE_SUMMARY.md](docs/development/PHASE2_COMPLETE_SUMMARY.md) for complete details
- **Library Scan API**: ✅ NEW - `POST /api/library/scan` endpoint with duplicate prevention (Oct 24, 2025)
- **Backend Refactoring**: ✅ COMPLETE - Modular router architecture (614 lines main.py, down from 1,960)
- **Library Management**: ✅ 740+ files/second scanning, **pagination support**, **query caching (136x speedup)**
- **Database**: ✅ Schema v3 with 12 performance indexes for large libraries
- **Track Metadata Editing**: ✅ Full CRUD with 14 editable fields (Mutagen integration)
- **Audio Player**: ✅ Full playback with real-time processing
- **WebSocket API**: ✅ Real-time player state updates
- **Large Library Support**: ✅ Optimized for 50k+ tracks (infinite scroll, caching, indexes)
- **Desktop Build**: ✅ **Beta.3 Release** - AppImage + DEB packages (Oct 27, 2025)
  - All platforms build successfully (Windows, Linux)
  - Beta.1 critical issues resolved
  - Production-quality audio processing
  - **8 UI/UX quick wins** integrated
- **Audio Fingerprint System**: ✅ **NEW - Phase 1 COMPLETE** (Oct 26, 2025)
  - 25-dimensional acoustic fingerprint extraction system
  - 7 specialized analyzers (~1,147 lines of code)
  - Validated on real tracks (Exodus, Rush, Steven Wilson) and synthetic signals
  - Foundation for cross-genre music discovery and recommendation
  - See [docs/sessions/oct26_fingerprint_system/](docs/sessions/oct26_fingerprint_system/) for complete details

**Beta.6 Known Limitations:**
- ⚠️ **Keyboard shortcuts temporarily disabled** - Production build minification issue
  - Root cause: Circular dependency in keyboard shortcut hook
  - Status: Feature code complete, disabled for Beta.6 release
  - Fix planned: Re-enable in Beta.7 with refactored architecture
  - See [BETA6_KEYBOARD_SHORTCUTS_DISABLED.md](BETA6_KEYBOARD_SHORTCUTS_DISABLED.md) for details
- **Playlist track order persistence** - May not persist across restarts (database migration planned for Beta.7)
- **Preset switching buffering** - Still requires 2-5s pause when changing presets (optimization ongoing)

**Beta.7 Roadmap (Planned):**
- 🎯 **P0 Priority**: Re-enable keyboard shortcuts with refactored architecture
- **Phase 3.1**: Smart Playlists based on 25D fingerprint similarity
- **Phase 3.2**: Enhanced Queue (save queue, history, suggestions)
- **Phase 3.3**: Playback Polish (configurable crossfade, improved gapless)
- See [RELEASE_NOTES_BETA6.md](RELEASE_NOTES_BETA6.md) for Beta.7 roadmap details

### Additional Documentation

**See [docs/README.md](docs/README.md) for the complete documentation index** (55 files, organized and up-to-date)

All technical documentation has been organized into categorized directories:

**📂 docs/completed/** - Completed features and optimizations
- [MULTI_TIER_PRIORITY1_COMPLETE.md](docs/completed/MULTI_TIER_PRIORITY1_COMPLETE.md) - ✅ Multi-tier buffer system (current)
- [AUDIO_FUZZ_FIX_OCT25.md](docs/completed/AUDIO_FUZZ_FIX_OCT25.md) - ✅ Audio quality fix (latest)
- [BACKEND_REFACTORING_ROADMAP.md](docs/completed/BACKEND_REFACTORING_ROADMAP.md) - ✅ Backend modularization
- [LARGE_LIBRARY_OPTIMIZATION.md](docs/completed/LARGE_LIBRARY_OPTIMIZATION.md) - ✅ Performance optimization
- [TECHNICAL_DEBT_RESOLUTION.md](docs/completed/TECHNICAL_DEBT_RESOLUTION.md) - ✅ Technical improvements
- [TESTING_SUMMARY.md](docs/completed/TESTING_SUMMARY.md) - ✅ Complete testing guide
- [performance/](docs/completed/performance/) - Performance optimization docs (4 files)

**📂 docs/development/** - Development guidelines and roadmaps
- [TESTING_GUIDELINES.md](docs/development/TESTING_GUIDELINES.md) - **🎯 MANDATORY** - Test quality principles
- [TEST_IMPLEMENTATION_ROADMAP.md](docs/development/TEST_IMPLEMENTATION_ROADMAP.md) - Testing roadmap (Beta 9.1 → Beta 11.0)

**📂 docs/guides/** - Implementation guides and technical designs
- [AUDIO_FINGERPRINT_GRAPH_SYSTEM.md](docs/guides/AUDIO_FINGERPRINT_GRAPH_SYSTEM.md) - **NEW** - Complete fingerprint system design
- [FINGERPRINT_SYSTEM_ROADMAP.md](docs/guides/FINGERPRINT_SYSTEM_ROADMAP.md) - **NEW** - 18-week implementation roadmap
- [FREQUENCY_SPACE_ENHANCEMENT_PATTERN.md](docs/guides/FREQUENCY_SPACE_ENHANCEMENT_PATTERN.md) - **NEW** - Enhancement patterns in continuous space
- [PRESET_ARCHITECTURE_RESEARCH.md](docs/guides/PRESET_ARCHITECTURE_RESEARCH.md) - Preset system design
- [MULTI_TIER_BUFFER_ARCHITECTURE.md](docs/guides/MULTI_TIER_BUFFER_ARCHITECTURE.md) - Buffer architecture
- [REFACTORING_QUICK_START.md](docs/guides/REFACTORING_QUICK_START.md) - Code refactoring guide
- [UI_QUICK_WINS.md](docs/guides/UI_QUICK_WINS.md) - UI improvement guide

**📂 docs/roadmaps/** - Current roadmaps
- [BETA3_ROADMAP.md](BETA3_ROADMAP.md) - **Next release** - MSE progressive streaming (P0 priority)
- [MULTI_TIER_ROBUSTNESS_ROADMAP.md](docs/roadmaps/MULTI_TIER_ROBUSTNESS_ROADMAP.md) - Buffer system roadmap
- [UI_UX_IMPROVEMENT_ROADMAP.md](docs/roadmaps/UI_UX_IMPROVEMENT_ROADMAP.md) - UI/UX improvements

**📂 docs/versions/** - Version management (5 files)
- [VERSIONING_STRATEGY.md](docs/versions/VERSIONING_STRATEGY.md) - Semantic versioning
- [RELEASE_GUIDE.md](docs/versions/RELEASE_GUIDE.md) - Release process
- [CHANGELOG.md](docs/versions/CHANGELOG.md) - Version history

**📂 docs/sessions/** - Session-specific work documentation
- [oct30_beta6_release/](docs/sessions/oct30_beta6_release/) - **LATEST** - Beta 6 release session
  - Phase 2 Enhanced Interactions complete (drag-drop, keyboard shortcuts, batch ops)
  - Bug fixes and polish session
  - Keyboard shortcuts hotfix and circular dependency resolution
- [oct27_mse_integration/](docs/sessions/oct27_mse_integration/) - Beta 4 MSE streaming architecture
- [oct26_fingerprint_system/](docs/sessions/oct26_fingerprint_system/) - 25D fingerprint system (11 files)
  - Complete implementation documentation and validation results
  - Album analysis studies (Rush 1977, Rush 1989, Exodus, Steven Wilson)
  - Mathematical framework from 64+ tracks across 9 albums
  - Enhancement pattern discoveries (sub-bass power, perceived loudness)
- [oct26_beta2_release/](docs/sessions/oct26_beta2_release/) - Beta 2 release session (10 files)
- [oct25_alpha1_release/](docs/sessions/oct25_alpha1_release/) - Beta 1 release session (12 files)
- [oct26_genre_profiles/](docs/sessions/oct26_genre_profiles/) - Genre profile research (5 files)

**📂 docs/archive/** - Historical documentation (14 files)

**Other key documentation:**
- `README.md` - User-facing documentation and quick start
- `BETA1_KNOWN_ISSUES.md` - Beta.1 issues (all resolved in Beta.2)
- `BETA2_TESTING_GUIDE.md` - Beta.2 testing procedures
- `BETA3_ROADMAP.md` - Next release roadmap (MSE streaming)
- `auralis-web/backend/WEBSOCKET_API.md` - WebSocket message types and protocol

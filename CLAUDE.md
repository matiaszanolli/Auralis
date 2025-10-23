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
- [auralis-web/backend/main.py](auralis-web/backend/main.py) - Backend API server (⚠️ 1,960 lines, needs refactoring)
- [auralis-web/frontend/src/components/ComfortableApp.tsx](auralis-web/frontend/src/components/ComfortableApp.tsx) - Main UI component
- [desktop/main.js](desktop/main.js) - Electron main process

**Running tests:**
```bash
python -m pytest tests/backend/ -v      # Backend tests (96 tests, 74% coverage, fastest)
python -m pytest tests/test_adaptive_processing.py -v  # Core processing tests (26 tests)
npm test                                 # Runs pytest via npm script
npm run test:coverage                   # Generate HTML coverage report
```

## Project Overview

**Auralis** is a professional adaptive audio mastering system with both desktop (Electron) and web (FastAPI + React) interfaces. The system provides intelligent, content-aware audio processing without requiring reference tracks.

**Target Users:**
- **End Users**: Music lovers who want a simple music player with one-click audio enhancement
- **Developers**: Audio engineers, researchers integrating audio processing APIs

**What makes it unique:**
- No reference tracks needed (adaptive processing)
- Professional-grade audio quality (52.8x real-time processing speed)
- Simple UI for end users, powerful API for developers
- 100% local processing (no cloud, complete privacy)

## Essential Commands

### Launch Applications
```bash
# Web interface (recommended for development and production)
python launch-auralis-web.py           # Production mode (http://localhost:8765)
python launch-auralis-web.py --dev     # Development mode with hot reload

# Electron desktop application
npm run dev                            # Development mode (starts backend + frontend + Electron)
npm run build                          # Build desktop application

# Package desktop application for distribution
npm run package                        # Current platform
npm run package:linux                  # Linux (.AppImage, .deb)
npm run package:win                    # Windows
npm run package:mac                    # macOS
```

### Testing
```bash
# Backend API tests (96 tests, fastest)
python -m pytest tests/backend/ -v
python -m pytest tests/backend/ --cov=auralis-web/backend --cov-report=term-missing -v

# Main adaptive processing test suite (26 comprehensive tests)
python -m pytest tests/test_adaptive_processing.py -v

# All tests with coverage
python -m pytest --cov=auralis --cov-report=html tests/ -v

# End-to-end audio processing validation
python test_e2e_processing.py       # Test all presets with real audio
python analyze_outputs.py           # Analyze audio quality metrics
```

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
- `dsp/dynamics/` - Dynamics processing (envelope follower, compressor, limiter with ISR/true peak)
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

### Other Key Systems

**Library Management (`auralis/library/`):**
- Repository pattern for data access (track, album, artist, playlist repositories)
- Intelligent folder scanning (740+ files/second)
- SQLite database with SQLAlchemy models

**Audio Player (`auralis/player/`):**
- Enhanced player with real-time processing
- Queue management with shuffle/repeat support

**Performance Optimization (`auralis/optimization/`):**
- Memory pools, smart caching, SIMD acceleration (197x speedup)

**Web Interface (`auralis-web/`):**
- `backend/main.py` - FastAPI server (⚠️ 1,960 lines with 59 endpoints - needs refactoring)
- `backend/processing_engine.py` - Background job queue for async audio processing
- `frontend/` - React app with Material-UI components

**Desktop Application (`desktop/`):**
- Electron wrapper that spawns Python backend and loads React UI
- IPC for native file/folder selection

## Frequently Modified Files

### Adding New Audio Processing Features
- [auralis/core/hybrid_processor.py](auralis/core/hybrid_processor.py) - Main processing pipeline
- [auralis/dsp/stages.py](auralis/dsp/stages.py) - Processing stages (EQ, compression, limiting)
- [auralis/core/unified_config.py](auralis/core/unified_config.py) - Processing configuration

### Modifying the Web UI
- [auralis-web/frontend/src/components/ComfortableApp.tsx](auralis-web/frontend/src/components/ComfortableApp.tsx) - Main app layout
- [auralis-web/frontend/src/components/CozyLibraryView.tsx](auralis-web/frontend/src/components/CozyLibraryView.tsx) - Library view
- [auralis-web/frontend/src/components/BottomPlayerBar.tsx](auralis-web/frontend/src/components/BottomPlayerBar.tsx) - Player controls

### Adding Backend API Endpoints
- [auralis-web/backend/main.py](auralis-web/backend/main.py) - Main API routes (⚠️ See BACKEND_REFACTORING_ROADMAP.md)
- [auralis-web/backend/processing_api.py](auralis-web/backend/processing_api.py) - Processing endpoints
- [auralis-web/backend/processing_engine.py](auralis-web/backend/processing_engine.py) - Background job queue

### Library Management Changes
- [auralis/library/manager.py](auralis/library/manager.py) - Library manager orchestrator
- [auralis/library/scanner.py](auralis/library/scanner.py) - Folder scanning logic
- [auralis/library/repositories/](auralis/library/repositories/) - Repository pattern data access

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

## Development Workflow

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

### Design Aesthetic
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

**Color Palette:**
- Background: `#0A0E27` (deep navy)
- Surface: `#1a1f3a` (lighter navy)
- Accent: `linear-gradient(135deg, #667eea 0%, #764ba2 100%)`
- Text primary: `#ffffff`
- Text secondary: `#8b92b0`
- Success: `#00d4aa` (turquoise)

**Key UI Components:**
- Album/Track Cards: 160x160px artwork, 8px border radius, scale(1.05) hover effect
- Player Controls: Large circular play button with aurora gradient, gradient progress bar
- Search Bar: 48px height, pill shape (24px border radius), semi-transparent background
- Navigation Sidebar: 40px item height, accent border-left for active state

See original CLAUDE.md for detailed component implementation guidelines.

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
- **File naming**: `test_<module_name>.py`
- **Function naming**: `test_<function_name>_<scenario>`
- **Structure**: Arrange-Act-Assert pattern
- **Fixtures**: Use pytest fixtures for common setup
- **Mock externals**: Use `unittest.mock` or `pytest-mock`

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

## Web Interface Access Points

When web interface is running:
- **Main UI**: http://localhost:3000 (dev) or http://localhost:8765 (production)
- **Backend API**: http://localhost:8765/api/
- **API Documentation**: http://localhost:8765/api/docs (Swagger UI)
- **Health Check**: http://localhost:8765/api/health

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
rm ~/.auralis/library.db  # Will be recreated on next launch
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
- **Core Processing**: ✅ Production-ready (52.8x real-time speed, E2E validated)
- **Backend API**: ✅ 74% test coverage (96 tests, 100% passing)
- **Library Management**: ✅ 740+ files/second scanning
- **Audio Player**: ✅ Full playback with real-time processing

**Technical Debt:**
- Backend refactoring needed (main.py at 1,960 lines) - See `BACKEND_REFACTORING_ROADMAP.md`
- Version management system needed before production launch - See `VERSION_MIGRATION_ROADMAP.md`

### Additional Documentation
- `README.md` - User-facing documentation
- `NEXT_STEPS.md` - Development roadmap
- `UI_SIMPLIFICATION.md` - UI design philosophy
- `LIBRARY_MANAGEMENT_ADDED.md` - Library features
- `NATIVE_FOLDER_PICKER.md` - Native OS integration
- `VERSION_MIGRATION_ROADMAP.md` - Version management plan
- `BACKEND_REFACTORING_ROADMAP.md` - Backend modularization plan

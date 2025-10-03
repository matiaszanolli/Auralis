# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Auralis** is a professional adaptive audio mastering system with both desktop (Electron) and web (FastAPI + React) interfaces. The system provides intelligent, content-aware audio processing without requiring reference tracks, combining advanced DSP algorithms, machine learning, and real-time processing for studio-quality audio mastering.

### Key Capabilities
- **Adaptive Mastering** - Content-aware processing without reference tracks, analyzing audio characteristics for optimal mastering
- **Dual Interface** - Modern web UI (FastAPI + React) and native Electron desktop application
- **Real-time Processing** - Ultra-low latency streaming with 52.8x real-time performance
- **ML-Powered Features** - Genre classification, user preference learning, and comprehensive content analysis
- **Professional Analysis** - ITU-R BS.1770-4 compliant LUFS, spectrum analysis, phase correlation, dynamic range measurement
- **Library Management** - SQLite-based music library with metadata extraction, intelligent scanning (740+ files/second)
- **Performance Optimization** - 197x speedup through memory pools, caching, and SIMD acceleration

## Essential Commands

### Launch Applications
```bash
# Web interface (recommended for development and production)
python launch-auralis-web.py           # Production mode (http://localhost:8000)
python launch-auralis-web.py --dev     # Development mode with hot reload

# Electron desktop application
npm run dev                            # Development mode (starts backend + frontend + Electron)
npm run build                          # Build desktop application

# Package desktop application for distribution
npm run package                        # All platforms
npm run package:win                    # Windows
npm run package:mac                    # macOS
npm run package:linux                  # Linux

# Backend only (for API server mode)
cd auralis-web/backend && python main.py
```

### Testing
```bash
# Main adaptive processing test suite (26 comprehensive tests)
python -m pytest tests/test_adaptive_processing.py -v

# Backend API tests (96 tests, 74% coverage)
python -m pytest tests/backend/ -v
python -m pytest tests/backend/ --cov=auralis-web/backend --cov-report=term-missing -v

# End-to-end audio processing validation
python test_e2e_processing.py       # Test all presets with real audio
python analyze_outputs.py           # Analyze audio quality metrics

# All tests with coverage report
python -m pytest --cov=auralis --cov-report=html --cov-report=term-missing tests/ -v

# Focused auralis module tests
python -m pytest tests/auralis/ -v

# Quick test runner
python run_all_tests.py
```

### Demonstrations and Benchmarks
```bash
# Complete system demonstration
python final_system_demo.py

# Adaptive mastering demonstration
python demo_adaptive_mastering.py

# Performance optimization benchmarks (197x speedup)
python test_performance_optimization.py

# User preference learning demo
python test_preference_learning.py

# Real-time EQ testing (0.28ms processing time)
python test_realtime_eq.py

# Advanced dynamics testing
python test_dynamics.py
```

### Environment Setup
```bash
# Install Python core dependencies
pip install -r requirements.txt

# Install Electron desktop dependencies
cd desktop && npm install

# Install web frontend dependencies (optional, for web UI development)
cd auralis-web/frontend && npm install

# Install all Node.js dependencies at once (alternative)
npm run install:all

# Install development tools
pip install pytest pytest-cov soundfile scikit-learn mutagen

# Clean all build artifacts and node_modules
npm run clean
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
The main audio processing pipeline that handles all mastering operations:

- **`hybrid_processor.py`** - Main processing engine with three modes:
  - **Adaptive Mode** (primary): Intelligent mastering without reference tracks
  - **Reference Mode**: Traditional reference-based mastering
  - **Hybrid Mode**: Combines reference guidance with adaptive intelligence
- **`unified_config.py`** - Configuration system with genre profiles and adaptive settings
- **`processor.py`** - Legacy compatibility wrapper

**Core Analysis Components (`core/analysis/`)** - Content-aware processing:
- **`content_analyzer.py`** - ContentAnalyzer for adaptive processing (spectral, temporal, genre, energy analysis)
- **`target_generator.py`** - AdaptiveTargetGenerator for processing parameter adaptation

**Processing Components (`core/processors/`)** - Processing mode implementations:
- **`reference_mode.py`** - Traditional reference-based matching algorithm

### Advanced DSP System (`auralis/dsp/`)
Professional-grade digital signal processing components with modular architecture:

**Core Modules:**
- **`basic.py`** - Basic DSP utilities (RMS, normalize, amplify, mid-side processing)
- **`advanced_dynamics.py`** - Dynamics processing orchestrator (facade for modular components)
- **`realtime_adaptive_eq.py`** - Real-time EQ adaptation (0.28ms processing time)
- **`stages.py`** - Processing stages orchestration (EQ, compression, limiting)

**Psychoacoustic EQ System (`dsp/eq/`)** - Modular 26-band critical band EQ:
- **`psychoacoustic_eq.py`** - Main EQ orchestrator with content-aware adaptation
- **`critical_bands.py`** - Bark scale critical band calculations and frequency mapping
- **`masking.py`** - Psychoacoustic masking threshold calculations
- **`filters.py`** - FFT-based EQ filter implementation
- **`curves.py`** - Genre-specific EQ curves and content adaptation

**Dynamics Processing System (`dsp/dynamics/`)** - Modular dynamics processing:
- **`settings.py`** - Configuration dataclasses (DynamicsMode, CompressorSettings, LimiterSettings)
- **`envelope.py`** - EnvelopeFollower for attack/release processing
- **`compressor.py`** - AdaptiveCompressor with multiple detection modes (peak, RMS, hybrid)
- **`limiter.py`** - AdaptiveLimiter with ISR (inter-sample peak) and true peak limiting

**DSP Utilities (`dsp/utils/`)** - Organized utility functions:
- **`audio_info.py`** - Audio metadata (channel count, size, mono/stereo detection)
- **`conversion.py`** - Format conversions (dB ↔ linear)
- **`spectral.py`** - Spectral analysis (centroid, rolloff, ZCR, crest factor, tempo)
- **`adaptive.py`** - Adaptive processing (gain calculation, parameter smoothing, loudness)
- **`stereo.py`** - Stereo processing (width analysis, mid-side manipulation)

**Legacy Compatibility:**
- **`unified.py`** - Backward compatibility wrapper (re-exports from `dsp/utils/`)
- **`psychoacoustic_eq.py`** (root) - Backward compatibility wrapper (re-exports from `dsp/eq/`)

### Analysis Framework (`auralis/analysis/`)
Comprehensive audio analysis tools for content understanding:

**Core Analysis Modules:**
- **`content_analysis.py`** - Comprehensive content analyzer orchestrator (facade for modular components)
- **`ml_genre_classifier.py`** - ML genre classification facade (re-exports from `ml/`)
- **`spectrum_analyzer.py`** - Professional FFT analysis with A/C/Z weighting curves
- **`loudness_meter.py`** - ITU-R BS.1770-4 compliant LUFS measurement with gating
- **`phase_correlation.py`** - Stereo correlation analysis and vectorscope functionality
- **`dynamic_range.py`** - EBU R128 dynamic range calculation and compression detection

**Content Analysis System (`analysis/content/`)** - Modular content analysis:
- **`feature_extractors.py`** - Audio feature extraction (dynamic range, spectral spread/flux, attack time, harmonicity, rhythm)
- **`analyzers.py`** - ContentFeatures, GenreAnalyzer, MoodAnalyzer (valence, arousal, danceability)
- **`recommendations.py`** - Processing recommendation engine (EQ, dynamics, stereo suggestions)

**ML Genre Classification (`analysis/ml/`)** - Machine learning genre detection:
- **`classifier.py`** - MLGenreClassifier with RandomForest model
- **`feature_extraction.py`** - MFCC, chroma, spectral contrast, tonnetz, zero crossing rate features
- **`genre_rules.py`** - Rule-based fallback genre classification
- **`training.py`** - Model training utilities and data preparation

**Quality Assessment System (`analysis/quality/`)** - Modular quality metrics:
- **`quality_metrics.py`** - Main quality orchestrator (0-100 scoring with sub-metrics)
- **`frequency_assessment.py`** - Frequency response quality analysis
- **`dynamic_assessment.py`** - Dynamic range categorization (Excellent/Good/Compressed/Over-compressed)
- **`stereo_assessment.py`** - Stereo imaging quality (width, correlation, mono compatibility)
- **`distortion_assessment.py`** - Distortion and noise analysis (THD, clipping, SNR)
- **`loudness_assessment.py`** - Loudness standards compliance (Spotify, Apple Music, YouTube, EBU R128, ATSC A/85)

**Legacy Compatibility:**
- **`quality_metrics.py`** (root) - Backward compatibility wrapper (re-exports from `analysis/quality/`)

### Machine Learning System (`auralis/learning/`)
User preference learning for personalized mastering:

- **`preference_engine.py`** - PreferenceEngine orchestrator for user preference learning

**Preference Learning Components (`learning/components/`)** - Modular preference system:
- **`models.py`** - UserAction and UserProfile dataclasses for tracking user interactions
- **`predictor.py`** - PreferencePredictor with lightweight linear regression for parameter prediction

### Performance Optimization (`auralis/optimization/`)
- **`performance_optimizer.py`** - Memory pools, smart caching, SIMD acceleration, parallel processing (197x speedup)

### Audio I/O (`auralis/io/`)
- **`unified_loader.py`** - Multi-format audio loading: WAV, FLAC, MP3, OGG, M4A, AAC, WMA
- **`saver.py`** - Audio output in multiple formats
- **`results.py`** - Processing result containers
- **`loader.py`** - Legacy loader

### Library Management (`auralis/library/`)
SQLite-based music library system with modular architecture:

- **`manager.py`** - LibraryManager orchestrator using repository pattern
- **`scanner.py`** - Intelligent folder scanning with duplicate detection (740+ files/second)
- **`models.py`** - SQLAlchemy database models for tracks, albums, artists, playlists
- **`scan_models.py`** - ScanResult and AudioFileInfo dataclasses for library scanning

**Library Repositories (`library/repositories/`)** - Data access layer:
- **`base.py`** - BaseRepository with common database operations
- **`track_repository.py`** - Track-specific queries and operations
- **`album_repository.py`** - Album management with relationship handling
- **`artist_repository.py`** - Artist queries and track associations
- **`playlist_repository.py`** - Playlist CRUD and track management

### Audio Player (`auralis/player/`)
Audio playback system with real-time processing:

- **`audio_player.py`** - Basic audio playback
- **`enhanced_audio_player.py`** - Advanced player with real-time processing and queue management
- **`realtime_processor.py`** - Real-time audio processing for playback
- **`config.py`** - Player configuration

**Player Components (`player/components/`)** - Modular player features:
- **`queue_manager.py`** - QueueManager for playlist handling with shuffle/repeat support

### Web Interface (`auralis-web/`)
Modern web UI with real-time updates:

- **`backend/`** - FastAPI backend with WebSocket support for live updates
  - **`main.py`** - Main API server (library, player, processing endpoints)
  - **`processing_engine.py`** - Job queue system for audio processing (async worker)
  - **`processing_api.py`** - 10 REST API endpoints for processing operations
  - REST API for audio processing, library management, real-time playback
  - Real-time progress updates via WebSockets
  - API documentation at `/api/docs`
- **`frontend/`** - React frontend with Material Design
  - **`ProcessingInterface.tsx`** - Audio processing UI with file upload, job management
  - **`processingService.ts`** - TypeScript API client with WebSocket support
  - Smart file browser with grid/list views
  - Advanced search with multiple filters
  - Real-time library statistics
  - Professional audio player with real-time processing controls

### Desktop Application (`desktop/`)
Electron wrapper for native desktop experience:

- **`main.js`** - Main Electron process that:
  - Spawns Python backend process
  - Creates browser window loading React UI
  - Handles IPC for file/folder selection
  - Manages application lifecycle
- **`preload.js`** - Preload script for secure IPC
- **`package.json`** - Electron dependencies and build configuration

### Build and Development Scripts (`scripts/`)
- **`dev.js`** - Development environment launcher (starts backend + frontend + Electron)
- **`quick_build.sh`** - Quick build script

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

### Reference Mode (Legacy Compatibility)
Traditional reference-based mastering:

```python
config.set_processing_mode("reference")
processed_audio = processor.process(target_audio, reference_audio)
```

### Hybrid Mode (Best of Both)
Combines reference guidance with adaptive intelligence:

```python
config.set_processing_mode("hybrid")
processed_audio = processor.process(target_audio, reference_audio)
```

### Content Analysis and Genre Detection
```python
from auralis.analysis.content_analysis import AdvancedContentAnalyzer

analyzer = AdvancedContentAnalyzer()
analysis = analyzer.analyze(audio, sample_rate)
# Returns: genre, tempo, energy, mood, spectral features, etc.
```

### Available Processing Presets
- **Adaptive** (default): Intelligent content-aware mastering
- **Gentle**: Subtle mastering with minimal processing
- **Warm**: Adds warmth and smoothness to the sound
- **Bright**: Enhances clarity and presence
- **Punchy**: Increases impact and dynamics

## Performance Characteristics

### Processing Speed
- **52.8x average real-time factor** for adaptive mastering
- **197x speedup** with performance optimizations enabled
- **Sub-20ms latency** for real-time streaming
- **7.4x real-time factor** for streaming chunks
- **0.28ms processing time** for real-time adaptive EQ

### Library Management
- **740+ files/second** scanning speed
- **8,618 FPS** visualization performance
- SQLite database for efficient queries

### System Requirements
- **Python 3.8+** (Python 3.11+ recommended and optimized)
- **Node.js 16+** for Electron and web frontend
- **Memory**: 2GB+ RAM for large audio files
- **Processing**: Multi-core CPU recommended for parallel processing
- **Storage**: Minimal (SQLite database for library)

## Development Workflow

### Testing Strategy
The test suite is comprehensive and focuses on production functionality:

- **Core Functionality**: `tests/test_adaptive_processing.py` (26 comprehensive tests covering adaptive mode, genre detection, ML features)
- **Backend API Testing**: `tests/backend/` (96 tests, 100% passing, 74% coverage)
  - **`test_main_api.py`**: 57 tests for library, player, and processing endpoints
  - **`test_processing_api.py`**: 27 tests for processing API and job management
  - **`test_processing_engine.py`**: 20 tests for async job queue and worker
- **Component Testing**: `tests/auralis/` (individual module tests for DSP, analysis, library, player)
- **End-to-End Testing**: `test_e2e_processing.py` (validates real audio processing with all presets)
- **Performance Testing**: `test_performance_optimization.py` (benchmarks memory pools, caching, SIMD)
- **Integration Testing**: `final_system_demo.py` (end-to-end system demonstration)
- **74% Backend Coverage** (96 tests) and **59% Core Coverage** focused on essential functionality

### Code Organization Principles
- **Modular Design**: Each component is self-contained with clear interfaces
  - Large modules (400+ lines) have been refactored into focused sub-modules
  - Backward compatibility maintained via facade pattern in original files
  - New code should be organized into modules of 100-200 lines maximum
- **Factory Functions**: Use `create_*` functions for component instantiation (e.g., `create_ml_genre_classifier()`)
- **Configuration-Driven**: All processing controlled via `UnifiedConfig` class
- **Performance-Optimized**: Built-in caching and optimization using decorators (`@optimized`, `@cached`)
- **No Legacy Dependencies**: Fully integrated, no external Matchering dependencies

### Module Refactoring Pattern
When refactoring large modules, follow this established pattern:

1. **Create sub-package**: `mkdir auralis/<subsystem>/<module_name>/`
2. **Split by responsibility**: Create focused modules (e.g., `frequency_assessment.py`, `dynamic_assessment.py`)
3. **Main orchestrator**: Keep main class in `<module_name>/<module_name>.py`
4. **Public API**: Export all public classes/functions in `<module_name>/__init__.py`
5. **Backward compatibility**: Original file becomes re-export wrapper with deprecation notice
6. **Verify tests**: Ensure all existing tests pass without modification

**Successfully refactored modules (13 total, 50+ new focused modules):**
```
auralis/dsp/eq/                      # Psychoacoustic EQ (623→123 lines, -80%)
auralis/dsp/utils/                   # DSP utilities (1158→150 lines, -87%)
auralis/dsp/dynamics/                # Dynamics processing (718→293 lines, -59%)
auralis/analysis/quality/            # Quality metrics (889→249 lines, -72%)
auralis/analysis/content/            # Content analysis (723→227 lines, -69%)
auralis/analysis/ml/                 # ML genre classifier (623→29 lines, -95%)
auralis/core/analysis/               # Core analysis components (extracted from hybrid_processor)
auralis/core/processors/             # Processing mode implementations (extracted from hybrid_processor)
auralis/library/repositories/        # Library data access (541→184 lines, -66%)
auralis/learning/components/         # Preference learning (564→392 lines, -31%)
auralis/player/components/           # Player features (611→555 lines, -9%)
```

**Refactoring results:**
- **Average 60% size reduction** in refactored files
- **100% backward compatibility** maintained via facade pattern
- **100% test pass rate** (122/122 core tests, 96/96 backend tests)
- **~6,000 lines reorganized** into focused, maintainable modules

### Key Design Patterns
- **Unified Interface**: Single `HybridProcessor` handles all three processing modes
- **Content-Aware Processing**: All components adapt based on audio characteristics
- **Real-time Ready**: All processing designed for streaming applications
- **ML Integration**: Machine learning seamlessly integrated into processing pipeline
- **Dual UI Support**: Same Python backend serves both web and desktop UIs

### Important API Notes
- **HybridProcessor.process()**: Returns numpy array directly (not a result object)
- **Audio Player Methods**: Use `seek_to_position()` not `seek()`, `next_track()` not `next()`, `previous_track()` not `previous()`
- **Processing Endpoints**: Volume parameter is `volume` not `level`
- **Library Manager**: Database location is `~/.auralis/library.db` by default

### Import Patterns

**Recommended imports (new modular structure):**
```python
# DSP utilities and components
from auralis.dsp.utils import spectral_centroid, to_db, adaptive_gain_calculation
from auralis.dsp.eq import PsychoacousticEQ, generate_genre_eq_curve
from auralis.dsp.dynamics import AdaptiveCompressor, AdaptiveLimiter, EnvelopeFollower

# Analysis components
from auralis.analysis.quality import QualityMetrics, FrequencyResponseAssessor
from auralis.analysis.content import FeatureExtractor, GenreAnalyzer, MoodAnalyzer
from auralis.analysis.ml import MLGenreClassifier, extract_ml_features

# Core processing components
from auralis.core.analysis import ContentAnalyzer, AdaptiveTargetGenerator
from auralis.core.processors import apply_reference_matching

# Library management
from auralis.library.repositories import TrackRepository, AlbumRepository
from auralis.library.scan_models import ScanResult, AudioFileInfo

# ML and learning
from auralis.learning.components import UserAction, UserProfile, PreferencePredictor

# Player components
from auralis.player.components import QueueManager
```

**Legacy imports (still supported via backward compatibility):**
```python
# These still work but are deprecated
from auralis.dsp.unified import spectral_centroid, to_db
from auralis.dsp.psychoacoustic_eq import PsychoacousticEQ
from auralis.dsp.advanced_dynamics import DynamicsProcessor
from auralis.analysis.quality_metrics import QualityMetrics
from auralis.analysis.content_analysis import AdvancedContentAnalyzer
from auralis.analysis.ml_genre_classifier import MLGenreClassifier
```

**When to use which:**
- Use new modular imports for new code (better for code organization and understanding)
- Legacy imports maintained for backward compatibility only (existing code continues to work)
- All refactored modules follow facade pattern (original files re-export from sub-packages)

## Web Interface Access Points

When web interface is running:

- **Main UI**: http://localhost:3000 (dev) or http://localhost:8000 (production)
- **Backend API**: http://localhost:8000/api/
- **API Documentation**: http://localhost:8000/api/docs (Swagger UI)
- **Health Check**: http://localhost:8000/api/health

## Important Notes

### Git Workflow
- **Current branch**: `react-gui`
- **Main branch**: `master` (use this for PRs)
- **Repository**: https://github.com/matiaszanolli/Auralis
- **License**: GPL-3.0

### Project Structure
- **Python Backend**: All audio processing in `auralis/` module
- **Web Backend**: FastAPI application in `auralis-web/backend/`
- **Web Frontend**: React application in `auralis-web/frontend/`
- **Desktop App**: Electron wrapper in `desktop/`
- **Tests**: Comprehensive test suite in `tests/` (96 backend tests, 100% passing)
- **Demos**: Standalone demonstration scripts at root level

### Architecture Migration
The project has successfully migrated from Tkinter GUI to a modern dual-interface system:
- **Web interface**: Production-ready, modern, cross-platform
- **Desktop app**: Electron-based, native-like experience
- **Legacy Tkinter**: Removed, no longer used
- **Matchering dependencies**: Fully integrated into Auralis, no external dependencies

### Current Status and Launch Readiness
- **Core Processing**: ✅ 100% functional, E2E validated with professional audio quality
- **Backend API**: ✅ 74% test coverage (96 tests, 100% passing)
- **Processing Interface**: ✅ Complete with file upload, job management, real-time progress
- **Library Management**: ✅ 740+ files/second scanning, metadata extraction working
- **Audio Player**: ✅ Full playback controls, real-time processing validated
- **E2E Testing**: ✅ All 5 presets validated (Adaptive, Gentle, Warm, Bright, Punchy)

**⚠️ Critical Before Production Launch:**
- **Version Management System**: Database schema versioning and migration system needed
- **See**: `VERSION_MIGRATION_ROADMAP.md` for 8-12 hour implementation plan
- **See**: `LAUNCH_READINESS_CHECKLIST.md` for launch decision guide

**Beta Launch Ready**: Can launch now with disclaimers about potential database resets
**Production Ready**: After implementing version management system (1-2 weeks)
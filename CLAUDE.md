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
- [auralis-web/backend/main.py](auralis-web/backend/main.py:1) - Backend API server
- [auralis-web/frontend/src/components/ComfortableApp.tsx](auralis-web/frontend/src/components/ComfortableApp.tsx:1) - Main UI component
- [desktop/main.js](desktop/main.js:1) - Electron main process

**Running tests:**
```bash
python -m pytest tests/backend/ -v      # Backend tests (96 tests, fastest)
python -m pytest tests/test_adaptive_processing.py -v  # Core processing tests
```

## Project Overview

**Auralis** is a professional adaptive audio mastering system with both desktop (Electron) and web (FastAPI + React) interfaces. The system provides intelligent, content-aware audio processing without requiring reference tracks, combining advanced DSP algorithms, machine learning, and real-time processing for studio-quality audio mastering.

**Target Users:**
- **End Users**: Music lovers who want a simple, beautiful music player with one-click audio enhancement (use Desktop app)
- **Developers**: Audio engineers, researchers, or developers integrating audio processing (use Web interface or API)

**What makes it unique:**
- No reference tracks needed (adaptive processing)
- Professional-grade audio quality (52.8x real-time processing)
- Simple UI for end users, powerful API for developers
- 100% local processing (no cloud, complete privacy)

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

## Frequently Modified Files

When working on common tasks, you'll most likely be editing these files:

### Adding New Audio Processing Features
- [auralis/core/hybrid_processor.py](auralis/core/hybrid_processor.py:1) - Main processing pipeline
- [auralis/dsp/stages.py](auralis/dsp/stages.py:1) - Processing stages (EQ, compression, limiting)
- [auralis/core/unified_config.py](auralis/core/unified_config.py:1) - Processing configuration

### Modifying the Web UI
- [auralis-web/frontend/src/components/ComfortableApp.tsx](auralis-web/frontend/src/components/ComfortableApp.tsx:1) - Main app layout
- [auralis-web/frontend/src/components/CozyLibraryView.tsx](auralis-web/frontend/src/components/CozyLibraryView.tsx:1) - Library view
- [auralis-web/frontend/src/components/BottomPlayerBar.tsx](auralis-web/frontend/src/components/BottomPlayerBar.tsx:1) - Player controls

### Adding Backend API Endpoints
- [auralis-web/backend/main.py](auralis-web/backend/main.py:1) - Main API routes (library, player)
- [auralis-web/backend/processing_api.py](auralis-web/backend/processing_api.py:1) - Processing endpoints
- [auralis-web/backend/processing_engine.py](auralis-web/backend/processing_engine.py:1) - Background job queue

### Library Management Changes
- [auralis/library/manager.py](auralis/library/manager.py:1) - Library manager orchestrator
- [auralis/library/scanner.py](auralis/library/scanner.py:1) - Folder scanning logic
- [auralis/library/models.py](auralis/library/models.py:1) - Database schema

### Desktop App Configuration
- [desktop/main.js](desktop/main.js:1) - Electron main process
- [desktop/package.json](desktop/package.json:1) - Build configuration
- [scripts/package.js](scripts/package.js:1) - Packaging script

## UI/UX Design Philosophy

### Design Aesthetic
Auralis combines the classic library-based player experience (iTunes, Rhythmbox) with modern touches from Spotify and Cider:

**Visual Style:**
- **Dark theme** with deep navy/black backgrounds (#0A0E27, #1a1f3a)
- **Aurora gradient branding** - flowing purple/blue/pink waves (signature visual element)
- **Neon accents** - Vibrant retro-futuristic elements (neon sunsets, starlight, glowing effects)
- **Album art grid** - Large, prominent artwork cards with hover effects
- **Smooth animations** - Subtle transitions, gradient progress bars

**Layout Structure:**
```
┌─────────────┬──────────────────────────────┬───────────────┐
│  Sidebar    │      Main Content Area       │  Remastering  │
│  (Library)  │                              │     Panel     │
├─────────────┼──────────────────────────────┴───────────────┤
│             │           Player Bar                          │
└─────────────┴───────────────────────────────────────────────┘
```

**Left Sidebar (240px fixed):**
- Aurora gradient logo at top
- Library sections: Artists, Albums, Songs
- Playlists section (collapsible)
- Favourites & Recently Played
- Icons + text navigation

**Main Content Area (flexible):**
- Search bar at top
- Album/track grid with large artwork (160x160+)
- Track list view option
- Connection status indicator
- Smooth scrolling

**Right Panel (280-320px, collapsible):**
- "Remastering" header
- Preset selector dropdown (Studio, Vinyl, Live, Custom)
- On/Off toggle
- Intensity slider (if applicable)
- Preset description/info

**Bottom Player Bar (80-100px fixed):**
- Album art thumbnail (60x60)
- Track info (title, artist)
- Playback controls (prev, play/pause, next, repeat)
- Progress bar with gradient fill
- Current time / total time
- Volume control
- Magic toggle (right side)

**Color Palette:**
- Background: `#0A0E27` (deep navy)
- Surface: `#1a1f3a` (lighter navy)
- Accent: Aurora gradient `linear-gradient(135deg, #667eea 0%, #764ba2 100%)`
- Text primary: `#ffffff`
- Text secondary: `#8b92b0`
- Success: `#00d4aa` (turquoise)

**Typography:**
- Headers: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto
- Body: Same system font stack
- Sizes: 24px (headers), 16px (body), 14px (secondary)

**Key UI Patterns:**
- **Hover states** - Subtle scale transforms, opacity changes
- **Active states** - Gradient highlights, glow effects
- **Loading states** - Skeleton screens, shimmer effects
- **Empty states** - Centered messages with icons
- **Error states** - Red accents with helpful messages

### Component Implementation Guidelines

**Album/Track Cards:**
```tsx
// Visual appearance from screenshot
- Size: 160x160px minimum for artwork
- Border radius: 8px
- Hover effect: scale(1.05), subtle glow
- Title: Below artwork, white text, 16px
- Subtitle: Artist/author, gray text (#8b92b0), 14px
- Spacing: 16-24px gap between cards
- Grid: 3-4 columns on desktop, responsive
```

**Track List (Bottom Queue):**
```tsx
// As shown in screenshot bottom section
- Row height: 48px
- Columns: Track number (40px) | Title (flex) | Duration (60px)
- Hover: Background color change to #1a1f3a
- Current track: Highlighted with accent color
- Font: 14px regular, current track bold
```

**Player Controls:**
```tsx
// Bottom bar controls
- Play button: Large circular, aurora gradient background
- Skip buttons: Standard size, white icons
- Progress bar: Full width, aurora gradient fill
- Progress text: Both sides (current/total)
- Album art: 60x60px, rounded corners, left side
- Volume: Slider on right side
```

**Navigation Sidebar:**
```tsx
// Left sidebar navigation
- Width: 240px fixed
- Item height: 40px
- Icons: 20x20px, left-aligned with 16px padding
- Active state: Background highlight + accent border-left
- Hover state: Background color #1a1f3a
- Text: 14px, 8px padding-left from icon
```

**Remastering Panel:**
```tsx
// Right sidebar panel
- Width: 280-320px
- Toggle: Large switch component, accent color when on
- Dropdown: Custom styled select, dark theme
- Slider: Gradient track, circular thumb
- Labels: 12px uppercase, letter-spacing: 0.5px
```

**Search Bar:**
```tsx
// Top of main content area
- Height: 48px
- Border radius: 24px (pill shape)
- Background: Semi-transparent (#1a1f3a80)
- Icon: Search glass icon, left side, 20x20px
- Placeholder: "Search" in gray (#8b92b0)
- Focus: Border glow with accent color
```

**Empty States:**
```tsx
// When library is empty
- Center-aligned content
- Large icon (64x64px) in accent color
- Primary text: "No music yet" (20px)
- Secondary text: "Scan a folder to get started" (14px, gray)
- Action button: "Scan Folder" with gradient background
```

### Interaction Patterns

**Library View Switching:**
- Grid view (default) - Large album art cards
- List view (alternative) - Compact rows with small artwork
- Toggle button in toolbar

**Playlist Management:**
- Collapsible section in sidebar
- Expand/collapse arrow animation
- Create new playlist: "+" button at section header
- Drag-and-drop to add tracks (future feature)

**Context Menus:**
- Right-click on tracks/albums
- Options: Play, Add to queue, Add to playlist, Show info, etc.
- Dark background with subtle shadow
- Hover highlights with accent color

**Real-time Feedback:**
- Progress updates via WebSocket
- Smooth progress bar animations
- Loading spinners with gradient colors
- Success/error toast notifications (top-right)

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
- **`frontend/`** - React frontend with Material-UI
  - **Main entry point**: `App.tsx` → `ComfortableApp.tsx` (current active UI)
  - **Key components**:
    - `ComfortableApp.tsx` - Main app container with 3-column layout
    - `Sidebar.tsx` - Left navigation with library sections
    - `CozyLibraryView.tsx` - Main content area with track/album grid
    - `PresetPane.tsx` - Right panel for remastering controls
    - `BottomPlayerBar.tsx` - Bottom player with playback controls
    - `MagicalMusicPlayer.tsx` - Alternative standalone player UI
  - **Legacy components**:
    - `ProcessingInterface.tsx` - Original file upload/processing UI
    - Various visualization components (Phase5, AnalysisDashboard, etc.)
  - **Current UI Status**:
    - ✅ Three-column layout implemented (sidebar, main, preset pane)
    - ✅ Bottom player bar with controls
    - ✅ WebSocket connection for real-time updates
    - 🔄 Album art grid partially implemented
    - 🔄 Aurora gradient branding in progress
    - 📋 Need to match screenshot design aesthetic (neon accents, dark theme refinement)

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

- **Main UI**: http://localhost:3000 (dev) or http://localhost:8765 (production)
- **Backend API**: http://localhost:8765/api/
- **API Documentation**: http://localhost:8765/api/docs (Swagger UI)
- **Health Check**: http://localhost:8765/api/health

## Deployment Options

Auralis can be deployed in three different modes:

### 1. Web Application (Recommended for Production)
```bash
# Production mode
python launch-auralis-web.py
# Access at http://localhost:8765

# Custom port
python launch-auralis-web.py --port 5000

# Development mode with hot reload
python launch-auralis-web.py --dev
```

**Use case:** Multi-user access, web-based deployment, server installation

### 2. Desktop Application (Recommended for End Users)
```bash
# Development
npm run dev

# Build standalone app
npm run package               # Current platform
npm run package:linux        # Linux (.AppImage, .deb)
npm run package:win          # Windows (.exe)
npm run package:mac          # macOS (.dmg)
```

**Use case:** Single-user, offline usage, native OS integration

### 3. API Server (Headless)
```bash
cd auralis-web/backend
python main.py
# API only, no UI
```

**Use case:** Integration with other systems, CLI workflows, automation

## Troubleshooting

### Common Development Issues

**"Module not found" errors:**
```bash
# Ensure virtual environment is activated and dependencies installed
pip install -r requirements.txt
pip install pytest pytest-cov soundfile scikit-learn mutagen
```

**Frontend build errors:**
```bash
# Clean and rebuild
cd auralis-web/frontend
rm -rf node_modules package-lock.json
npm install
npm run build
```

**Database errors (library.db):**
```bash
# Reset database (WARNING: deletes all library data)
rm ~/.auralis/library.db
# Will be recreated on next launch
```

**WebSocket connection fails:**
- Ensure backend is running before loading frontend
- Check CORS settings in [auralis-web/backend/main.py](auralis-web/backend/main.py:1)
- Verify port 8765 is not blocked by firewall

**Tests failing:**
```bash
# Run tests with verbose output to see specific failures
python -m pytest tests/ -v --tb=short

# Run specific test file
python -m pytest tests/backend/test_main_api.py -v

# Run with coverage to identify missing tests
python -m pytest tests/ --cov=auralis --cov-report=term-missing -v
```

### Electron Build Issues

**AppImage shows startup error:**
- Check that port 8765 is not in use: `lsof -ti:8765 | xargs kill -9`
- Run from terminal to see logs: `./dist/Auralis-1.0.0.AppImage`
- Look for "Backend ready" and "Frontend loaded" messages

**DEB package installation:**
```bash
sudo dpkg -i dist/auralis-desktop_1.0.0_amd64.deb
sudo apt-get install -f  # Fix dependencies if needed
```

**Backend can't find frontend (during development):**
- The frontend path resolution differs between development and PyInstaller mode
- Check `auralis-web/backend/main.py` for correct path logic:
  - Development: `../../auralis-web/frontend/build`
  - PyInstaller: `Path(sys._MEIPASS).parent / "frontend"`

**Port conflicts:**
```bash
# Kill process on port 8765 (backend)
lsof -ti:8765 | xargs kill -9

# Kill process on port 3000 (frontend dev server)
lsof -ti:3000 | xargs kill -9
```

**See also:** `ELECTRON_BUILD_FIXED.md` for detailed build troubleshooting

## Important Notes

### Git Workflow
- **Current branch**: `master`
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

### Distribution Packages
Latest builds are production-ready:
- **AppImage**: `dist/Auralis-1.0.0.AppImage` (~246 MB) - portable, runs anywhere
- **DEB Package**: `dist/auralis-desktop_1.0.0_amd64.deb` (~176 MB) - for Ubuntu/Debian
- **Build includes**: Bundled Python backend (25 MB), React frontend (141 KB), all dependencies
- **Startup time**: ~5-8 seconds from launch to ready
- **Database location**: `~/.auralis/library.db` (auto-created on first run)

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

### UI Design Implementation Status

**Target Design** (from reference screenshot):
- Rhythm-based player aesthetic (iTunes/Rhythmbox) with modern touches (Spotify/Cider)
- Dark navy theme with neon/aurora accents
- Large album art grid with vibrant artwork
- Track queue at bottom of main view
- Three-panel layout: Sidebar | Main | Remastering

**Current Implementation Status:**

✅ **Completed:**
- Three-column responsive layout
- Bottom player bar with playback controls
- WebSocket real-time connection
- Material-UI component framework
- Basic library management

🔄 **In Progress:**
- Aurora gradient branding throughout UI
- Album art grid with proper sizing (160x160+)
- Dark navy theme refinement (#0A0E27 backgrounds)
- Neon accent integration
- Hover/active state animations

📋 **Needed for Target Design:**
- Large album art cards with neon/retro artwork style
- Track queue view below album grid (as shown in screenshot)
- Aurora gradient progress bar
- Gradient play button with proper styling
- Search bar with pill shape and semi-transparent background
- Sidebar active state with accent border-left
- Empty states with centered content and icons
- Album/track detail views with vibrant artwork
- Context menu on right-click
- Smooth transitions and micro-interactions
- Loading states with skeleton screens

**Design Files/References:**
- Target aesthetic: See screenshot in conversation (Auralis player with neon artwork)
- Color palette: Defined in UI/UX Design Philosophy section above
- Component specs: See Component Implementation Guidelines above

**Implementation Roadmaps:**
- **UI_IMPLEMENTATION_ROADMAP.md** - Complete 6-week implementation plan with phases
- **QUICK_START_UI_DEVELOPMENT.md** - Get started immediately with Phase 1 components
- **UI_COMPONENTS_CHECKLIST.md** - Track progress on all 35+ UI components

## Code Style and Best Practices

### Python Backend
- **Type hints**: Use type hints for function parameters and return values
- **Docstrings**: All public classes and functions should have docstrings
- **Error handling**: Use appropriate exceptions (ValueError, TypeError, etc.)
- **NumPy arrays**: Preferred over lists for audio processing
- **Async/await**: Use for I/O operations in FastAPI endpoints

**Example:**
```python
from typing import Optional
import numpy as np

def process_audio(audio: np.ndarray, sample_rate: int, volume: float = 1.0) -> np.ndarray:
    """
    Process audio with adaptive mastering.

    Args:
        audio: Input audio array (samples, channels)
        sample_rate: Sample rate in Hz
        volume: Output volume multiplier (0.0-1.0)

    Returns:
        Processed audio array with same shape as input

    Raises:
        ValueError: If audio is empty or sample_rate is invalid
    """
    if audio.size == 0:
        raise ValueError("Audio array cannot be empty")
    # Processing logic here
    return processed_audio
```

### React Frontend
- **TypeScript**: Always use TypeScript, no plain JavaScript
- **Functional components**: Use hooks instead of class components
- **Material-UI**: Use MUI components for consistency
- **State management**: useState for local, context for global state
- **API calls**: Use the service layer (e.g., `processingService.ts`)

**Example:**
```typescript
import React, { useState, useEffect } from 'react';
import { Button, CircularProgress } from '@mui/material';
import { processingService } from '../services/processingService';

interface TrackPlayerProps {
  trackId: string;
  onPlaybackChange?: (isPlaying: boolean) => void;
}

export const TrackPlayer: React.FC<TrackPlayerProps> = ({ trackId, onPlaybackChange }) => {
  const [isPlaying, setIsPlaying] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  // Component logic here
};
```

### Database Operations
- **Use repositories**: Always use repository pattern for database access
- **Transactions**: Use context managers for database transactions
- **Eager loading**: Use `joinedload()` to avoid N+1 queries
- **Error handling**: Catch SQLAlchemy exceptions and return meaningful errors

**Example:**
```python
from auralis.library.repositories import TrackRepository

# Good - uses repository
track_repo = TrackRepository(session)
tracks = track_repo.get_by_album(album_id)

# Avoid - direct SQLAlchemy queries in business logic
tracks = session.query(Track).filter_by(album_id=album_id).all()  # Don't do this
```

### File Organization
- **Maximum file size**: Keep modules under 300 lines
- **One class per file**: Except for related dataclasses
- **Use `__init__.py`**: Export public API from sub-packages
- **Avoid circular imports**: Use factory functions or forward references

### Testing
- **Test file naming**: `test_<module_name>.py`
- **Test function naming**: `test_<function_name>_<scenario>`
- **Arrange-Act-Assert**: Structure tests clearly
- **Fixtures**: Use pytest fixtures for common setup
- **Mock external dependencies**: Use `unittest.mock` or `pytest-mock`

**Example:**
```python
def test_process_audio_with_volume():
    # Arrange
    audio = np.random.randn(44100, 2)
    processor = HybridProcessor()

    # Act
    result = processor.process(audio, volume=0.5)

    # Assert
    assert result.shape == audio.shape
    assert np.max(np.abs(result)) <= 1.0
```

### Common Pitfalls to Avoid
- ❌ Don't modify audio files in place (always create new outputs)
- ❌ Don't use blocking I/O in FastAPI endpoints (use async)
- ❌ Don't hardcode file paths (use Path objects and configuration)
- ❌ Don't access database directly from UI components (use API)
- ❌ Don't commit large audio files to git (use .gitignore)
- ❌ Don't use `print()` for logging (use Python `logging` module)

### Performance Considerations
- ✅ Use NumPy vectorized operations instead of loops
- ✅ Cache expensive computations with `@lru_cache`
- ✅ Use generators for large datasets
- ✅ Profile before optimizing (use `cProfile` or `py-spy`)
- ✅ Use memory pools for repeated array allocations
- ✅ Batch database operations when possible
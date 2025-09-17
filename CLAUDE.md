# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Auralis** is a professional audio mastering system that combines the power of Matchering 2.0 with advanced library management and real-time processing. The project has evolved from a Python audio processing library into a comprehensive audio production platform with both desktop and web interfaces.

### Key Components
1. **Matchering 2.0** - Core audio processing library for reference-based mastering
2. **Auralis System** - Enhanced audio processing with library management and player functionality
3. **Web Interface** - Modern React/TypeScript frontend with FastAPI backend
4. **Analysis System** - Professional-grade audio analysis tools (Phase 5 completed)

## Architecture Overview

### Core Audio Processing (`matchering/`)
- **`core.py`** - Main processing pipeline with `process(target, reference)` function
- **`stages.py`** - Multi-stage processing: Level → Frequency → Limiting
- **`dsp.py`** - Core DSP functions (RMS, normalize, amplify, mid-side processing)
- **`limiter/`** - Custom Hyrax brickwall limiter implementation
- **`stage_helpers/`** - Level matching and frequency matching algorithms
- **`loader.py`** & **`saver.py`** - Audio I/O with multiple format support

### Auralis System (`auralis/`)
- **`core/`** - Enhanced processing pipeline and configuration
- **`dsp/`** - Advanced DSP algorithms and real-time processing
- **`library/`** - SQLite-based music library with metadata extraction
- **`player/`** - Audio player components with enhanced playback features
- **`analysis/`** - Professional analysis tools (spectrum, LUFS, correlation, quality metrics)
- **`io/`** - Audio input/output handling
- **`utils/`** - Utility functions and helpers

### Web Interface (`auralis-web/`)
- **Backend (`auralis-web/backend/`)** - FastAPI server with WebSocket support
- **Frontend (`auralis-web/frontend/`)** - React/TypeScript with Material-UI
- **Real-time Features** - WebSocket-based live updates and processing
- **Analysis Dashboard** - Professional visualization components (Phase 5)

### Test Suite (`tests/`)
- **66 comprehensive tests** covering all major functionality
- **Cross-platform validation** (Windows, macOS, Linux)
- **Performance benchmarks** (25-111x real-time processing speeds)
- **End-to-end workflow testing**

## Essential Commands

### Quick Launch
```bash
# Launch complete web interface (automatic)
python launch-auralis-web.py

# Development mode with hot reloading
python launch-auralis-web.py --dev

# Traditional desktop GUI (legacy)
python auralis_gui.py
```

### Web Interface (Manual)
```bash
# Backend API server
cd auralis-web/backend && python main.py

# Frontend development server
cd auralis-web/frontend && npm install && npm start

# Frontend production build
cd auralis-web/frontend && npm run build
```

### Testing
```bash
# Run all tests (recommended)
python run_all_tests.py

# Run with pytest (if available)
pytest tests/ --cov=auralis --cov=matchering

# Individual test suites
python tests/auralis/test_auralis_gui.py
python tests/auralis/test_playlist_manager.py
python tests/auralis/test_folder_scanner.py
```

### Dependencies
```bash
# Activate project virtual environment
pyenv activate matchering-3.11.11

# Core Python dependencies
pip install -r requirements.txt

# Additional GUI dependencies (if using desktop)
pip install customtkinter tkinterdnd2 mutagen psutil

# Development tools
pip install pytest pytest-cov soundfile
```

## Key Technical Details

### Audio Processing Pipeline
1. **Loading** - Multi-format support (WAV, FLAC, MP3, OGG, M4A, AAC, WMA)
2. **Level Matching** - RMS analysis and amplitude normalization
3. **Frequency Matching** - Spectral analysis with EQ curve application
4. **Dynamic Processing** - Advanced compression and limiting
5. **Output** - 16-bit/24-bit PCM in WAV/FLAC formats

### Core Dependencies
- **numpy** (>=1.23.4) - Numerical processing
- **scipy** (>=1.9.2) - Signal processing algorithms
- **soundfile** (>=0.11.0) - Audio I/O
- **resampy** (>=0.4.2) - Sample rate conversion
- **fastapi** (>=0.104.0) - Web API framework
- **SQLAlchemy** (>=2.0.22) - Database ORM

### Database & Library Management
- **SQLite database** for music library storage
- **Metadata extraction** from audio files (title, artist, album, duration)
- **Duplicate detection** and intelligent folder scanning
- **Real-time search** with multiple filter options
- **Playlist management** with full CRUD operations

### Web API Access Points
- **Main Interface**: http://localhost:3000 (dev) or http://localhost:8000
- **API Documentation**: http://localhost:8000/api/docs (Swagger UI)
- **Health Check**: http://localhost:8000/api/health
- **WebSocket**: ws://localhost:8000/ws for real-time updates

## Analysis System (Phase 5 - Complete)

### Professional Analysis Components
- **Spectrum Analyzer** - FFT-based analysis with A/C/Z weighting (`auralis/analysis/spectrum_analyzer.py`)
- **LUFS Loudness Meter** - ITU-R BS.1770-4 compliant measurement (`auralis/analysis/loudness_meter.py`)
- **Phase Correlation** - Stereo analysis with vectorscope (`auralis/analysis/phase_correlation.py`)
- **Dynamic Range** - DR calculation and compression detection (`auralis/analysis/dynamic_range.py`)
- **Quality Metrics** - Comprehensive quality scoring (`auralis/analysis/quality_metrics.py`)

### Visualization Components (React/TypeScript)
- **Enhanced Waveform** - Interactive waveform with zoom/grid controls
- **Professional Meter Bridge** - Multi-channel meters with peak hold
- **Correlation Display** - Vectorscope and stereo field visualization
- **Processing Activity View** - Real-time processing chain monitoring
- **Analysis Dashboard** - Integrated dashboard with performance optimization

### Performance Optimization
- **Adaptive quality adjustment** for smooth 60 FPS rendering
- **Data decimation** for large datasets
- **WebGL acceleration** for intensive visualizations
- **Canvas pooling** for memory efficiency

## Development Status

### Production Ready Components
- ✅ **Core Matchering Library** - 25-111x real-time processing speeds
- ✅ **Auralis Desktop GUI** - Feature-complete with modern interface
- ✅ **Web Interface** - Modern React frontend with FastAPI backend
- ✅ **Analysis System** - Professional-grade audio analysis tools
- ✅ **Test Suite** - 66 tests with comprehensive coverage
- ✅ **Cross-platform Support** - Windows, macOS, Linux compatibility

### Key Performance Metrics
- **Audio Processing**: 25-111x real-time factor (average ~70x)
- **Large File Support**: 2+ minute files at 100.6x real-time
- **Library Scanning**: 740+ files/second processing
- **Visualization**: 60 FPS with adaptive quality control
- **Memory Efficiency**: Optimized scaling with file size

## Configuration & Customization

### Processing Configuration
- **Default parameters** in `matchering/defaults.py`
- **Runtime configuration** via `auralis/core/config.py`
- **Web API settings** via environment variables

### UI Customization
- **React themes** in frontend Material-UI components
- **Color schemes** configurable in analysis dashboard
- **Layout options** (grid/tabs/compact) for different workflows

### File Structure Notes
- **Legacy GUI files** at repository root (`*gui*.py`, `launch_*.py`)
- **Modern web interface** in `auralis-web/` directory
- **Core processing** split between `matchering/` (legacy) and `auralis/` (enhanced)
- **Comprehensive documentation** in various `*.md` files
- **Examples and demos** in `examples/` directory

## Branch Information
- **Main branch**: `master`
- **Current development**: `react-gui` (Phase 5 analysis system)
- **Production ready**: All major components completed and tested
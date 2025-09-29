# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Auralis** is a professional adaptive audio mastering system that provides intelligent, content-aware audio processing without requiring reference tracks. The system combines advanced DSP algorithms, machine learning, and real-time processing to deliver studio-quality audio mastering.

### Key Capabilities
- **Adaptive Mastering** - Content-aware processing that analyzes audio characteristics and applies optimal mastering
- **Real-time Processing** - Ultra-low latency streaming with 52.8x real-time performance
- **ML-Powered Features** - Genre classification, user preference learning, and content analysis
- **Professional Analysis** - Spectrum analysis, LUFS metering, phase correlation, dynamic range analysis
- **Performance Optimization** - 197x speedup through memory pools, caching, and SIMD acceleration

## Essential Commands

### Development and Testing
```bash
# Run main adaptive processing tests
python -m pytest tests/test_adaptive_processing.py -v

# Run focused test suite (clean, no legacy dependencies)
python -m pytest tests/auralis/ -v

# Test with coverage reporting
python -m pytest --cov=auralis --cov-report=html --cov-report=term-missing tests/ -v

# Run performance benchmarks
python test_performance_optimization.py

# Test user preference learning
python test_preference_learning.py

# Complete system demonstration
python final_system_demo.py
```

### Core Processing
```bash
# Basic adaptive mastering
python -c "from auralis.core.hybrid_processor import HybridProcessor; from auralis.core.unified_config import UnifiedConfig; config = UnifiedConfig(); processor = HybridProcessor(config); print('Adaptive mastering system ready')"

# Test audio loading and analysis
python -c "from auralis.io.unified_loader import load_audio; from auralis.analysis.content_analysis import ContentAnalyzer; analyzer = ContentAnalyzer(); print('Analysis system ready')"
```

### Environment Setup
```bash
# Install core dependencies
pip install -r requirements.txt

# Additional ML dependencies for advanced features
pip install scikit-learn>=1.3.0 mutagen>=1.47.0

# Development and testing tools
pip install pytest pytest-cov soundfile
```

## Architecture Overview

### Core Processing Engine (`auralis/core/`)
- **`hybrid_processor.py`** - Main processing engine supporting adaptive, reference, and hybrid modes
- **`unified_config.py`** - Comprehensive configuration system with genre profiles and adaptive settings
- **`processor.py`** - Legacy wrapper maintaining compatibility

### Advanced DSP System (`auralis/dsp/`)
- **`unified.py`** - Core DSP functions (RMS, spectral analysis, adaptive gain calculation)
- **`psychoacoustic_eq.py`** - 26-band critical band EQ with masking threshold calculations
- **`realtime_adaptive_eq.py`** - Real-time EQ adaptation with 0.28ms processing time
- **`advanced_dynamics.py`** - Intelligent compression and limiting with content-aware adaptation

### Analysis Framework (`auralis/analysis/`)
- **`content_analysis.py`** - Comprehensive audio content analysis with 50+ features
- **`ml_genre_classifier.py`** - Machine learning-based genre classification
- **`spectrum_analyzer.py`** - Professional FFT analysis with A/C/Z weighting
- **`loudness_meter.py`** - ITU-R BS.1770-4 compliant LUFS measurement
- **`phase_correlation.py`** - Stereo analysis and vectorscope functionality
- **`dynamic_range.py`** - DR calculation and compression detection
- **`quality_metrics.py`** - Comprehensive audio quality assessment

### Learning System (`auralis/learning/`)
- **`preference_engine.py`** - ML-powered user preference learning with adaptive parameter generation

### Performance Optimization (`auralis/optimization/`)
- **`performance_optimizer.py`** - Memory pools, smart caching, SIMD acceleration, and parallel processing

### Audio I/O (`auralis/io/`)
- **`unified_loader.py`** - Multi-format audio loading (WAV, FLAC, MP3, OGG, M4A, AAC, WMA)
- **`saver.py`** - Audio output in multiple formats
- **`results.py`** - Processing result containers

### Library Management (`auralis/library/`)
- **`manager.py`** - SQLite-based music library with metadata extraction
- **`scanner.py`** - Intelligent folder scanning with duplicate detection
- **`models.py`** - Database models for tracks, albums, artists, playlists

### Player Components (`auralis/player/`)
- **`audio_player.py`** - Core audio playback functionality
- **`enhanced_audio_player.py`** - Advanced player with real-time processing
- **`realtime_processor.py`** - Real-time audio processing for playback

## Key Processing Modes

### Adaptive Mode (Primary)
```python
from auralis.core.hybrid_processor import HybridProcessor
from auralis.core.unified_config import UnifiedConfig

config = UnifiedConfig()
config.set_processing_mode("adaptive")
processor = HybridProcessor(config)

# Process audio without reference
processed_audio = processor.process(target_audio)
```

### Reference Mode (Legacy Compatibility)
```python
# Traditional reference-based mastering
config.set_processing_mode("reference")
processed_audio = processor.process(target_audio, reference_audio)
```

### Hybrid Mode (Best of Both)
```python
# Combines reference guidance with adaptive intelligence
config.set_processing_mode("hybrid")
processed_audio = processor.process(target_audio, reference_audio)
```

## Performance Characteristics

### Processing Speed
- **52.8x average real-time factor** for adaptive mastering
- **197x speedup** with performance optimizations enabled
- **Sub-20ms latency** for real-time streaming applications
- **7.4x real-time factor** for streaming chunks

### System Requirements
- **Python 3.11+** (tested and optimized)
- **Memory**: 2GB+ RAM for large files
- **Processing**: Multi-core recommended for parallel processing
- **Storage**: SQLite for library management

## Advanced Features

### Machine Learning Integration
- **Genre Classification**: 50+ audio features with ML prediction
- **User Preference Learning**: Adaptive parameter adjustment based on user feedback
- **Content Analysis**: Automatic mood detection and processing recommendations

### Real-time Capabilities
- **Streaming Processing**: Process audio chunks in real-time
- **Adaptive EQ**: 26 critical bands with instant adaptation
- **Performance Monitoring**: Built-in profiling and optimization

### Professional Analysis
- **Spectrum Analysis**: FFT with professional weighting curves
- **Loudness Metering**: Broadcast-standard LUFS measurement
- **Quality Assessment**: Comprehensive audio quality metrics
- **Phase Analysis**: Stereo correlation and vectorscope

## Development Workflow

### Testing Strategy
- **Core Functionality**: `tests/test_adaptive_processing.py` (26 comprehensive tests)
- **Component Testing**: `tests/auralis/` (individual module tests)
- **Performance Testing**: `test_performance_optimization.py`
- **Integration Testing**: `final_system_demo.py`

### Code Organization
- **Modular Design**: Each component is self-contained with clear interfaces
- **Factory Functions**: Use `create_*` functions for component instantiation
- **Configuration-Driven**: All processing controlled via `UnifiedConfig`
- **Performance-Optimized**: Built-in caching and optimization throughout

### Key Design Patterns
- **Unified Interface**: Single `HybridProcessor` handles all processing modes
- **Content-Aware Processing**: All components adapt based on audio characteristics
- **Real-time Ready**: All processing designed for streaming applications
- **ML Integration**: Machine learning seamlessly integrated into processing pipeline

## File Structure Notes
- **Main Processing**: All core functionality in `auralis/` module
- **Legacy Removed**: No matchering dependencies (fully integrated)
- **Clean Tests**: Test suite focused on production code only
- **Performance Demos**: Standalone demonstration scripts at root level
- **Configuration**: Runtime settings via `UnifiedConfig` class

## Current Status
- **Production Ready**: Core adaptive mastering system complete
- **59% Test Coverage**: Focused on essential functionality
- **Performance Optimized**: Production-ready with significant speedups
- **Clean Architecture**: No legacy dependencies, modern Python design
- **Fully Integrated**: All components work together seamlessly
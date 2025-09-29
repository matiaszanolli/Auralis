# Auralis - Professional Audio Mastering System

🎵 **A unified audio mastering platform combining the power of Matchering 2.0 with advanced library management and real-time processing.**

## 🚀 Quick Start

### Installation
```bash
# Install dependencies
pip install -r requirements.txt

# Install additional GUI dependencies
pip install customtkinter tkinterdnd2 mutagen psutil
```

### Launch Auralis
```bash
python auralis_gui.py
```

## ✨ Features

- **🎛️ Professional Audio Mastering** - Advanced DSP with real-time level matching and auto-mastering
- **📊 Advanced Audio Analysis** - ITU-R BS.1770-4 compliant loudness measurement, spectrum analysis, phase correlation
- **📚 Comprehensive Library Management** - SQLite-based music library with metadata extraction
- **🖱️ Drag-and-Drop Import** - Easy music file import with progress tracking
- **📁 Intelligent Folder Scanning** - Recursive directory scanning with duplicate detection
- **📋 Playlist Management** - Create, edit, and manage playlists with full GUI support
- **📈 Real-time Visualizations** - Professional mastering parameter displays with dynamic range analysis
- **⚡ High Performance** - 740+ files/second scanning, 8,618 FPS visualizations

## 🎵 Supported Formats

**Audio Input:** MP3, FLAC, WAV, OGG, M4A, AAC, WMA
**Audio Output:** WAV, FLAC (16-bit/24-bit PCM)

## 📊 Advanced Audio Analysis (Phase 5.1)

Auralis features a comprehensive audio analysis suite with professional-grade algorithms:

### 🔬 Spectrum Analyzer
- **FFT-based analysis** with configurable window sizes and overlap
- **Frequency weighting** support (A, C, Z weighting curves)
- **Logarithmic frequency bins** for professional audio visualization
- **Real-time smoothing** with configurable time constants

### 📢 Loudness Meter
- **ITU-R BS.1770-4 compliant** LUFS measurement
- **K-weighting filters** for accurate loudness perception
- **Gating algorithms** for integrated and short-term loudness
- **True peak detection** with oversampling
- **Loudness range (LRA)** calculation

### 🎭 Phase Correlation Analyzer
- **Stereo correlation coefficient** calculation
- **Phase stability analysis** over time
- **Stereo width measurement** and spatial positioning
- **Mono compatibility** assessment

### 📈 Dynamic Range Analyzer
- **EBU R128 dynamic range** measurement
- **Compression ratio estimation** with attack/release detection
- **Peak-to-Loudness Ratio (PLR)** calculation
- **Crest factor analysis** for signal dynamics
- **Loudness war assessment** metrics

### 🔧 Usage Example
```python
from auralis.analysis import SpectrumAnalyzer, LoudnessMeter, PhaseCorrelationAnalyzer, DynamicRangeAnalyzer

# Initialize analyzers
spectrum = SpectrumAnalyzer()
loudness = LoudnessMeter(sample_rate=44100)
phase = PhaseCorrelationAnalyzer()
dynamics = DynamicRangeAnalyzer()

# Analyze audio
spectrum_data = spectrum.analyze_spectrum(audio_data)
loudness_data = loudness.measure_loudness(audio_data)
phase_data = phase.analyze_correlation(stereo_audio)
dr_data = dynamics.analyze_dynamic_range(audio_data)
```

## 🧪 Testing

```bash
# Run all tests
python run_all_tests.py

# Run individual test suites
python tests/auralis/test_auralis_gui.py
python tests/auralis/test_playlist_manager.py
python tests/auralis/test_folder_scanner.py
python tests/auralis/test_drag_drop.py
```

## 📖 Documentation

- **[Technical Documentation](docs/)** - Detailed system documentation
- **[Development Roadmap](docs/DEVELOPMENT_ROADMAP.md)** - Future development plans
- **[Performance Benchmarks](docs/PERFORMANCE_BENCHMARKS.md)** - System performance metrics
- **[Examples](examples/)** - Audio examples and usage demonstrations

## 🏗️ Architecture

```
auralis/                 # Core Auralis system
├── analysis/           # Advanced audio analysis (Phase 5.1)
│   ├── spectrum_analyzer.py    # FFT-based spectrum analysis with A/C/Z weighting
│   ├── loudness_meter.py       # ITU-R BS.1770-4 compliant LUFS measurement
│   ├── phase_correlation.py    # Stereo correlation and spatial analysis
│   └── dynamic_range.py        # Dynamic range analysis with compression detection
├── core/               # Core system components
├── dsp/                # Digital signal processing
├── io/                 # Audio input/output
├── library/            # Music library management
├── player/             # Audio player components
└── utils/              # Utility functions

matchering/             # Legacy Matchering 2.0 core
tests/                  # Comprehensive test suite
examples/               # Usage examples and demo files
docs/                   # Documentation
```

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the GPL-3.0 License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Original **Matchering 2.0** audio processing algorithms
- **CustomTkinter** for modern GUI framework
- All contributors and supporters of the project

---

**🎵 Professional audio mastering made accessible to everyone.**
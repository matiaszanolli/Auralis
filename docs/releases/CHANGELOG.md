# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.2.0-beta.1] - 2025-12-21

### Overview
Major release featuring enhanced audio streaming stability, real-time playback improvements, and automated CI/CD release pipeline. This release focuses on production-ready audio streaming with significant buffer management improvements.

**Status**: ✅ Beta Release | **Breaking Changes**: Rust DSP module now required | **Platforms**: Linux, Windows, macOS

### Added

#### Enhanced Playback Mode
- New enhanced playback mode toggle in PlayerEnhancementPanel
- Real-time audio enhancement controls for live streaming playback
- UI toggle for switching between standard and enhanced playback modes

#### Automated CI/CD Release Pipeline
- GitHub Actions workflow for automated multi-platform builds
- Linux builds: AppImage (universal) and .deb (Debian/Ubuntu)
- Windows builds: NSIS installer (.exe)
- macOS builds: DMG disk image (x64 and arm64)
- Automated GitHub Release creation with draft review workflow
- Build artifact retention and smoke testing

### Changed

#### Rust DSP Module Now Required
- Rust DSP module (`vendor/auralis-dsp`) is now a required dependency
- Previously optional with librosa fallback, now mandatory for performance
- PyO3 bindings with ABI3 forward compatibility for Python 3.13+
- HPSS, YIN, Chroma, Tempo detection all use optimized Rust implementations

#### Audio Buffer Management
- Increased buffer size to prevent audio position jumps
- Changed overflow behavior from error to graceful handling
- Improved buffer health monitoring to prevent underrun cascades
- PCMStreamBuffer overflow now handled gracefully to prevent buffer corruption

### Fixed

#### Audio Streaming Stability
- **Position jumps**: Prevented by increasing buffer and changing overflow behavior
- **Buffer underruns**: Added health monitoring to prevent underrun cascades
- **Buffer corruption**: PCMStreamBuffer overflow now handled gracefully
- **Stale playback state**: WebSocket disconnect handling prevents stale state
- **Backward audio jumps**: Resolved chunk overlap bug causing backward jumps

#### WebSocket Integration
- Proper disconnect handling prevents stale playback state
- Improved streaming playback integration with library components
- Better error recovery during WebSocket reconnection

### Performance

#### Streaming Improvements
- Real-time factor: 36.6x on real-world audio (maintained)
- Reduced buffer-related audio glitches
- More stable playback under varying network conditions
- Improved chunk processing reliability

### Build & Infrastructure

#### CI/CD Configuration
- Node.js 24 support across all platforms
- Python 3.13 with PyO3 ABI3 forward compatibility
- Protobuf compiler installation for Rust DSP builds
- Cross-platform build matrix (Linux, Windows, macOS)

### Documentation

#### Updated References
- CLAUDE.md updated to reflect Rust DSP requirement
- Version synchronization across all project files
- Build workflow documentation

### Known Issues

- macOS builds require code signing for Gatekeeper (currently bypassed)
- First-time launch on macOS may require right-click → Open

---

## [1.1.0-beta.3] - 2025-11-29

### Overview
Comprehensive 6-phase refactoring of the fingerprint module, eliminating 750+ lines of duplicate code, reorganizing 27 files into a logical hierarchy, and adding complete type hints for production-ready code quality.

**Status**: ✅ Ready for Release | **Breaking Changes**: None | **Test Coverage**: 51/51 passing

### Added

#### Phase 6: Enhanced Type Hints & Code Quality
- Complete type hints for `spectral_ops.py` (4/4 functions typed)
- Complete type hints for `variation_ops.py` (5/5 functions typed)
- Class attribute typing in `dsp_backend.py` (AVAILABLE, _module)
- Module-level constant typing in `harmonic_ops.py` (RUST_DSP_AVAILABLE)
- Instance attribute typing in `harmonic_sampled.py` (DEFAULT_FEATURES, chunk_duration, interval_duration)
- Type coverage: 82% → 100% on critical modules
- Support for static type checking with mypy
- Enhanced IDE autocomplete and type checking

#### Phase 5: Directory Reorganization
- Logical hierarchical structure for fingerprint module
- `analyzers/batch/` - Full-audio batch processing analyzers (6 analyzers)
- `analyzers/streaming/` - Real-time streaming analyzers (5 analyzers)
- `utilities/` - Reusable calculation components (5 utility modules)
- Updated 150+ import statements across codebase
- Clear separation of batch vs streaming architecture

#### Phase 4: Spectral & Variation Operations Consolidation
- `SpectralOperations` utility class (231 lines)
  - `calculate_spectral_centroid()` - Spectral centroid (0-1 normalized)
  - `calculate_spectral_rolloff()` - Spectral rolloff (0-1 normalized)
  - `calculate_spectral_flatness()` - Spectral flatness (0-1 normalized)
  - `calculate_all()` - All spectral features with STFT pre-computation optimization
- `VariationOperations` utility class (259 lines)
  - `get_frame_peaks()` - Vectorized frame peak detection
  - `calculate_dynamic_range_variation()` - Dynamic range variation (0-1)
  - `calculate_loudness_variation()` - Loudness variation (0-10 dB)
  - `calculate_peak_consistency()` - Peak consistency (0-1)
  - `calculate_all()` - All variation features with RMS/peaks pre-computation optimization
- Pre-computation optimization pattern: STFT computed once, reused across all spectral features
- Pre-computation optimization pattern: RMS and frame peaks computed once, reused

#### Phase 3: Streaming Analyzer Infrastructure Consolidation
- `BaseStreamingAnalyzer` mixin class for shared streaming infrastructure
- Unified streaming algorithm framework
- Shared buffer management with configurable ring buffers
- Consistent STFT windowing across all streaming analyzers
- Reusable online statistical computation patterns (Welford's algorithm)
- 5 streaming analyzers refactored to use base class

#### Phase 2: Temporal Operations Consolidation
- `TemporalOperations` utility class
- Shared temporal feature calculations for batch and streaming analyzers

#### Phase 1: Harmonic Operations Consolidation
- `HarmonicOperations` utility class
- Shared harmonic feature calculations for batch and streaming analyzers
- Backward compatibility: RUST_DSP_AVAILABLE re-export

### Changed

#### Code Consolidation
- `SpectralAnalyzer`: 203 lines → 54 lines (-73%, 149 lines eliminated)
- `VariationAnalyzer`: 222 lines → 54 lines (-76%, 168 lines eliminated)
- 8+ analyzer files refactored to use consolidated utilities
- Total: 750+ lines of duplicate code eliminated

#### File Organization
- 27 files reorganized into logical hierarchy
- Batch analyzers moved to `analyzers/batch/` subdirectory
- Streaming analyzers moved to `analyzers/streaming/` subdirectory
- Utility modules consolidated in `utilities/` subdirectory
- Base classes centralized for reuse

#### Import Paths
- All relative imports updated to reflect new directory structure
- Backward compatibility maintained through re-exports
- Old import paths still functional

### Fixed

#### Phase 4: Backward Compatibility
- Fixed RUST_DSP_AVAILABLE re-export in `HarmonicAnalyzer`
- Ensured existing imports continue working unchanged

### Performance

#### Spectral Features Optimization
- Pre-computed STFT reused across all 3 spectral features
- Elimination of 2 redundant STFT computations per call to `calculate_all()`
- Estimated savings: 100-200ms on typical audio (prevents 3x computation overhead)

#### Variation Features Optimization
- Pre-computed RMS reused across dynamic range and loudness variation calculations
- Pre-computed frame peaks reused across dynamic range and peak consistency calculations
- Elimination of redundant expensive computations
- Estimated savings: Multiple STFT/RMS/peak computations avoided

#### Vectorization Improvements
- Frame peak detection uses NumPy vectorization
- Spectral rolloff calculation optimized with vectorized operations
- Frame-based operations use efficient NumPy indexing

### Testing

#### Test Coverage
- All 51 tests passing (100% pass rate)
- Zero test regressions
- No test modifications needed (backward compatible)

#### Test Categories
- Unit tests (fast, isolated)
- Integration tests (multiple components)
- Boundary tests (edge cases, limits)
- Invariant tests (properties that MUST hold)
- Performance tests (benchmarks)

### Documentation

#### New Documentation
- `docs/RELEASE_1_1_0_FINGERPRINT_REFACTORING.md` - Comprehensive release notes
- `REFACTORING_PHASE_6_SUMMARY.md` - Type hints & code quality details
- `REFACTORING_PHASE_5_SUMMARY.md` - Directory reorganization details
- `REFACTORING_PHASE_4_SUMMARY.md` - Spectral & variation consolidation details

#### Existing Documentation
- Phase 1-3 summaries already documented in project history

### Backward Compatibility

✅ **100% Maintained**
- All public APIs unchanged
- All imports supported (direct imports from utilities + re-exports)
- All functionality identical (zero behavioral changes)
- Type hints are optional (no runtime impact)
- Test suite unchanged (no test modifications needed)

### Type Safety

#### Type Hint Coverage
- `utilities/spectral_ops.py`: 4/4 functions (100%)
- `utilities/variation_ops.py`: 5/5 functions (100%)
- `utilities/dsp_backend.py`: 4/4 methods + class attributes (100%)
- `utilities/harmonic_ops.py`: 4/4 functions + module constant (100%)
- `utilities/temporal_ops.py`: 5/5 functions (100%)
- `analyzers/batch/harmonic_sampled.py`: 4/4 methods + class attributes (100%)

#### Type Hint Patterns
- `np.ndarray` for audio signals
- `int` for sample rate and parameters
- `Optional[X]` for nullable values
- `Tuple[X, Y, Z]` for multiple returns
- `Dict[str, float]` for feature dictionaries
- `Any` for flexible/module types

#### Static Type Checking
- mypy validation successful on all modified modules
- Full IDE autocomplete support
- Real-time type checking in modern IDEs

---

## Previous Releases

### [1.0.0] - Prior Release
- Initial stable release with fingerprint module functionality
- Contains: batch analyzers, streaming analyzers, utility calculations
- Note: Contains duplicate code and lacks type hints (addressed in 1.1.0)

---

## Release Commits

```
bb5ab1c docs: Release 1.1.0 - Fingerprint Module Refactoring Summary
b9ee6c6 refactor: Phase 6 - Enhanced Type Hints & Code Quality
3a7a847 refactor: Phase 5 - Directory Reorganization & Structural Improvement
b1bf376 refactor: Phase 4 - Spectral & Variation Operations Consolidation
bddf858 refactor: Phase 3 - Streaming Analyzer Infrastructure Consolidation
96a2e97 refactor: Phases 1 & 2 - Fingerprint Module Consolidation (350+ lines eliminated)
```

---

## Future Roadmap

### Phase 7: Expand Type Hints (Optional)
- Type hints for remaining streaming analyzers
- Type hints for infrastructure modules (normalizer, similarity)
- Type hints for common_metrics module
- Coverage: 100% of fingerprint module

### Phase 8: Type Protocols (Advanced)
- Define `Protocol` for analyzer interface
- Define `Protocol` for operation interface
- Improved type checking for polymorphic code

### Phase 9: Type Stubs (Advanced)
- Create `.pyi` stub files for generated modules
- Type hints for compiled Rust extensions
- Type information for dynamic code

### Phase 10: Performance Profiling (Optional)
- Profile audio processing performance
- Identify remaining optimization opportunities
- Benchmark against previous version

---

## Migration Guide

### For Users Upgrading from 1.0.0 → 1.1.0

**No action required!** This release is 100% backward compatible.

#### Optional: Migrate to New Import Paths
```python
# Old imports (still work)
from auralis.analysis.fingerprint.harmonic_analyzer import HarmonicAnalyzer

# New imports (recommended for clarity)
from auralis.analysis.fingerprint.analyzers.batch.harmonic import HarmonicAnalyzer
from auralis.analysis.fingerprint.utilities.harmonic_ops import HarmonicOperations
```

#### Type Checking (New Feature)
```bash
# Type check with mypy (now possible!)
mypy auralis/analysis/fingerprint/
```

---

## Known Issues

### None Identified
- All tests passing
- All functionality verified
- Zero regressions detected

---

## Contributors

- Claude Code (Refactoring implementation, type hints, documentation)
- Test suite: 51 tests validating all changes

---

## License

GPL-3.0 (See LICENSE file)

---

**Release maintained by**: Claude Code
**Last updated**: 2025-11-29

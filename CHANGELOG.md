# Changelog

All notable changes to Auralis will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Features in development

### Changed
- Changes in development

### Fixed
- Fixes in development

## [1.0.0-alpha.1] - 2025-10-24

### Added
- **Performance Optimization System**: Comprehensive audio processing optimizations
  - Numba JIT compilation for envelope following (40-70x speedup)
  - NumPy vectorization for psychoacoustic EQ (1.7x speedup)
  - Parallel FFT processing for long audio files (3.4x speedup)
  - Overall real-time factor: 36.6x on real-world audio
- **Version Management System**: Single source of truth (`auralis/version.py`)
  - Version sync script for bumping versions across project
  - Version API endpoint (`/api/version`)
  - Semantic versioning standard (SemVer 2.0.0)
- **Library Scan API**: Backend endpoint for scanning music folders
  - `POST /api/library/scan` with duplicate prevention
  - Background job processing with progress updates
- **Large Library Support**: Optimizations for 10k+ track libraries
  - Pagination support (50 tracks per page)
  - Query result caching (136x speedup on cache hits)
  - 12 performance indexes in database (schema v3)
- **Comprehensive Documentation**: 12+ documents covering performance work
  - Performance optimization quick start guide
  - Complete benchmark results and analysis
  - Technical deep dives on Numba JIT and vectorization

### Changed
- **Backend Architecture**: Refactored to modular router pattern
  - Reduced `main.py` from 1,960 to 614 lines
  - Separated concerns into focused router modules
  - Improved maintainability and testability
- **Processing Pipeline**: Optimized with graceful fallbacks
  - Compressor uses vectorized envelope follower
  - Limiter uses vectorized envelope follower
  - PsychoacousticEQ uses vectorized processing
  - Falls back to standard implementations without Numba
- **Performance**: 2-3x overall pipeline improvement
  - Processes 1 hour of audio in ~98 seconds
  - Component performance: 54-323x real-time
  - Zero breaking changes, optional Numba dependency

### Fixed
- **RMS Boost Overdrive**: No more overdrive on already-loud material
- **Dynamics Expansion**: All 4 behaviors working correctly
  - Heavy Compression
  - Light Compression
  - Preserve Dynamics
  - Expand Dynamics (de-mastering)
  - Average 0.67 dB crest error, 1.30 dB RMS error
- **Database Performance**: Optimized queries for large libraries

### Performance
- **Real-time Factor**: 36.6x on real-world audio (Iron Maiden - 232.7s track in 6.35s)
- **Envelope Following**: 40-70x faster (7.4ms → 0.1ms per second of audio)
- **EQ Processing**: 1.7x faster (0.22ms → 0.13ms per chunk)
- **Spectrum Analysis**: 3.4x faster for long audio (> 60 seconds)
- **Library Queries**: 136x faster on cache hits

### Documentation
- [PERFORMANCE_OPTIMIZATION_QUICK_START.md](PERFORMANCE_OPTIMIZATION_QUICK_START.md) - Quick start guide
- [BENCHMARK_RESULTS_FINAL.md](BENCHMARK_RESULTS_FINAL.md) - Complete benchmark data
- [PERFORMANCE_REVAMP_FINAL_COMPLETE.md](PERFORMANCE_REVAMP_FINAL_COMPLETE.md) - Complete technical story
- [VERSIONING_STRATEGY.md](VERSIONING_STRATEGY.md) - Versioning and release process
- Plus 8 more technical deep-dive documents

### Technical Debt Resolved
- Backend refactoring complete (modular routers)
- Performance optimization complete (36.6x real-time)
- Version management system implemented
- Database schema optimized (v3 with indexes)

## [0.8.0] - 2025-10-20

### Added
- **Dynamics Expansion System**: All 4 Matchering behaviors
  - Heavy Compression: Reduce dynamic range for loud masters
  - Light Compression: Gentle compression for natural sound
  - Preserve Dynamics: Maintain original dynamic range
  - Expand Dynamics: De-mastering to increase dynamic range
- **Track Metadata Editing**: Full CRUD operations
  - 14 editable fields (title, artist, album, year, etc.)
  - Mutagen integration for file format support
  - Validation and error handling
- **Backend Modular Router Architecture**
  - Separated endpoints into focused modules
  - Player, library, enhancement, playlists, files, artwork, system routers

### Changed
- **Processing Behavior**: Intelligent content-aware rules
  - Loud material: Limited stereo expansion
  - Quiet material: Enhanced stereo imaging
  - Dynamic material: Preserved dynamics

### Fixed
- **Crest Factor Accuracy**: Average 0.67 dB error across all behaviors
- **RMS Level Targeting**: Average 1.30 dB error across all behaviors
- **Stereo Width Processing**: Proper correlation handling

### Performance
- Library scanning: 740+ files/second
- Database operations: Optimized with indexes

## [0.7.0] - 2025-10-15

### Added
- **Real-time Audio Player**: Full playback with processing
  - Queue management
  - Shuffle and repeat modes
  - Real-time enhancement toggle
- **WebSocket API**: Real-time player state updates
- **Library Management**: Track, album, artist repositories
  - Repository pattern for data access
  - SQLAlchemy models with proper relationships

### Changed
- **Database Schema**: Upgraded to v2 with indexes

### Fixed
- Player synchronization issues
- WebSocket connection stability

## [0.6.0] - 2025-10-10

### Added
- **Web Interface**: FastAPI backend + React frontend
  - Material-UI components
  - Modern, responsive design
- **Electron Desktop App**: Cross-platform desktop application
  - Native file/folder selection
  - System tray integration

### Changed
- **Architecture**: Two-tier architecture (web + Python core)

## [0.5.0] - 2025-10-01

### Added
- **Adaptive Processing**: No reference tracks needed
- **Content Analysis**: ML-based genre classification
- **Psychoacoustic EQ**: 26-band critical bands
- **Dynamics Processing**: Compressor, limiter, envelope follower

### Changed
- **Core Engine**: Hybrid processor with multiple modes

## [0.4.0] - Earlier releases

Earlier releases not documented in this changelog.

---

## Version Links

[Unreleased]: https://github.com/matiaszanolli/Auralis/compare/v1.0.0-alpha.1...HEAD
[1.0.0-alpha.1]: https://github.com/matiaszanolli/Auralis/compare/v0.8.0...v1.0.0-alpha.1
[0.8.0]: https://github.com/matiaszanolli/Auralis/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/matiaszanolli/Auralis/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/matiaszanolli/Auralis/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/matiaszanolli/Auralis/releases/tag/v0.5.0

## Release Notes

### Alpha Release Philosophy

During the alpha phase (1.0.0-alpha.x):
- **Active Development**: New features and improvements
- **Early Testing**: Expect rough edges and bugs
- **Rapid Iteration**: Frequent releases with fixes and features
- **Breaking Changes Possible**: API/config may change between alphas

### Beta Release Philosophy

During the beta phase (1.0.0-beta.x):
- **Feature Freeze**: No new major features after beta.1
- **Bug Fixes Only**: Beta.2, beta.3, etc. focus on fixes and improvements
- **Performance Tuning**: Minor optimizations acceptable
- **UI Polish**: UX improvements and polish

### Upgrade Path

**From 0.8.0 to 1.0.0-alpha.1**:
- Database schema compatible (both use v3)
- Optional Numba installation recommended for performance
- No breaking changes in API or configuration
- Library data preserved

**Future Upgrades**:
- Automatic database migrations
- Version compatibility checking
- Clear upgrade instructions

### Known Issues (1.0.0-alpha.1)

- Library scan UI not implemented (backend ready, frontend TODO)
- Frontend test coverage limited (< 50%)
- Alpha testing phase - expect rough edges

### Roadmap to 1.0.0 Stable

1. **Alpha Testing** (1.0.0-alpha.x) - Current Phase
   - Feature development and integration
   - Initial testing and validation
   - Library scan UI completion
   - Frontend test coverage expansion

2. **Beta Testing** (1.0.0-beta.x)
   - Feature freeze (no new features)
   - Bug fixes and stability improvements
   - User feedback collection
   - Performance validation

3. **Release Candidate** (1.0.0-rc.x)
   - Feature complete
   - All critical bugs fixed
   - Final testing phase

4. **Stable Release** (1.0.0)
   - Production-ready
   - Full platform support (Linux, Windows, macOS)
   - Complete documentation
   - Marketing materials

### Contributing

See [VERSIONING_STRATEGY.md](VERSIONING_STRATEGY.md) for:
- How to bump versions
- Release process
- Binary build triggers
- Git tagging conventions

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

**Target:** 1.5.1

Database schema 16 → 34 and fingerprint algorithm 4 → 16 relative to the 1.5.0 source milestone.
An existing library migrates on first start (a pre-migration backup is kept) and its stored
fingerprints are recomputed in the background; see *Changed* below.

### Added

- A desktop-first semantic theme contract shared by MUI, Emotion, and plain DOM controls,
  plus an explicit unsupported-platform notice when the renderer runs in a browser.
- Working-state recovery audit with a concrete definition of “working,” four phased recovery
  slices, and evidence-backed release gates.
- v1.5.1 release notes and an executable release checklist.
- Automated consistency coverage for Python, backend fallback, Python packaging, container,
  root package, frontend, and desktop version metadata.
- Required cross-platform release packaging for Linux x64 AppImage, Flatpak, and `.deb`,
  Windows x64, and macOS Apple Silicon, with artifact and architecture assertions.
- A single source launcher, `launch-auralis-web.py`, that owns the backend and Vite (and, with
  `--electron`, the desktop shell), waits on `/api/ready` before reporting success, propagates
  one port, and stops only the children it started. `pnpm run dev` delegates to it
  (#4805, #5373, #6157).
- `GET /api/ready`, which reports 503 until the engine and library database are initialized and
  carries the launch ID so a supervisor can tell its own backend from a stale one (#4684).
- A collected, isolated launch smoke, `tests/integration/test_application_startup.py`, with a
  temporary home, ephemeral ports, a failed-initialization case, and a port-collision case.
- `scripts/reference_bench.py` and `auralis/analysis/reference_profile.py`, which hold the
  adaptive render to a set of reference records.
- Durable persistence for processing jobs.
- A fingerprint-coverage card in Library settings (#4865), a playlist detail view reached from
  the sidebar (#6007), `PlaylistRepository.search()` (#5171), and a paged playlists endpoint.
- Orphaned metadata-edit backups found during a scan are reported (#6177).
- A nightly slow-suite job with its own baseline (#5966, #6502), a Python and npm dependency
  advisory gate (#6178, #6530), and a CI job that builds the Rust module so fingerprint tests run
  (#6657).

### Changed

- Unified the application shell, sidebar, library header, right inspection pane, player,
  queue, dialogs, search, view toggle, and theme toggle around a restrained three-level
  surface hierarchy. Glass is now reserved for overlays instead of every application region.
- Migrated shared typography, form fields, skeletons, recovery UI, compact settings/search
  surfaces, and tested player leaf controls to the runtime semantic palette.
- Deprecated standalone browser/PWA use. The React application remains the Electron renderer
  and a browser-accessible development preview, but it is no longer an official platform.
- Advanced the source tree to v1.5.1 as an **unreleased recovery milestone**.
- Reworked the README, documentation hub, roadmap, versioning strategy, and release guide to
  distinguish a prepared source version from a tagged, tested, published release.
- Updated the version synchronizer to work from any current directory and propagate the
  canonical version to the packaging, container, and JavaScript metadata.
- Made release tags and manual CI builds validate their requested version against repository
  metadata, fail on missing artifacts, and generate SHA-256 checksums before drafting a release.
- Moved the Flatpak target to the 25.08 runtime and made it a required release artifact.
- **Analysis is whole-track; only rendering is chunked.** The 25D fingerprint now analyses the
  entire track (up to 900 s; longer tracks keep a body window plus probes) instead of one 90 s
  window, and a track with no stored fingerprint is analysed once before its first chunk renders.
  Chunks only render one track-level plan. The analysis gate is fair, prioritised, cancellable,
  and reserved before decode (#6336, #6338). Algorithm versions 5–16 corrected individual
  dimensions: tempo octaves (#5742), partial trailing frames (#6322, #6341), band shares read
  from the whole track, and silent seconds excluded from the variation dimensions (#6112, #6113).
- **Enhancement presets narrowed to `adaptive`.** The gentle, warm, bright, punchy, and live
  presets are gone from the engine, API, frontend, and settings; stored preset values are
  normalized by migration (#5824).
- **Level and EQ plan.** The adaptive peak target and makeup gain are continuous in source
  loudness, crest, and peak (#6303, #5704, #6305); one track-level gain applies on the
  fixed-targets path (#5552); a fixed-target plan leaves excellent masters alone; the
  2–4 kHz correction cuts at twice the law and boosts at half.
- **Loudness measurement** uses the BS.1770-4 K-weighting filters (#5593) and EBU Tech 3342
  loudness range (#5741); the hot path measures K-weighted LUFS rather than an RMS offset (#5221).
- **Toolchain.** Python 3.14 is required, and backend CI runs on it. The runtime and the release
  build tooling install from hash-locked files (#4871, #6151); the Rust module builds as a full-API
  cp314 wheel on pyo3/numpy 0.29, asserted in the release workflow (#5485), on Rust edition 2024
  (#5443); every workflow action is pinned to a commit SHA (#4868); Electron is 43.8.12 (#6519).
- **Database.** Albums are owned by the file's ALBUMARTIST tag, so the next scan re-reads every
  track (#6332); a track's artists keep tag order (#6714); upgraded databases gain the unique
  `filepath_key` index fresh ones have (#6335); never-written columns and unread indexes are
  dropped (#5755, #6261); a pre-versioning library file is refused instead of stamped current
  (#5851); pre-migration backups are owner-only, restored when a migration fails, and pruned to the
  newest three (#5333, #5316, #5750).
- **Performance.** `HybridProcessor.process()` no longer holds whole-track copies across its
  stages (#6717); the fingerprint queue claims from a per-queue cursor (#5310); streaming and I/O
  use separate thread pools (#5086); M4A/AAC/WMA decode once per track (#4737); streams of one
  track share their converted temp WAV (#5402); long artist and cache lists are virtualized
  (#6023, #4471); player-state snapshots are O(1) in queue length (#5960, part).
- **Engineering gates.** The pytest, slow-suite, and frontend failure baselines are empty and
  fail the job on stale entries (#4562, #5091, #5344, #6709). A LOC ratchet holds every closed
  split target at its size (#6266, #6268, #6701), a breadcrumb gate rejects “was removed in #N”
  comments (#6257, #6680), the path-reference gate rejects file-and-line-number anchors (#5144, #6248,
  #6675), and a weak-assertion gate rejects tautological tests (#5224, #6237).
- Client-to-server WebSocket commands are a typed discriminated union (#6050); queue, player,
  WebSocket, and fingerprint payloads describe a track's artists and album like the library
  does (#6508).

### Removed

- The crossfade, gapless, and replay-gain settings that nothing consumed, with their
  `user_settings` columns (schema v34) and API fields (#6683).
- The user preference-learning engine and its configuration (#5763), and the preference bias
  layer of the continuous parameter generator (#6123).
- Nine PyO3 bindings with no production caller (#5764) and the `process_chunks` binding with
  its chunk processor (#5738); the Rust crate now carries the 25D fingerprint only.
- The whole-track processed-audio export and chunk batch helper (#5088), the unwired album-target
  plumbing and `process_album` (#6199), the unwired queue history/undo feature (#5526),
  `AVAILABLE_PRESETS` (#6240), and the legacy `Config`/`LimiterConfig` (#4918).
- The `mastering_recommendation` broadcast and its service (#6579), and the dead backend version
  module with its `/api/version` fallback (#6686).
- Design tokens, primitives, styled components, and barrel-exported components that nothing
  reads or renders (#6062, #6442, #6443, #6612, #6613); Google Fonts links in favor of bundled
  fonts (#6060).
- The manual release script: CI is the only release publisher (#6529).

### Fixed

- Restored the production TypeScript gate by handling the cache-health endpoint's optional
  timestamp instead of constructing a `Date` from `undefined`.
- Theme changes now update the complete runtime semantic palette, including surfaces, borders,
  status colors, focus treatment, shadows, and explicit foregrounds for accent/destructive
  actions; light mode no longer inherits dark shell values.
- The backend compatibility module now reads the product version from `auralis/version.py`
  instead of the stale `auralis/__version__.py` mirror.
- FastAPI metadata and system endpoint tests now use the canonical product/database versions
  and respect production OpenAPI-route disabling.
- Corrected release documentation that used npm commands for pnpm-managed workspaces or
  described the broken root launcher as a supported path.
- Removed the invalid Intel macOS package produced on an Apple Silicon runner with an ARM64
  Python/Rust backend; macOS release builds now target ARM64 end to end.
- **Recovery blockers.** Fresh databases persist the first fingerprint (#5530); `(samples, 1)`
  mono input is measured and rendered without crashing, and `HybridProcessor` refuses input that
  violates its `(samples, channels)` float contract (#5550, #6118); rapid track selection leaves
  the last selection active (#4426); the launcher no longer reports ready before the backend is,
  and Electron no longer kills whatever listens on port 8765 (#6157).
- **Packaged app.** The backend launches only when it matches its build-time digest (#6527) and
  exits when the Electron process that started it is gone (#6720); it is pinned to the port
  Electron loads (#6170).
- **Engine quality.** `HybridProcessor` removes DC offset before mastering (#5187); the loudness
  plan does not lift near-silence on any render path, and the silence floor ramps gain in
  instead of stepping (#6108); a mono source is measured as the dual-mono it renders as (#6138);
  true peak is no longer biased by block-edge overshoot (#6327); the brick-wall limiter looks
  ahead and ramps its gain (#5562, #5699); chunked render no longer pads M4A/MP3 tracks with
  encoder-delay silence (#6345); the stereo-width correlation no longer leaves BLAS threads
  spinning after `process()` (#6717); `phase_correlation` is signed (#5743).
- **Scanner.** A scan reports an undecodable file as a failure (#5567), keeps no rows for a folder
  removed mid-scan (#6556), uses a watermark taken before the file is read (#6560), treats an
  older mtime as a change (#5748), clears a tag removed from a file (#6333), and keeps a moved
  file's row, playlists, favorite, and play count (#5880, #6569). One unreadable or looping
  symlink no longer aborts discovery of its directory (#6116), and an incomplete walk no longer
  prunes tracks (#5877).
- **Playback and queue.** The gapless prebuffer is invalidated on every queue edit and survives
  a sample-rate change (#5508, #5583, #6307); position, duration, and file swap as one snapshot
  (#6081); the first track added to an empty queue becomes current (#5727); shuffle keeps the
  playing track by identity (#5564); removing the playing row skips to its successor (#6016); a
  late end or error from a superseded track no longer tears down the new stream (#6017).
- **WebSocket.** A client evicted by a broadcast is closed with 1013 so it reconnects and
  resyncs (#5884), and a rejected origin is closed with 1008 (#5883).

### Security

- **Electron.** Fuses, deny-by-default web permissions, and IPC sender validation (#6174);
  `sandbox: true` (#4848); navigation to non-app origins and non-allowlisted URL schemes is
  blocked (#4858, #4844); the preload exposes only channels with a handler (#4851); main-process
  security events go to `electron-log` with control characters escaped (#6187, part).
- **Backend boundary.** Host header checked against a loopback allowlist (#4353); state-changing
  requests and cross-site GETs under `/api` need a trusted Origin or Referer (#6158); the
  WebSocket origin allowlist drops `file://` and follows `AURALIS_PORT` (#5066, #5796); at most 16
  concurrent WebSocket connections (#6171, part); uvicorn does not trust `X-Forwarded-For` (#6168);
  CSP gains `form-action` and `base-uri` (#5363) and builds `connect-src` from the loopback policy
  (#4712).
- **Filesystem.** Scan roots refuse the system temp and app-data directories (#6164) and resolve
  symlinks (#6097); persisted scan folders are revalidated when read (#6525); uploaded tracks pass
  path validation (#6513); folder-cover lookup refuses symlinks and special files (#6160); a `.25d`
  sidecar is trusted only if this installation wrote it (#6522); logs and scan failures carry no
  absolute paths (#6537, #5341).
- **Artwork and export.** Artwork downloads accept only https, validate every redirect hop, reject
  decompression bombs, and keep API credentials off the command line (#5337, #5330, #6153, #6182);
  M3U export strips CR/LF from tag fields (#5348).
- **Supply chain.** Release build tooling is hash-locked (#6151) and `SHA256SUMS.txt` is
  GPG-signed when the repository key is configured (#4905, part); signing certificates are not
  yet configured.

### Known release blockers

The three product blockers from the recovery audit (fresh fingerprint persistence, mono
enhancement, rapid selection) are fixed and re-verified (#6678). The source launcher is
implemented and covered by the collected startup smoke. What still blocks a tag:

- Validation of the installed Linux, Windows, and macOS artifacts, including the default Electron
  sandbox configuration.
- The audit's eleven-point definition of “working” against a fresh home, the repeated-run gates,
  and a clean release commit.
- Windows Authenticode and macOS Developer ID signing and notarization (#4905), and a published
  GPG key fingerprint.

See [RELEASE_NOTES_1_5_1.md](RELEASE_NOTES_1_5_1.md),
[RELEASE_CHECKLIST_1_5_1.md](RELEASE_CHECKLIST_1_5_1.md), and the
[working-state recovery audit](../audits/AUDIT_RECOVERY_2026-07-24.md). The interface migration
boundary and remaining debt are recorded in the
[desktop UI theme audit](../audits/UI_THEME_UNIFICATION_2026-07-25.md).

## [1.5.0] - 2026-07-18

> **Source-preparation milestone, not a tagged release.** Local git history contains no
> `v1.5.0` tag. Its changes remain part of the v1.5.1 recovery baseline.

### Overview
**First stable source milestone (not tagged).** Consolidates everything since the last binary
release (v1.2.0-beta.2, 2025-12-27): two source-only pre-release versions
(v1.2.1-beta.1, v1.2.1-beta.2) and the subsequent unreleased work were never given a binary
build, so this source milestone folds all three together — a large batched audit-remediation
effort (dozens of concurrency, data-integrity, API-contract, DSP, and security issues,
`v1.2.0-beta.3..v1.2.1-beta.2` plus issues #2299–#2472) followed by a mastering-pipeline
quality-refinement pass.

### Changed

#### Multiband Stereo Processing
- Replaced 2nd-order Butterworth bandpass filters with **Linkwitz-Riley LR4 crossovers** (24dB/octave) for phase-coherent band splitting that sums flat at crossover points
- Raised low crossover from 200Hz to 300Hz to preserve bass harmonics and kick punch in the center channel
- Balanced expansion ratios to avoid "scooped mids" effect:
  - Lows (<300Hz): 0% expansion - keeps bass centered
  - Low-mids (300Hz-2kHz): 70% expansion - preserves warmth and body
  - High-mids (2kHz-8kHz): 100% expansion - full presence
  - Highs (>8kHz): 100% expansion - air and brilliance (removed excessive 120% boost)

#### Auto-Mastering Pipeline
- Fixed headroom calculation for tracks with LUFS between -14 and -12 that have peaks near 0dBFS - now properly applies peak reduction before makeup gain
- Reduced safety margin from -2.0dB to -0.5dB for more effective loudness normalization
- Batch processing now outputs FLAC (24-bit) instead of WAV

#### Smooth Processing Curves
Replaced hard thresholds with cosine-interpolated curves for natural transitions:
- **Intensity calculation**: Smooth 2D interpolation based on crest factor (8-15 dB) and LUFS (-13 to -11 dB)
- **Stereo expansion**: Cosine fade from full (width < 25%) to none (width > 55%)
- **Bass enhancement**: Cosine fade from full boost (bass < 20%) to none (bass > 50%)
- **Normalization peak**: Smooth bass-aware adjustment (10% to 40% bass range)

#### Engine Cleanup
- Removed the deprecated engine `process()` wrapper and `API_VERSION`/`MIN_COMPATIBLE_VERSION`/`is_compatible()` machinery
- `version.py` `DB_SCHEMA_VERSION` now mirrors the live schema (16)
- Extensive documentation accuracy pass (architecture, testing, style guides, versioning docs)

### Fixed

#### Mastering
- QuietBranch makeup-gain now uses the whole-song peak instead of a per-chunk peak; improved loudness targeting and crest reduction; NaN/Inf guard on AdaptiveMode/ContinuousMode final normalization

#### Concurrency
- Resolved hard deadlock between `seek`/`load_file`/`next_track` and `get_playback_info`; guarded against a `LibraryManager()` construction race during migration; a single slow WebSocket client no longer stalls player-state updates
- `RLock` added to QueueManager (fixed `_auto_advancing` bypass); `asyncio.Lock` for PlayerStateManager and streaming-task tracking; stop processing on client disconnect

#### Resource Leaks
- HybridProcessor cache eviction no longer leaks fingerprint-analyzer threads; ProcessingEngine/StreamlinedCacheWorker no longer stay truthy after their background task dies

#### Repositories
- Album/Artist sibling lookups now apply the `DetachedInstanceError` fix; scan endpoint REST/WS payloads reconciled

#### DSP / Correctness
- Vectorized EQ gain curve; batch metadata updates made atomic with rollback

#### Desktop
- Resolved DB version mismatch and WebSocket heartbeat rejection

#### Testing
- Fixed test-collection failures from `sys.path` and missing schemas; added AudioStreamController lifecycle tests

- Multiple additional batched fixes across issues #2299–#2472; see commit log (`v1.2.0-beta.2..v1.5.0`) for the full list

## [1.2.0-beta.3] - 2026-01-03

### Added
- Multiband stereo expansion and bass enhancement in the mastering pipeline
- `ARCHITECTURE.md` documenting the processor hierarchy and naming conventions

### Changed
- Enforced the repository pattern for all database access
- Removed "Enhanced"/"Advanced" naming violations; resolved the RealtimeProcessor naming collision
- Split god-files into modular packages (`base_processing_mode.py` → `base/`, `common_metrics.py` → `metrics/`); moved fingerprint services from `library/` to `services/`; consolidated the duplicate WebM encoder

### Fixed
- CI/build: Rust toolchain + `auralis-dsp` build in GitHub Actions; Electron output paths; Vite build output moved to `dist/`; WebSocket deps in the PyInstaller spec

## [1.2.0-beta.2] - 2025-12-27

### Added
- Tempo detection, fluid bass handling, and time metrics in the mastering pipeline (with regression tests)
- UX polish: Inter font, simplified player, flat design, visual-hierarchy pass

### Changed
- **AppImage size**: reduced from ~2.8GB to ~205MB by removing CUDA/GPU libraries and optimizing dependencies
- Reorganized root documentation into `docs/` subfolders

### Fixed
- Restored AppImage playback by migrating to WebSocket streaming
- Included the Rust DSP module and backend modules (config, routers) in PyInstaller builds

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

AGPL-3.0, dual-licensed (see LICENSE and COMMERCIAL_LICENSE.md)

---

**Release maintained by**: Claude Code
**Last updated**: 2025-11-29

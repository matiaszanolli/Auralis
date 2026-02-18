# Audio Engine Audit

Audit the Auralis core audio engine for sample integrity, DSP pipeline correctness, player state safety, I/O robustness, parallel processing correctness, analysis reliability, and library/database integrity. Then create GitHub issues for every new confirmed finding.

**Shared protocol**: Read `.claude/commands/_audit-common.md` first for project layout, severity framework, methodology, critical invariants, deduplication rules, and GitHub issue template.

## Scope

| Component | Path | Key Files |
|-----------|------|-----------|
| Core Pipeline | `auralis/core/` | `hybrid_processor.py`, `simple_mastering.py`, `processor.py`, `config.py` |
| DSP Modules | `auralis/dsp/` | `unified.py`, `psychoacoustic_eq.py`, `advanced_dynamics.py`, `realtime_adaptive_eq.py` |
| Player | `auralis/player/` | `enhanced_audio_player.py`, `gapless_playback_engine.py`, `queue_controller.py`, `realtime_processor.py` |
| Audio I/O | `auralis/io/` | `unified_loader.py`, `results.py` |
| Parallel Processing | `auralis/optimization/` | `parallel_processor.py` |
| Analysis | `auralis/analysis/` | `fingerprint/` (25D system), `content/`, `ml/`, `quality/` |
| Library | `auralis/library/` | `manager.py`, `repositories/` (12 repos), `scanner.py`, `migration_manager.py` |
| Services | `auralis/services/` | Background services (fingerprint, artwork) |
| Rust DSP | `vendor/auralis-dsp/` | PyO3 bindings (HPSS, YIN, Chroma) |

Out of scope: React frontend, FastAPI backend (routing, WebSocket layer), Electron desktop. DO verify engine public API contracts.

## Severity Examples

| Severity | Engine-Specific Examples |
|----------|------------------------|
| **CRITICAL** | Sample count mismatch causing clicks/gaps, buffer corruption from missing copy, in-place modification of shared array, database corruption from concurrent writes |
| **HIGH** | Phase cancellation in parallel processing, RLock deadlock in player, gapless transition audible gap, memory leak during extended playback |
| **MEDIUM** | Inconsistent dtype handling across stages, missing copy-before-modify in non-critical path, fingerprint accuracy degradation at edge cases |
| **LOW** | Redundant array copies hurting performance, sub-optimal FFT windowing, unused analysis metrics |

## Audit Dimensions

### Dimension 1: Sample Integrity

**Key files**: `auralis/core/hybrid_processor.py`, `auralis/core/simple_mastering.py`, `auralis/dsp/unified.py`, all DSP modules

**Check**:
- [ ] `len(output) == len(input)` — verified at EVERY processing stage, not just the outer wrapper?
- [ ] `audio.copy()` before ANY in-place NumPy operation — no exceptions?
- [ ] dtype preservation — does audio stay `float32`/`float64` throughout? Any silent casts?
- [ ] Clipping prevention — is audio clamped to [-1.0, 1.0] before output? Inter-stage clipping?
- [ ] NaN/Inf propagation — can a NaN from one DSP stage corrupt the entire output?
- [ ] Mono/stereo handling — are mono files correctly handled through stereo pipelines?
- [ ] Bit depth output — does `auralis/io/results.py` (pcm16, pcm24) correctly scale and quantize?

### Dimension 2: DSP Pipeline Correctness

**Key files**: `auralis/core/hybrid_processor.py`, `auralis/core/simple_mastering.py`, `auralis/dsp/unified.py`, `auralis/dsp/psychoacoustic_eq.py`, `auralis/dsp/advanced_dynamics.py`, `auralis/dsp/realtime_adaptive_eq.py`

**Check**:
- [ ] Processing chain order — is the sequence (EQ → dynamics → mastering) correct and documented?
- [ ] Stage independence — does each stage receive clean input, or can a failed stage leave dirty state?
- [ ] Parameter validation — are gain, frequency, Q factor ranges validated before DSP math?
- [ ] Windowing — are FFT windows applied correctly? Double-windowing removed? (Fix: `cca59d9c`)
- [ ] Spectral leakage — are FFT sizes appropriate for the sample rate?
- [ ] Phase coherence — does multi-band processing maintain phase relationships?
- [ ] Sub-bass parallel path — correctly mixed back in? (Fix: `8bc5b217`)
- [ ] Rust DSP boundary — do PyO3 calls handle errors and return correct formats?
- [ ] GIL handling — does Rust code release the GIL during compute? Can concurrent calls corrupt state?

### Dimension 3: Player State Machine

**Key files**: `auralis/player/enhanced_audio_player.py`, `auralis/player/gapless_playback_engine.py`, `auralis/player/queue_controller.py`, `auralis/player/realtime_processor.py`

**Check**:
- [ ] State transitions — are play/pause/stop/seek transitions atomic under RLock?
- [ ] Position invariant — can `position > duration` ever occur? During seek?
- [ ] Queue bounds — can index go out of bounds during skip/previous/remove?
- [ ] Gapless transitions — is the next track pre-loaded? Race between load and play?
- [ ] Callback safety — are callbacks invoked outside the lock to prevent deadlock?
- [ ] Resource cleanup — does stop() release file handles, audio buffers, threads?
- [ ] Real-time processor lifecycle — started/stopped atomically with playback?
- [ ] Can `stop()` race with `play()` leaving player in undefined state?

### Dimension 4: Audio I/O

**Key files**: `auralis/io/unified_loader.py`, `auralis/io/results.py`

**Check**:
- [ ] Format coverage — MP3, FLAC, WAV, AAC, OGG, OPUS, M4A all tested?
- [ ] Corrupt file handling — crash vs meaningful error on corrupt header?
- [ ] Large file handling — files > 1GB without OOM?
- [ ] Sample rate detection — always from metadata, never assumed?
- [ ] Channel handling — files with > 2 channels downmixed correctly?
- [ ] FFmpeg subprocess — properly terminated on cancellation? Zombie risk?
- [ ] File path safety — paths validated before passing to FFmpeg?
- [ ] Metadata extraction — ID3/Vorbis/FLAC tags parsed robustly? Malformed tags?

### Dimension 5: Parallel Processing

**Key files**: `auralis/optimization/parallel_processor.py`, `auralis/core/simple_mastering.py`

**Check**:
- [ ] Chunk independence — chunks are true copies, not views into same buffer?
- [ ] Reassembly order — processed chunks reassembled in correct order?
- [ ] Boundary smoothing — chunk boundaries crossfaded to prevent discontinuities?
- [ ] Partial failure — one chunk failing doesn't corrupt or skip the rest?
- [ ] Thread pool — sized appropriately? Tasks cleaned up on cancellation?
- [ ] Sample count — `sum(chunk_lengths) == total_length` after parallel processing?
- [ ] Spectral preservation — frequency content preserved across chunk boundaries?

### Dimension 6: Analysis Subsystem

**Key files**: `auralis/analysis/fingerprint/`, `auralis/analysis/content/`, `auralis/analysis/ml/`, `auralis/analysis/quality/`

**Check**:
- [ ] Fingerprint determinism — same file always produces same fingerprint?
- [ ] Resource bounds — pathological files (silence, noise, 6hr podcast) bounded in CPU/memory?
- [ ] Batch vs streaming — both analysis paths produce identical results?
- [ ] ML model lifecycle — loaded once and reused, not reloaded per-track?
- [ ] Quality metrics — LUFS, dynamic range, distortion correctly computed?
- [ ] Thread safety — concurrent analysis tasks don't interfere?
- [ ] KeyboardInterrupt — analysis can be interrupted cleanly? (Fix: `53cef6b4`)

### Dimension 7: Library & Database

**Key files**: `auralis/library/manager.py`, `auralis/library/repositories/`, `auralis/library/scanner.py`, `auralis/library/migration_manager.py`

**Check**:
- [ ] Repository pattern — ALL database access via repository classes? No raw SQL?
- [ ] SQLite config — `check_same_thread=False`, `pool_pre_ping=True` set?
- [ ] N+1 queries — list operations use `selectinload()`?
- [ ] Scanner robustness — symlinks, permission errors, Unicode filenames handled?
- [ ] Migration safety — can run while app is serving requests? (Uses file locking)
- [ ] Concurrent scans — two scan operations can't conflict?
- [ ] Cleanup — `cleanup_missing_files` handles large libraries without OOM? (Fix: `bd94fd59`)
- [ ] Engine disposal — SQLAlchemy engine disposed on close? (Fix: `8adb8d0a`)

## Phase 1: Audit

Write your report to: **`docs/audits/AUDIT_ENGINE_<TODAY>.md`** (use today's date, format YYYY-MM-DD).

### Per-Finding Format

```
### <ID>: <Short Title>
- **Severity**: CRITICAL | HIGH | MEDIUM | LOW
- **Dimension**: Sample Integrity | DSP Pipeline | Player State | Audio I/O | Parallel Processing | Analysis | Library & Database
- **Location**: `<file-path>:<line-range>`
- **Status**: NEW | Existing: #NNN | Regression of #NNN
- **Description**: What is wrong and why
- **Evidence**: Code snippet or exact call path
- **Impact**: What breaks — audio artifacts, crashes, data loss
- **Suggested Fix**: Brief direction (1-3 sentences)
```

## Phase 2: Publish to GitHub

Use labels: severity label + domain labels (`audio-integrity`, `dsp`, `player`, `library`, `fingerprint`, `performance`) + `bug`

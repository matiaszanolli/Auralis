# Engine Audit — 2026-03-25

**Auditor**: Claude Opus 4.6 (automated)
**Scope**: Core pipeline, DSP, player, I/O, parallel processing, analysis, library
**Dimensions**: 7 (combined into 3 parallel agents)
**Method**: Deep — full call graph tracing, post-fix verification

## Executive Summary

Post-fix audit following ~20 engine commits fixing prior findings. **35 new findings**: 4 HIGH, 10 MEDIUM, 21 LOW. Many prior HIGH findings now resolved (HybridProcessor lock, envelope follower dtype, BrickWallLimiter origin, auto-advance races, MigrationManager session).

**Key clusters:**

1. **Limiter polarity bugs** (ENG-NEW-01, ENG-NEW-02) — AdaptiveLimiter has same origin bug as the fixed BrickWallLimiter, plus its envelope follower has inverted attack/release polarity. Defeats lookahead limiting entirely.

2. **Fingerprint cache 100% miss** (AN-04) — `FingerprintStorage.load` rejects every `.25d` file because `not {}` evaluates to `True`. File-tier cache never loads.

3. **Parallel processing silent failure** (PP-01) — Failed band future returns zeros silently, producing corrupted frequency sum.

4. **Player fingerprint race** (PTS-D3-02) — Stale fingerprint applied to wrong track after rapid skip.

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 4 |
| MEDIUM | 10 |
| LOW | 21 |
| **Total** | **35** |

## Prior Findings Status

~20 issues fixed since 2026-03-23:
- HybridProcessor per-instance lock (#3349)
- PerformanceOptimizer gc_counter lock (#3351)
- Module optimization idempotency (#3353)
- get_audio_chunk atomic state check (#3295)
- MigrationManager session rewrite (#3368)
- Case-insensitive file discovery (#3314)
- auto_advancing generation counter (#3350)
- stop() re-check in next/previous (#3361)
- load_track_from_library atomic (#3346)
- Envelope follower float32 (#3305)
- BrickWallLimiter mirror-pad (#3308/3291)
- process_mono_chunks overlap-add (#3358)
- Max-duration RAM guard (#3300)
- load_reference TOCTOU fix (#3302)

---

## New Findings

### HIGH

---

### ENG-NEW-01: AdaptiveLimiter._compute_peak_envelope uses backward origin — same bug as fixed BrickWallLimiter
- **Severity**: HIGH
- **Dimension**: DSP Pipeline
- **Location**: `auralis/dsp/advanced_dynamics.py` (AdaptiveLimiter, limiter.py:147)
- **Status**: NEW
- **Description**: `maximum_filter1d` uses `origin=-(lookahead // 2)` which looks backward. BrickWallLimiter was fixed (commit `178688b7`) but AdaptiveLimiter was not.
- **Impact**: Lookahead limiting defeated — transients clip before gain reduction kicks in.
- **Suggested Fix**: Change to positive origin, matching BrickWallLimiter fix.

---

### ENG-NEW-14: PsychoacousticEQ spectrum analysis applies wrong coherent-gain correction (~3dB excess boost)
- **Severity**: HIGH
- **Dimension**: DSP Pipeline
- **Location**: `auralis/dsp/psychoacoustic_eq.py:140`
- **Status**: NEW
- **Description**: Assumes full Hann window (+6.02 dB correction) but receives sqrt(hann)-windowed chunks from EQProcessor. Under-compensates by ~3 dB, causing systematic excess boost in AdaptiveMode and ContinuousMode.
- **Impact**: All adaptive EQ processing applies ~3 dB too much boost across all bands.

---

### PP-01: ParallelBandProcessor silently returns zeros for failed bands — corrupted frequency sum
- **Severity**: HIGH
- **Dimension**: Parallel Processing
- **Location**: `auralis/optimization/parallel_processor.py`
- **Status**: NEW
- **Description**: Failed band future's slot stays as `np.zeros`. No error raised. Caller receives sum with missing frequency content.
- **Impact**: Silent frequency content deletion. Could remove entire bass or treble band.

---

### PP-02: ParallelSpectrumAnalyzer._process_fft_to_spectrum races on smoothing_buffer across threads
- **Severity**: HIGH
- **Dimension**: Parallel Processing / Analysis
- **Location**: `auralis/analysis/fingerprint/`
- **Status**: NEW (distinct from #2890 which covers streaming path — this is the batch/file path)
- **Description**: ThreadPoolExecutor workers share `self.smoothing_buffer` with no lock. Non-deterministic fingerprint inputs.

---

### MEDIUM

---

### ENG-NEW-02: AdaptiveLimiter.gain_smoother has inverted attack/release polarity
- **Severity**: MEDIUM
- **Dimension**: DSP Pipeline
- **Location**: `auralis/dsp/advanced_dynamics.py` (AdaptiveLimiter)
- **Description**: VectorizedEnvelopeFollower uses level-detector polarity. For gain signals, limiting uses release (slow) and recovery uses attack (fast) — opposite of correct behavior.

### ENG-NEW-04: EQ processor WOLA truncates terminal chunk — level dip at end of block
- **Severity**: MEDIUM
- **Dimension**: Sample Integrity
- **Location**: `auralis/core/processing/eq_processor.py:169-208`

### ENG-NEW-06: ParallelFFTProcessor silently returns empty on sub-FFT-size audio
- **Severity**: MEDIUM
- **Dimension**: Parallel Processing
- **Location**: `auralis/optimization/parallel_processor.py:135`

### PTS-D3-01: previous_track() commits queue index before file load succeeds
- **Severity**: MEDIUM
- **Dimension**: Player State
- **Location**: `auralis/player/enhanced_audio_player.py:305-317`

### PTS-D3-02: Stale fingerprint applied to wrong track after rapid skip
- **Severity**: MEDIUM
- **Dimension**: Player State
- **Location**: `auralis/player/enhanced_audio_player.py:186-236`

### LIB-01: Similarity scan_all_tracks loads full library without cursor pagination
- **Severity**: MEDIUM
- **Dimension**: Library & Database

### LIB-02: Artist repository get_artist_tracks no selectinload on album relationship
- **Severity**: MEDIUM
- **Dimension**: Library & Database

### LIB-06: restore_database still uses shutil.copy2 — WAL corruption risk
- **Severity**: MEDIUM
- **Dimension**: Library & Database

### LIB-07: KNNGraphBuilder.build_graph loads all fingerprints unbounded
- **Severity**: MEDIUM
- **Dimension**: Library & Database

### AN-02: StreamingHarmonicAnalyzer.finalize produces NaN when buffer < min_frames
- **Severity**: MEDIUM
- **Dimension**: Analysis

---

### LOW (21 findings)

**DSP**: ENG-NEW-03 (AdaptiveLimiter missing .copy on ring buffer), ENG-NEW-10 (HybridMode NaN propagation gap), ENG-NEW-11 (AdaptationEngine NaN on silence), ENG-NEW-13 (emergency limiter 0.0 dBFS ceiling)

**Player**: PTS-D3-03 (end-of-track advance spawn not atomic), PTS-D3-04 (sample_rate read without lock), PTS-D3-05 (fingerprint threads survive cleanup)

**Audio I/O**: IO-D3-01 (dead 1D branch in loader), IO-D3-02 (loader bypasses RIFF check), IO-D3-03 (audio_data setter no lock/dtype check)

**Parallel Processing**: PP-03 (crossfade length not validated against chunk), PP-04 (ParallelBandProcessor executor not shut down)

**Analysis**: AN-01 (StreamingSpectralAnalyzer smoothing_buffer shared), AN-03 (BatchAnalyzer analyze_batch exception swallows errors), AN-04 (FingerprintStorage.load rejects all .25d files — `not {}` is True), AN-05 (ML genre classifier model loaded per-call)

**Library**: LIB-03 (scan_folder_task no deduplicate guard), LIB-04 (playlist track_order not maintained on bulk add), LIB-05 (stats_repository total_duration sums all tracks without WHERE), LIB-08 (fingerprint_repository upsert race)

---

## Relationships

1. **Limiter sibling divergence**: ENG-NEW-01 + ENG-NEW-02 are the same AdaptiveLimiter class. BrickWallLimiter was fixed but AdaptiveLimiter was not. Classic sibling fix gap.

2. **Fingerprint pipeline chain**: PP-02 (smoothing race) → AN-04 (.25d cache miss) → PTS-D3-02 (stale fingerprint race). The entire fingerprint pipeline from analysis through caching to player application has issues.

3. **Silent failure pattern**: PP-01 (zeros for failed bands) + ENG-NEW-06 (empty for short audio) — both silently return incorrect data instead of raising errors.

## Prioritized Fix Order

1. **AN-04** — FingerprintStorage.load `not {}` bug. One-line fix, massive impact (100% cache miss).
2. **ENG-NEW-01** — AdaptiveLimiter origin. Copy BrickWallLimiter fix.
3. **PP-01** — Failed band returns zeros. Add error propagation.
4. **ENG-NEW-14** — Coherent gain correction. Adjust from 6.02 to ~3 dB for sqrt(hann).
5. **PTS-D3-02** — Fingerprint generation counter. Prevent stale fingerprint on skip.
6. **PTS-D3-01** — previous_track peek-then-commit. Mirror advance_with_prebuffer pattern.
7. **PP-02** — smoothing_buffer thread safety. Per-thread buffer or lock.

---

*Report generated by Claude Opus 4.6 — 2026-03-25*
*Suggest next: `/audit-publish docs/audits/AUDIT_ENGINE_2026-03-25.md`*

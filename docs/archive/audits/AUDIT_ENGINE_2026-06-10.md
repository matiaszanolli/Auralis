# Audio Engine Audit — Auralis Core

**Date**: 2026-06-10
**Scope**: `auralis/core/`, `auralis/dsp/`, `auralis/player/`, `auralis/io/`, `auralis/optimization/`, `auralis/analysis/`, `auralis/library/`, `vendor/auralis-dsp/`
**Depth**: deep (full call-graph tracing) · **Limit**: unlimited · **Dimensions**: all 7
**Method**: 7 parallel dimension agents (general-purpose / sonnet, max 3 concurrent), cross-deduplicated against the live GitHub issue tracker (270 open) and recent engine audit reports; the highest-severity claims re-verified by the orchestrator against live code.

---

## Executive Summary

**20 NEW findings**: **1 CRITICAL, 5 HIGH, 8 MEDIUM, 6 LOW**. The engine has been audited repeatedly (last 2026-06-02) so the obvious defects are already filed; this pass surfaced new issues concentrated in **DSP filter-frequency clamps**, **loudness/analysis correctness**, **player lock atomicity**, and **a user-facing DB crash**. All prior-fix commits checked (`cca59d9c`, `8bc5b217`, `53cef6b4`, `bd94fd59`, `8adb8d0a`) are **intact**.

### Findings by severity

| Severity | Count | Headline |
|----------|-------|----------|
| CRITICAL | 1 | RealtimeAdaptiveEQ buffer-flush returns a multiple-of-buffer length → `AssertionError` crash in `process_realtime_chunk` |
| HIGH | 5 | Transient-shaper bass band starts at 110 Hz (excludes kick fundamentals); gapless non-prebuffer fallback de-syncs audio/queue; LUFS K-weighting uses non-standard coefficients; `signal.hilbert()` on full tracks → multi-GB OOM; `ArtistRepository` order-by-count crashes the artists API |
| MEDIUM | 8 | masking-window double-application bias; sub-bass HP clamp at 110 Hz; `load_track_from_library` skips `_audio_lock`; soundfile path has no pre-decode size guard; cross-track analyzer history bleed; per-call `ContentAnalyzer`; cleanup N+1; `limit=0` sentinel bug |
| LOW | 6 | dtype-hardcode in envelope follower; dead `EQSettings.overlap`; unlocked `_advance_thread` read; temp-dir leak on error; uncopied band fallback; duplicate `LoudnessMeter` |

### Key themes

1. **A stale normalized-frequency floor (`max(0.005, …)`) silently relocates low-frequency filters.** The same `0.005` clamp — a historical SciPy-stability guard that is now unnecessary — appears in `transient_shaper.py:81` (HIGH, DSP-NEW-3) and `sub_bass_control.py:59` (MEDIUM, DSP-NEW-2). At 44.1 kHz it moves a 60 Hz / 25 Hz edge up to **110 Hz**, excluding kick/bass fundamentals from the stages designed to protect them. One floor change (`max(1e-4, …)`) fixes both.
2. **Analysis correctness drifts from standards and leaks state across tracks.** The LUFS K-weighting (AN-NEW-1) uses a 1500 Hz shelf and 1st-order HP instead of BS.1770-4's 1681.974 Hz shelf / 2nd-order HP, biasing every stored `lufs` fingerprint dimension and the loudness quality gate. Analyzer history lists (`crest_history`, `correlation_history`) bleed across tracks (AN-NEW-3, sibling of open #4120).
3. **Player audio/state atomicity has residual gaps.** `load_track_from_library` swaps audio outside `_audio_lock` (PS-NEW-2, same class as the fixed #3667); the gapless **non**-prebuffer fallback lacks the rollback its prebuffer sibling has (PS-NEW-1, cites #4100). These compound the already-open lock-ordering issues (#3781/#3782/#3785/#4141).
4. **Unbounded allocations on long audio.** `signal.hilbert()` on full tracks (AN-NEW-2) and the soundfile decode path's missing pre-decode guard (IO-NEW-1, sibling of #4128) both risk multi-GB RSS / OOM on 2-hour reference tracks.

### Most impactful (recommended first fixes)

- **DSP-NEW-3 + DSP-NEW-2** — one-line floor change (`0.005 → 1e-4`) restores kick/bass to the transient shaper and sub-bass HP. Highest audible benefit / lowest risk.
- **LIB-NEW-1** — join the count subquery; fixes a hard 500 on `GET /api/artists?order_by=album_count|track_count`.
- **SI-NEW-1** — fix the realtime-EQ flush to return exactly `len(audio_chunk)` (verify the path is reachable in the live streaming pipeline first).

---

## Verification Notes (orchestrator)

| Claim | Verdict | Evidence |
|-------|---------|----------|
| SI-NEW-1: flush returns wrong length; assert guards it | **CONFIRMED (precondition flagged)** | `realtime_eq.py:165-193` returns `np.concatenate(processed_chunks)` (∑ accumulated ≥ buffer_size); `hybrid_processor.py:440` `assert len(processed_chunk) == input_len`. Crashes **iff** the realtime-adaptive-EQ variable-chunk accumulation path is reached during streaming — fix-owner should confirm reachability vs. the chunked (simple_mastering) path. |
| LIB-NEW-1: order-by-count subquery not joined | **CONFIRMED** | `artist_repository.py:88-101` builds `album_count_query`/`track_count_query` subqueries; outer `select(Artist).order_by(desc(subq.c.…))` never joins them → `OperationalError: no such column: anon_1.album_count`. |
| AN-NEW-1: LUFS K-weighting non-standard | **CONFIRMED, with one sub-claim corrected** | `loudness_meter.py:70-96`: HP is `butter(1, 40.0)` (should be 2nd-order ~38.1 Hz); shelf `f0=1500.0` (should be 1681.974 Hz). **Correction**: the agent's "stage order swapped" sub-claim is moot — cascaded LTI filters commute, so apply-order does not change the result. The real defects are the **frequency and filter-order** errors. |
| DSP-NEW-3 / DSP-NEW-2: `0.005` clamp relocates LF edges | **CONFIRMED** | `transient_shaper.py:81` `lo_n = max(0.005, …)`; `60/22050=0.00272 → 0.005 → 110 Hz`. Same clamp at `sub_bass_control.py:59`. |
| Prior fixes `cca59d9c`/`8bc5b217`/`53cef6b4`/`bd94fd59`/`8adb8d0a` | **ALL INTACT** | Verified per dimension. |

---

## CRITICAL Findings

### CRIT-1 (SI-NEW-1): RealtimeAdaptiveEQ buffer-flush returns a multiple-of-buffer length → assertion crash
- **Severity**: CRITICAL · **Dimension**: Sample Integrity · **Status**: NEW · **Verified (precondition flagged)**
- **Location**: `auralis/dsp/realtime_adaptive_eq/realtime_eq.py:158-193` · guard at `auralis/core/hybrid_processor.py:440`
- **Description**: `_handle_variable_chunk_size` accumulates incoming chunks in a deque; when `total_samples >= buffer_size` it processes the **entire accumulated buffer** and returns `np.concatenate(processed_chunks)`, whose length is a multiple of `buffer_size` — generally `>> len(audio_chunk)`. `HybridProcessor.process_realtime_chunk` asserts `len(processed_chunk) == input_len` (line 440). On a flush event the assert fires (`AssertionError`), hard-crashing the realtime chunk path.
- **Evidence**:
  ```python
  # realtime_eq.py:165,193
  combined_audio = np.concatenate(list(self.input_buffer))   # all accumulated samples
  ...
  return np.concatenate(processed_chunks)                     # len = ∑ accumulated, not len(audio_chunk)
  # hybrid_processor.py:440
  assert len(processed_chunk) == input_len, ("realtime chunk shape mismatch ...")
  ```
- **Impact**: Crash on the low-latency realtime path **if** the realtime-adaptive-EQ variable-chunk accumulation branch is exercised (incoming chunk size ≠ EQ `buffer_size`, accumulation reaches `buffer_size`). The chunked streaming path (`simple_mastering`, 30 s chunks) does not use this branch — confirm which path the live WebSocket stream takes before assigning final severity.
- **Suggested Fix**: Buffer on **both** sides: after processing `combined_audio`, return exactly the `len(audio_chunk)` samples corresponding to the current input and retain the remainder in an output buffer for subsequent calls. Or redesign to always emit `len(audio_chunk)` processed samples.

---

## HIGH Findings

### HIGH-1 (DSP-NEW-3): TransientShaper bass band starts at 110 Hz — kick/bass fundamentals excluded
- **Severity**: HIGH · **Dimension**: DSP Pipeline · **Status**: NEW · **Verified**
- **Location**: `auralis/core/dsp/transient_shaper.py:81`
- **Description**: `lo_n = max(0.005, min(0.995, band_low_hz / nyq))`. For the bass transient band `band_low_hz = 60 Hz`; at 44.1 kHz `60/22050 = 0.00272` is clamped to `0.005` → effective low edge **110 Hz**. The bandpass spans 110–250 Hz instead of 60–250 Hz, so the 60–110 Hz range (kick fundamental + bass) is excluded from the attack-restoration envelope. The stage still fires and logs a positive result but does nothing for the most important range. `QuietBranch` relies on this to restore kick punch on quiet/compressed material.
- **Impact**: No audible attack improvement on kick-heavy tracks despite the stage reporting success.
- **Related/Siblings**: DSP-NEW-2 (same `0.005` clamp in `sub_bass_control.py:59`). Shared one-line root-cause fix.
- **Suggested Fix**: `lo_n = max(1e-4, min(0.995, band_low_hz / nyq))` (stable at all SR ≥ 40 kHz). Apply identically to `sub_bass_control.py:59`.

### HIGH-2 (PS-NEW-1): Gapless non-prebuffer fallback de-syncs `audio_data` from `queue.current_index`
- **Severity**: HIGH · **Dimension**: Player State · **Status**: NEW · **Verified by agent**
- **Location**: `auralis/player/gapless_playback_engine.py:328-340`
- **Description**: In `advance_with_prebuffer()`'s non-gapless fallback, `file_manager.load_file(next)` atomically swaps `audio_data/sample_rate/current_file`, then `queue.advance_if_next_matches(next_track)` commits the index. If the queue was mutated between `peek_next_track()` and now, the commit returns `False` — but audio is already swapped to N+1 while `current_index` still points at N, and the caller returns `False` without rollback. The gapless-with-prebuffer path (lines 285-303) **does** capture and restore `old_audio/old_sr/old_file` (cites #4100); the non-gapless else-branch does not.
- **Impact**: `current_file` = N+1, `queue.current_index` = N. Next `play()` resumes the old track's position on the new track's audio; UI shows N while N+1 plays. Triggered when a queue mutation (add/remove/reorder/shuffle) races an auto-advance with no prebuffer ready.
- **Suggested Fix**: Snapshot `old_audio/old_sr/old_file` under `_audio_lock` before `load_file()`; restore on `advance_if_next_matches` failure (mirror lines 287-303).

### HIGH-3 (AN-NEW-1): LUFS K-weighting uses non-standard coefficients (biases every stored `lufs`)
- **Severity**: HIGH · **Dimension**: Analysis · **Status**: NEW · **Verified (order-swap sub-claim corrected)**
- **Location**: `auralis/analysis/loudness_meter.py:70-96`
- **Description**: BS.1770-4 K-weighting = a high-shelf pre-filter at **1681.974 Hz** (+3.999843 dB) cascaded with a **2nd-order** Butterworth high-pass at **~38.135 Hz**. The code uses a **1st-order** HP at **40 Hz** and a shelf at **1500 Hz** (+4 dB). The shelf frequency error (~1.8 semitones) and the 1st-vs-2nd-order HP both alter the weighting curve. **Note**: the apply-order is irrelevant — cascaded LTI filters commute — so only the coefficient errors matter.
- **Impact**: The `lufs` fingerprint dimension (one of 25 compared by the similarity engine) is systematically biased vs BS.1770-4, and `loudness_assessment.py` pass/fail in the quality gate is wrong. Not a crash — a correctness/accuracy defect.
- **Siblings**: Same meter feeds `QualityMetrics.assess_quality()` and `AudioFingerprintAnalyzer._analyze_dynamics_cached()`.
- **Suggested Fix**: Replace with exact ITU-R BS.1770-4 biquad coefficients (or adopt `pyloudnorm`). A fingerprint re-analysis/migration is needed for stored `lufs` values to become comparable to corrected ones.

### HIGH-4 (AN-NEW-2): `signal.hilbert()` on full-length audio — multi-GB allocation / OOM
- **Severity**: HIGH · **Dimension**: Analysis · **Status**: NEW · **Verified by agent**
- **Location**: `auralis/analysis/dynamic_range.py:245,278,325` · `auralis/analysis/phase_correlation.py:108-109`
- **Description**: `DynamicRangeAnalyzer` (3 sites) and `PhaseCorrelationAnalyzer` (2 sites) call `scipy.signal.hilbert()` on the full array with no length cap. `hilbert` allocates a complex128 analytic signal (16 B/sample). `load_audio` permits up to `MAX_DURATION_SECONDS = 7200`; a 2-hour 44.1 kHz track is ~317 M samples/channel → ~5 GB per call, ~15 GB across the three DR calls. Reached via `QualityMetrics.assess_quality()` → `ContentAnalyzer.analyze_content()` with full audio in the learning/reference path (`reference_analyzer.py`, `hybrid_mode.py:58`).
- **Impact**: `MemoryError` crash analysing long reference tracks; OOM risk during library analysis.
- **Suggested Fix**: Cap input before Hilbert (e.g. first 5 s for envelope shape), or replace with an O(N) RMS envelope via `filtfilt(abs(audio))`. Fix all 5 sites.

### HIGH-5 (LIB-NEW-1): `ArtistRepository.get_all()` crashes on `order_by='album_count'`/`'track_count'`
- **Severity**: HIGH · **Dimension**: Library & Database · **Status**: NEW · **Verified**
- **Location**: `auralis/library/repositories/artist_repository.py:86-127`
- **Description**: The count-ordering subqueries are built and `order_column = desc(subq.c.album_count)`, but the outer `select(Artist)…order_by(order_column)` never joins the subquery → emitted SQL `ORDER BY anon_1.album_count` references an unjoined alias → SQLite `OperationalError: no such column: anon_1.album_count`. Both values are advertised in the route's `Literal[...]` param and passed by `library.py:107-114`.
- **Impact**: `GET /api/artists?order_by=album_count|track_count` → hard 500 for any user sorting artists by count.
- **Siblings**: `track_count_query` (same method, lines 98-104).
- **Suggested Fix**: `outerjoin` the subquery and order by `func.coalesce(sq.c.album_count, 0)`, or use a grouped `func.count()` in the main select.

---

## MEDIUM Findings

| ID | Location | Issue | Fix |
|----|----------|-------|-----|
| MED-DSP-1 (DSP-NEW-1) | `core/processing/eq_processor.py:196-204` · `dsp/eq/psychoacoustic_eq.py:163-167` | `analyze_spectrum` receives an already `sqrt(hann)`-windowed chunk, then applies its own full Hann → masking analysis sees `hann^(3/2)` (+6 dB center, −38 dB edges) while `apply_eq` processes only `sqrt(hann)`. Systematic per-chunk masking bias (bounded by ±12 dB gain cap). | Pass the unwindowed chunk to `process_realtime_chunk` and apply the WOLA window only to the returned chunk (option a). |
| MED-DSP-2 (DSP-NEW-2) | `core/stages/sub_bass_control.py:59` | Same `max(0.005,…)` clamp puts the 25 Hz rumble HP at ~110 Hz (44.1 k) / 240 Hz (96 k), cutting kick fundamentals on extreme-rumble material. | `max(1e-4,…)`; also switch `sosfilt`→`sosfiltfilt` per #4097. |
| MED-PS-2 (PS-NEW-2) | `player/enhanced_audio_player.py:351-352` | `load_track_from_library` calls `playback.load_and_stop()` **outside** `_audio_lock` (unlike `load_file` at 222-223). A concurrent `get_audio_chunk()` can read new audio at the old position → silence/wrong-position chunk / spurious advance; `track_loaded` callback can report `position > duration`. Same class as fixed #3667. | Wrap the call in `with self.file_manager._audio_lock:`. |
| MED-IO-1 (IO-NEW-1) | `io/unified_loader.py:82` · `io/loaders/soundfile_loader.py:74` | soundfile path runs `sf.read()` fully **before** the `MAX_DURATION_SECONDS` check; a 3-hour 96 kHz FLAC decodes ~7.8 GB before rejection. The player `loader.py` correctly calls `sf.info()` first. Sibling of #4128. | Add an `sf.info()` duration guard before `sf.read()` in `load_with_soundfile`. |
| MED-AN-3 (AN-NEW-3) | `analysis/quality/quality_metrics.py:68` · `analysis/content_analysis.py:75-77` | `QualityMetrics` resets `loudness_meter` per call but not `dynamic_range_analyzer.crest_history` / `phase_analyzer.correlation_history`, so they bleed across tracks (corrupts `phase_stability`, `correlation_variance`). Shared-instance sibling of #4120. | Add `dynamic_range_analyzer.reset_history()` + `phase_analyzer.reset_history()` to `assess_quality()`. |
| MED-AN-5 (AN-NEW-5) | `analysis/content_analysis.py:225-228` | Public `analyze_audio_content()` builds a fresh `ContentAnalyzer` (~15-20 objects, 2 `LoudnessMeter`s) per call; combined with AN-NEW-2 a batch loop allocates GBs/track. | Accept an optional pre-built analyzer or cache a module-level singleton. |
| MED-LIB-2 (LIB-NEW-2) | `library/repositories/track_repository.py:913-921` | `cleanup_missing_files` re-verify loop issues one `session.get(Track, tid)` per missing id (≤1000/batch) on a single long-lived connection — N+1. | Batch-fetch `SELECT id, filepath WHERE id IN (...)`, then re-verify. |
| MED-LIB-3 (LIB-NEW-3) | `fingerprint_repository.py:397,447,500` · `similarity_graph_repository.py:156` | `if limit:` treats `limit=0` as unbounded (returns all rows) — e.g. `get_missing_fingerprints(0)` loads the whole table (OOM). Correct form `if limit is not None:` was established by #3683 at line 259 but not propagated. | `if limit is not None:` at all 4 sites. |

---

## LOW Findings

- **LOW-SI-2 (SI-NEW-2)** — `dsp/dynamics/vectorized_envelope.py:70` hardcodes `np.zeros_like(input_levels, dtype=np.float32)`, ignoring caller dtype (latent float64→float32 downcast; masked today by `compressor.py` casting first). Use `np.zeros_like(input_levels)` or assert the dtype.
- **LOW-DSP-4 (DSP-NEW-4)** — `dsp/eq/psychoacoustic_eq.py:42,79` `EQSettings.overlap = 0.75` is dead; `EQProcessor` hardcodes 50% hop. WOLA is COLA-correct at 50%, but editing `overlap` silently does nothing. Remove it or wire it through.
- **LOW-PS-3 (PS-NEW-3)** — `player/enhanced_audio_player.py:795` reads `self._advance_thread` (written under `_audio_lock` at 575) without the lock; torn-read risk under free-threaded Python 3.14+ (join skipped, advance thread survives cleanup; `_cleanup_in_progress` mitigates). Read under `_audio_lock`. Sibling of #3785.
- **LOW-IO-2 (IO-NEW-2)** — `core/simple_mastering.py:149` creates a `TemporaryDirectory` for FFmpeg-decoded PCM but `.cleanup()` only on the happy path (line 451); any exception leaves up to ~500 MB on tmpfs until exit. Wrap in `try/finally`.
- **LOW-PP-1 (PP-NEW-1)** — `optimization/parallel_processor.py:395-399` `_process_band_groups` exception-fallback calls `band_filters[idx](audio)` without `.copy()` (workers at 380 use `audio.copy()`); corrupts subsequent fallback iterations if a band filter mutates in place. **Currently inert** (no production callers of `ParallelBandProcessor`). Add `.copy()`.
- **LOW-AN-4 (AN-NEW-4)** — `analysis/content_analysis.py:74` `ContentAnalyzer.loudness_meter` is a dead duplicate alongside `QualityMetrics`'s own live meter (extends #4135). Delete the dead instance.

---

## Relationships & Shared Root Causes

1. **The `max(0.005, …)` normalized-frequency floor** is the shared root cause of HIGH-1 (DSP-NEW-3) and MED-DSP-2 (DSP-NEW-2) — a single floor change to `1e-4` fixes both LF filters. Grep `0.005` across `auralis/core/dsp/` and `auralis/core/stages/` when fixing, in case other stages copied the idiom.
2. **Cross-track analyzer state** ties MED-AN-3 (shared-instance history in `QualityMetrics`) to open **#4120** (standalone analyzer) and to AN-NEW-2's per-call allocation — a single "reset/own analyzer lifecycle per track" refactor addresses the family.
3. **Unbounded allocation on long audio**: HIGH-4 (Hilbert) and MED-IO-1 (soundfile pre-decode) both stem from trusting `MAX_DURATION_SECONDS=7200` without a streaming/cap strategy; sibling of open #4128.
4. **Audio/position atomicity under `_audio_lock`**: MED-PS-2 and HIGH-2 join the open lock-ordering cluster (#3781/#3782/#3785/#4141) — the `load_file` rollback+lock pattern is the reference fix to propagate.
5. **LUFS correctness chain**: HIGH-3 (K-weighting) feeds both the stored `lufs` fingerprint dimension and the quality gate; fixing it requires a re-analysis migration to make old/new `lufs` comparable (relates to the broader fingerprint-determinism concerns and Rust LUFS #4123).

---

## Prioritized Fix Order

1. **HIGH-1 + MED-DSP-2** — the `0.005 → 1e-4` floor (2 lines). Highest audible gain, lowest risk; restores kick/bass to the transient shaper and sub-bass HP.
2. **HIGH-5 (LIB-NEW-1)** — join the count subquery; fixes a live 500 on the artists API. Small, self-contained.
3. **CRIT-1 (SI-NEW-1)** — fix the realtime-EQ flush length (after confirming the path is reachable in the live stream; if not reachable, downgrade to HIGH and still fix).
4. **HIGH-2 + MED-PS-2** — add rollback to the gapless fallback and wrap `load_track_from_library` in `_audio_lock` (player atomicity).
5. **HIGH-4 + MED-IO-1** — cap/replace Hilbert on long audio and add the soundfile pre-decode guard (OOM safety).
6. **HIGH-3 (AN-NEW-1)** — correct K-weighting coefficients; plan a `lufs` re-analysis migration.
7. **MEDIUM** masking-window bias, analyzer history resets, per-call ContentAnalyzer, N+1, `limit=0`.
8. **LOW** dtype hardcode, dead `overlap`, unlocked read, temp-dir leak, uncopied fallback, duplicate meter.

---

*Generated by `/audit-engine` (7 dimensions, deep). Dedup against live GitHub (270 open) + recent engine reports. Headline findings re-verified against source; AN-NEW-1's apply-order sub-claim corrected (LTI filters commute). Suggest publishing via `/audit-publish docs/audits/AUDIT_ENGINE_2026-06-10.md`.*

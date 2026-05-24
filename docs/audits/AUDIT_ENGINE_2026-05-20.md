# Engine Audit — 2026-05-20

**Auditor**: Claude Opus 4.7 (1M ctx) — orchestrator + 7 dimension subagents
**Scope**: Core pipeline, DSP, player, I/O, parallel processing, analysis, library
**Method**: Deep (full call-graph tracing). Per-dimension subagents investigated; orchestrator verified each finding in code before inclusion.

## Executive Summary

Audit follows a heavy wave of mastering features added since 2026-03-25 — adaptive mastering stages (notches, transients, clarity), harmonic exciter, cross-dimensional guard framework — plus ~20 fixes to prior findings.

**16 new findings**: 5 HIGH, 8 MEDIUM, 3 LOW (subagent turn-budget exhaustion forced orchestrator to verify findings directly; only verified items are included).

**Key clusters:**

1. **Adaptive-fingerprint coverage gap** (PLR-01, AN-04-PERSIST) — the generation-counter fix (#3445) only covers `load_file()`. Library-load and gapless-next paths still apply stale fingerprints to the wrong track. Compounding this, the on-disk `.25d` cache returns `None` for every entry because `targets={}` triggers the `not targets` reject in `FingerprintStorage.load()` — the fingerprint cache is effectively dead.

2. **Mastering DSP dtype/phase regressions in new modules** (SI-01, DSP-01, DSP-02) — `sosfiltfilt` in stereo widening silently upgrades the chain to float64; `sosfilt` (causal) in the new HarmonicExciter / TransientShaper extracts donor bands with phase delay, then adds them back into the un-delayed dry path — parallel addition with phase offset risks comb filtering and smeared transients.

3. **PCM encode-path invariants** (IO-01, IO-02, IO-03) — `Code.ERROR_CORRUPTED` referenced but not defined (turns a helpful error into AttributeError); `saver.py` skips the `[-1.0, 1.0]` clamp before `sf.write(... PCM_16)`; loader's `validate_audio` doesn't check NaN/Inf so corrupt files can reach the chunked encoder.

4. **Library data-integrity** (LIB-01) — `fingerprint_repository.upsert()` runs `INSERT OR REPLACE` without listing the `fingerprint_blob` column, so any subsequent call to `upsert()` after a `store_fingerprint()` wipes the quantized blob the similarity scanner depends on.

5. **Loudness measurement broken for normal tracks** (AN-05) — `LoudnessMeter.finalize_measurement()` reads `block_buffer`, but `measure_chunk` pops blocks beyond `short_term_blocks=30`. Integrated LUFS is the gated average of all blocks per ITU-R BS.1770; instead it reflects only the most recent ~30 chunks.

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 5 |
| MEDIUM | 8 |
| LOW | 3 |
| **Total** | **16** |

## Prior Findings Status (since 2026-03-25)

Verified fixed and holding:
- AdaptiveLimiter origin (#3426, ENG-NEW-01)
- AdaptiveLimiter attack/release polarity (#3435, ENG-NEW-02)
- WOLA terminal-chunk dip (#3437, ENG-NEW-04)
- Coherent-gain correction (#3428, ENG-NEW-14)
- HybridMode finite validation (#3429)
- AdaptationEngine empty `np.mean` guard (#3431)
- Emergency limiter -0.3 dBFS ceiling (#3432)
- ParallelSpectrumAnalyzer batch smoothing-race (#3433, PP-02)
- ParallelBandProcessor failed band fallback (PP-01)
- Sub-FFT-size zero-pad (ENG-NEW-06)
- Artist repo `selectinload(Track.album)` (LIB-02 from prior)
- `restore_database` SQLite backup API (LIB-06)
- KNN graph batched streaming (LIB-07)
- Per-directory scan dedup (LIB-03)
- BatchAnalyzer error logging (AN-03)
- RuleBasedGenreClassifier `@lru_cache(maxsize=1)` (AN-05 from prior)

Still open (not re-reported here):
- #3438 fingerprint daemon threads survive cleanup
- #3434 end-of-track advance spawn not atomic
- #3354 IntegrationManager callback ordering
- #3352 advance_with_prebuffer peek-twice
- #3340 PlaylistRepository.remove_track lazy load
- #3312 MigrationManager PRAGMA busy_timeout
- #3459 fingerprint_repository upsert race
- #3458 stats_repository total_duration WHERE clause
- #3448 StreamingSpectralAnalyzer smoothing_buffer
- #3446 ParallelBandProcessor executor shutdown
- #3355 ParallelBandProcessor copy() to threads

---

## New Findings

### HIGH

---

### PLR-01: Stale fingerprint applied to wrong track after gapless next_track / load_track_from_library
- **Severity**: HIGH
- **Dimension**: Player State
- **Location**: `auralis/player/enhanced_audio_player.py:275-291` (`load_track_from_library`), `:295-321` (`next_track`)
- **Status**: NEW (coverage gap in #3445 fix)
- **Description**: The generation-counter fix (#3445) only bumps `_track_generation` and spawns `_load_fingerprint_for_file` from `load_file()`. The library and gapless-advance paths bypass `load_file()`:
  - `load_track_from_library()` calls `integration.load_track_from_library(track_id)` + `playback.load_and_stop()` + `gapless.start_prebuffering()` — never increments `_track_generation` and never schedules a fingerprint load. The processor keeps the prior track's fingerprint.
  - `next_track()` uses `gapless.advance_with_prebuffer()` which swaps `audio_data` directly without touching `_track_generation`. An in-flight fingerprint thread for the *previous* file passes the `if self._track_generation != generation` guard (line 232) and applies its fingerprint to the new track via `processor.set_fingerprint(fingerprint)`.
- **Evidence**: `load_file()` at lines 186-213 contains the bump + thread; `load_track_from_library()` at 275-291 does not; `next_track()` at 295-321 calls only `gapless.advance_with_prebuffer()` + `seek(0,...)` + `play()`.
- **Impact**: Adaptive mastering applies the wrong fingerprint for every track loaded via the library API or advanced via gapless next. Since the player is mostly used through the queue, this is the common case.
- **Suggested Fix**: In both `load_track_from_library` (after `integration.load_track_from_library` succeeds) and after a successful `gapless.advance_with_prebuffer()`, bump `_track_generation` and spawn `_load_fingerprint_for_file` for the new file path.

---

### AN-04-PERSIST: FingerprintStorage `.25d` cache always misses — `targets={}` triggers `not targets` reject
- **Severity**: HIGH
- **Dimension**: Analysis
- **Location**: `auralis/analysis/fingerprint/fingerprint_storage.py:162`, `auralis/analysis/fingerprint/fingerprint_service.py:146`
- **Status**: Carry-forward from prior AN-04 (2026-03-25) — re-classified HIGH after confirming impact
- **Description**: `FingerprintStorage.load()` does `if not fingerprint or not targets: return None` at line 162. `fingerprint_service.py:146` always calls `FingerprintStorage.save(audio_path, fingerprint, {})` — empty dict for targets. After save, the file on disk has `mastering_targets: {}`. On load, `not {}` is True, so `load()` returns `None` for every cached file. The `.25d` file-tier of the 3-tier cache (database → .25d → on-demand) is effectively unused — every miss falls through to on-demand computation.
- **Evidence**:
  ```python
  # fingerprint_service.py:146
  FingerprintStorage.save(audio_path, fingerprint, {})
  # fingerprint_storage.py:162
  if not fingerprint or not targets:
      return None
  ```
- **Impact**: Massive wasted compute on every "cached" fingerprint lookup. Player startup, library scan, similarity build all pay full fingerprint cost despite the cache layer existing.
- **Suggested Fix**: Either (a) drop the `not targets` check in `load()` since targets can legitimately be empty until mastering-target computation runs, or (b) have `fingerprint_service` compute and store actual targets when saving. Option (a) is the one-line fix.

---

### IO-01: `Code.ERROR_CORRUPTED` referenced in ffmpeg loader but not defined — AttributeError on probe failure
- **Severity**: HIGH
- **Dimension**: Audio I/O
- **Location**: `auralis/io/loaders/ffmpeg_loader.py:114`; `Code` class at `auralis/utils/logging.py:16`
- **Status**: NEW
- **Description**: `Code.ERROR_CORRUPTED` does not exist on the `Code` class. When `_probe_audio` returns `None` for `sample_rate` or `channels`, the f-string at line 114 raises `AttributeError: type object 'Code' has no attribute 'ERROR_CORRUPTED'` instead of the intended `ModuleError("...: Could not probe sample rate / channel count ...")`. The fix for #2495 (the regression that motivated this guard) is half-wired — the guard fires but the error is swallowed into an opaque AttributeError.
- **Evidence**:
  ```python
  # ffmpeg_loader.py:112-116
  if probe['sample_rate'] is None or probe['channels'] is None:
      raise ModuleError(
          f"{Code.ERROR_CORRUPTED}: Could not probe sample rate / channel count for "
          f"'{file_path}'. FFprobe output may be malformed or the container unsupported."
      )
  ```
  Searching `auralis/utils/logging.py`, the `Code` class has `ERROR_LOADING`, `ERROR_INVALID_AUDIO`, `ERROR_TRUNCATED_FILE`, etc. — no `ERROR_CORRUPTED`.
- **Impact**: Corrupt/unsupported files surface as `AttributeError` instead of the descriptive `ModuleError`. Logs lose the diagnostic message; upstream try/except for `ModuleError` does not catch it; the chunked-processor wrapper may also fail to translate.
- **Suggested Fix**: Add `ERROR_CORRUPTED = "Corrupted or unsupported audio file"` to `Code` in `auralis/utils/logging.py`, or change line 114 to use `Code.ERROR_INVALID_AUDIO` / `Code.ERROR_UNSUPPORTED_FORMAT`.

---

### AN-05: LoudnessMeter integrated LUFS reads truncated block_buffer — wrong for tracks longer than buffer
- **Severity**: HIGH
- **Dimension**: Analysis
- **Location**: `auralis/analysis/loudness_meter.py:213-214` (pop), `:289-345` (`finalize_measurement`)
- **Status**: NEW
- **Description**: `measure_chunk()` appends one block per chunk to `self.block_buffer`, then truncates: `if len(self.block_buffer) > self.short_term_blocks: self.block_buffer.pop(0)` with `short_term_blocks=30`. `finalize_measurement()` then computes the gated integrated loudness as `gated_blocks = [b for b in self.block_buffer if b >= -70.0]` — but `self.block_buffer` only holds the last 30 blocks at this point. ITU-R BS.1770 integrated loudness is defined as the gated mean over the *entire* measurement window; here it reflects only the tail.
- **Evidence**:
  ```python
  # loudness_meter.py:210-214
  self.block_buffer.append(block_loudness)
  # Maintain buffer size for short-term measurement
  if len(self.block_buffer) > self.short_term_blocks:
      self.block_buffer.pop(0)
  ```
  ```python
  # :309
  gated_blocks = [b for b in self.block_buffer if b >= -70.0]
  ```
  Plus `measurement_duration=len(self.block_buffer) * 0.1` (line 350) reports a 3 s window regardless of true track length.
- **Impact**: Every integrated-LUFS measurement (fingerprint extraction, mastering target derivation, mastering-quality assessment) is wrong for tracks longer than 30 measurement chunks. Mastering decisions made from this LUFS value are systematically biased toward the track's ending.
- **Suggested Fix**: Maintain a separate `integrated_buffer` that is appended without truncation, and keep `block_buffer` strictly for short-term/momentary windows. Compute integrated LUFS in `finalize_measurement` from `integrated_buffer`.

---

### LIB-01: `fingerprint_repository.upsert()` drops `fingerprint_blob` and `fingerprint_version` columns via INSERT OR REPLACE
- **Severity**: HIGH
- **Dimension**: Library & Database
- **Location**: `auralis/library/repositories/fingerprint_repository.py:599-639`
- **Status**: NEW (related to but distinct from #3459)
- **Description**: SQLite `INSERT OR REPLACE` deletes the existing row and inserts a new one with exactly the columns named. `upsert()` lists only `track_id` + the 25 fingerprint dimensions:
  ```python
  text(f"INSERT OR REPLACE INTO track_fingerprints (track_id, {cols_str}) VALUES (:track_id, {named_placeholders})")
  ```
  If `store_fingerprint()` previously wrote a row with `fingerprint_blob` and `fingerprint_version`, a subsequent `upsert()` deletes that row and inserts a new one *without* the blob — those columns revert to whatever default the schema has (likely NULL). The similarity scanner depends on the quantized blob.
- **Evidence**: `upsert()` at lines 599-639 omits the blob columns; `store_fingerprint()` at lines 641-705 includes them.
- **Impact**: Any call path that hits `upsert()` after a `store_fingerprint()` wipes the quantized fingerprint blob. Similarity / KNN graph lose that track silently until the next full fingerprint pass.
- **Suggested Fix**: Convert `upsert()` to use SQLite's `ON CONFLICT (track_id) DO UPDATE SET ...` syntax instead of `INSERT OR REPLACE`. The `ON CONFLICT` form only updates the listed columns and leaves the others (blob, timestamps) intact.

---

### MEDIUM

---

### SI-01: `adjust_stereo_width_multiband` silently promotes float32 → float64 via `sosfiltfilt`
- **Severity**: MEDIUM
- **Dimension**: Sample Integrity
- **Location**: `auralis/dsp/utils/stereo.py:140-176`
- **Status**: NEW
- **Description**: `sosfiltfilt` always returns float64 regardless of input dtype. `band_lowmid`, `band_highmid`, `band_high` (and their widened variants and `diff_*`) are all float64. The final return `stereo_audio + diff_lowmid + diff_highmid + diff_high` promotes the float32 input to float64.
- **Evidence**:
  ```python
  band_lowmid = sosfiltfilt(sos_lowmid, stereo_audio, axis=0)   # always float64
  ...
  return stereo_audio + diff_lowmid + diff_highmid + diff_high   # float32 + float64 → float64
  ```
  Call site `auralis/core/simple_mastering.py:865` passes the result downstream, where subsequent stages then operate on float64 contrary to the project invariant.
- **Impact**: Doubled memory bandwidth and processing cost from this point in the chain onward. Subtle bug surface if any downstream code asserts dtype.
- **Suggested Fix**: Cast each band back at extraction time: `band_lowmid = np.asarray(sosfiltfilt(...), dtype=stereo_audio.dtype)`. Apply the same to `band_highmid`, `band_high`.

---

### DSP-01: HarmonicExciter uses causal `sosfilt` for donor band — phase offset against dry path
- **Severity**: MEDIUM
- **Dimension**: DSP Pipeline
- **Location**: `auralis/core/dsp/harmonic_exciter.py` (donor extraction path; commit `2a162a99`)
- **Status**: NEW
- **Description**: The harmonic exciter extracts its donor band with `sosfilt` (causal, non-zero-phase). The processed donor is mixed back into the dry signal with `audio + wet * donor_harmonic`. Because `sosfilt` introduces a frequency-dependent phase delay (~filter order × samples), the donor harmonic content is mixed with the dry signal at a *different* time alignment than the original spectral content at that frequency — producing comb filtering or smearing at the crossover.
- **Evidence**: Donor extraction at the bandpass uses `sosfilt(bp_sos, audio, axis=axis)` (causal); the dry path is the unfiltered `audio`. The wet add re-injects harmonics that originate from delayed source content.
- **Impact**: Subtle frequency-response artifacts in the donor band — a comb-like ripple whose period depends on the filter delay. Audible primarily as a "hollow" presence range after the exciter, not as obvious distortion.
- **Suggested Fix**: Switch the donor extraction to `sosfiltfilt` for zero-phase, OR introduce a matching dry-path delay so the wet and dry are time-aligned, OR move to a linear-phase FIR bandpass.

---

### DSP-02: TransientShaper bandpass uses causal `sosfilt` — delta added late to dry signal
- **Severity**: MEDIUM
- **Dimension**: DSP Pipeline
- **Location**: `auralis/core/dsp/transient_shaper.py` (envelope band extraction; commit `c55d008f`)
- **Status**: NEW
- **Description**: Same pattern as DSP-01. The transient shaper extracts a band with `sosfilt` to drive its attack/release envelope, computes a `delta`, and adds the delta back into the un-delayed dry path. The delta corresponds to source content from filter-delay-samples ago, so the transient "boost" arrives *after* the dry transient has already played — the dry transient passes un-shaped, then a delayed echo follows.
- **Evidence**: Bandpass `sosfilt(...)` followed by `dry + delta` addition in the shaper.
- **Impact**: The transient shaper smears rather than sharpens transients. Mild but the audible result is the opposite of the algorithm's intent on percussive content.
- **Suggested Fix**: Use `sosfiltfilt` for the analysis band (and accept the doubled compute), or apply an equal delay to the dry path before adding the delta.

---

### IO-02: `saver.py` does not clamp to [-1.0, 1.0] before PCM encode
- **Severity**: MEDIUM
- **Dimension**: Audio I/O
- **Location**: `auralis/io/saver.py:19-42`
- **Status**: NEW
- **Description**: `save()` casts to float32 and calls `sf.write(file_path, audio_data, sample_rate, subtype=subtype)` directly. When `subtype` is `PCM_16` / `PCM_24`, libsndfile clamps out-of-range float samples to ±1.0 (modern libsndfile) but historically would wrap on some builds. The project audio invariants explicitly require `output = np.clip(output, -1.0, 1.0)` before quantization. `wav_encoder.py` does clamp; `saver.py` does not.
- **Evidence**:
  ```python
  if audio_data.dtype != np.float32:
      audio_data = audio_data.astype(np.float32)
  sf.write(file_path, audio_data, sample_rate, subtype=subtype)
  ```
- **Impact**: Out-of-range samples (from a buggy upstream stage) silently rely on libsndfile clamping. No defensive layer at the encode boundary.
- **Suggested Fix**: Add `audio_data = np.clip(audio_data, -1.0, 1.0)` between the dtype cast and `sf.write`.

---

### IO-03: `validate_audio` does not check NaN/Inf — loader output can carry non-finite samples
- **Severity**: MEDIUM
- **Dimension**: Audio I/O
- **Location**: `auralis/io/processing.py` (`validate_audio`)
- **Status**: NEW
- **Description**: `HybridProcessor` validates finiteness at its entry (commit `791de0ec`), but the chunked processor and player paths load via `auralis/io/processing.validate_audio`, which only checks shape/length/empty — not `np.isfinite`. A corrupt source file producing NaN/Inf samples can pass through the chunked encoder without sanitization. The downstream `BrickWallLimiter` then propagates NaN through the entire output buffer.
- **Evidence**: `validate_audio` has no `np.isfinite` / `np.isnan` check; `Code.ERROR_NAN_DETECTED` exists in `logging.py` but is unused by the loader.
- **Impact**: A single corrupt sample can poison an entire chunk; the player then emits a stream of NaN samples (decoder dependent: clicks, silence, or wrap to ±max).
- **Suggested Fix**: Add `if not np.isfinite(audio_data).all(): raise ModuleError(f"{Code.ERROR_NAN_DETECTED}: ...")` (or sanitize via `np.nan_to_num`) in `validate_audio`.

---

### PLR-02: `_track_generation += 1` not atomic — concurrent load_file may produce duplicate generations
- **Severity**: MEDIUM
- **Dimension**: Player State
- **Location**: `auralis/player/enhanced_audio_player.py:190-191`
- **Status**: NEW
- **Description**: `self._track_generation += 1; generation = self._track_generation` runs outside any lock. Python's `+=` on an int attribute is read-modify-write at the bytecode level; two concurrent `load_file` calls can both read the same value, both write the same `+1`, and both pass the same `generation` to their fingerprint threads. The `if self._track_generation != generation` guard (line 232) then admits both — fingerprints applied in nondeterministic order.
- **Evidence**: Lines 190-191 sit outside `_audio_lock` and `_fingerprint_lock`. The companion `if self._track_generation == generation` at line 251 is also a TOCTOU check.
- **Impact**: With two near-simultaneous track loads (rare but possible from queue auto-load + user click), the wrong fingerprint can be applied. Severity is MEDIUM because the practical race window is small.
- **Suggested Fix**: Wrap the increment-and-read in `_fingerprint_lock` or use `itertools.count()` for a thread-safe monotonic generation.

---

### PLR-03: `IntegrationManager` reads `audio_data is None` outside `_audio_lock`
- **Severity**: MEDIUM
- **Dimension**: Player State
- **Location**: `auralis/player/integration_manager.py:263`
- **Status**: NEW (companion to the audio_data setter fix #3443)
- **Description**: The audio_data setter was hardened (`a9b480d4` / #3443) but readers still access it lock-free. `integration_manager.py:263` checks `self.file_manager.audio_data is None` while only `_position_lock` is held — not `_audio_lock`. A concurrent `clear_audio()` between the None check and the subsequent `sample_rate` access produces an inconsistent state.
- **Impact**: Rare race; manifests as inconsistent position/sample-rate reporting around stop/load boundaries.
- **Suggested Fix**: Acquire `_audio_lock` (or snapshot under it) before reading both `audio_data` and `sample_rate` together.

---

### LIB-02: `fingerprint_service` bypasses repository pattern with direct `session.execute(select(Track.id))`
- **Severity**: MEDIUM
- **Dimension**: Library & Database
- **Location**: `auralis/analysis/fingerprint/fingerprint_service.py:164`, `:252`
- **Status**: NEW
- **Description**: Project convention is that all DB access goes through repository classes. `fingerprint_service.py` does `session.execute(select(Track.id).where(...))` directly. `track_repository.get_by_filepath()` already exists and returns the same. Duplicating ORM query logic outside the repository violates the project's DRY principle and risks divergence (e.g., a future `Track` field that the repository handles correctly won't apply here).
- **Impact**: Maintenance burden, future divergence risk. No immediate correctness issue.
- **Suggested Fix**: Replace the two `session.execute(select(Track.id)...)` calls with `track_repo.get_by_filepath(filepath)` (or add `get_id_by_filepath` to the repo if id-only lookup is wanted for perf).

---

### LOW

---

### PP-01: Duplicate dead-code `ParallelProcessor` class with multiple bugs
- **Severity**: LOW
- **Dimension**: Parallel Processing
- **Location**: `auralis/optimization/acceleration/parallel_processor.py`
- **Status**: NEW
- **Description**: A second `ParallelProcessor` class exists (separate from `auralis/optimization/parallel_processor.py`). It has: no exception handling on `future.result()`, no `.copy()` of the input array passed to thread workers (same pattern as #3355), `__del__`-based shutdown (fragile), and treats `gain` as linear when callers might pass dB. No active call sites — grep shows only a `parallel.shutdown()` reference. Dead code with latent landmines.
- **Impact**: Zero today; risk if a future caller wires it up.
- **Suggested Fix**: Delete the file. If the acceleration variant is needed, consolidate with the live `optimization/parallel_processor.py`.

---

### PP-02: BatchAnalyzer outer try/except only catches `KeyboardInterrupt` — other exceptions skip executor shutdown
- **Severity**: LOW
- **Dimension**: Parallel Processing
- **Location**: `auralis/analysis/fingerprint/` batch analyzer (per-chunk loop)
- **Status**: NEW
- **Description**: The outer `try / except KeyboardInterrupt / else` block shuts down the executor on KeyboardInterrupt or normal completion. An exception that escapes the inner `future.result()` handler (e.g., a `MemoryError` in `fingerprint.update`) propagates without the `executor.shutdown(cancel_futures=True)` ever running. Workers leak.
- **Suggested Fix**: Use `try / finally` for executor shutdown rather than `try / except / else`.

---

### DSP-03: ResonanceNotcher uses `find_peaks(distance=10)` independent of sample rate
- **Severity**: LOW
- **Dimension**: DSP Pipeline
- **Location**: `auralis/core/dsp/resonance_notcher.py` (`detect`)
- **Status**: NEW
- **Description**: `find_peaks(..., distance=10)` is in *FFT bins*. With `n_fft=16384`, 10 bins is ~27 Hz at 44.1 kHz and ~59 Hz at 96 kHz — the minimum separation between detected resonances depends on the source SR.
- **Impact**: At higher sample rates, two resonances that would be detected as separate notches at 44.1 kHz get merged. Cosmetic for typical use.
- **Suggested Fix**: Convert `distance` to a fixed Hz value: `distance_bins = int(MIN_HZ_BETWEEN_PEAKS * n_fft / sample_rate)`.

---

## Relationships

1. **Adaptive-mastering coverage chain**: PLR-01 (wrong fingerprint on library/gapless paths) + AN-04-PERSIST (no `.25d` cache hits) + PLR-02 (atomic generation increment) all degrade the adaptive-mastering feature. Fixing PLR-01 without AN-04-PERSIST means every track still re-runs the full fingerprint compute on load. Fix order matters: AN-04-PERSIST first (one-line, biggest win), PLR-01 second.

2. **New mastering module phase coherence**: DSP-01 (HarmonicExciter) + DSP-02 (TransientShaper) share a `sosfilt` (causal) + parallel-add pattern. Same fix template applies to both — either swap to `sosfiltfilt` or apply matching dry-path delay. Likely the same engineer added both.

3. **Float dtype erosion**: SI-01 (stereo widening) is the only currently-confirmed sosfiltfilt→float64 leak, but the pattern is common. Worth a single sweep `grep -n 'sosfiltfilt' auralis/` to confirm every other call wraps with `np.asarray(..., dtype=input.dtype)`.

4. **Encode-boundary invariants missing**: IO-01 (undefined error code), IO-02 (no PCM clamp), IO-03 (no NaN check) are three independent gaps on the loader/saver boundary. The project documents these invariants in CLAUDE.md but enforcement is inconsistent.

## Prioritized Fix Order

1. **AN-04-PERSIST** — one-line change in `fingerprint_storage.py:162` removes a 100% cache miss. Biggest win for effort.
2. **IO-01** — add `ERROR_CORRUPTED` constant; restores diagnostic surface for corrupt files.
3. **LIB-01** — convert `upsert()` to `ON CONFLICT DO UPDATE` to preserve `fingerprint_blob`.
4. **PLR-01** — wire `_track_generation` bump + fingerprint thread into `load_track_from_library` and the gapless-advance path.
5. **AN-05** — split integrated vs short-term buffers in `LoudnessMeter`.
6. **SI-01** — cast `sosfiltfilt` outputs back to input dtype.
7. **DSP-01 + DSP-02** — switch to `sosfiltfilt` for the donor/transient extraction bands (do both at once).
8. **IO-02 + IO-03** — clamp before PCM write; NaN/Inf check in `validate_audio`.

---

*Report generated by Claude Opus 4.7 (1M ctx) — 2026-05-20*
*Suggest next: `/audit-publish docs/audits/AUDIT_ENGINE_2026-05-20.md`*

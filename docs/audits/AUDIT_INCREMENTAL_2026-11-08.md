# Incremental Audit — 2026-11-08

**Range**: `HEAD~10..HEAD` (default): the ten commits from `970cbe08e` through `aca64af3a` (HEAD).
**Method**: read every non-test diff in the range and the code around it, then probed the suspicious paths with the real modules (scratch `HOME`, synthetic and one real track, no repo file changed). Findings were deduplicated against the full issue dump (`gh issue list --state all`, 6082 issues, highest #6335, verified complete); there are no earlier `AUDIT_INCREMENTAL_*` reports.
**Not verified**: the full test suites and the CI baseline gates were not run. Test diffs were read, not re-run.

## 1. Change Summary

36 files, +1971 / −279. Ten commits. One is the #6332 album-artist fix from the previous session; the other nine are a parallel line of work that moves fingerprint analysis from a 90 s window to the **whole track** and rebuilds the mastering plan on top of it.

| Theme | Commits | Key files |
|---|---|---|
| Whole-track fingerprint (algorithm v13) | `3252f2f17` | `analysis/fingerprint/track_audio.py` (new), `analysis_budget.py` (new), `windowed_compute.py`, `windows.py` |
| Band shares over the whole input (algorithm v14) | `956222e7a` | `vendor/auralis-dsp/src/frequency_analysis.rs`, `fingerprint_compute.rs` |
| Extract a missing fingerprint before the first chunk | `0171dc6bb` | `backend/core/chunk_processor_init.py`, `chunk_cache_manager.py` |
| One EQ law for both render paths, headroom-capped level plan, no waveshaper compression | `8b004ae40`, `a0a2b6565`, `aca64af3a` | `core/processing/parameter_generator_eq.py`, `fixed_target_params.py`, `backend/core/mastering_target_generation.py` |
| Reference bench | `aa0749709`, `60b3bf13a`, `955331ef1` | `analysis/reference_profile.py` (new), `scripts/reference_bench.py` (new) |
| Album artist owner, schema v31 | `970cbe08e` | `library/*` (audited and tested in the previous session) |

## 2. High-Risk Changes

- **Rust fingerprint (HIGH domain)**: `frequency_analysis.rs` now accumulates Hann-windowed band energy over every frame of the input in f64 instead of one FFT over the first 30 s. The accumulation and normalisation read correctly, the tests added pin it, and no sample-count or NaN hazard was found. See I-06 for a small inconsistency with `compute_bass_mid_ratio`.
- **Streaming init (HIGH domain)**: `ChunkedAudioProcessor.__init__` now runs whole-track analysis (`extract_if_missing=True`) inside the 30 s `CHUNK_PROCESS_TIMEOUT`. See I-01.
- **Mastering plan (HIGH domain)**: the fixed-target path the app streams with changed its EQ law, level plan and compression amount (0.6 → 0.0). Rendered-chunk cache invalidation was checked: the key embeds a content hash of the targets, and the new targets differ in content (`eq_curve_db` replaces `eq_adjustments_db`, other levels), so chunks rendered under the old plan are never served. Not a finding.
- **Fingerprint version 14**: a global bump, so every stored fingerprint is recomputed in the background. Intended (documented in `__version__.py`), and it also means the outdated-fingerprint queue path fixed in #6334 is now the one every library exercises.

## 3. Findings

| Severity | Count |
|---|---|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 2 |
| LOW | 4 |

### I-01: Whole-track analysis behind a starvable gate runs inside the 30 s stream-init timeout
- **Severity**: MEDIUM
- **Changed File**: `auralis/analysis/fingerprint/analysis_budget.py` (commit: `3252f2f17`), `auralis-web/backend/core/chunk_processor_init.py` (commit: `0171dc6bb`)
- **Status**: NEW
- **Description**: `0171dc6bb` makes `init_fingerprint_and_processor` extract a missing fingerprint (`extract_if_missing=True`) while the processor is constructed. Construction runs under `asyncio.wait_for(asyncio.to_thread(...), timeout=CHUNK_PROCESS_TIMEOUT)` (30 s, `stream_enhanced.py:145`). The extraction goes through `analysis_budget.reserve(minutes)` (`windowed_compute.py`), a process-wide gate of 40 minutes of audio shared with the background fingerprint queue. `AnalysisBudget.reserve` admits any waiter that fits (`wait_for(lambda: in_flight == 0 or in_flight + minutes <= capacity)`) with no queueing, so while many small jobs keep the gate near full, a long job never fits. Nothing in the extraction or the wait takes the stream's `cancel_event`.
- **Evidence**: probe against the real class, each worker looping on ~4 min jobs (job time scaled to 50 ms), one probe job after the pool saturated:
  ```
   4 workers, probe  4 min -> admitted after 0.00s
  12 workers, probe  4 min -> admitted after 0.01s
  12 workers, probe 12 min -> NOT admitted within 20 s
  24 workers, probe 12 min -> NOT admitted within 20 s
  24 workers, probe 15 min -> NOT admitted within 20 s
  ```
  At the real ~0.8 s of analysis per minute of audio (a 4.25 min track took 3.4 s) the 20 s window is hundreds of job lifetimes. The queue's default is `max(4, cpu*0.5)` workers, scaling up to `2*cpu`. The starvation is reproduced on the real class; the timeout error and the abandoned, stacking threads follow from `wait_for` over `to_thread` (which does not cancel the worker thread) and were not reproduced end to end through the streaming path.
- **Impact**: while a library scan keeps the fingerprint queue saturated (exactly when new tracks have no fingerprint), playing an unfingerprinted track of roughly 10+ minutes cannot start: the request ends with "Audio processor initialization timed out" after 30 s. The `to_thread` worker is not cancelled by `wait_for`, so it keeps waiting, then runs the whole analysis for nobody, and each retry stacks another waiting thread. Short tracks and an idle queue are unaffected. The same starvation delays the long track's own queue worker.
- **Suggested Fix**: make the gate fair (a FIFO ticket so an earlier large waiter blocks later small ones) and give the interactive path priority or a bounded wait; pass `cancel_event` into the extraction and the budget wait; keep the 30 s timeout from also covering analysis (extract after construction, or raise the timeout for that step).

### I-02: The level plan derives the track peak from a mono mix, so wide masters get more boost than the headroom allows
- **Severity**: MEDIUM
- **Changed File**: `auralis-web/backend/core/mastering_target_generation.py` (commits: `8b004ae40`, `aca64af3a`)
- **Status**: NEW
- **Description**: `plan_level` recovers the peak as `lufs + 0.691 + crest_db` and caps a boost at the headroom to `SAFE_CEILING_DB`. The Rust engine computes both `lufs` and `crest_db` on `mono_audio = (L+R)/2` (`fingerprint_compute.rs:218-236`), but the renderer's limiter acts on the per-channel sample peak. For decorrelated or hard-panned material the mono-mix peak is lower than the channel peak, so the plan believes there is headroom that does not exist.
- **Evidence**: through the real fingerprint and `plan_level`:
  ```
  salida.mp3      plan peak -0.76 dBFS vs true channel peak -1.14 (conservative by 0.39 dB) | planned +0.96 dB, free headroom 0.84 dB -> 0.11 dB excess
  wide synthetic  plan peak -4.36 dBFS vs true channel peak -0.92 (under-reads by 3.44 dB)  | planned +3.13 dB, free headroom 0.62 dB -> 2.51 dB excess
  ```
- **Impact**: the situation the plan was written to prevent ("a +4.8 dB boost cost a 21 dB-crest master 4 dB of crest") returns for wide stereo masters: up to ~2.5 dB of the planned boost is paid for by the limiter in crest. Typical correlated material is barely affected, so the error is content-dependent. `test_target_level_plan_headroom.py` only uses inputs where the mono peak equals the channel peak.
- **Suggested Fix**: have the analyzer report the per-channel sample peak (as metadata, not a new schema dimension), or make the headroom term conservative using the fingerprint's `stereo_width` / `phase_correlation`; add a decorrelated-channel case to the headroom test.

### I-03: The analysis memory gate sits after the buffer is loaded and cannot be interrupted
- **Severity**: LOW
- **Changed File**: `auralis/analysis/fingerprint/windowed_compute.py` (commit: `3252f2f17`)
- **Status**: NEW
- **Description**: `analysis_budget.py` says the gate "bounds the analyzer at about 3.4 GB however many workers there are", but `compute_windowed_fingerprint` calls `load_track_audio(...)` first and only then `with analysis_budget.reserve(...)`: the whole decoded track (up to 900 s × 22.05 kHz × 2 ch × 4 B ≈ 159 MB) is resident per worker before it is admitted. `reserve` also has no timeout and no stop awareness, so a worker waiting on it cannot honour `FingerprintExtractionQueue.should_stop`; `_stop_blocking` joins with a timeout and logs "did not stop within timeout".
- **Evidence**: code order in `windowed_compute.py:118-123`; `AnalysisBudget.reserve` (`wait_for` with no timeout argument).
- **Impact**: peak memory is the gate (~3.4 GB) plus one input buffer per waiting worker (dozens of workers × tens to ~160 MB), more than the documented bound; shutdown can be delayed behind a wait. Typical 4 min tracks (≈42 MB) keep this modest.
- **Suggested Fix**: reserve before loading (the duration is known from `probe_duration_s`), and give `reserve` a `should_stop` predicate or timeout.

### I-04: `profile_audio` raises on digital silence, and `SAFE_CEILING_DBFS` copies an engine constant
- **Severity**: LOW
- **Changed File**: `auralis/analysis/reference_profile.py` (commits: `aa0749709`, `8b004ae40`)
- **Status**: NEW
- **Description**: `_bands` divides each band by `total`, which is 0.0 for silence; `max(x, 1e-20) / total` raises `ZeroDivisionError` when `max` returns the Python float. Separately, `SAFE_CEILING_DBFS = -0.3` repeats `continuous_dsp_ops.SAFE_CEILING_DB` ("The renderer's true-peak safety ceiling") instead of importing it, so a change to the renderer's ceiling silently diverges from the bench's "forced by ceiling" allowance.
- **Evidence**: `profile_audio(np.zeros((192000, 2), dtype=np.float32), 48000)` → `ZeroDivisionError: division by zero`.
- **Impact**: the bench aborts on a silent or all-zero render instead of reporting it; ceiling drift would make `near_identity_violations` pass or fail wrongly. Dev tool only, not on the app path.
- **Suggested Fix**: guard `total <= 0` (return silence floors), import `SAFE_CEILING_DB`.

### I-05: Docstrings still describe the 90 s window
- **Severity**: LOW
- **Changed File**: `auralis/analysis/fingerprint/windowed_compute.py` (commit: `3252f2f17`); stale text in `auralis-web/backend/core/fingerprint_loading.py:178-182` and `auralis/analysis/fingerprint/windowed_loading.py` (`_decode_window`)
- **Status**: NEW
- **Description**: `extract_from_audio` still documents "bounded 90s-body + 2x30s-probe decoding, #4595 LUFS/crest bias correction"; under v13 a track up to 900 s is analysed whole with no probes. `_decode_window`'s docstring argues for "no FINGERPRINT_ALGORITHM_VERSION bump", while the version is now 14. `tests/auralis/analysis/test_fingerprint_schema_units.py` also repeats one assertion line (`low_shelf_gain !=`) twice after the edit.
- **Evidence**: `fingerprint_loading.py:178-182` reads "bounded 90s-body + 2x30s-probe decoding, #4595 LUFS/crest bias correction, and non-finite sanitization", and a second copy of the same wording sits in a comment at `:194`; `FINGERPRINT_FULL_TRACK_MAX_S = 900.0` in `windows.py` makes every track up to 900 s whole-track with `probes == []`, so `_apply_probe_correction` returns early for them.
- **Impact**: misleads the next reader about what a fingerprint measures.
- **Suggested Fix**: update the three docstrings; drop the duplicate assertion.

### I-06: The two whole-input band analyses handle the final partial frame differently
- **Severity**: LOW
- **Changed File**: `vendor/auralis-dsp/src/frequency_analysis.rs`, `vendor/auralis-dsp/src/fingerprint_compute.rs` (commit: `956222e7a`)
- **Status**: NEW
- **Description**: `compute_frequency_distribution` drops a trailing frame shorter than half the FFT size (`if index > 0 && frame.len() < fft_size / 2 { break; }`, up to ~1.5 s at 22.05 kHz), while `compute_bass_mid_ratio` keeps every tail frame. The new comment in `compute_bass_mid_ratio` states the dimensions of one fingerprint "must not have inconsistent scopes". The frames are also non-overlapping Hann windows, so samples near a frame edge (every ~3 s) count for almost nothing. The dead `let _ = frame_count;` was left in place.
- **Evidence**: code at `frequency_analysis.rs` (frame loop) and `fingerprint_compute.rs:150-170`. Energy is summed, not averaged per frame, so the effect is bounded by the dropped tail's share of the energy; it is not the #6322-class blow-up.
- **Impact**: a small, bounded difference between `bass_pct` and `bass_mid_ratio` scope for the same track, and a periodic weighting of the analysed signal. Low.
- **Suggested Fix**: share one frame iterator between the two functions (same tail rule), consider 50% overlap, remove the dead variable.

## 4. Cross-Layer Impact

- **Engine → backend (fixed targets)**: `convert_targets_to_parameters` now reads `eq_curve_db`, and a missing key means a flat EQ without error. No producer of the old `eq_adjustments_db` remains in the repo (checked with grep; only two old audit reports mention it), and any cached targets carry the new fingerprint version, so no stale shape reaches the converter.
- **Backend cache**: see §2: invalidated by the targets hash, so the on-disk chunk cache needs no version bump for this change. (`CACHE_VERSION` is unchanged at 5; a DSP change that does not alter the targets would still not invalidate it.)
- **Fingerprint queue ↔ stream**: both can now extract the same never-fingerprinted track. The repository read path excludes claim placeholders (`fingerprint_shared.py`), so a worker's placeholder row is not served as a fingerprint.
- **Database schema**: v31 is a data-only step with its migration file, README line and `__db_schema_version__` bump (previous session).
- **Frontend**: no frontend or REST/WebSocket contract file changed in the range.

## 5. Missing Tests

- `AnalysisBudget`: admit, wait and oversize cases are covered (`test_whole_track_analysis_v13.py::TestAnalysisBudget`); there is no fairness or starvation test (I-01).
- `plan_level`: no decorrelated or hard-panned case, so the mono-peak assumption in I-02 is untested.
- `chunk_processor_init` with `extract_if_missing=True`: covered for the happy path (`test_chunk_init_extracts_missing_fingerprint.py`); nothing exercises a slow or blocked extraction against `CHUNK_PROCESS_TIMEOUT`.
- `reference_profile.profile_audio`: no silent-input case (I-04).
- `join_segments`: the joined whole-track decode is covered; a probed duration that is wrong in either direction (a header-less VBR MP3, where ffprobe's estimate is off) has no test. I ran one such file (ffprobe 38.3 s for a nominal 40 s) and the loader returned 38.3 s without error, so I did not file it.

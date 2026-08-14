# Audio Engine Audit — 2026-08-13

**Scope**: Auralis core audio engine — `auralis/core/`, `auralis/dsp/`, `auralis/player/`,
`auralis/io/`, `auralis/analysis/`, `auralis/library/`, `auralis/services/`, `vendor/auralis-dsp/`
**Commit audited**: `622dba22` (fresh read of the tree at HEAD; no prior report reused)
**Depth**: deep (full call-graph tracing) — all 7 dimensions, no `--focus` / `--limit`
**Dedup baseline**: 3,000 GitHub issues (open **and** closed), `gh issue list --state all`
**Out of scope**: React frontend, FastAPI backend routing/WebSocket layer, Electron desktop
(covered by the backend/frontend/integration audits already completed in this suite)

---

## Executive Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 3 |
| MEDIUM | 6 |
| LOW | 6 |
| **Total** | **15** |

Plus 2 non-findings retained deliberately: one re-examined closed issue (§ Re-examined) and one
negative-result verification of today's artist-query refactor (§ Verification Notes).

**No CRITICAL findings.** The engine's core audio-integrity invariants hold: every public
`HybridProcessor` entry point asserts shape preservation and runs finite-validation at both
boundaries; all 13 named stages in `auralis/core/stages/` route their bypass paths through the
shared `no_op()` copy helper; the chunked mastering loop carries explicit sample-count assertions
on both sides of crossfade reassembly. Nothing in this audit found a sample-count mismatch, an
in-place mutation of a caller-owned array, or DB corruption.

**The three HIGH findings share one shape: a hardening fix that was applied to some siblings but
not all of them.** Each is a known bug class the project has already fixed at least once
elsewhere, sitting unfixed at a call site the original fix never reached:

1. **ENG-D6-01** — NaN/Inf sanitization existed in the fingerprint analyzer (#2531) and was
   deleted, not ported, during the Rust-engine migration (`871356f7`). NaN now reaches the
   `track_fingerprints` table unchecked. Verified as a genuine **regression**.
2. **ENG-D4-01** — the byte-budget OOM guard from #4875 reached three of the four decode paths;
   the one it missed (`auralis/io/loader.py::load`) is the actual playback/gapless loader.
3. **ENG-D3-01** — the "no blocking I/O under `_audio_lock`" fix from #3656 reached
   `add_to_queue()` but not the gapless-advance fallback in the same subsystem.

**Themes across the MEDIUM band**: residual hard thresholds inside the continuous-parameter space
(ENG-D2-01, echoing open #4938), dtype-promotion call sites that missed the `float()` wrap the rest
of the codebase applies (ENG-D1-01), and one repository that never migrated to the aggregate-count
pattern its three siblings now use (ENG-D7-01).

**Most impactful single fix**: ENG-D6-01. It is the only finding that writes bad data to durable
storage, it is the only confirmed regression, and its blast radius extends past the engine into
similarity search and automatic mastering-target selection.

---

## HIGH

### ENG-D6-01: NaN/Inf from the Rust fingerprint engine is never validated before reaching storage
- **Severity**: HIGH
- **Dimension**: Analysis
- **Location**: `vendor/auralis-dsp/src/dsp_math.rs:11-40`, `auralis/analysis/fingerprint/windowed_compute.py:79-295`, `auralis/services/fingerprint_extractor.py:239-260`, `auralis/library/repositories/fingerprint_repository.py:623-679`
- **Status**: **Regression of #2531** (closed)
- **Description**: A single `NaN` sample in decoded audio (corrupt/truncated encode, malformed
  container, upstream decoder bug) propagates into stored fingerprint dimensions with no guard
  anywhere in the write path. `compute_rms()` sums squares with no NaN filtering, and the only
  guard in `estimate_lufs()` / `compute_crest_factor()` is `if rms < 1e-10` — but `NaN < 1e-10` is
  `false` in IEEE-754, so the silence early-return does not catch NaN, and `.clamp(-120.0, 0.0)` is
  a no-op on NaN. The Python glue does no `isfinite` check; `_prepare_for_storage()` validates
  dimension **count** only; `upsert()` validates column **names** only, then writes the floats to
  SQLite.
- **Evidence**: Verified at HEAD. `vendor/auralis-dsp/src/dsp_math.rs:11-40` is exactly as
  described. A repo-wide grep for `isfinite`/`isnan` across `auralis/analysis/fingerprint/`,
  `auralis/services/fingerprint_extractor.py` and
  `auralis/library/repositories/fingerprint_repository.py` returns only two hits, neither on the
  write path: `metrics/variation_metrics.py:45` (an internal mask) and `catalog.py:134` (a `store()`
  method with no callers outside its own module). The deleted sanitization is recoverable from
  history — `git show 3702c6d4:auralis/analysis/fingerprint/audio_fingerprint_analyzer.py:291-296`
  carries the comment *"Sanitize NaN/Inf values (replace with 0.0) ... (fixes #2531)"*; the commit
  that removed it is `871356f7` ("route fingerprinting through in-process Rust engine"), which
  replaced the analyzer wholesale without porting the guard.
- **Impact**: One corrupt source file permanently poisons that track's `track_fingerprints` row —
  nothing re-validates existing rows, so it survives indefinitely. `analysis/fingerprint/distance.py`
  has no finite guard either, so a NaN fingerprint corrupts Euclidean similarity, kNN neighbour
  lists, and reference selection for that track, and propagates into automatic mastering-target
  selection. The read-time `_band_pct_valid()` check only inspects the 7 band percentages, so a NaN
  `lufs` reads back as "valid" forever.
- **Siblings**: The same missing-guard gap exists independently at each layer:
  `rust_fingerprint.py` (schema mapping), `windowed_compute.py` (windowing),
  `fingerprint_extractor.py::_prepare_for_storage` (count-only), `fingerprint_repository.py::upsert`
  (name-only), and `analysis/fingerprint/distance.py` (consumer).
- **Related**: #4910 added value validation for the sidecar `.25d` **read** path only — it does not
  run at DB write time. #4123 (Rust LUFS is an RMS approximation) is a separate, deferred concern.
- **Suggested Fix**: Add one `isfinite` validation at the single choke point every fingerprint
  passes through before persistence — either in `windowed_compute.py::compute_windowed_fingerprint()`
  (return `None` on any non-finite dimension, matching its existing incompleteness check) or in
  `_prepare_for_storage()` alongside the dimension-count check. Reinstating #2531's
  replace-with-0.0-and-warn behaviour is the lower-risk option.

### ENG-D4-01: Playback loader skips the byte-budget OOM guard its three sibling loaders enforce
- **Severity**: HIGH
- **Dimension**: Audio I/O
- **Location**: `auralis/io/loader.py:104-146` (the `else` branch, 133-146)
- **Status**: NEW (a fourth call site the #4875 fix never touched — not a regression)
- **Description**: `auralis/io/loader.py` **defines** `MAX_DECODED_BYTES` /
  `oversize_decode_detail()` / `estimated_decoded_bytes()`, added by #4875 precisely because a
  duration-only cap "assumes a fixed 96 kHz/stereo profile" and admits high-sample-rate or
  multichannel files that blow the RAM budget while under the duration cap. The fix was applied to
  `auralis/io/loaders/soundfile_loader.py`, `auralis/io/loaders/ffmpeg_loader.py`, and
  `auralis/io/unified_loader.py` — but not to `load()` in the very file that defines the helper.
  Its soundfile branch checks `file_info.duration > MAX_DURATION_SECONDS` and then calls `sf.read()`
  directly, despite `file_info` already carrying `samplerate` and `channels` for free.
- **Evidence**: Confirmed at HEAD — `auralis/io/loader.py:133-146` contains only the duration
  check before `sf.read(...)`, while `auralis/io/loaders/soundfile_loader.py:79-86` performs the
  byte-budget check on the same shape of input. This is the *playback* loader, not a rarely-reached
  helper: `grep` confirms `auralis/player/audio_file_manager.py:17` and
  `auralis/player/gapless_playback_engine.py:17` both import `load` directly from
  `auralis.io.loader`, bypassing `unified_loader.load_audio` (which does carry the fix).
  Concretely, a 192 kHz stereo WAV at ~55 min is `3300 × 192000 × 2 × 4 ≈ 5.1 GiB` decoded — well
  under the 7200 s duration cap, well over the 6 GiB byte budget — and is accepted here while being
  rejected by every other decode path.
- **Impact**: Playing or gapless-preloading a legitimately-shaped high-resolution WAV/FLAC/AIFF can
  attempt a multi-GB contiguous allocation on the playback thread. Best case `MemoryError` (caught
  and reported as a load failure); worst case, under Linux memory overcommit, the OOM killer
  SIGKILLs the desktop app before Python sees an exception.
- **Siblings**: None outstanding — the other three decode paths already carry the guard.
- **Suggested Fix**: Call
  `oversize_decode_detail(file_info.duration, file_info.samplerate, file_info.channels)` before
  `sf.read()` in `load()`'s soundfile branch — the helper is already imported at module scope in
  that same file — and raise the same error shape the function already uses.

### ENG-D3-01: Gapless fallback runs blocking disk I/O while `_audio_lock` is held, stalling the real-time audio callback
- **Severity**: HIGH
- **Dimension**: Player State
- **Location**: `auralis/player/gapless_playback_engine.py:296-336` and `:352-389` (both fallback
  branches of `advance_with_prebuffer`), reached via `auralis/player/enhanced_audio_player.py:344-362`
- **Status**: NEW (a sibling location #3656's fix never reached)
- **Description**: `next_track()` wraps the whole gapless advance in
  `with self.playback.defer_notifications(), self.file_manager._audio_lock:` so the fast,
  memory-only prebuffer swap is atomic with `get_audio_chunk()`'s read (#3717). But when the
  prebuffer is *not* usable — short tracks, cold cache, `prebuffer_enabled=False`, or an
  `invalidate_prebuffer()` just fired by a shuffle/repeat toggle or queue mutation —
  `advance_with_prebuffer()` falls back to `file_manager.load_file()`, a genuinely blocking disk
  read with no timeout. Because `_audio_lock` is an `RLock` already held by the calling thread, that
  read executes inside the critical section.
- **Evidence**: Verified at HEAD. `enhanced_audio_player.py:344` opens the combined
  `defer_notifications()` + `_audio_lock` scope and calls `advance_with_prebuffer(was_playing)`
  inside it; `gapless_playback_engine.py:322` and `:372` both call
  `self.file_manager.load_file(...)` on their fallback branches within that still-held outer lock.
  Contrast the already-fixed sibling at `enhanced_audio_player.py:449-461`, where #3656 deliberately
  hoists the I/O outside the lock via a `needs_load` flag.
- **Impact**: The real-time playback thread's `get_audio_chunk()` needs the same `_audio_lock` on
  every buffer tick and blocks for the full read (tens to hundreds of ms), starving the audio
  backend and producing an audible glitch/underrun — the exact failure the gapless engine exists to
  prevent. `seek()` and `cleanup()` also take `_audio_lock`, so a stop or seek issued during the
  window waits out the load too.
- **Siblings**: Two occurrences in the same function. `add_to_queue`, `load_file`,
  `previous_track`, and `load_track_from_library` were all checked and correctly perform their I/O
  outside any lock.
- **Related**: #3656 (closed, fix verified present at its own site); #3735 (closed — it moved
  callback dispatch out of the lock but never touched the I/O inside `advance_with_prebuffer()`,
  which is why this is NEW rather than a regression).
- **Suggested Fix**: Narrow `next_track()`'s `_audio_lock` scope to the prebuffer-hit path only,
  and have `advance_with_prebuffer()` signal "no prebuffer available" back to the caller so the
  fallback `load_file()` runs outside the lock, re-acquiring only for the final atomic swap —
  mirroring the #3656 pattern already used in the same file.

---

## MEDIUM

### ENG-D1-01: Unwrapped `np.clip()` scalar silently promotes audio to float64 in two live call paths
- **Severity**: MEDIUM
- **Dimension**: Sample Integrity
- **Location**: `auralis/core/processors/reference_mode.py:37-44`, `auralis/core/processing/eq_processor.py:301-307`
- **Status**: NEW
- **Description**: `np.clip(python_float, lo, hi)` returns a `numpy.float64` scalar, not a Python
  float. Under NEP 50 that is a *strong* dtype, so multiplying a float32 array by it promotes the
  entire result to float64. Every other scalar-clip-into-audio site in `auralis/core/` and
  `auralis/dsp/` wraps the result in `float(...)`; these two are the only exceptions.
- **Evidence**: Reproduced against the pinned NumPy 2.4.6 —
  `type(np.clip(2.5/1.3, 0.1, 10.0))` is `numpy.float64`, and `(np.ones(5, np.float32) * it).dtype`
  is `float64`. `reference_mode.py` does `gain_factor = np.clip(gain_factor, 0.1, 10.0)` then
  `matched_audio = target_audio * gain_factor`. Guarded siblings for contrast:
  `auralis/core/stages/harmonic_exciter.py:55-56`, `auralis/core/stages/bass_enhancement.py:59`,
  `auralis/dsp/utils/adaptive.py:41,48`.
- **Impact**: `apply_reference_matching()` is the live reference-mode path and fires whenever
  `target_rms > 0` — effectively always. The promotion propagates through the rest of that chain
  (`brick_wall_limiter.process()` preserves whatever dtype it is given), doubling memory and CPU for
  every downstream array. It does not violate the project's `dtype in [float32, float64]` invariant
  and is not audible, which is why it is MEDIUM rather than HIGH.
- **Siblings**: None — a full sweep of `np.clip()` scalar-multiply sites under `auralis/core/` and
  `auralis/dsp/` found these two as the sole unguarded cases.
- **Related**: #4972 (open) covers a *different* bug in the same function
  (`_apply_simple_eq_fallback` applies a broadband gain rather than real EQ). This finding is about
  dtype, not DSP behaviour. Historical instances of this same promotion class: #2158, #2450, #3468,
  #3659, #3687, #4105, #4107, #4934/#4225 (all closed).
- **Suggested Fix**: Wrap both results in `float(...)` at the point of computation, matching every
  other scalar-clip site in the codebase.

### ENG-D1-02: Two limiter bypass paths hand back the caller's array without copying, breaking the `no_op()` contract
- **Severity**: MEDIUM (latent — currently mitigated by callers)
- **Dimension**: Sample Integrity
- **Location**: `auralis/core/processing/base/peak_management.py:46-57`, `auralis/core/processing/hf_aware_limiter.py:76-78`
- **Status**: NEW
- **Description**: `auralis/core/stages/__init__.py` defines `no_op(audio) -> (audio.copy(), None)`
  specifically so every early-return bypass "never hands back the caller's array", and all 13 named
  stages honour it. `SafetyLimiter.apply_if_needed()` and `apply_hf_aware_limiter()` implement the
  same maybe-process pattern one package over, but their bypass branches `return audio, False` — the
  literal input object.
- **Evidence**: Both functions return the parameter unchanged on their "nothing to do" branch, with
  no `.copy()`.
- **Impact**: Traced both current call sites (`auralis/core/processing/adaptive_mode.py:329`,
  `auralis/core/processing/continuous_mode.py:748`) back to entry points that begin with
  `processed_audio = target_audio.copy()`, with only allocating (non-aliasing) stages in between —
  so no caller-owned buffer is exposed today. This is a latent hazard: any future direct caller, or
  a refactor that moves these earlier in the chain, silently gets a caller-owned array back.
- **Siblings**: `auralis/core/mastering_process_chunk.py:57-66` (`reduce_peaks`) has the identical
  shape and is mitigated the same way — its only caller passes an already-copied array.
- **Suggested Fix**: Return `audio.copy()` on both bypass branches, matching `stages.no_op()`.
  Cheap, since these are the do-nothing branches.

### ENG-D2-01: Stereo-width expansion retains a hard peak-threshold skip inside the continuous-space path
- **Severity**: MEDIUM
- **Dimension**: DSP Pipeline
- **Location**: `auralis/core/processing/continuous_mode.py:636-668` (guard at line 662)
- **Status**: NEW
- **Description**: `ContinuousMode._apply_stereo_width` — the live default path
  (`use_continuous_space = True` per `auralis/core/config/unified_config.py:154`) — gates the entire
  widening operation on `if pre_peak_db > -2.0 and target_width > WIDTH_FACTOR_UNITY: return audio`.
  The three analogous cross-dimensional guard corrections in the same file (EQ→LUFS drift,
  dynamics→spectral tilt, stereo→phase correlation) were all deliberately rewritten to use
  `cross_dimensional_guard.smooth_gate()` to eliminate exactly this bug class (#4860 — the code
  comments describe it as "reintroducing exactly the categorical on/off step the continuous-space
  architecture replaced"). This fourth guard, a few lines below the phase-drop branch in the same
  method, was never migrated.
- **Evidence**: `continuous_mode.py:661-663` is a bare boolean skip with a debug log
  (`"[Stereo Width] SKIPPED expansion due to high peak"`) and an unconditional `return audio`.
- **Impact**: Two masters differing by 0.01 dB of pre-widening peak level, straddling -2.0 dBFS
  (a common region given the pipeline's own -0.3 dBFS ceiling), receive either full
  `adjust_stereo_width_multiband()` treatment or none — an audible stereo-image difference from an
  inaudible input difference, violating the documented continuous-space invariant.
- **Siblings**: `auralis/core/processing/adaptive_mode.py:219-221` has a structurally similar hard
  clamp, but that file is the explicitly-legacy preset path reached only when
  `use_continuous_space` is `False`, so it is not held to the same invariant — noted, not included
  in scope.
- **Related**: #4938 (open) tracks the same bug class at `auralis/core/processing/delta_eq.py`'s
  `_EMPTY_BAND_THRESHOLD`, confirmed still present at HEAD (`delta_eq.py:110-112`). Independent
  instance, not a duplicate.
- **Suggested Fix**: Replace the hard skip with a `smooth_gate()`-scaled `target_width` ramping
  toward `WIDTH_FACTOR_UNITY` across a knee (e.g. `[-3.0, -2.0]` dB), matching the pattern already
  used three times in the same file.

### ENG-D5-01: A chunk raising mid-track leaves a truncated-but-valid WAV masquerading as a complete master
- **Severity**: MEDIUM
- **Dimension**: Chunked Mastering
- **Location**: `auralis/core/mastering_chunk_loop.py:63-70`; callers `auralis/core/auto_master.py:41-46`, `:100-116`, `:157-186`
- **Status**: NEW
- **Description**: `process_chunks` opens the output `sf.SoundFile` sink once and writes
  incrementally inside a plain `while` loop with no per-chunk `try/except` and no output cleanup on
  error. If any chunk raises — `validate_audio_finite(..., repair=False)` in
  `auralis/core/mastering_process_chunk.py:87`, the `_assert_finite` checks in
  `auralis/core/mastering_branches/continuous.py`, or any DSP stage — the exception propagates, but
  the `with` block's `__exit__` still finalizes a syntactically valid WAV header for whatever was
  written. Neither `master_single_file` nor `master_folder` deletes or renames the partial file.
- **Evidence**: Empirically confirmed that `sf.SoundFile` finalizes a fully readable file on
  exception-driven unwind (write 1000 frames, raise inside the `with`, then `sf.read()` succeeds
  with 1000 frames). `master_folder`'s per-file `except` appends to `failed_files` and moves on —
  `output_file` is never removed.
- **Impact**: In batch mode the failure *is* reported in the console summary, but the truncated
  file sits in the output folder under the exact expected name, indistinguishable from its
  successful neighbours. A user who automates the pipeline or skips the summary ships an incomplete
  master. In single-file mode the truncated file lands at the exact path requested.
- **Siblings**: Both CLI callers share the pattern.
- **Related**: ENG-D5-02 is a concrete (if narrow) way to trigger the raise.
- **Suggested Fix**: Write to a temp path and rename into place only after `chunks_processed`
  reaches `total_chunks`, or delete the partial output on any exception escaping the loop.

### ENG-D6-02: FFmpeg-routed fingerprint windowing decodes and resamples the whole file for a 150 s window
- **Severity**: MEDIUM
- **Dimension**: Analysis
- **Location**: `auralis/analysis/fingerprint/windowed_compute.py:126-158`
- **Status**: NEW
- **Description**: `compute_windowed_fingerprint()` needs a 90 s body window plus two 30 s probes.
  The libsndfile-native branch achieves that efficiently (`librosa.load(..., offset, duration)`
  seeks and decodes only the window), and the pre-loaded branch crops *before* resampling with an
  explicit docstring about avoiding full-duration allocation. The FFmpeg branch (`.mp3`, `.m4a`,
  `.aac`, `.ogg`, `.wma`, `.opus`) does the opposite: `load_with_ffmpeg()` decodes the entire file
  (bounded only by the 7200 s cap), `librosa.resample()` runs over the entire buffer, and only then
  is the 150 s crop applied.
- **Evidence**: `windowed_compute.py:127-158` — the crop (`raw_audio[..., _body_start:_body_end]`)
  happens after both the full decode and the full-buffer resample. This contradicts
  `auralis/services/fingerprint_extractor.py:218-221`'s own comment claiming the function "never
  materialises the whole decoded file", which is true only for the non-FFmpeg branch.
- **Impact**: Every MP3/AAC/OGG/M4A/WMA/OPUS track fingerprinted pays full-file decode plus
  full-buffer resample instead of the intended bounded cost — up to ~50× the necessary CPU for a
  2-hour file, with a peak footprint in the GB range per in-flight file. `FingerprintExtractionQueue`
  runs this concurrently across a semaphore sized `max(8, max_workers)`, so a podcast/audiobook
  library scan multiplies it. Bounded (2 h cap, 300 MB size cap, 600 s per-track timeout), so this
  is waste rather than a crash risk.
- **Related**: #4737 (closed) rated the same "full decode when only a window is needed" pattern HIGH
  when it hit the interactive path; here it is a background batch cost, hence MEDIUM.
- **Suggested Fix**: Add optional `offset`/`duration` passthrough to `load_with_ffmpeg()` mapping to
  `ffmpeg -ss`/`-t`, and decode only the body+probe span.

### ENG-D7-01: `GenreRepository` list reads hydrate every Track row to compute a count
- **Severity**: MEDIUM (capped from HIGH — see Impact)
- **Dimension**: Library & Database
- **Location**: `auralis/library/repositories/genre_repository.py:27,75-113,275-312`
- **Status**: NEW
- **Description**: `_GENRE_LOAD_OPTIONS = (selectinload(Genre.tracks),)` is used by both
  `get_all()` and `search()` — the paginated list paths — solely so `Genre.to_dict()` can compute
  `len(_safe_collection(self, 'tracks'))` (`auralis/library/models/core.py:433`). `ArtistRepository`
  (#5084, today), `AlbumRepository` (#4777), and `PlaylistRepository` (#4554) all moved to a
  correlated `COUNT` subquery via `with_expression()`, touching zero `Track` rows.
  `GenreRepository` was fixed for *correctness* by #4641 (the eager-load stopped a
  `DetachedInstanceError`) but never migrated to the cheaper pattern its siblings later adopted.
- **Evidence**: Compare `genre_repository.py`'s `selectinload(Genre.tracks)` against
  `auralis/library/repositories/artist_repository.py:117-120`, which uses
  `with_expression(Artist.track_count_expr, _track_count_subquery())` and does not load
  `Artist.tracks` at all.
- **Impact**: Each genre on a list page would pull every `Track` row it owns — including unbounded
  `lyrics`/`fingerprint_vector` text columns — with cost scaling by tracks-per-genre rather than
  page size. **Capped to MEDIUM** because no backend router currently calls these methods (no
  genre-list endpoint is wired), so today's blast radius is nil; this becomes a live HIGH the moment
  a genre-browsing endpoint ships.
- **Siblings**: None outstanding — Genre is the last repository with a `to_dict()` count field that
  never got migrated.
- **Suggested Fix**: Add a `with_expression()` correlated `COUNT` over `track_genre` mirroring
  `ArtistRepository._track_count_subquery()`, and drop `Genre.tracks` from the list-path options
  (keep it on `get_by_id`/`get_by_name`, which legitimately need the collection).

---

## LOW

### ENG-D2-02: `UnifiedConfig` defines 9 parameters the live reference-mode processor never reads
- **Severity**: LOW
- **Dimension**: DSP Pipeline
- **Location**: `auralis/core/config/unified_config.py:29-49`; consumer `auralis/core/processors/reference_mode.py:17-53`
- **Status**: NEW
- **Description**: `UnifiedConfig.__init__` accepts, asserts on, and stores 9 parameters carried
  over "from original Matchering" — `threshold`, `min_value`, `max_piece_size`,
  `lin_log_oversampling`, `rms_correction_steps`, `clipping_samples_threshold`,
  `limited_samples_threshold`, `allow_equality`, `lowess_frac`/`lowess_it`/`lowess_delta`,
  `preview_analysis_step` — none of which are read anywhere outside `unified_config.py` itself. The
  live reference-mode processor is a ~35-line RMS gain match that takes no config object at all. The
  algorithm that would consume these lives only in `auralis/dsp/stages.py`, documented as a
  standalone CLI, not part of the runtime pipeline.
- **Evidence**: `reference_mode.py:31-44` is the entire live algorithm: `rms()` of both signals, a
  clipped gain ratio, one multiply. No config parameter is consulted.
- **Impact**: No crash, but tuning any of these on `UnifiedConfig` silently has zero effect on
  audio output — a plausible source of "I changed the setting and nothing happened".
- **Siblings**: None — `fft_size`, `internal_sample_rate`, `processing_sample_rate`, `preview_*`,
  and the `adaptive`/`limiter`/`genre_profiles` sub-configs are all genuinely read downstream.
- **Suggested Fix**: Either remove the dead parameters and document reference mode as a deliberate
  simplified RMS match, or route reference mode through the real algorithm.

### ENG-D2-03: Soft k-NN target derivation has a hard top-k neighbour cutoff
- **Severity**: LOW
- **Dimension**: DSP Pipeline
- **Location**: `auralis/core/processing/target_derivation.py:152-165`
- **Status**: NEW
- **Description**: `derive_target()` sorts references by z-scored distance and takes a hard
  `distances[:k]` slice (k=10) before softmax weighting. The softmax makes the target smooth
  *within* the selected k, but which k participate is a rank cutoff: two sources differing
  infinitesimally in distance can land on opposite sides of the 10th/11th boundary, so one reference
  goes from a nonzero weight to exactly zero.
- **Impact**: Bounded in practice — `tau` is the mean distance of the selected neighbours, so a
  boundary reference already carries small weight, and in a dense cloud the k-th and (k+1)-th
  references are similar in target-feature space. Flagged for completeness under the
  "no discrete steps in continuous space" check, not because an audible artifact is known.
- **Siblings**: None — the only top-k selection in the continuous-space pipeline.
- **Suggested Fix**: If it ever proves audible, softmax over the whole cloud and let `tau` decay far
  neighbours to ~0, removing the rank boundary at O(n) instead of O(k) cost.

### ENG-D3-02: Raw `AudioPlayer.position` can transiently exceed track length at end-of-track
- **Severity**: LOW
- **Dimension**: Player State
- **Location**: `auralis/player/playback_controller.py:201-216`, `auralis/player/enhanced_audio_player.py:488-547`, `:670-673`
- **Status**: NEW
- **Description**: `read_and_advance_position()` advances `position` by the full `chunk_size` with
  no clamp to `total_samples`. When the last chunk is short (or exactly reaches the end), `position`
  sits at `>= total_samples` until the asynchronous auto-advance calls `seek(0, ...)`, violating the
  documented `position ≤ duration` invariant for that window. ENG-D3-01 can lengthen the window.
- **Impact**: Low — the one real external consumer,
  `IntegrationManager._get_position_seconds()` (behind `get_playback_info()`), clamps independently,
  and no backend code reads the raw property. Limited to future direct consumers.
- **Siblings**: None — `seek()`, `load_and_stop()`, and `stop()` all clamp or reset correctly.
- **Related**: #4141 (closed) fixed the `position` *setter*; this is the unclamped *increment*.
- **Suggested Fix**: Clamp in `read_and_advance_position` (threading `max_samples` through, as
  `seek` already does), or document the raw property and steer consumers to
  `get_playback_info()`'s clamped value.

### ENG-D4-02: `_terminate_process` swallows a post-SIGKILL `TimeoutExpired` with no log
- **Severity**: LOW
- **Dimension**: Audio I/O
- **Location**: `auralis/io/loaders/ffmpeg_loader.py:55-69`
- **Status**: NEW
- **Description**: The shared cleanup path sends SIGTERM, waits 5 s, escalates to SIGKILL, waits
  another 5 s — but the outer `try/except Exception: pass` means a `TimeoutExpired` on the
  *post-kill* wait returns silently, with the child unconfirmed-reaped and no log line.
- **Impact**: Extremely narrow — only plausible with a child in uninterruptible D-state (hung NFS
  or similar). The caller still raises correctly either way, so the job fails cleanly; the residual
  risk is an orphaned `ffmpeg` with no diagnostic trail.
- **Siblings**: None — single definition, single call site.
- **Suggested Fix**: Log a warning when the post-SIGKILL wait times out. Observability only.

### ENG-D5-02: Two per-chunk EQ filter sites use raw `sosfiltfilt` without the project's length guard
- **Severity**: LOW
- **Dimension**: Chunked Mastering
- **Location**: `auralis/core/dsp/parallel_eq.py:101,103`, `auralis/core/stages/sub_bass_control.py:72`
- **Status**: NEW
- **Description**: `auralis/dsp/utils/filters.py` defines `sosfiltfilt_safe` /
  `is_long_enough_for_sosfiltfilt` precisely so callers degrade instead of raising when a signal is
  shorter than scipy's `padlen`. These two sites call `scipy.signal.sosfiltfilt` directly. The chunk
  loop's final iteration reads exactly `total_frames - read_pos` samples with no `overlap_after`
  (`auralis/core/mastering_chunk_loop.py:83-84`), so a track length leaving a tiny remainder can
  feed a final chunk shorter than `padlen`.
- **Evidence**: Empirically, `butter(1..2, ...)` → `sosfiltfilt` `padlen` ≈ 6-9 samples; below that
  scipy raises `ValueError`. Both trigger conditions are whole-track fingerprint values, so it is
  all-chunks-or-none for a given file.
- **Impact**: For the narrow set of file lengths whose final-chunk remainder lands under ~9 samples
  (out of a ~1.3 M-sample chunk), this raises an unhandled `ValueError` that aborts the file — and
  compounds into ENG-D5-01's truncated-output-left-on-disk behaviour. LOW because of the trigger
  window, not because the crash is benign.
- **Siblings**: Both sites listed; `sosfiltfilt_safe` already exists as the intended pattern.
- **Suggested Fix**: Route both through `sosfiltfilt_safe`.

### ENG-D7-03: Several hand-rolled repository write paths omit the `except: rollback()` pattern of #2238
- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: `auralis/library/repositories/queue_repository.py:96,153,180`; `auralis/library/repositories/queue_history_repository.py:65,155,181,252`; `auralis/library/repositories/settings_repository.py:47,104,126`; `auralis/library/repositories/album_repository.py:271`; `auralis/library/repositories/fingerprint_repository.py:421,450,468`
- **Status**: NEW (extends a pattern #2238 fixed only in `AlbumRepository`)
- **Description**: #2238 added `except Exception: session.rollback(); raise` to two
  `AlbumRepository` methods to prevent dirty session reuse after a failed commit. The same shape —
  `session.commit()` inside a bare `try/finally` with no `except` — persists at the sites above.
- **Impact**: **Verified not to be a live bug.** SQLAlchemy's `Session.close()` performs an
  implicit rollback before returning the connection to the pool (reproduced directly: forced
  `IntegrityError` on commit, then bare `close()`, left the pool clean for the next session), and
  the exception propagates identically either way. This is consistency against the codebase's own
  precedent, not a corruption risk — hence LOW rather than #2238's MEDIUM.
- **Siblings**: Listed exhaustively above; all 13 repositories were swept for commit/rollback
  imbalance.
- **Suggested Fix**: Add the guard opportunistically when these files are touched for other reasons.

---

## Re-examined Closed Issues (deliberately NOT re-filed)

**`loudness_maximizer` constructs a fresh `BrickWallLimiter` per 30 s chunk — Existing: #2390
(CLOSED).** Two dimensions reached this code independently (`auralis/core/stages/loudness_maximizer.py:80-85`)
and converged on the same conclusion, so it is recorded here rather than as a finding.
`BrickWallLimiter._release_envelope()` documents that it updates `self.current_gain` so consecutive
chunks form a continuous envelope, implying one instance should be reused; the stage instead builds
one per call, resetting `current_gain` to 1.0 at every 30 s boundary. #2390 was closed on the
rationale that the surrounding architecture absorbs the transient, and that rationale survives
scrutiny: the push gain (not the limiter) sets loudness and is derived from whole-track
`source_lufs`/`source_crest_db` (constant across chunks); the release is 60 ms with 2 ms lookahead,
so the state transient decays in tens of ms; and `mastering_chunk_loop.py` blends a 3-second
crossfade weighted toward the chunk with full within-chunk continuity exactly where a discrepancy
would be largest. Neither dimension could construct a scenario producing an audible step outside
sustained heavy limiting landing precisely at a boundary. **No action recommended**; re-open #2390
only if that edge case is observed in practice.

---

## Verification Notes (negative results worth recording)

**Today's artist-repository refactor (#5084, `188db72a`) is sound.** The audit brief asked
specifically whether the reduced, aggregate-only list options still satisfy every `to_dict()`
relationship access. They do:
`Artist.to_dict()` branches on `track_count_expr is not None` before falling back to
`_safe_collection()` (`auralis/library/models/core.py:385-390`), and list reads always populate the
expression, so the fallback that would need `Artist.tracks` is never taken for list-sourced rows;
`_attach_genre_names()` unconditionally sets `genre_names` on every artist from `get_all()`/`search()`,
so `auralis-web/backend/routers/artists.py::_artist_genres()` always short-circuits before touching
`artist.tracks`; and the detail endpoints still use `get_by_id()` with the unchanged full
`_ARTIST_DETAIL_OPTIONS`. No `DetachedInstanceError` gap was introduced.

**`similarity_graph` orphans after a library reset — hypothesis disproven.**
`RepositoryFactory.reset_library()` does not explicitly delete `similarity_graph` rows, but both FK
columns carry `ondelete='CASCADE'` in the ORM model and in the `v004_to_v005` migration, and
`PRAGMA foreign_keys=ON` is set on every connection. Reproduced directly: deletion cascades and
leaves zero orphans.

**The Rust `process_chunks` path remains unreachable from live Python.** The #4989 crossfade
double-count fix is present (`vendor/auralis-dsp/src/chunk_processor.rs:101-111`) with regression
tests, and a grep of both `auralis/` and `auralis-web/` confirms nothing calls the binding — so its
f64-vs-float32 dtype question stays moot until it is wired up.

---

## Relationships

- **One root cause behind all three HIGH findings: incomplete sibling propagation.** #2531's
  sanitization, #4875's byte budget, and #3656's lock-scope discipline were each applied at the site
  where the bug was reported and not swept across structurally identical siblings. ENG-D1-01 and
  ENG-D7-01 are lower-severity instances of the same organizational pattern (the `float()` wrap
  applied at 8 sites but missed at 2; the aggregate-count migration applied to 3 repositories but
  missed the 4th). A sibling sweep at fix time — which the audit protocol already mandates for
  *findings* — would have caught five of the fifteen findings in this report.
- **ENG-D5-02 → ENG-D5-01 is a live chain.** The unguarded `sosfiltfilt` is the concrete way to
  raise mid-chunk, and the missing output cleanup is what turns that raise into a truncated file
  presented as a finished master. Fixing ENG-D5-01 defuses ENG-D5-02's real-world consequence even
  if the filter guard is never added.
- **ENG-D3-01 → ENG-D3-02 amplification.** The unclamped position overrun is bounded by how long
  auto-advance takes; the gapless blocking load is exactly what makes that window long enough to
  matter. Fixing ENG-D3-01 shrinks ENG-D3-02 back to sub-chunk duration.
- **ENG-D2-01 and open #4938 are the same bug class in two files.** Both reintroduce a categorical
  step into the continuous parameter space that #4860 was supposed to have eliminated. They should
  be fixed together with a single sweep for remaining hard `if measured > threshold` gates across
  every `ProcessingCoordinates` consumer.
- **ENG-D6-01 and ENG-D6-02 both stem from the Rust-engine migration.** One dropped a guard, the
  other left an efficiency path un-ported to the new windowing contract. A follow-up review of what
  else `871356f7`/`29650ea0` replaced wholesale is warranted.

---

## Prioritized Fix Order

1. **ENG-D6-01** (HIGH, regression) — the only finding that writes bad data to durable storage, the
   only confirmed regression, and it silently degrades similarity search and mastering-target
   selection with no self-healing path. One `isfinite` check at one choke point.
2. **ENG-D4-01** (HIGH) — a one-line call to a helper already imported in the same file; removes an
   OOM-kill risk on the playback thread for high-resolution files. Highest fix-value-to-effort ratio
   in the report.
3. **ENG-D3-01** (HIGH) — audible glitch on a realistic path (any gapless transition without a warm
   prebuffer). Larger fix than the two above (requires restructuring the lock scope), so third
   despite equal severity.
4. **ENG-D5-01** (MEDIUM) — silent delivery of an incomplete master is a data-integrity-adjacent
   failure; temp-path-then-rename is a contained change. Fix ENG-D5-02 in the same pass.
5. **ENG-D2-01** (MEDIUM) — sweep it together with open #4938 so the continuous-space invariant is
   restored in one change rather than two.
6. **ENG-D1-01** (MEDIUM) — two `float()` wraps; trivial, and closes the last two gaps in an
   8-times-fixed pattern.
7. **ENG-D6-02** (MEDIUM) — real CPU/memory waste on the most common file formats, but bounded and
   background-only; needs an `offset`/`duration` passthrough, so more work than the items above.
8. **ENG-D1-02** (MEDIUM, latent) and **ENG-D7-01** (MEDIUM, dormant) — both are defensive.
   ENG-D7-01 should be scheduled *before* any genre-browsing endpoint ships, at which point it
   becomes HIGH.
9. **LOW band** — ENG-D5-02 (fold into #4), ENG-D3-02, ENG-D4-02, ENG-D2-02, ENG-D2-03, ENG-D7-03:
   fix opportunistically when the surrounding code is touched.

---

## Coverage and Confidence

All 7 dimensions completed. Dimension 2 (DSP Pipeline) delegated to four `dsp-specialist`
sub-agents that stalled without returning; that dimension was re-run by direct read/grep against
HEAD, and its findings and verified-clean claims are first-hand — but the following were
spot-checked rather than exhaustively swept and carry lower confidence:
`auralis/dsp/realtime_adaptive_eq/adaptation_engine.py`, `auralis/core/processing/base/` internals,
`auralis/core/hybrid/preference_manager.py` / `realtime_manager.py`,
`auralis/core/config/preset_profiles.py` / `genre_profiles.py`, and the individual dtype/shape
contracts of 8 of the 11 Rust PyO3 exports (their GIL-release and panic-catch wrapping *was*
confirmed uniform). Dimension 1 similarly did not read `auralis/dsp/utils/*` and several
`auralis/core/processing/*` modules end-to-end, relying on pattern greps there.
`auralis/dsp/realtime_adaptive_eq/` is documented as unwired (#4615, with a regression test guarding
its reachability), so gaps there are currently unreachable in production.

The three HIGH findings were each independently re-verified by the orchestrator against HEAD before
inclusion — the loader guard gap, the fingerprint NaN path (including recovering the deleted #2531
sanitization from `3702c6d4` and confirming `871356f7` removed it), and the lock-across-I/O scope in
`next_track()`.

---

## Deduplication

All findings were checked against 3,000 open and closed GitHub issues plus `docs/audits/` and
`.claude/issues/`. Issues closed today — **#5082, #5084, #5086, #5087, #4810** — were explicitly
excluded and are not re-reported; #5084's code was instead verified as correct (§ Verification
Notes). Open issues confirmed still valid and deliberately not re-filed: **#4938** (delta_eq hard
cutoff), **#4972** (`_apply_simple_eq_fallback` broadband gain), **#4966** (crossfade
equal-power/equal-gain label), **#5058** (reference/hybrid fallback config flip), **#4123** (Rust
LUFS RMS approximation, deferred). Closed issues whose fixes were re-verified present at HEAD
include #3290, #3656, #3735, #4100/#4212, #4141, #3670/#3781, #4328/#4495, #3668/#3726/#4098, #2429,
#2515, #2157, #3684, #3700, #4989, #4875 (at its three sites), #4496, #4119/#4540, #3743/#3672,
#4611/#4597, #2495, #4131/#4112, #2908, #4595/#4994, #3741, #2528, #4837, #4404/#4636, #2496,
#3671, #4910, #2238, #4641, #4777, #4554, #3769, #3455, #4841, #4503, #4502, #4985, #4852, #4101,
#3666, #3660, #2402, #2292, and today's `39c5d36e`. **#2531 is the sole confirmed regression.**

---

*Report generated by `/audit-engine` (7 dimensions, deep). Next step:*
`/audit-publish docs/audits/AUDIT_ENGINE_2026-08-13.md`

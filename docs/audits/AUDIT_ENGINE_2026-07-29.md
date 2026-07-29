# Audio Engine Audit — 2026-07-29

**Scope**: Auralis core audio engine — `auralis/core/`, `auralis/dsp/`, `auralis/player/`, `auralis/io/`, `auralis/optimization/`, `auralis/analysis/`, `auralis/library/`, `auralis/services/`, `vendor/auralis-dsp/`
**Depth**: deep (full call-graph tracing)
**Method**: 7 independent dimension agents, fresh read of current source at `09004fa2`. 128 commits since the prior engine audit (2026-07-25) — nothing was carried over from that report without re-verification. Numeric claims were re-run in the repo venv (`.venv/bin/python`, 3.14.0) rather than reasoned about on paper.
**Dedup baseline**: 241 open + 4291 closed GitHub issues, `docs/audits/AUDIT_ENGINE_2026-07-25.md`, `docs/audits/AUDIT_ENGINE_2026-07-12.md`, `.claude/issues/`

---

## Executive Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 7 |
| MEDIUM | 13 |
| LOW | 20 |
| **Total** | **40** |

**No CRITICAL findings.** No sample-count mismatch, no in-place mutation of a caller-owned array, and no data-corruption path survived verification. Every assertion-based invariant (`processed.shape == target_audio.shape` on all three mode handlers, `write_region.shape[1] == core_samples` in the chunk loop, the `#3792` realtime length check) is intact, and 60+ previously-closed fixes were re-verified as genuinely still present.

The finding count is roughly double the prior audit's. That is not a quality regression in the code — it is coverage: this pass traced the `auralis/dsp/` primitives (limiters, envelope followers, EQ curve tables, stereo utils) and the `auralis/io/` loader stack at a depth the previous engine audits did not reach, and most of what it found there is latent rather than live.

### Key themes

1. **Two hard failures on live paths, both from schema/API drift between a caller and a callee.** ENG-D1-2 (`expansion_params` missing `target_crest_increase` → `KeyError`) and ENG-D3-1 (`QueueController.add_to_queue` does not exist → `AttributeError`) are the same shape: one side builds a dict/call in a format the other side does not accept, and nothing — no dataclass, no ABC, no test — pins the contract. Both were reproduced against real objects, not inferred.

2. **Reachability is the dominant severity modifier, and it cuts both ways.** 18 of the 40 findings are on code with zero production callers. Three separate dimensions independently converged on the same structural fact: **the sophisticated part of the engine is not the part that ships.** The 13-stage `auralis/core/stages/` pipeline (ENG-D2-3), the whole `auralis/optimization/parallel/` family (ENG-D5-3), the `AdaptiveLimiter`/`RealtimeAdaptiveEQ` realtime chain (ENG-D1-8/9/10), and `RecordingTypeDetector` (ENG-D6-8) are all correct-and-unused, while everything a user actually hears goes through `ContinuousMode`'s much simpler five-stage chain. Engineering effort and audit severity have both been landing on the wrong side of that line.

3. **Continuity violations in the "continuous" space.** The architecture deliberately replaced discrete presets with a continuous 3D parameter space, but three cross-dimensional guard corrections (ENG-D2-1) and one delta-EQ band cutoff (ENG-D2-2) reintroduce hard `if measured > threshold` steps that jump straight to a substantial, audible correction with no ramp. A 0.002-unit change in a measured quantity flips a track between 0% and a fixed 50% stereo-to-mono blend. This is the exact failure mode the continuous redesign was built to eliminate.

4. **Half-applied fixes remain the most reliable bug source.** ENG-D1-15 (`#4225`'s dtype fix landed on the non-default of two buffer paths), ENG-D4-1 (`#4497`'s full-decode-fallback fix applied to the metadata path but not the hotter audio-data path), ENG-D6-5 (`#4538`'s normalization-constant fix applied to centroid but not rolloff), ENG-D6-7 (`#4539`'s smoothing-buffer reset applied to three of four analyzers), ENG-D7-2 (`#3339`'s `with_for_update()` is a silent no-op on SQLite). Five findings, one mechanism: duplicated logic where only one copy got fixed.

5. **Timezone and unit mismatches that Python will never raise on.** ENG-D7-1 compares a naive-UTC DB timestamp against a naive-local file mtime — both naive, so no `TypeError`, just a silently wrong answer offset by the user's UTC offset. ENG-D6-5 normalizes against 10 kHz and denormalizes against 8 kHz. Neither produces an error; both produce plausible wrong numbers.

### Most impactful issues

- **ENG-D1-2 (HIGH)** — the `.25d` fixed-targets fast path builds `expansion_params` without the one key `ExpansionStrategies.apply_rms_reduction_expansion()` reads, and `_apply_dynamics` calls it unconditionally. Verified end-to-end: `chunked_processor.py:226` loads targets → `processor_factory` → `HybridProcessor.set_fixed_mastering_targets` → `ContinuousMode._resolve_parameters` fast path → `KeyError`. This is the primary chunked-streaming path whenever a `.25d` sidecar exists.
- **ENG-D3-1 (HIGH)** — `POST /api/player/queue/add-track` with the documented default body (`position: null`) 500s on every call, because `QueueService` calls a method `QueueController` does not have. Reproduced live. The drag-to-position branch works; the ordinary "add to queue" button does not.
- **ENG-D2-1 (HIGH)** — three cross-dimensional guards in the default production mastering path snap from no correction to a 1–1.5 dB gain/tilt step or a fixed 50% stereo collapse at a hard threshold, reintroducing categorical behaviour into the continuous space.

---

## Findings

### HIGH

#### ENG-D1-1: WOLA overlap-add ramps the first `fft_size/2` samples up from digital silence
- **Severity**: HIGH
- **Dimension**: Sample Integrity
- **Location**: `auralis/core/processing/eq_processor.py:190-222`
- **Status**: NEW (related to closed #3437, which fixed the *terminal* chunk truncation; the leading edge was never addressed. Distinct from closed #4107 (window dtype) and #2680 (`=` vs `+=`), both verified intact.)
- **Description**: The WOLA loop starts frames at `i = 0, hop, 2*hop, …` with `hop = chunk_size//2` and applies a full Hann synthesis window to every frame including the first. For output samples `n < hop` only frame 0 contributes (there is no frame at `i = -hop`), so the COLA sum is not 1.0 there — it is the rising half of the Hann window. The result is a fade-in from exactly 0.0 over the first `fft_size/2` samples. The tail is correctly handled (the #3437 buffer extension plus zero-padded frames make the trailing COLA sum ≈ 1), so this is a head-only defect.
- **Evidence**: Verified numerically by replaying the exact loop with an identity EQ on a constant-1.0 signal at the default `fft_size: int = 4096`:
  ```
  first 8:   [0.0, 5.9e-07, 2.4e-06, 5.3e-06, 9.4e-06, 1.5e-05, 2.1e-05, 2.9e-05]
  at hop/2:  0.5001918     at hop: 0.9999999
  min over [hop, len-hop]: 0.9996164   (correct)
  ```
  ```python
  wola_window = hann(chunk_size).astype(audio.dtype, copy=False)
  for i in range(0, original_length, hop_size):
      processed_audio[i:i + chunk_size] += processed_chunk[:chunk_size] * wola_window
  ```
- **Impact**: Sample count is preserved, but ~46 ms (2048 samples @ 44.1 kHz) of every EQ-processed buffer is amplitude-corrupted, starting from digital silence. Reachable on the main production path: `HybridProcessor.process()` → `_process_adaptive_mode` → `ContinuousMode.process` → `_stage_eq` → `_apply_eq` → `EQProcessor.apply_psychoacoustic_eq`. **Partially mitigated**: the backend loads `CONTEXT_DURATION = 5.0 s` of leading context and trims it, so for chunks ≥ 1 the ramp lands in discarded context. It is **not** mitigated for chunk 0 (`load_start = max(0, chunk_start - CONTEXT)` = 0), which gets a 46 ms fade-in at t=0 of every track, nor for any direct whole-buffer caller. Worst case: `HybridProcessor` accepts buffers down to `MIN_SAMPLES = 1024`; a 1024-sample buffer is entirely inside the ramp and comes out as a 0→~0.5 fade.
- **Siblings**: The tail-side equivalent is already fixed (`out_shape = (original_length + chunk_size,)`). No other WOLA loop in scope.
- **Related**: ENG-D2-3 (the WOLA path is in `ContinuousMode`, i.e. the *live* chain, unlike most of `stages/`).
- **Suggested Fix**: Normalize by the accumulated window sum — accumulate `wola_window` into a parallel `norm` buffer and divide (`processed_audio /= np.maximum(norm, eps)`), which fixes both edges generically and also removes the residual ~0.0004 COLA error from the symmetric-vs-periodic Hann choice. Alternatively prepend one frame at `i = -hop` fed with a zero-padded head copy.

#### ENG-D1-2: Fixed-targets fast path builds `expansion_params` without the key the expander reads (`KeyError` on a live streaming path)
- **Severity**: HIGH
- **Dimension**: Sample Integrity / DSP Pipeline
- **Location**: `auralis/core/processing/continuous_mode.py:220-227` (producer), `:559-562` (unconditional call), `:575-577`; consumer at `auralis/core/processing/base/compression_expansion.py:204`
- **Status**: NEW
- **Description**: `ContinuousMode._convert_targets_to_parameters()` — the `.25d` fixed-targets fast path that skips fingerprint extraction — constructs `expansion_params` with keys `{threshold_db, ratio, attack_ms, release_ms, amount}`. `ExpansionStrategies.apply_rms_reduction_expansion()` reads `exp_params['target_crest_increase']`, which that dict does not contain, **before** it reads `amount`, so the `amount: 0.0` "disabled" value does not short-circuit it. Only the fingerprint path (`ContinuousParameterGenerator._generate_expansion`, `auralis/core/processing/parameter_generator.py:421`) emits `target_crest_increase`.
- **Evidence**: Call chain re-verified line by line in current source:
  ```
  ChunkedAudioProcessor  (chunked_processor.py:226 self.fingerprint, self.mastering_targets = result)
    → processor_factory  → HybridProcessor.set_fixed_mastering_targets   (hybrid_processor.py:176)
      → HybridProcessor._process_adaptive_mode  (hybrid_processor.py:334 fixed_params = self.current_targets)
        → ContinuousMode.process → _resolve_parameters → _convert_targets_to_parameters   # dict w/o the key
          → _apply_dsp_stages → _stage_dynamics → _apply_dynamics (continuous_mode.py:562, UNCONDITIONAL)
            → _apply_expansion → ExpansionStrategies.apply_rms_reduction_expansion
              → target_increase = exp_params['target_crest_increase']   # KeyError
  ```
  Disproof attempts that failed: `ProcessingParameters` is a plain dataclass with no `__post_init__` normalization, so the dict passes through verbatim; `_apply_dynamics` does a *shallow* `.copy()`, no key injection; `_apply_expansion` has no `amount == 0` guard; there is no `try/except` between `ContinuousMode.process` and the lookup.
- **Impact**: Hard crash of the mastering call whenever `.25d` mastering targets are active — the primary chunked-streaming path for any track with a sidecar. Surfaces as a failed/degraded chunk rather than corrupt audio, but the enhancement silently does not happen. The compression side is accidentally fine (both dicts happen to carry `ratio` and `amount`), which is why this went unnoticed; `limiter_params` has the same schema drift but is currently unread.
- **Siblings**: Same dict-schema drift between `_convert_targets_to_parameters` and `ContinuousParameterGenerator` for `compression_params` (`threshold_db/attack_ms/release_ms/knee_db/makeup_db` vs `threshold/attack/release`) and `limiter_params` — both currently harmless only by coincidence of which keys are read.
- **Suggested Fix**: Add `'target_crest_increase': 0.0` to the `expansion_params` dict in `_convert_targets_to_parameters` (expansion is intentionally disabled on this path, so 0.0 is behaviour-preserving), and replace both `*_params` dicts with typed dataclasses so the schemas cannot drift again.

#### ENG-D2-1: Cross-dimensional guard corrections in `ContinuousMode` reintroduce hard on/off thresholds — the exact categorical step the continuous architecture was built to eliminate
- **Severity**: HIGH
- **Dimension**: DSP Pipeline
- **Location**: `auralis/core/processing/continuous_mode.py:409-484` (`_stage_eq`, `_stage_dynamics`, `_stage_stereo_width`)
- **Status**: NEW
- **Description**: `_apply_dsp_stages` runs EQ → dynamics → stereo width → normalization, and after each of the first three stages measures a continuous quantity (LUFS drift, bass/high energy shift, phase-correlation drop) and gates a corrective DSP action behind a hard `if measured > threshold` test. The correction is not scaled from 0 at the threshold — it jumps straight to a substantial, audible value the instant the threshold is crossed.
  - EQ guard (`:421-428`): `if abs(lufs_drift) > 1.5: correction = clip(-lufs_drift, -3, 3)`. At the boundary the correction is already −1.5 dB.
  - Dynamics guard (`:442-455`): `if abs(bass_shift) > 0.10 or abs(high_shift) > 0.10: tilt = clip(-dominant*10, -2, 2)`. At the boundary, ≈ −1.0 dB applied as a shelf-filter spectral tilt.
  - Stereo guard (`:468-483`): `if phase_drop < -0.2 and post_phase < 0.3: blend 50% toward mid`. Worst of the three — the correction is not even proportional to how far past the threshold the signal is; it is a **fixed** 50% stereo-to-mono blend whether `phase_drop` is −0.201 or −0.9.
  - (`_stage_normalization`'s crest-crush check at `:503` is **not** part of this finding: `pullback_db = max(-3.0, crest_crush + 4.0)` evaluates to exactly 0 dB at the `crest_crush < -4.0` boundary and ramps linearly beyond it. Verified continuous; not a bug.)
- **Evidence**: Guard logic reproduced exactly in the repo venv:
  ```
  lufs_drift=1.49 -> correction=0.00 dB      lufs_drift=1.51 -> correction=-1.51 dB
  bass_shift=0.099 -> tilt=0.00 dB           bass_shift=0.101 -> tilt=-1.01 dB
  phase_drop=-0.199 -> blend=0.0             phase_drop=-0.201 -> blend=0.5 (50% to mono)
  ```
- **Impact**: Reachable on the default production path — `enable_cross_dimensional_guard` defaults to `True` (`auralis/core/config/unified_config.py:159`), `use_continuous_space` defaults to `True`, and `ContinuousMode` is what `HybridProcessor._process_adaptive_mode` drives for every backend enhancement job. Two similar-sounding tracks in a library, or the same track reprocessed after a tiny upstream change, can come out with an audible ~1–1.5 dB loudness/tonal step or a full stereo-width collapse on one side of a boundary and none on the other. Directly violates the stated continuous-space invariant.
- **Siblings**: All three occurrences are in the same class and reported together per the sibling rule.
- **Related**: ENG-D2-2 (same class of hard cutoff, in `delta_eq.py`).
- **Suggested Fix**: Replace each hard gate with a smooth ramp keyed off the same measured quantity — e.g. `correction = cap * tanh(max(0, |measured| - soft_start) / cap)` so the correction rises continuously from 0. For the stereo guard specifically, make the blend fraction itself a continuous function of `phase_drop` (e.g. `blend = clip((0.3 - post_phase)/0.3, 0, 1) * 0.5`) rather than a fixed 50%.

#### ENG-D3-1: `QueueService.add_track_to_queue` calls a method that does not exist on `QueueController` — every default (append) queue-add request 500s
- **Severity**: HIGH
- **Dimension**: Player State
- **Location**: `auralis-web/backend/services/queue_service.py:317-327` (bug); `auralis/player/queue_controller.py` (missing method); `auralis-web/backend/routers/player.py:674-685` (entry point)
- **Status**: NEW
- **Description**: `add_track_to_queue()` does `queue_manager = self.audio_player.queue` (the engine's `QueueController`) and, on the "append to end" branch (`position is None`, which the request schema documents as the default), calls `queue_manager.add_to_queue(track.filepath)`. `QueueController` has no `add_to_queue` method — only `add_track(track_info: dict)`. `add_to_queue` exists only on the top-level `AudioPlayer` facade (`auralis/player/enhanced_audio_player.py:428`), a different object. The typing `Protocol` in `auralis-web/backend/services/queue_protocols.py` papers over the mismatch at type-check time without making the real object implement it.
- **Evidence**: Reproduced live against the real class:
  ```
  >>> qc = QueueController(get_repository_factory=lambda: Mock())
  >>> qc.add_to_queue('/tmp/foo.wav')
  AttributeError: 'QueueController' object has no attribute 'add_to_queue'
  ```
  Independently re-confirmed by listing `QueueController`'s full method set: `add_track`, `add_tracks`, `add_track_from_library`, `set_queue`, … — no `add_to_queue`. Path: `POST /api/player/queue/add-track` → `service.add_track_to_queue(track_id, None)` → `AttributeError` → generic `except Exception` at `queue_service.py:349` re-raises → router converts to `HTTPException(500, "Failed to add track to queue")`.
- **Impact**: The canonical "add track to queue" endpoint fails with a 500 for every call that doesn't specify an explicit insertion `position` — i.e. the common case. The drag-and-drop-to-position branch (`set_queue`) is unaffected.
- **Siblings**: None — every other `queue_manager.*` call in `queue_service.py` resolves to a real `QueueController` method. The other backend `add_to_queue` call site (`routers/player.py:397`) correctly targets `audio_player.add_to_queue` (the facade method that does exist).
- **Suggested Fix**: Change `queue_service.py:327` to `queue_manager.add_track(...)` (building the dict-shaped `track_info` the rest of the file uses), or add a thin `add_to_queue` alias on `QueueController` forwarding to `add_track`. Add an integration test that actually exercises the append branch — the existing `test_queue_add_track_api` skips whenever the library is empty, which is how this shipped unnoticed.

#### ENG-D4-1: Per-chunk audio decode still falls back to whole-file FFmpeg conversion — sibling of the closed #4497, in the data path instead of the metadata path
- **Severity**: HIGH
- **Dimension**: Audio I/O
- **Location**: `auralis-web/backend/core/chunk_operations.py:106-142` (`ChunkOperations.load_chunk_from_file`)
- **Status**: NEW (distinct, unfixed sibling of closed #4497 — not a regression of it; #4497's own fix in `_load_metadata` was verified intact)
- **Description**: `load_chunk_from_file` always tries `sf.SoundFile(filepath)` directly, with no extension routing through `FFMPEG_FORMATS`/`SOUNDFILE_FORMATS` (`auralis/io/formats.py`). For any file libsndfile cannot open, the `except Exception` branch falls back to `unified_loader.load_audio(filepath, target_sample_rate=sample_rate)` — a full FFmpeg conversion plus full float32 decode of the **entire track** — merely to slice out one ~20-25 s chunk window. This is exactly the anti-pattern #4497 fixed in `ChunkedAudioProcessor._load_metadata()`, but the fix was never applied to the sibling method that loads actual chunk audio data, which runs once per chunk instead of once per session.
- **Evidence**: Confirmed live in this environment (ffmpeg 8.0.1, soundfile 0.14.0 / libsndfile 1.2.2):
  ```
  test.mp3  -> sf.SoundFile OPEN OK       test.m4a -> FAIL: "Format not recognised."
  test.ogg  -> sf.SoundFile OPEN OK       test.aac -> FAIL: "Format not recognised."
  test.opus -> sf.SoundFile OPEN OK       test.wma -> FAIL: "Format not recognised."
  ```
  M4A/AAC/WMA can never be opened by libsndfile, so every chunk load for those formats hits the full-decode fallback unconditionally. MP3/OGG/OPUS succeed only because this libsndfile build is ≥1.1; an older build (e.g. whatever ships in the packaged Electron/AppImage) hits the fallback for all six `FFMPEG_FORMATS`. Full chain verified: `process_chunk_safe` → `process_chunk` → `_process_chunk_core` → `load_chunk` → this fallback. There is no cached decoded full-audio buffer anywhere in `ChunkedAudioProcessor`, and `process_all_chunks_async` iterates every remaining chunk, so playing an N-chunk file once triggers N full decodes.
- **Impact**: O(n²) total decode work to play an n-chunk FFmpeg-only-format file once. For long-form content (podcasts, DJ mixes, classical) a 90-minute file is ~540 chunks ⇒ ~540 redundant full conversions. It also reintroduces the OOM exposure #3671/#4128 were written to close (each fallback briefly holds a full decoded buffer plus a full temp WAV) and makes background prebuffering effectively unbounded CPU work.
- **Siblings**: One call site, but the direct structural sibling of `_load_metadata()` (fixed for metadata only).
- **Related**: ENG-D4-2 (the OOM guard this repeatedly re-enters).
- **Suggested Fix**: Check the extension against `FFMPEG_FORMATS` up front (mirroring `unified_loader.load_audio`'s routing) and, for FFmpeg-only formats, either decode once per `ChunkedAudioProcessor` instance and cache the buffer, or use `ffmpeg -ss/-t` to extract only the needed window. Reserve "load full file and slice" as a genuine last resort.

#### ENG-D4-2: Duration-only pre-decode OOM guard assumes a fixed 96 kHz/stereo profile
- **Severity**: HIGH
- **Dimension**: Audio I/O
- **Location**: `auralis/io/loader.py:24-40` (`MAX_DURATION_SECONDS`), `auralis/io/loaders/soundfile_loader.py:67-78`, `auralis/io/loaders/ffmpeg_loader.py:291-313`, `auralis/io/unified_loader.py:93-104`
- **Status**: NEW (narrows the scope of closed #3671/#4220 — the guard those added exists and is intact, but is duration-only)
- **Description**: Every pre-decode OOM guard in the loader stack checks **only duration** against `MAX_DURATION_SECONDS` (default 7200 s, overridable via `AURALIS_MAX_DURATION_SECONDS`). The 7200 s default is justified in-code as "2 hours of stereo float32 at 96 kHz ≈ 5.3 GB — a safe upper bound", but the guard has no dependency on sample rate or channel count, both of which are already available in the same `sf.info()` / ffprobe `probe` dict at guard time and are simply never consulted.
- **Evidence**:
  ```python
  # auralis/io/loaders/soundfile_loader.py:73-78 — pre-decode guard, duration only
  file_info = sf.info(str(file_path))
  if file_info.duration > MAX_DURATION_SECONDS:
      raise ModuleError(...)
  # no check of file_info.samplerate or file_info.channels before the full sf.read() below
  ```
  Same pattern in `ffmpeg_loader.py:296-313` and the post-decode backstop in `unified_loader.py:98-104`.
- **Impact**: A ~7199 s 192 kHz stereo float32 source is ≈ 11 GB decoded (double the "safe" assumption); a 192 kHz multichannel master near the cap is tens of GB, before any downstream copies in `validate_audio`/`sanitize_audio`/resampling. Since Auralis is a mastering-focused tool, high-resolution masters are squarely in its expected input domain. The guard gives a false sense of safety: it was tuned to a single assumed profile the code never verifies.
- **Siblings**: All three pre-decode sites plus the post-decode backstop share the identical duration-only check.
- **Suggested Fix**: Compute an estimated peak byte size from `duration × sample_rate × channels × 4` (all three values already in hand) and enforce a byte-based ceiling (e.g. ~6–8 GB) in addition to the duration check.

#### ENG-D7-1: Scanner's modification-check compares a naive-UTC DB timestamp against a naive-local file mtime
- **Severity**: HIGH
- **Dimension**: Library & Database
- **Location**: `auralis/library/scanner/batch_processor.py:114-120` (`process_single_file`); root cause shared by `auralis/library/models/base.py:60-61` (`TimestampMixin`)
- **Status**: NEW
- **Description**: `TimestampMixin.updated_at` is set via `datetime.now(timezone.utc)`, but the column type is plain `DateTime` (no `timezone=True`, no `TypeDecorator`), and SQLAlchemy's SQLite dialect silently strips `tzinfo` — what comes back is a **naive datetime holding UTC wall-clock numbers**. Meanwhile `batch_processor.py:117` computes `datetime.fromtimestamp(file_stat.st_mtime)`, which without a `tz` argument returns a **naive datetime in the process's LOCAL timezone**. Line 119 compares them directly. Because both are naive, Python never raises `TypeError` (which would at least surface the bug) — it silently compares two different clock bases, off by exactly the local UTC offset.
- **Evidence**:
  ```python
  # auralis/library/models/base.py:60-61
  updated_at: Mapped[datetime | None] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=...)

  # auralis/library/scanner/batch_processor.py:114-120
  file_mtime = datetime.fromtimestamp(file_stat.st_mtime)          # naive LOCAL
  if existing_track.updated_at and existing_track.updated_at >= file_mtime:  # naive UTC-numbers
      return 'skipped', None
  ```
  Confirmed empirically that the SQLAlchemy/SQLite round-trip returns `tzinfo=None`, and that this sandbox's own offset is `-03:00` — i.e. the bug is live in this very environment, not hypothetical.
- **Impact**: `check_modifications=True` is hardcoded at both production call sites (`auralis-web/backend/routers/library_scan.py:134` manual rescan, and `auralis-web/backend/services/library_auto_scanner.py:279` hourly auto-scan). For any user not on UTC+0 — the large majority — the "has this file changed?" check is systematically wrong by the local offset: in negative-offset zones a genuine on-disk edit (re-tag, re-encode, replaced file) made within roughly the offset window around the last DB write is silently skipped, and stays skipped until some unrelated write touches the row; in positive-offset zones a track gets one spurious extra reprocess. No error, warning, or log line indicates anything is wrong.
- **Siblings**: `SidecarManager.write()`/`is_valid()` (`auralis/library/sidecar_manager.py:135,219`) also use naive `datetime.fromtimestamp(...)`, but both sides of that comparison use the same local-naive basis — **not** a sibling of this bug.
- **Suggested Fix**: Compare on one clock basis. Either make `TimestampMixin` timezone-aware end to end (`DateTime(timezone=True)` plus a `TypeDecorator` re-attaching UTC on load), or — localized to this check — use `datetime.fromtimestamp(file_stat.st_mtime, tz=timezone.utc)` against `existing_track.updated_at.replace(tzinfo=timezone.utc)`. Add a regression test that runs under `TZ=America/New_York` + `time.tzset()`.

---

### MEDIUM

#### ENG-D1-3: No-op / bypass paths hand the caller's own array back without a copy (8 sites across `core/dsp/` and `dsp/`)
- **Severity**: MEDIUM
- **Dimension**: Sample Integrity
- **Location**: `auralis/core/dsp/harmonic_exciter.py:98-99,106-108`; `auralis/core/dsp/transient_shaper.py:77-78,88-89`; `auralis/core/dsp/resonance_notcher.py:179-180`; `auralis/dsp/utils/stereo.py:97-98,150-155`; `auralis/dsp/dynamics/lookahead_buffer.py:35-36`; `auralis/dsp/dynamics/lowmid_transient_enhancer.py:75-76`; `auralis/dsp/realtime_adaptive_eq/realtime_eq.py:160-162`
- **Status**: NEW (merged from two dimension-1 halves that found the same pattern in different directories)
- **Description**: Eight DSP entry points, on their "nothing to do" branch, `return audio` — the caller's exact object — instead of `audio.copy()`. Every one advertises a "returns processed audio" contract, so a caller is entitled to treat the result as its own to mutate. This is the pattern that `stages.no_op()` (`auralis/core/stages/__init__.py:16-31`, added by #4298) exists to prevent, and that closed #3427 (`LookaheadBuffer`) and #2512 (`mono_to_stereo`) were opened for — those two were fixed; these eight were not. `auralis/core/stages/harmonic_exciter.py:69-78` additionally propagates the alias straight out of the stage boundary as `processed`, bypassing `no_op` entirely, which makes it the one stage of thirteen that does not honour the uniform contract.
- **Evidence**:
  ```python
  # core/dsp/harmonic_exciter.py
  if wet_db <= -60.0: return audio     # alias, not a copy
  if low_norm >= high_norm: return audio
  # dsp/utils/stereo.py:150-155
  if abs(width_factor - 0.5) < 0.01: return stereo_audio
  # dsp/dynamics/lookahead_buffer.py:35-36
  if self.lookahead_samples == 0: return audio
  ```
  Contrast the correct pattern elsewhere in the same tree: `basic.normalize` → `return audio.copy()`; `audio_info.mono_to_stereo` → `return audio.copy()`; `stages/safety_limiter.py:35` → `return audio.copy()`; `realtime_eq._dequeue_output` underrun → `return audio_chunk.copy()`. The `harmonic_exciter` bypass is genuinely reachable: `stages/harmonic_exciter.py:66` computes `wet_db = base_wet_db + 20*log10(wet_mix)` and the guard above it only rejects `wet_mix <= eps`, so any `wet_mix` below ~1e-3 takes the aliasing branch.
- **Impact**: **No live corruption today** — every reachable caller was traced and the array is already pipeline-owned by that point (`mastering_branches/continuous.py:58` and `mastering_process_chunk.py:84` both `audio.copy()` first; `stages/transient_shaper.py:72` copies per #4129; `LowMidTransientEnhancer` has zero callers; `RealtimeAdaptiveEQ` is the unwired #4615 chain). It becomes a CRITICAL in-place-mutation bug the moment any consumer adds an in-place op (`+=`, `np.clip(..., out=)`, slice assignment) — eight one-line deviations from the project's first stated invariant.
- **Siblings**: Also `auralis/core/processing/base/peak_management.py:57`, `auralis/core/processing/hf_aware_limiter.py:78`, `auralis/core/mastering_process_chunk.py:61-62`, `auralis/core/processing/continuous_mode.py:571,607`, `auralis/core/processing/base/stereo_width_processor.py:98,109`, `auralis/core/processing/realtime_dsp_pipeline.py:90` — all return an unchanged caller-owned array, though for these the fix arguably belongs upstream.
- **Suggested Fix**: `return audio.copy()` at all sites (a no-op branch is by definition not the hot path) and route `stages/harmonic_exciter.py`'s bypass through `no_op(audio)` so the stage-boundary contract is uniform across all 13 stages. Add a shared test helper asserting `result is not input` for every public DSP stage.

#### ENG-D1-4: `AdaptiveLimiter`'s oversample → downsample round-trip is a +2.5 dB 3-tap lowpass
- **Severity**: MEDIUM (would be CRITICAL if wired)
- **Dimension**: Sample Integrity
- **Location**: `auralis/dsp/dynamics/limiter.py:59-80,197-246`
- **Status**: NEW (distinct root cause from closed #3752, which fixed only the *dtype* of `_oversample`; that fix is intact)
- **Description**: With the default `LimiterSettings.oversampling = 4`, `_oversample()` zero-stuffs by `factor`, convolves with a moving-average kernel of length `2*factor+1` normalized by `1/(2*factor+1)`, then multiplies by `factor`; `_downsample()` takes `audio_os[::factor]`. At decimation phase `k*factor` the convolution window contains exactly three non-zero taps, so the round trip reduces algebraically to a 3-tap FIR at the base rate with kernel `[1,1,1] * factor/(2*factor+1)`.
- **Evidence**: DC signal of amplitude A: `filtered[k*4] = (A+A+A)/9 * 4 = 1.333*A` → **+2.5 dB**. Base-rate Nyquist (alternating ±A): `(A-A+A)/9*4 = 0.444*A` → **−7.0 dB**. The limiter therefore alters level and frequency response even when `gain_curve` is identically 1.0 — and the +2.5 dB happens *after* the gain curve, defeating the peak-control intent.
- **Impact**: Latent, not live. `AdaptiveLimiter` is constructed by `DynamicsProcessor` and invoked only from `RealtimeDSPPipeline.process_chunk` (`auralis/core/processing/realtime_dsp_pipeline.py:80`), reachable only from `HybridProcessor.process_realtime_chunk`, which `tests/regression/test_realtime_eq_unwired_4615.py` pins as having zero production callers.
- **Siblings**: `BrickWallLimiter` — the *live* limiter (`hybrid_processor.py:305,360,387`, `auralis/core/stages/loudness_maximizer.py:80`) — does not oversample and is unaffected. No other oversampling code in `auralis/dsp/`.
- **Related**: ENG-D1-5, ENG-D1-6 (same class, same unwired path).
- **Suggested Fix**: Replace zero-stuff + moving-average with `scipy.signal.resample_poly` (designed anti-imaging filter, unity passband gain), or — given the path is unwired — delete the oversampling branch and document `oversampling` as reserved. Add a unit test asserting `process(x)` with a flat gain curve returns `x` to float tolerance.

#### ENG-D1-5: `AdaptiveLimiter` applies its gain curve to a lookahead-delayed signal the curve was not computed from
- **Severity**: MEDIUM (HIGH by impact; latent path)
- **Dimension**: Sample Integrity
- **Location**: `auralis/dsp/dynamics/limiter.py:82-125,127-172`
- **Status**: NEW
- **Description**: `_process_core` computes `peak_envelope` from the **undelayed** `audio` using a forward-looking `maximum_filter1d(origin=(lookahead-1)//2)` — i.e. `peak_envelope[i] ≈ max(|audio[i .. i+L]|)` — then multiplies the **delayed** signal by the resulting gain curve. Delaying by `L` on top of a window that already looks forward by `L` double-applies the lookahead: the gain applied to input sample `k` is derived from samples `k+L .. k+2L`, and sample `k`'s own amplitude is never in the window that gates it.
- **Evidence**:
  ```python
  delayed_audio = self._apply_lookahead_delay(audio)   # delayed_audio[i] = audio[i-L]
  peak_envelope = self._compute_peak_envelope(audio)   # peak_envelope[i] = max(|audio[i..i+L]|)
  limited_audio = delayed_audio * gain_curve           # gain for audio[k] comes from audio[k+L..k+2L]
  ```
  `BrickWallLimiter.process` (`auralis/dsp/dynamics/brick_wall_limiter.py:88-165`) uses the same forward-origin max filter but deliberately applies it to the **undelayed** audio — the correct construction (and the #3308 fix rationale), and the reference this limiter's own comment claims to mirror.
- **Impact**: The limiter both fails to catch peaks (they arrive with gain already recovered) and ducks unrelated material `L` samples early — pumping plus threshold overshoot. Secondary defect in the same function: `_process_core` runs on the *oversampled* signal while `self.lookahead_samples` is computed at the base rate, so the effective lookahead is `lookahead_ms / oversampling` (1.25 ms instead of 5 ms at defaults). Same unwired-path reachability caveat as ENG-D1-4.
- **Siblings**: `AdaptiveCompressor.process` (`auralis/dsp/dynamics/compressor.py:106-116`) has the mirror-image defect — it derives `sample_levels` from `delayed_audio` and applies to `delayed_audio`, self-consistent but making the lookahead pure latency with zero gain-computer benefit. `BrickWallLimiter` is correct.
- **Suggested Fix**: Pick one convention for both classes: either drop `_apply_lookahead_delay` and multiply the undelayed audio by the forward-looking curve (matching `BrickWallLimiter`), or keep the delay and make the max filter backward-looking. Scale `lookahead_samples` by `oversampling` inside `_process_core`. Test that a single-sample spike at index `k` produces gain reduction at index `k`.

#### ENG-D1-6: `DynamicsProcessor.process()` ignores the runtime `enable_compressor` / `enable_limiter` flags
- **Severity**: MEDIUM
- **Dimension**: Sample Integrity
- **Location**: `auralis/dsp/advanced_dynamics.py:126-140`; call site `auralis/core/hybrid_processor.py:97-99`
- **Status**: NEW
- **Description**: `DynamicsProcessor.__init__` reads `settings.enable_compressor` / `settings.enable_limiter` once, at construction, to decide whether to instantiate the sub-processors. `process()` then gates on the *object* (`if self.limiter is not None:`), not the settings flag, so post-construction changes are silently ignored. The gate is internally inconsistent — `enable_gate` **is** re-read per call.
- **Evidence**:
  ```python
  if self.settings.enable_gate:          # respects runtime flag
  if self.compressor is not None:        # ignores settings.enable_compressor
  if self.limiter is not None:           # ignores settings.enable_limiter
  ```
  ```python
  # hybrid_processor.py:92-99 — flags set AFTER create_dynamics_processor() built the sub-processors
  self.dynamics_processor.settings.enable_limiter = False    # SILENTLY IGNORED
  ```
- **Impact**: An `AdaptiveLimiter` the engine explicitly asks to be off still runs on every chunk on that path, dragging in ENG-D1-4 and ENG-D1-5. Live consequence today is nil (unwired realtime chain), but the code reads as if the limiter is disabled, which hides those two defects from anyone auditing by intent rather than by execution.
- **Siblings**: Only these two flags; `enable_gate` is correct.
- **Suggested Fix**: Change both guards to `if self.settings.enable_compressor and self.compressor is not None:` (likewise for the limiter), or make `enable_*` properties that construct/tear down the sub-processor.

#### ENG-D1-7: `generate_genre_eq_curve` returns a live view into module-level `GENRE_CURVES`, which `create_target_curve` mutates in place
- **Severity**: MEDIUM (copy-before-modify violation on process-global state; currently unreachable)
- **Dimension**: Sample Integrity
- **Location**: `auralis/dsp/eq/curves.py:16-52,177-213`
- **Status**: NEW
- **Description**: When `len(curve) >= num_bands`, `generate_genre_eq_curve` returns `curve[:num_bands]` — basic slicing, therefore a **view** into the module-level `GENRE_CURVES[genre]` array. `create_target_curve` immediately does in-place element writes on that return value. Every call with non-zero `brightness` or `warmth` permanently corrupts the shared genre curve for the process lifetime, and the corruption accumulates across calls.
- **Evidence**:
  ```python
  def generate_genre_eq_curve(genre, num_bands=25):
      curve = GENRE_CURVES[genre_lower]
      if len(curve) >= num_bands:
          return curve[:num_bands]          # VIEW, no .copy()

  def create_target_curve(genre=None, brightness=0.0, warmth=0.0, num_bands=25):
      curve = generate_genre_eq_curve(genre, num_bands)
      curve[i] += brightness * 2.0 * (i / num_bands)   # mutates GENRE_CURVES['rock']
  ```
  The `num_bands < len(curve)` and unknown-genre branches build fresh arrays and are safe; only the equal-length branch (the default, 25 vs 25) aliases.
- **Impact**: Cross-call corruption of a shared EQ preset table — the exact class the project's first invariant exists to prevent. **Reachability: no production caller.** `create_target_curve` has zero callers anywhere; `generate_genre_eq_curve` is called only from two test files, neither of which mutates the return. Verified by repo-wide grep.
- **Siblings**: `curves.apply_content_adaptation` / `_apply_genre_adaptation` / `_apply_energy_adaptation` / `_apply_spectral_adaptation` all correctly `gains.copy()` first — this is the one function in the file that does not.
- **Related**: ENG-D1-13 (same function, dtype defect).
- **Suggested Fix**: `return curve[:num_bands].copy()`, and make `GENRE_CURVES` values read-only via `arr.setflags(write=False)` so a future regression fails loudly.

#### ENG-D1-8: FFT-EQ zero-padding collapses a 2-D single-channel `(N, 1)` buffer to 1-D output
- **Severity**: MEDIUM
- **Dimension**: Sample Integrity
- **Location**: `auralis/dsp/eq/filters.py:35-60`; `auralis/dsp/eq/parallel_eq_processor/vectorized_processor.py:48-77`; `auralis/dsp/eq/parallel_eq_processor/parallel_processor.py:52-88`
- **Status**: NEW
- **Description**: All three EQ front-ends pad short chunks into a 2-D `(fft_size, channels_or_1)` array and then call `.squeeze()`. For genuinely mono 1-D input this correctly restores 1-D; for stereo `squeeze()` is a no-op. But for a 2-D **single-channel** `(N, 1)` input with `N < fft_size`, the padded array is `(fft_size, 1)` and `squeeze()` drops the channel axis, returning shape `(N,)` where it was handed `(N, 1)`. Sample count is preserved; `ndim` is not. Note the asymmetry: the `>= fft_size` path takes no `squeeze()`, so the same `(N, 1)` chunk returns 2-D when long and 1-D when short — the output rank depends on chunk length.
- **Evidence**:
  ```python
  padded = np.zeros((fft_size, audio_chunk.shape[1] if audio_chunk.ndim == 2 else 1), dtype=audio_chunk.dtype)
  ...
  audio_chunk = padded.squeeze()      # (fft_size, 1) -> (fft_size,)
  ```
- **Impact**: Violates the shape-consistency invariant. Downstream stages branch on `audio.ndim == 2` throughout (`limiter.py:133`, `brick_wall_limiter.py:102`, `stereo.py:97`), so a silent 1↔2-D flip changes which code path runs. No live producer of `(N, 1)` buffers was found — `unified_loader.py` uses `always_2d=True` for stereo and #3440 notes the 1-D branch there is unreachable — so this needs a mono-source-loaded-as-2-D path to trigger. Reported because the three copies are identical and the guard is one line.
- **Siblings**: All three EQ processors carry a byte-identical copy of the padding block — the same duplication drift that #4309 and #4507 were filed for (#4507's oversized-chunk guard had to be separately back-ported to `_apply_eq_mono_sequential`).
- **Suggested Fix**: Record `input_ndim` before padding and restore it on return, or replace `padded.squeeze()` with `padded[:, 0] if input_ndim == 1 else padded`. Extract the padding block into one shared helper so the next fix lands in all three at once.

#### ENG-D1-9: `VectorizedEnvelopeFollower.process_buffer_numba` still hard-casts to float32 — #4225 fixed the non-default path
- **Severity**: MEDIUM
- **Dimension**: Sample Integrity
- **Location**: `auralis/dsp/dynamics/vectorized_envelope.py:94-137`
- **Status**: NEW (incomplete fix of the closed #4225 — the change that issue describes is still in place where it was made, so this is not a regression)
- **Description**: #4225 changed `process_buffer_vectorized` from `np.zeros(..., dtype=np.float32)` to `np.zeros_like(input_levels)`, with the rationale "forcing float32 here silently downcast a float64 caller". The sibling `process_buffer_numba` was not changed and still ends with `output.astype(np.float32, copy=False)`. `process_buffer()` — the only method any caller uses — tries **numba first** and falls back to the vectorized path only on exception, so the fixed path is the one that almost never runs.
- **Evidence**:
  ```python
  def process_buffer_numba(self, input_levels):
      return output.astype(np.float32, copy=False)     # unchanged by #4225
  def process_buffer(self, input_levels):
      if self.use_numba:                                # default True
          try:    return self.process_buffer_numba(input_levels)
          except: return self.process_buffer_vectorized(input_levels)   # the #4225-fixed path
  ```
  `AdaptiveLimiter._process_core` builds `target_gains` in float64 and receives a float32 gain curve back, so a float64 audio buffer is multiplied by a float32-quantised envelope.
- **Impact**: Precision loss only (~7 significant digits on the gain curve), not corruption — the multiply promotes back. Reported chiefly because a closed dtype issue is only half-fixed and the two-implementations-one-fix pattern repeats #4309.
- **Siblings**: `FastEnvelopeFollower.process_buffer_fast` (same file, line 201) and `envelope.EnvelopeFollower.process_buffer` (line 46) both correctly use `np.zeros_like`. `AdaptiveCompressor.process` (`compressor.py:126`) explicitly forces float32 before the call, making that downcast intentional — only the limiter path is affected.
- **Suggested Fix**: `output.astype(input_levels.dtype, copy=False)`, matching #4225's rationale. Also note `process_buffer_vectorized` returns a bare `np.array([])` (float64) for empty input regardless of input dtype.

#### ENG-D2-2: `delta_eq.py`'s `_EMPTY_BAND_THRESHOLD` hard cutoff produces a ~4 dB EQ discontinuity for a 0.01-percentage-point fingerprint change
- **Severity**: MEDIUM
- **Dimension**: DSP Pipeline
- **Location**: `auralis/core/processing/delta_eq.py:64-118` (`compute_delta_eq`)
- **Status**: NEW
- **Description**: When the reference-cloud path is active (`ContinuousParameterGenerator._generate_eq_curve_from_target`, used whenever any track is flagged `is_reference=True`), each of the 7 fingerprint bands is delta-corrected toward its k-NN-derived target using a smooth, capped `tanh` — *except* that bands whose source fraction falls below `_EMPTY_BAND_THRESHOLD = 0.005` are hard-set to `0.0` dB regardless of target (`if src_val_raw < _EMPTY_BAND_THRESHOLD: per_band[band] = 0.0; continue`). Immediately above the threshold the same band receives its full `tanh`-saturated correction with no ramp-in — the "acoustically empty" guard is a binary switch, not a fade.
- **Evidence**: Reproduced with the actual `compute_delta_eq()`/`to_eq_curve()` functions:
  ```
  src_sub_bass=0.0049 -> low_shelf_gain=0.000 dB
  src_sub_bass=0.0050 -> low_shelf_gain=1.990 dB   (per-band delta 3.981)
  ```
- **Impact**: Any track with a near-silent sub-bass/bass/air band (vinyl transfers, aggressively high-passed masters, mono/vocal-only sources) sits on this cliff. Whether the engine applies ~0 dB or ~4 dB to that band becomes noise-sensitive rather than content-driven, and the same source re-fingerprinted could land on either side. Fires only on the reference-cloud path (requires a populated `is_reference` cloud), narrowing real-world frequency without making it unreachable.
- **Siblings**: The threshold applies uniformly to all 7 `BAND_CAPS_DB` keys via the same loop — one location, all bands affected identically.
- **Related**: ENG-D2-1 (same class of hard threshold in `ContinuousMode`).
- **Suggested Fix**: Replace the hard cutoff with a smooth fade — multiply the computed `applied` delta by a smoothstep of `src_val_raw` between 0 and `_EMPTY_BAND_THRESHOLD` (or `2 ×` it) so the correction approaches zero continuously.

#### ENG-D2-3: The 13-stage per-band mastering pipeline is unreachable from the shipped product — only a standalone root CLI script uses it
- **Severity**: MEDIUM
- **Dimension**: DSP Pipeline
- **Location**: `auralis/core/simple_mastering.py`, `auralis/core/mastering_process_chunk.py`, `auralis/core/mastering_chunk_loop.py`, `auralis/core/mastering_prepare.py`, `auralis/core/mastering_branches/continuous.py`, all 13 modules under `auralis/core/stages/`
- **Status**: NEW
- **Description**: Tracing every caller shows this entire chain is reachable **only** from `create_simple_mastering_pipeline()` / `SimpleMasteringPipeline`, which in turn is imported and instantiated **only** by the standalone root script *auto_master.py*. That script is not referenced by `auralis-web/backend/`, not wired into any FastAPI router, not called by `desktop/`'s Electron main process, and not in any `package.json` script — it is a developer/offline CLI tool, not part of the shipped desktop app. Meanwhile the actual production path is `HybridProcessor.process()` → `_process_adaptive_mode()` → `ContinuousMode.process()`, confirmed via `auralis-web/backend/core/processing_engine.py` and `auralis-web/backend/core/chunked_processor.py`. `ContinuousMode` implements a *different*, simpler 5-stage chain (input gain → 5-shelf psychoacoustic EQ → broadband compression/expansion → stereo width → normalization) and never imports `auralis.core.stages` or `mastering_branches`. A third independent implementation, `AutoMasterProcessor` (`auralis/player/realtime/auto_master.py`), serves the real-time playback path and also does not touch `stages/`.
- **Evidence**:
  ```
  $ grep -rln "SimpleMasteringPipeline(" auralis/ auralis-web/ --include="*.py"
  auralis/core/simple_mastering.py        # its own factory function only
  $ grep -rln "from ..stages\|core.stages import" auralis/ auralis-web/ --include="*.py"
  auralis/core/mastering_branches/continuous.py   # only consumer of stages/
  $ grep -n "HybridProcessor\|SimpleMastering" auralis-web/backend/core/processing_engine.py
  # only HybridProcessor appears
  ```
- **Impact**: Every fix and invariant this dimension was asked to verify against `stages/`/`mastering_branches/` (sub-bass parallel mixing, EQ band-by-frequency mapping, resonance-notch Nyquist clamping, harmonic-exciter crest preservation) is real, correct, and well-engineered — and has **zero effect on what a user of the shipped app hears**. All production mastering goes through the much simpler `ContinuousMode` chain, which carries ENG-D2-1 and ENG-D2-2. Either `stages/`'s sophistication is intended to reach users and currently doesn't (a missing integration), or it is a dev tool and should be documented as one. Further hardening of `stages/` in isolation does not currently improve the product.
- **Siblings**: N/A — a reachability/wiring finding, verified by exhaustive grep.
- **Related**: ENG-D5-3, ENG-D6-8, ENG-D1-4/5/6 (the same "correct but unreachable" pattern in four other subsystems).
- **Suggested Fix**: Either wire `ContinuousMasteringBranch`/`stages/` into the backend processing path if the richer per-band processing is the intended user-facing behaviour, or document the split explicitly in `docs/architecture/` and in `.claude/commands/audit-engine.md`'s file list so future DSP audits stop validating a path with no production listeners.

#### ENG-D3-2: `PlaybackController.load_and_stop()` skips the position reset when already STOPPED, leaving a stale position on the next track load
- **Severity**: MEDIUM
- **Dimension**: Player State
- **Location**: `auralis/player/playback_controller.py:223-267`; `auralis/player/enhanced_audio_player.py:219-254,274-307`; `auralis-web/backend/services/playback_service.py:250-297`
- **Status**: NEW
- **Description**: `seek()` clamps and writes `self.position` unconditionally with no check on `self.state` — and it can be called while STOPPED, since the REST `seek()` service has no playing-state guard. `load_and_stop()`, which every track-load entry point calls to reset position for the incoming track, is a no-op when `self.state == PlaybackState.STOPPED` — it returns early *without* resetting `position` to 0. So: stop a track, seek forward, then load a different (possibly shorter) track, and `PlaybackController.position` still holds the stale offset.
- **Evidence**: Reproduced directly:
  ```
  pc.play(); pc.seek(10000, 44100); pc.stop()      # state=STOPPED, position=0
  pc.seek(5000, 999999999)                          # state=STOPPED, position=5000 (no state gate)
  pc.load_and_stop()                                # returns False; position STILL 5000
  ```
  Downstream, `AudioFileManager.get_audio_chunk()` slices `audio_data[start_position:end]` past the end — degrading to a zero-padded silent chunk (no crash), but `end_of_track` is immediately `True`. The externally-reported `position_seconds` is clamped by `IntegrationManager._get_position_seconds()`, so the number never visibly exceeds `duration_seconds`; the raw internal position and the chunk-slicing math are not protected.
- **Impact**: Loading a new track right after stopping-and-seeking either silently auto-skips the freshly-loaded track (if a next track exists) or plays silence indefinitely with a runaway internal position counter. User-visible as "nothing happens when I press play" or "it skipped by itself".
- **Siblings**: `previous_track()` calls `load_file()` internally and is subject to the same mechanism if invoked while already STOPPED.
- **Suggested Fix**: Have `load_and_stop()` always reset `self.position = 0` regardless of whether the state transition itself is a no-op (split the "was there a state change to notify" return value from the position-reset side effect), or have `seek()` refuse to move `position` while STOPPED.

#### ENG-D3-3: Fingerprint-load failure never clears the previous track's fingerprint from `AutoMasterProcessor`
- **Severity**: MEDIUM
- **Dimension**: Player State
- **Location**: `auralis/player/fingerprint_loader_mixin.py:94-121`; `auralis/player/realtime/processor.py:87-97`; `auralis/player/realtime/auto_master.py:93-106`
- **Status**: NEW (distinct from the closed #3463/#3445/#3719 stale-fingerprint *races*, whose generation-counter fix was verified intact — this is the failure path, not the race)
- **Description**: `_load_fingerprint_for_file()` handles "fingerprint failed / returned falsy" and "exception raised" identically: it sets `self._current_fingerprint = None` and calls `self.processor.set_fingerprint(None)`. But `RealtimeProcessor.set_fingerprint()` only forwards when the fingerprint is truthy (`if self.auto_master and fingerprint:`), so passing `None` is a guarded no-op — `AutoMasterProcessor.fingerprint` and the adaptive gain/EQ parameters derived from it are never reset. There is no `clear_fingerprint()`/`reset()` in the load path; the equivalent only happens at `AudioPlayer.cleanup()`.
- **Evidence**:
  ```python
  # fingerprint_loader_mixin.py:104-110
  debug(f"Failed to load fingerprint for {audio_path.name}, using profile-based mastering")
  self._current_fingerprint = None
  self.processor.set_fingerprint(None)   # no-ops inside RealtimeProcessor; auto_master.fingerprint untouched
  ```
  `FingerprintService.get_or_compute()` documents and implements returning `None` on failure — a normal, reachable outcome (corrupt/unsupported audio, transient analyzer failure, unfingerprinted placeholder row), not a hypothetical.
- **Impact**: Track N plays with a valid fingerprint; track N+1's fingerprint lookup fails; auto-mastering for track N+1 is silently computed from track N's stale LUFS/crest/bass/transient-density parameters instead of falling back to neutral as the log message claims. The message "using profile-based mastering" is itself misleading — no profile reset happens.
- **Siblings**: The exception-handler branch (`fingerprint_loader_mixin.py:117-121`) has the identical bug.
- **Suggested Fix**: Add an explicit `AutoMasterProcessor.clear_fingerprint()` (reset `self.fingerprint = None` and derived adaptive parameters to defaults) and have `RealtimeProcessor.set_fingerprint(None)` call it instead of silently no-op'ing.

#### ENG-D6-1: `spectral_rolloff` is normalized against 10 kHz but denormalized against 8 kHz
- **Severity**: MEDIUM (would be HIGH the moment a caller is wired)
- **Dimension**: Analysis
- **Location**: `auralis/analysis/fingerprint/rust_fingerprint.py:20-23,45,98` (write side) vs `auralis/analysis/fingerprint/schema.py:98-110` (read side)
- **Status**: NEW
- **Description**: `spectral_rolloff` is normalized with `ROLLOFF_NORMALIZATION_HZ = 10_000.0` on write, but `schema.py`'s `rolloff_to_hz()` denormalizes using `CENTROID_NORMALIZATION_HZ = 8000.0` (reused from the centroid helper). `rust_fingerprint.py`'s own module docstring documents this — *"note `schema.rolloff_to_hz` uses 8 kHz, a pre-existing inconsistency in that helper"* — but it was documented, not fixed. This is exactly the bug class #4538 fixed for centroid.
- **Evidence**:
  ```
  raw 6000.0 Hz -> /10000 -> 0.6 -> rolloff_to_hz(0.6) -> 4800.0    # 20% systematic underestimate
  ```
  The test suite does not catch it: `tests/auralis/analysis/test_fingerprint_schema_units.py:76` asserts `rolloff_to_hz(0.5) == 4000.0`, checking the helper's arithmetic against itself, never against the write-side constant.
- **Impact**: Any consumer of `rolloff_to_hz()` gets a frequency 20% too low. Today there are **zero production callers** — grep finds only the definition — so no live decision is corrupted. But `centroid_to_hz()` (the sibling helper in the same file) has four production call sites in `RecordingTypeDetector`, showing exactly how such a helper gets wired into a real decision path.
- **Siblings**: `centroid_to_hz()`/`CENTROID_NORMALIZATION_HZ` is correct and consistent end to end — rolloff is the only mismatched dimension.
- **Suggested Fix**: Add a `ROLLOFF_NORMALIZATION_HZ` constant to `schema.py` and use it in `rolloff_to_hz()` (or align the write side to 8 kHz), and change the test to assert the round-trip against the actual write-side constant rather than the helper's internal math.

#### ENG-D7-2: `add_scan_folder`/`remove_scan_folder`'s `with_for_update()` is a silent no-op on SQLite
- **Severity**: MEDIUM
- **Dimension**: Library & Database
- **Location**: `auralis/library/repositories/settings_repository.py:134-158`, `:160-184`
- **Status**: Regression of #3339 (closed as "DB-C-03: add_scan_folder/remove_scan_folder non-atomic read-modify-write" — the fix as shipped does not close the race it claims to)
- **Description**: Both methods do `session.execute(select(UserSettings).with_for_update())` and comment "(atomic read-modify-write, #3339)". `with_for_update()` compiles to `SELECT ... FOR UPDATE` on databases with row locking, but SQLite has no such syntax and SQLAlchemy's SQLite dialect silently drops the clause — no exception, no warning, just a plain `SELECT`. The method remains read JSON → decode → mutate in Python → re-encode → `commit()`. Two concurrent calls can both read the same starting list and the second `commit()` overwrites the first's addition. SQLite's database-level write lock serializes the two `COMMIT`s but does nothing to serialize the read-modify-write window between them, which is exactly what row locking would have done.
- **Evidence**: Confirmed via `stmt.compile(engine)` against a SQLite `Engine` in this repo's venv: `select(T).with_for_update()` compiles to `SELECT t.id FROM t` — the `FOR UPDATE` clause is entirely absent.
- **Impact**: Concurrent folder-list edits can silently lose one edit. Scoped to the `scan_folders` JSON list only (not track data), and the app is single-user desktop, so the realistic trigger is a double-click or two tabs rather than multi-tenant contention — real but narrow.
- **Suggested Fix**: SQLite has no row-lock primitive to fall back on; use `BEGIN IMMEDIATE` (acquire the write lock before the read) via the connection, or serialize both methods through an explicit `threading.RLock` around the whole read→mutate→commit sequence. SQLAlchemy gives no portable warning when `with_for_update()` degrades to a no-op, so a comment claiming atomicity here is actively misleading.

---

### LOW

#### ENG-D1-10: Chunk-loop crossfade is equal-**gain**, not the equal-power the comment claims — the label is wrong, the math is right
- **Severity**: LOW
- **Dimension**: Sample Integrity
- **Location**: `auralis/core/mastering_chunk_loop.py:48-51,181-189`
- **Status**: NEW (engine-side twin of open backend issue #3878, which reports the identical mislabelling in `apply_crossfade` — different file, so not covered by it)
- **Description**: The comment and module docstring both say "Equal-power crossfade (cosine curves maintain loudness)", but `fade_in = np.sin(t)**2` / `fade_out = np.cos(t)**2` sum to 1.0 in *amplitude*, which is an equal-**gain** (raised-cosine) crossfade. Equal-power would be `sin(t)`/`cos(t)` (sum of squares = 1).
- **Evidence**: Verified directly in current source at `mastering_chunk_loop.py:186-189`:
  ```python
  t = np.linspace(0.0, np.pi / 2, head_len, dtype=chunk_dtype)
  fade_in = np.sin(t) ** 2
  fade_out = np.cos(t) ** 2
  crossfaded = prev_tail[:, :head_len] * fade_out + head * fade_in
  ```
- **Impact**: **The math is correct and the label is wrong — not the other way round.** Adjacent chunks process the *same* source samples in the overlap region, so their outputs are near-identical (correlated); for correlated signals equal-gain is the right choice and equal-power would produce a +3 dB bulge mid-crossfade. "Fixing" this by switching to `sin`/`cos` would introduce an audible level bump at every 30 s boundary. Reported so nobody corrects it. Sample-count safety verified: `write_region.shape[1] == core_samples` is asserted on the non-last branch, and `sum(core_samples) == total_frames` / `head_len == len(prev_tail)` hold for every branch including the short-final-chunk case.
- **Siblings**: Backend `apply_crossfade` (#3878, open).
- **⚠ Conflicting reports — do not resolve by picking one**: Dimension 5 of this same audit described this crossfade as "equal-power (cosine)", i.e. accepted the comment at face value, and a separate backend audit dimension reported *a* crossfade as mislabelled and −3.01 dB at midpoint. Those are **different files** (`auralis/core/mastering_chunk_loop.py` here vs the backend `apply_crossfade`). This finding was independently re-verified against current source by the orchestrator: `mastering_chunk_loop.py` is `sin²`/`cos²` = equal-gain, and that is correct for its correlated-overlap use. Anyone acting on #3878 must confirm which file they are changing and whether that file's overlap region is correlated (same source samples processed twice → equal-gain) or uncorrelated (different material → equal-power) before touching the ramps.
- **Suggested Fix**: Change the comment and module docstring to "equal-gain (raised-cosine) crossfade — correct for correlated overlap regions; do NOT change to sin/cos", with the rationale inline so it survives the next audit.

#### ENG-D1-11: True-Peak guard applies a per-chunk gain and silently swallows all failures
- **Severity**: LOW
- **Dimension**: Sample Integrity
- **Location**: `auralis/core/mastering_chunk_loop.py:124-138`
- **Status**: NEW
- **Description**: The 4× oversampled true-peak guard computes `_tp` per chunk and scales the whole chunk by `_TP_CEILING / _tp`. Because `_tp` differs between chunk N and N+1, adjacent chunks can receive different broadband gains. Separately, the whole block is wrapped in `except Exception: pass`, so a scipy import failure or unexpected shape silently disables true-peak protection for the entire file with no log line.
- **Evidence**:
  ```python
  try:
      _chunk_4x = _rsp(processed_chunk, 4, 1, axis=1)
      _tp = float(np.max(np.abs(_chunk_4x)))
      if _tp > _TP_CEILING:
          processed_chunk = processed_chunk * (_TP_CEILING / _tp)
  except Exception:
      pass   # best-effort; never let this path break the pipeline
  ```
- **Impact**: Reachable on every `master_file()` chunk (though see ENG-D2-3 — that entry point is CLI-only). The level step at the boundary is smoothed by the following crossfade, so it is a soft discontinuity rather than a click. The silent `except` is the more actionable half: it converts a hard failure into inaudible-until-it-isn't loss of the −0.5 dBTP ceiling.
- **Siblings**: None; the only true-peak guard in scope.
- **Suggested Fix**: Log at `warning` level in the `except` rather than `pass`, and derive the TP gain from the whole-song peak — `auralis/core/mastering_prepare.py:209-222` already establishes exactly this pre-scan pattern for the makeup-gain headroom clamp, for exactly this reason.

#### ENG-D1-12: `_apply_simple_eq_fallback` applies a broadband gain, not EQ
- **Severity**: LOW
- **Dimension**: Sample Integrity
- **Location**: `auralis/core/processing/eq_processor.py:262-288`
- **Status**: NEW
- **Description**: The fallback invoked when psychoacoustic EQ raises applies `processed * (1.0 + (bass_gain_linear - 1.0) * 0.1)` — a wideband scalar multiply — for both the bass and the treble adjustment. There is no filtering of any kind, despite the comment "Very basic frequency adjustment using simple filtering". No filter object, no `sosfilt`, no band split anywhere in the method.
- **Impact**: When the fallback fires, the requested spectral shaping is replaced by a small overall level change (and if both bass and treble are requested, two multiplicative level changes stack). Sample count, dtype and copy semantics are all correct (`processed = audio.copy()` at `:273`), so this is a DSP-correctness issue, not an integrity one. Reachability is now narrow: `apply_psychoacoustic_eq` re-raises `AssertionError/ValueError/TypeError` (`:59-60`), and the #4217 fix (`_eq_curve_to_array` mapping bands by centre frequency, `:243-254`) removed the `IndexError` that used to make this fallback the *normal* path. That fix was verified intact — no regression.
- **Suggested Fix**: Either implement a real 2-band shelving fallback using `ParallelEQUtilities.apply_low_shelf_boost` / `apply_high_shelf_boost` (already in-tree, dtype-safe), or delete the fallback and let the exception propagate — a silent tonal no-op is worse than a visible failure now the #4217 root cause is gone.

#### ENG-D1-13: Empty-input early return skips mono→stereo expansion, so output rank depends on input length
- **Severity**: LOW
- **Dimension**: Sample Integrity
- **Location**: `auralis/core/hybrid_processor.py:256-263`
- **Status**: NEW
- **Description**: `_process_impl` returns `target_audio.copy()` for `len(target_audio) == 0` **before** the mono→stereo `np.column_stack` conversion, while the all-zeros early return at `:275-276` happens **after** it. A mono input therefore yields a 1-D `(0,)` array when empty and a 2-D `(N, 2)` array otherwise, from the same entry point.
- **Impact**: A caller that unconditionally indexes `result[:, 0]` breaks on the empty-mono path. Length invariant (`0 == 0`) and copy semantics both hold, so no corruption — a shape-contract inconsistency only. Low reachability: production callers pass ≥ `MIN_SAMPLES` buffers.
- **Suggested Fix**: Move the mono→stereo expansion above the empty check, or return `np.empty((0, 2), dtype=target_audio.dtype)` for empty mono input.

#### ENG-D1-14: Genre EQ curves are `int64`, so brightness/warmth adjustments are silently truncated to whole dB
- **Severity**: LOW (unreachable)
- **Dimension**: Sample Integrity
- **Location**: `auralis/dsp/eq/curves.py:16-26,199-211`
- **Status**: NEW
- **Description**: `GENRE_CURVES` entries are built from Python ints, so each is `dtype=int64`. `curve[i] += brightness * 2.0 * high_freq_factor` on an integer array truncates the float result back to `int64` on assignment, so sub-1 dB brightness/warmth adjustments evaluate to zero. The no-genre path (`curve = np.zeros(num_bands)`) is `float64` and behaves correctly, so the bug manifests only when a genre is supplied — i.e. exactly when the caller most expects a shaped curve.
- **Evidence**: With `brightness=0.3`, band 5 of 25: `0.3 * 2.0 * (5/25) = 0.12` → truncated to 0.
- **Impact**: Silent loss of the brightness/warmth control for genre-seeded curves. Same zero-production-caller reachability as ENG-D1-7.
- **Siblings**: The only integer-dtype gain arrays in scope; `eq/critical_bands.py`, `eq/masking.py`, and `realtime_adaptive_eq/adaptation_engine.py` all use float arrays.
- **Related**: ENG-D1-7 (same function).
- **Suggested Fix**: Declare `GENRE_CURVES` values with `dtype=np.float64` (which also composes with the `.copy()` fix).

#### ENG-D1-15: `AdaptationEngine` state arrays are sized 26 while there are 25 critical bands, and `analyze_and_adapt` returns the live mutable state array
- **Severity**: LOW (unreachable path)
- **Dimension**: Sample Integrity
- **Location**: `auralis/dsp/realtime_adaptive_eq/adaptation_engine.py:27-31,189-219`
- **Status**: NEW
- **Description**: Two defects in one object. (a) `adaptation_state` is initialised with `np.zeros(26)`/`np.ones(26)` and commented "26 critical bands", but `create_critical_bands()` (`auralis/dsp/eq/critical_bands.py:39-43`) builds 25 bands from 26 Bark edges; `_update_adaptation_state` loops over 25 target gains and never writes index 25, which stays 0.0 forever. (b) `_update_adaptation_state` mutates `current_gains` in place and `analyze_and_adapt` then returns `self.adaptation_state['current_gains']` — handing the caller the live internal array, which the next call overwrites underneath them.
- **Impact**: The stale 26th gain is harmless — `apply_eq` masks on `freq_to_band_map == 25`, which is empty. The aliased return is currently benign: the sole consumer only reads it, and `PsychoacousticEQ._update_history` does `gains.copy()`. `RealtimeAdaptiveEQ` has zero production callers (#4615, pinned by `tests/regression/test_realtime_eq_unwired_4615.py`).
- **Siblings**: `_get_frequency_weight`'s band-index bands (`< 4`, `< 8`, `< 16`, `< 20`) also assume a 26-band layout. `PsychoacousticEQ` sizes everything from `len(self.critical_bands)` and is correct.
- **Suggested Fix**: Size all three arrays from `len(create_critical_bands())` rather than the literal `26`; return `current_gains.copy()` from `analyze_and_adapt`.

#### ENG-D1-16: No dithering on any float → PCM quantisation path
- **Severity**: LOW (design gap, not a defect)
- **Dimension**: Sample Integrity
- **Location**: `auralis/io/results.py:1-81`; `auralis/io/saver.py:19-49`; `auralis-web/backend/encoding/wav_encoder.py:35-80`
- **Status**: NEW
- **Description**: `auralis/io/results.py` performs **no** bit-depth conversion — `Result` is a value object holding `file` + `subtype` (#4106 removed the last vestigial flags). All float→int quantisation is delegated to libsndfile via `sf.write(...)`, which is the right call: libsndfile uses correct asymmetric scaling (`×0x8000` with saturation, not `×32767`) and round-to-nearest, so none of the classic hand-rolled errors are present. What is absent is any dither or noise shaping before truncation to 16 bits.
- **Evidence**: `grep -rn "32767|32768|8388607|astype(np.int" auralis/ auralis-web/backend/` returns zero arithmetic hits — only `subtype='PCM_16'` string constants. Every writer clamps first (`saver.py:41` per #3471, `wav_encoder.py:59`, `mastering_chunk_loop.py:216` per #3660), so out-of-range floats cannot reach the cast.
- **Impact**: Truncation distortion (signal-correlated, hence more audible than equivalent-level noise) on very quiet passages and long fades in the 16-bit streaming path. At 16 bits with typical program material this is genuinely inaudible. Worth documenting as a deliberate trade-off rather than leaving as an unexamined omission.
- **Suggested Fix**: Either add TPDF dither before the PCM_16 encode in `wav_encoder.encode_to_wav`/`saver.save`, or add a sentence to `results.py`'s module docstring recording that dither is intentionally omitted and why. Worth noting in the same docstring that `saver.save` casts to `float32` before a `PCM_24` write — float32's 24-bit mantissa is adequate, but the cast is implicit and easy to misread as a bug.

#### ENG-D1-17: `DynamicsSettings.gate_ratio` has no validation, unlike every sibling settings field
- **Severity**: LOW
- **Dimension**: Sample Integrity
- **Location**: `auralis/dsp/dynamics/settings.py:64-90`; use site `auralis/dsp/advanced_dynamics.py:151-153`
- **Status**: NEW
- **Description**: `CompressorSettings.__post_init__` and `LimiterSettings.__post_init__` clamp every numeric field to a safe range. `DynamicsSettings.__post_init__` only fills in `None` sub-objects — it validates none of its own fields, including `gate_ratio`, which is used as a bare divisor: `target_gain = 1.0 / self.settings.gate_ratio`. `gate_ratio = 0.0` raises `ZeroDivisionError`; a negative value silently inverts the gate's polarity.
- **Impact**: An unguarded reciprocal on a config-supplied value. Not reachable with a bad value today: `HybridProcessor` sets `enable_gate = False` (which `process()` *does* honour — see ENG-D1-6), and nothing constructs `DynamicsSettings` with a non-default `gate_ratio`. Every other reciprocal/log in the reviewed tree is guarded.
- **Siblings**: `gate_threshold_db`, `adaptation_speed`, `target_lufs`, `target_lra` are likewise unvalidated in the same dataclass.
- **Suggested Fix**: Add a `__post_init__` clamp, e.g. `self.gate_ratio = max(1.0, min(100.0, self.gate_ratio))`, matching `CompressorSettings.ratio`.

#### ENG-D1-18: `_apply_eq_mono_vectorized` / `_apply_eq_mono_parallel` assume an even `fft_size`
- **Severity**: LOW
- **Dimension**: Sample Integrity
- **Location**: `auralis/dsp/eq/parallel_eq_processor/vectorized_processor.py:114-127`; `auralis/dsp/eq/parallel_eq_processor/parallel_processor.py:144-153`
- **Status**: NEW
- **Description**: The Hermitian mirror `spectrum[num_bins:] *= gain_curve[1:-1][::-1]` is length-consistent only for even `fft_size`. For odd `fft_size` the left side has `(fft_size-1)/2` elements and the right `(fft_size-3)/2`, so the multiply raises a broadcast `ValueError`.
- **Impact**: A loud crash, not silent corruption — the safe failure mode. Not reachable today: `EQSettings.fft_size` defaults to 4096 and `RealtimeAdaptiveEQ` sets `buffer_size * 2` (always even). Reported only because `fft_size` is a caller-supplied int with no validation anywhere.
- **Siblings**: `filters.apply_eq_mono` (`auralis/dsp/eq/filters.py:113`) shares the assumption via `band_mask[1:-1][::-1]`.
- **Suggested Fix**: Assert `fft_size % 2 == 0` in an `EQSettings.__post_init__` (which does not currently exist), or use `np.fft.rfft`/`irfft` and drop the manual mirroring entirely — that mirror logic has already been the subject of two bug fixes.

#### ENG-D3-4: `AudioPlayer.set_shuffle()` only toggles a flag, never reorders the queue
- **Severity**: LOW (dead code path)
- **Dimension**: Player State
- **Location**: `auralis/player/enhanced_audio_player.py:648-653`; `auralis/player/queue_controller.py:279-285`; `auralis/player/components/queue_manager.py:289-335`
- **Status**: NEW
- **Description**: `set_shuffle(enabled)` → `QueueController.set_shuffle(enabled)` only writes the `shuffle_enabled` boolean; it never calls `QueueManager.shuffle()`/`unshuffle()`, which are what actually reorder `self.tracks`. Unlike `repeat_enabled` (consulted live by `next_track()`/`peek_next()`, so a flag-only setter is correct there), shuffle order is baked into the list at `shuffle()`-call time and never re-derived — so `set_shuffle(True)` leaves the queue order untouched while reporting `shuffle_enabled: True`.
- **Evidence**: Grepping `auralis-web/` for `set_shuffle(` returns zero matches. The only production path (`POST /api/player/queue/shuffle` → `QueueService.shuffle_queue()`/`unshuffle_queue()`) calls `queue_manager.shuffle()`/`.unshuffle()` directly, bypassing `set_shuffle()`, so the reorder always happens correctly in production.
- **Impact**: None in the current call graph. Latent trap for any future caller or test that assumes `set_shuffle(True)` behaves like the REST endpoint.
- **Suggested Fix**: Either have `set_shuffle()` call `queue.shuffle()`/`unshuffle()` to match its name, or remove/deprecate it in favour of the two explicit methods.

#### ENG-D4-3: ffprobe positional filename passed without `-i`/`--` — dash-prefixed filenames misparsed as options
- **Severity**: LOW (mitigated — unreachable from any current production caller)
- **Dimension**: Audio I/O
- **Location**: `auralis/io/loaders/ffmpeg_loader.py:195-202` (`_probe_audio`), `auralis/io/unified_loader.py:209-216` (`_get_info_with_ffprobe`)
- **Status**: NEW
- **Description**: Both ffprobe wrappers append the file path as a bare trailing positional argument, with no preceding `-i` and no `--` end-of-options marker. ffprobe's cmdutils parser treats any argument beginning with `-` as an option, so a file whose basename starts with `-` is misinterpreted rather than opened. The main FFmpeg **decode** command does not have this problem — it correctly uses `['-i', file_path_str, ...]`.
- **Evidence**: Reproduced live — `ffprobe ... -myfile.wav` returns 1 with empty stdout/stderr; the same command with a `./` prefix returns 0.
- **Impact / Reachability**: Every current caller was traced back to its filepath source. The upload path builds paths via `tempfile.NamedTemporaryFile` and `Path.home() / ".auralis" / "uploads" / f"{uuid4().hex}{suffix}"` — always absolute. The library scanner walks `Path(directory).iterdir()` off an absolute directory in every call site. No production path passes a bare relative, user-controlled filename into either probe function. Latent defense-in-depth debt in two general-purpose functions.
- **Siblings**: Both ffprobe wrappers share the exact command construction; the decode command in the same file does not.
- **Suggested Fix**: Insert `'-i'` before the path (matching what the decode command already does) or add a `'--'` separator immediately before `str(file_path)` in both probe command lists.

#### ENG-D5-1: Rust `ChunkProcessor::process_chunks` double-counts the previous chunk in the crossfade region
- **Severity**: LOW (would be CRITICAL if reachable)
- **Dimension**: Parallel Processing
- **Location**: `vendor/auralis-dsp/src/chunk_processor.rs:83-116`, exposed via `vendor/auralis-dsp/src/py_bindings.rs:748-784`
- **Status**: NEW (distinct from the closed #2889 "assign instead of `+=`" fix — that fix is present and correct in isolation; this is a different defect in how the crossfade interacts with it)
- **Description**: For chunk N (N>0), `process_chunks` first overwrites `chunk[..crossfade_len]` in place via `apply_crossfade` with `chunk*fade_in + overlap_buffer*fade_out` — a complete, already-blended value. It then writes that same region into `output` via `scaled_add` (`+=`), i.e. *adds* it on top of what is already there. But `output[write_start..write_start+overlap]` already holds chunk N−1's own unfaded output in exactly that range, and `overlap_buffer` is a copy of that same tail. The previous chunk's contribution is therefore summed twice.
- **Evidence**: Confirmed empirically with the compiled module at production-matching parameters (`chunk_size=131072, overlap=2205`), identity pass-through on an all-ones input:
  ```
  values around first boundary: [1. 1. 1. 1. 1. 2. 2. 2. 2. 2. 2. 2. 2. 2. 2.]
  max in first 200000 samples: 2.0
  ```
  A pure pass-through of constant 1.0 should stay at 1.0; instead every crossfade region jumps to 2.0 and stays there until the next boundary.
- **Impact**: If wired into production, every chunk boundary would produce a ~2× amplitude discontinuity — audible pop plus clipping/limiter engagement, a CRITICAL-class bug. As shipped it has **zero effect**: `auralis_dsp.process_chunks` has no Python callers anywhere; the identically-named production function is `process_chunks` in `auralis/core/mastering_chunk_loop.py`, an entirely separate pure-Python implementation with correct (overwrite-not-accumulate) crossfade math.
- **Siblings**: `process_mono_chunks` (`chunk_processor.rs:147-192`) shares the OLA accumulate pattern but has no separate pre-blend step, so it does not double-count. It has no Python binding either.
- **Suggested Fix**: Either stop pre-blending in `apply_crossfade` and let `scaled_add` do the whole crossfade by scaling `processed` by `fade_in` only, or keep the full blend and switch the corresponding `output` write back to `assign` for that overlap region. Add a regression test asserting a constant-signal identity pass stays flat across boundaries.

#### ENG-D5-2: `MemoryPool` keys its buffer pool by shape only, not `(shape, dtype)`
- **Severity**: LOW (unreachable)
- **Dimension**: Parallel Processing
- **Location**: `auralis/optimization/memory/memory_pool.py:32-51` (`get_buffer`), `:53-69` (`return_buffer`)
- **Status**: NEW
- **Description**: `available_buffers` is keyed only by `shape`. `get_buffer(shape, dtype)` pops any buffer of that shape regardless of its original dtype and returns `np.asarray(buffer, dtype=dtype)` — a cast **copy** when the dtypes differ, so the object handed back is a different Python object from the one whose `id()` was just recorded in `allocated_buffers`. Consequences: the orphaned buffer is permanently marked allocated and never returns to the pool (accounting-only growth); and once it is GC'd, CPython may reuse its `id()` for an unrelated object, which `return_buffer` (keying solely on `id(buffer)`) would then accept into a possibly-wrong shape bucket.
- **Impact**: None — `get_buffer`/`return_buffer` have zero production callers. `MemoryPool` is only constructed by `PerformanceOptimizer.__init__`, and `PerformanceOptimizer.get_audio_buffer`/`return_audio_buffer` are never called anywhere in `auralis/` or `auralis-web/`. `PerformanceOptimizer` *is* constructed at import time by `hybrid_processor.py`, but only to wrap `AdaptiveMode.process` with the profiler (per the #4524 fix rationale) — the cache/memory-pool/SIMD members are allocated and never exercised.
- **Siblings**: `PerformanceOptimizer.cached_function` / `optimize_real_time_processing` / `optimized_fft` / `optimized_convolution` are equally unreachable.
- **Suggested Fix**: If ever wired up, key by `(shape, dtype)` and match dtype on return. Given it is fully unreachable, the lower-cost fix is removal (see ENG-D5-3).

#### ENG-D5-3: Dead parallel-processing infrastructure beyond the already-tracked #4565
- **Severity**: LOW
- **Dimension**: Parallel Processing
- **Location**: `auralis/analysis/parallel_spectrum_analyzer.py` (whole file, 351 lines); `auralis/dsp/eq/parallel_eq_processor/parallel_processor.py` (whole file, 221 lines) plus its factory functions
- **Status**: NEW (open issue #4565 covers `auralis/optimization/parallel/` specifically — these are two additional files outside that issue's scope)
- **Description**: `ParallelSpectrumAnalyzer` has zero constructors/imports anywhere outside its own module. `ParallelEQProcessor` is exported from `auralis/dsp/eq/parallel_eq_processor/__init__.py` alongside `VectorizedEQProcessor`, but the production EQ path (`auralis/dsp/eq/psychoacoustic_eq.py:30,118`) imports and instantiates only `VectorizedEQProcessor`.
- **Evidence**: `grep -rn "ParallelSpectrumAnalyzer\|create_parallel_spectrum_analyzer" auralis auralis-web` → only self-definition. `grep -rn "ParallelEQProcessor" auralis auralis-web | grep -v /parallel_eq_processor/` → nothing.
- **Impact**: No functional impact, but ~570 combined lines of thread-pool/FFT-parallelism code sit alongside the genuinely-live equivalents, inviting future contributors to wire up the wrong one. Note that the closed #2890/#3433 smoothing-buffer race fix and #3685/#3659 dtype fixes were all spent hardening code nothing calls.
- **Siblings**: Same class as open #4565 (`auralis/optimization/parallel/`, 753 LOC, 5 fix commits on unreachable code).
- **Related**: ENG-D2-3, ENG-D6-4, ENG-D6-3.
- **Suggested Fix**: Fold these two files into the #4565 cleanup, or wire them into an actual call site if the parallelism was intended to be used.

#### ENG-D5-4: Fingerprint queue's semaphore capacity comment and log hardcode a stale "3"
- **Severity**: LOW
- **Dimension**: Parallel Processing
- **Location**: `auralis/services/fingerprint_queue.py:118-124`, `:391-394`
- **Status**: NEW
- **Description**: Comments at `:118` ("Generous limit: 1 semaphore per worker") and `:392` ("Only 3 workers can process audio simultaneously") describe a fixed limit of 3, and the debug log at `:394` literally hardcodes `/3`. The real capacity, constructed two lines later, is `ResizableSemaphore(max(8, max_workers))` — at least 8, scaling with `max_workers` (itself defaulting to `2.0× cpu_count`), so 16–48+ on a modern machine.
- **Impact**: Misleading debug output and comments only — the semaphore is correctly sized and used. A developer debugging apparent over-concurrency from these logs would look for the wrong ceiling.
- **Suggested Fix**: Change the log to `f"...{self.stats['processing']}/{self.processing_semaphore.capacity} in use)"` and update the stale "3" in both comments.

#### ENG-D6-2: `compute_windowed_fingerprint()`'s two branches use materially different windowing
- **Severity**: LOW (currently unreachable)
- **Dimension**: Analysis
- **Location**: `auralis/analysis/fingerprint/windowed_compute.py:103-198`
- **Status**: NEW
- **Description**: #4595 unified the batch and on-demand fingerprint paths into `compute_windowed_fingerprint()` specifically so two implementations could not disagree on windowing. But the function itself has two internal branches that disagree: when `audio is None` (fresh load) it uses the validated body-centered-at-50%-of-duration window plus 25%/75% probes; when the caller passes pre-loaded `audio`/`sr` it instead crops the **first 90 s from the start** with no centering and no probe-based LUFS/crest correction — exactly the less-accurate strategy #4595 eliminated elsewhere.
- **Evidence**: `windowed_compute.py:185` `audio = audio[..., :int(sr * 90.0)]` (unconditional start-crop) vs `:118` `_body_offset = min(_total_s * 0.50, ...)`. The multi-window LUFS/crest correction (`:220-248`) fires only when `_probe_audios` was populated, which only happens in the fresh-load branch.
- **Impact**: The docstring claims "Both paths now call `compute_windowed_fingerprint()`, so they cannot drift again" — but a caller passing pre-loaded audio would silently reintroduce the systematic negative-LUFS bias for ambient/intro-heavy tracks. **Reachability**: both production callers (`auralis/core/mastering_prepare.py:108`, `auralis/player/fingerprint_loader_mixin.py:82`) call `get_or_compute(path)` with no `audio`/`sr` argument, so the branch is dead today.
- **Suggested Fix**: Delete the pre-loaded-audio branch if no caller needs it, or make it extract probe sub-windows at 25%/50%/75% of the already-loaded buffer so both branches share one strategy.

#### ENG-D6-3: `ParallelSpectrumAnalyzer`'s sequential fallback doesn't reset `smoothing_buffer`
- **Severity**: LOW (class has zero production callers)
- **Dimension**: Analysis
- **Location**: `auralis/analysis/parallel_spectrum_analyzer.py:111-162`, vs the fixed sibling `auralis/analysis/base_spectrum_analyzer.py:285-295`
- **Status**: NEW (fourth instance of the #4539/#3448/#3433/#2890 pattern)
- **Description**: `SpectrumAnalyzer.analyze_file()` was hardened for #4539 to call `self.reset_smoothing()` at the top, because `smoothing_buffer` had already leaked across analysis-session boundaries three times before. `ParallelSpectrumAnalyzer` overrides `analyze_file()` independently (does not call `super()`) and never picked up that fix. When `num_chunks < min_chunks_for_parallel` or `enable_parallel=False`, it falls back to `_process_chunks_sequential()` → `_process_fft_to_spectrum()`, which reads and mutates `self.smoothing_buffer` exactly like the pre-#4539 code did.
- **Evidence**: `parallel_spectrum_analyzer.py:111-129` has no `reset_smoothing()` call, unlike `base_spectrum_analyzer.py:295`. The parallel branch (`_process_fft_no_smoothing`) correctly avoids the buffer per the #3433 fix; only the sequential fallback touches it unreset.
- **Impact**: Two short files analyzed back-to-back on one instance would smooth the second's first FFT frame against the first's trailing spectrum. **Reachability**: only `tests/validation/validate_parallel_quick.py` uses this class — zero production callers.
- **Related**: ENG-D5-3 (same file, dead-code angle).
- **Suggested Fix**: Add `self.reset_smoothing()` at the top of `ParallelSpectrumAnalyzer.analyze_file()`, matching the sibling fix, before this class gets a production caller.

#### ENG-D6-4: `RecordingTypeDetector` has zero production callers — confirmed dead code
- **Severity**: LOW (dead code)
- **Dimension**: Analysis
- **Location**: `auralis/core/recording_type_detector.py` (whole module)
- **Status**: NEW
- **Description**: `RecordingTypeDetector` (STUDIO/BOOTLEG/METAL categorical classification plus per-category parameter generation) is not imported by `HybridProcessor`, `ContinuousMode`, or any other production mastering path. Grepping outside `tests/` finds only three standalone offline scripts (`scripts/update_profile.py`, `scripts/rate_track.py`, `scripts/analyze_feedback.py`) plus the module itself. `tests/auralis/core/test_continuous_mode_target_integration.py:108` explicitly asserts `not hasattr(instance, 'recording_type_detector')`, confirming the removal was intentional and consistent with the retired-categorical architecture.
- **Impact**: None on live behaviour. Worth recording because the closed #4538 fix's "runs on every mastering pass" impact framing no longer describes current architecture — the fix is still correct, just unreachable. Flagging so future audits stop allocating severity budget to this file's categorical logic.
- **Related**: ENG-D2-3, ENG-D5-3.
- **Suggested Fix**: Remove `recording_type_detector.py` and its three offline-script consumers, or explicitly document it as a retained standalone tool outside the mastering pipeline.

#### ENG-D6-5: Degenerate-length audio crashes two quality-analysis internals via unguarded FFT/Hilbert calls
- **Severity**: LOW (no reachable unmitigated path)
- **Dimension**: Analysis
- **Location**: `auralis/analysis/quality_assessors/utilities/estimation_ops.py:44-49,358-360`; `auralis/analysis/phase_correlation.py:107-112`
- **Status**: NEW
- **Description**: Three functions slice audio to a "middle section" or directly Hilbert-transform it without checking for zero length. `estimate_thd`/`estimate_fundamental_frequency` compute `mid_start = len//4; mid_end = 3*len//4`, which yields an **empty** segment for `len(audio_mono)` in `{0, 1}`, and the subsequent `np.fft.rfft(audio_segment)` (no explicit `n=`) raises. `PhaseCorrelationAnalyzer._calculate_phase_correlation` calls `signal.hilbert(left[:_cap])` on a possibly-empty array; `analyze_correlation()` validates only `ndim==2 and shape[1]==2`, never minimum length.
- **Evidence**:
  ```
  >>> np.fft.rfft(np.array([]))        ValueError: Invalid number of FFT data points (0) specified.
  >>> scipy.signal.hilbert(np.array([]))  ValueError: N must be positive.
  ```
  Every current caller is mitigated: `mastering_file_evaluation.evaluate_mastering_files()` raises its own `ValueError` if `shared_frames < int(sample_rate * 0.4)` before calling `QualityMetrics` (so windows are ≥17,640 samples @44.1 kHz, far above the 4-sample threshold); `auralis/core/processing/continuous_mode.py:394` wraps the `compare_quality()` call in `except (ValueError, RuntimeError)`; `estimate_fundamental_frequency` has zero callers at all.
- **Impact**: None on any reachable path today. A latent landmine in shared utility code — the moment either function gets a new caller without matching length guards it crashes on exactly the pathological inputs (silence-trimmed buffers, 1-sample files) this audit checks for.
- **Siblings**: Both estimation functions share the identical `len//4`/`3*len//4` pattern with unguarded `rfft`.
- **Suggested Fix**: Add explicit minimum-length early returns at the top of `estimate_thd`, `estimate_fundamental_frequency`, and `_calculate_phase_correlation`/`analyze_correlation`, rather than relying on every current and future caller to enforce a large-enough window.

#### ENG-D7-3: `QueueTemplateRepository` — the 14th repository, wired into `RepositoryFactory` — has zero callers anywhere in the backend
- **Severity**: LOW
- **Dimension**: Library & Database
- **Location**: `auralis/library/repositories/factory.py:171-176`; `auralis/library/repositories/queue_template_repository.py` (374 lines, full CRUD + search)
- **Status**: NEW (distinct from #4604/#4294, which are about `_session_scope()` adoption, not reachability)
- **Description**: `QueueTemplateRepository` is fully implemented (create/get/update/delete/search/favorites/tags) and exposed via `RepositoryFactory.queue_templates`, but no router, service, or WebSocket handler ever calls it. The two closed issues that once touched this file (#2692 LIKE-escaping, #2249 unbounded `get_by_tag`) show it was worked on as if it mattered, but there is no live HTTP surface for it.
- **Evidence**: `grep -rln "queue_template" auralis-web/backend/` matches nothing outside PyInstaller `.toc` build artifacts; `grep -rln "template" auralis-web/backend/routers/` returns nothing.
- **Impact**: None at runtime. Flagged because — unlike `LibraryManager`, which is explicitly tracked as a deprecated facade (#4619) — this repository was never marked as retired, so a reader would reasonably assume it is exercised the way its 13 siblings are.
- **Related**: ENG-D2-3, ENG-D5-3, ENG-D6-4.
- **Suggested Fix**: Either add a *routers/queue_templates.py* (the model and repository already support the full feature) or remove the repository and its factory property, consistent with the project's no-dead-variants principle.

---

## Relationships

**Cluster A — "correct but unreachable" (7 findings, one root cause).**
ENG-D2-3, ENG-D5-2, ENG-D5-3, ENG-D6-3, ENG-D6-4, ENG-D7-3, and the reachability caveats on ENG-D1-4/5/6/7/14/15 all describe the same structural problem from different angles: substantial, carefully-hardened subsystems have no production callers, while the code users actually hear is a simpler chain that receives less audit and less engineering. Three separate dimensions reached this conclusion independently. Deciding the fate of each cluster (wire it up, or delete it) is a single architectural decision that would resolve roughly a third of this report.

**Cluster B — incomplete fixes on duplicated logic (5 findings).**
ENG-D1-9, ENG-D4-1, ENG-D6-1, ENG-D6-3, ENG-D7-2. Each is a closed issue whose fix landed on one of N copies of the same logic. In every case the DRY violation *is* the bug mechanism, and in ENG-D1-9's case the fixed copy is not even the default path. A grep-for-siblings step during fix verification would have caught all five. Note ENG-D7-2 is worse than the others: the fix is present in the source but is a semantic no-op on the project's actual database engine, so it reads as fixed to any inspection short of compiling the statement.

**Cluster C — hard thresholds in a continuous space (2 findings).**
ENG-D2-1 and ENG-D2-2 are the same defect class in two files. Both are on live paths and both directly contradict a stated architectural invariant. They should be fixed together with one shared smoothstep/soft-knee helper, not independently.

**Cluster D — contract drift between caller and callee (2 findings, both hard failures).**
ENG-D1-2 (dict-schema drift → `KeyError`) and ENG-D3-1 (method-name drift → `AttributeError`). Both are on live paths, both are deterministic, and both would have been caught by typed boundaries: a dataclass instead of a `dict` for ENG-D1-2, and an actual ABC/`runtime_checkable` Protocol conformance check instead of a structural `Protocol` for ENG-D3-1 (the `queue_protocols.py` Protocol currently makes the type checker *agree with the bug*).

**Cluster E — the copy-before-modify perimeter (1 merged finding, 8+6 sites).**
ENG-D1-3 consolidates every bypass path in the engine that returns a caller-owned array. Nothing corrupts today, but the invariant is the project's first stated rule and 8 sites deviate from it. The `no_op()` helper that exists to enforce it is used by 12 of 13 stages.

---

## Prioritized Fix Order

1. **ENG-D1-2** (`KeyError` on the `.25d` fast path) — one-line fix, deterministic hard failure on a live streaming path. Highest value per unit of effort in the report.
2. **ENG-D3-1** (`add_to_queue` does not exist) — one-line fix, breaks the most ordinary user action in the product. Add the integration test that would have caught it (the existing one skips on an empty library).
3. **ENG-D2-1 + ENG-D2-2** (hard thresholds in continuous space) — fix together with one shared soft-knee helper. These are the only findings that degrade what users *hear* on the default path.
4. **ENG-D7-1** (scanner timezone comparison) — silently wrong for every non-UTC user, with no diagnostic. Two-line fix plus a `TZ=`-parameterized regression test.
5. **ENG-D1-1** (WOLA head fade-in) — affects t=0 of every track through the live EQ path. The window-sum normalization fix also removes the residual COLA error, so it is worth doing properly rather than patching the first frame.
6. **ENG-D4-1** (per-chunk full-file decode) — O(n²) decode work on M4A/AAC/WMA today, and on *all* FFmpeg formats if the packaged build ships an older libsndfile. Verify the packaged AppImage's libsndfile version as part of this.
7. **ENG-D4-2** (byte-based OOM guard) — small change, closes a real crash class for hi-res masters, which are in this tool's core domain.
8. **Cluster A architectural decision** — before spending more time on `stages/`, `optimization/parallel/`, the `AdaptiveLimiter` chain, or `RecordingTypeDetector`, decide per-cluster: wire up or delete. This subsumes ENG-D2-3, ENG-D5-2, ENG-D5-3, ENG-D6-3, ENG-D6-4, ENG-D7-3 and changes the correct severity of ENG-D1-4, ENG-D1-5, ENG-D1-6, ENG-D1-7, ENG-D1-14, ENG-D1-15.
9. **ENG-D1-3** (copy-before-modify perimeter) — 8 one-line changes plus a shared `result is not input` test helper. Cheap, and it converts a latent CRITICAL class into a structurally-impossible one.
10. **Cluster B sweep** — ENG-D1-9, ENG-D6-1, ENG-D7-2 are each small; do them in one pass and add a "grep for siblings before closing" step to the fix-verification workflow.
11. **Remaining LOW findings** — opportunistic. ENG-D1-10 (crossfade comment) should be prioritized *within* this group because the wrong comment actively invites a harmful "fix".

---

## Coverage and Caveats

**All 7 declared dimensions were audited and produced output.** No dimension is missing from this report.

Per-dimension caveats carried forward verbatim from the dimension agents:

- **Dimension 1 (Sample Integrity)** — ran as two parallel halves (core mastering pipeline; `auralis/dsp/` + `auralis/io/`). ENG-D1-2's real-world hit rate could not be fully closed out: the code path is confirmed live, but the agent did not determine how often `mastering_targets` is non-`None` in ordinary playback. The orchestrator subsequently traced it to `chunked_processor.py:226` and confirmed it fires whenever a `.25d` sidecar exists — but the *fraction of a typical library that has sidecars* remains unmeasured.
- **Dimension 2 (DSP Pipeline)** — did not exhaustively verify monotonicity across the full 3D coordinate space; checked the axes individually and the compression bell specifically. A systematic sweep of the parameter space is still outstanding.
- **Dimension 3 (Player State)** — did not attempt to reproduce concurrency races under real thread contention; conclusions about lock discipline are from code reading plus the existing regression tests, not from stress runs.
- **Dimension 4 (Audio I/O)** — format testing used files generated in this environment with ffmpeg 8.0.1 / libsndfile 1.2.2. Behaviour on the packaged Electron/AppImage build's bundled libsndfile was **not** verified and is the key unknown for ENG-D4-1's blast radius.
- **Dimension 5 (Parallel Processing)** — `auralis-web/backend/core/chunked_processor.py` was deliberately left to the backend and concurrency audits; its threading model was characterized (serialized via `_processor_lock`, not parallel) but its broader correctness was not assessed here.
- **Dimension 6 (Analysis)** — #4508, #4510, #4630/#4629/#4626/#4625, and #4391 were noted as open but **not re-verified in depth** this pass. A full column-by-column check of fingerprint determinism across differing resample paths was not performed.
- **Dimension 7 (Library & Database)** — #2693 (missing DB indexes) was spot-checked on two newer tables only; a full column-by-column index audit was out of time budget. `#4333/#2144/#2672/#2930` (legacy `session.query()` usage) were not re-verified line by line since they are test-tree scope.

**Conflicting reports flagged rather than resolved** — see the ⚠ block under **ENG-D1-10**. Two dimensions of this audit and one backend audit dimension describe crossfade behaviour differently. They concern **different files**. The orchestrator independently re-read `auralis/core/mastering_chunk_loop.py:186-189` and confirms it is `sin²`/`cos²` (equal-gain) and that equal-gain is correct there. Anyone acting on #3878 must first establish which file they are changing and whether that file's overlap region is correlated or uncorrelated. Do not apply a fix derived from one report to the other file.

---

## Disproven Hypotheses (summary)

Roughly 70 candidate findings were investigated and discarded across the seven dimensions. The full per-dimension lists are worth preserving for the next audit; highlights:

- **Sample-count invariants**: all three mode handlers assert `processed.shape == target_audio.shape` post-limiter (#2519), `process_realtime_chunk` asserts length (#3792), `mastering_chunk_loop` asserts both `processed_chunk.shape[1] == chunk.shape[1]` (#3700) and `write_region.shape[1] == core_samples` (#2515). `sum(core_samples) == total_frames` was verified algebraically for every branch including the short-final-chunk case.
- **NaN/Inf from degenerate fingerprints**: traced every `_smooth_unit()` input back through the Rust `fingerprint_compute.rs`/`dsp_math.rs`. `estimate_lufs()` and `compute_crest_factor()` guard `rms < 1e-10`; `compute_frequency_distribution()` and `compute_bass_mid_ratio()` fall back to uniform/neutral. An all-zero or single-sample input cannot reach `ProcessingCoordinates` with a NaN/Inf.
- **`KeyError` on partial fingerprints in `continuous_space.py`**: every call site passes either `unpacker.as_dict()` (always 25 defaulted keys) or a fail-loud full schema. No partial dict can reach `map_fingerprint_to_space`.
- **GIL retention across PyO3**: all 11 `#[pyfunction]` wrappers in `vendor/auralis-dsp/src/py_bindings.rs` wrap heavy compute in `py.allow_threads(|| ...)` with `catch_unwind`.
- **Double-windowing (`cca59d9c`), EQ band-mapping-by-index (`2b3c5b35`/#4217), sub-bass parallel mix (`8bc5b217`), filter-floor (#4211), Nyquist clamping**: all re-read and confirmed intact.
- **`_generate_compression`'s Gaussian bell**: flagged as a possible monotonicity violation, then confirmed as an intentional, documented, everywhere-smooth bell — non-monotonicity is deliberate audio-engineering intent, not a discontinuity.
- **FFmpeg pipe deadlock, zombie processes, corrupt-file crashes, malformed-tag crashes, `shell=True` injection**: all disproven with live reproduction, not code comments.
- **`io/results.py` bit-depth math**: it contains none — repo-wide grep for `32767|32768|8388607|astype(np.int` returns zero arithmetic hits. All quantisation is libsndfile's, with correct asymmetric scaling, and all three write sites clamp first.
- **Library/DB**: N+1, `DetachedInstanceError`, SQL injection, the `if limit:` truthy-sentinel bug, migration atomicity/locking/backup (`sqlite3.Connection.backup()`, not `copy2`), WAL/pragma config, scan-slot accounting, `cleanup_missing_files` batching, and engine disposal ordering (#3769) were all re-verified against current source and found genuinely intact.
- **Player**: gapless rollback under `_audio_lock` (#4100/#4212), callback-outside-lock discipline at every notify site, and the `snapshot_index`/`rollback_index` navigation serialization (#3352/#3726/#3668) all hold.
- **Prior audit's ENG-D4-1 and ENG-D4-2** (ffprobe hardening on one wrapper; loader shape contract by extension): both re-checked and found *fixed* — the ffprobe `check_ffprobe()`/`FileNotFoundError` handling is present in both wrappers per #4119/#4540, and both loader backends now normalize mono and >2-channel sources before returning per #3672/#3743/#4597.
- **Prior audit's ENG-D5-1 and ENG-D5-2** (SmartCache `repr()` collision; fingerprint-queue drain-callback stall): both closed as #4524/#4596 and both fixes verified genuinely present — `_identify()` now hashes full array bytes via blake2b with an `UNCACHEABLE` sentinel, and `_on_worker_drained` thresholds on `len(self.workers)`.
- **Prior audit's ENG-D6-1 through ENG-D6-3** (fingerprint windowing divergence, centroid `* 20000`, smoothing-buffer reset): closed as #4595/#4538/#4539 and all three fixes verified present. This is a notable improvement over the prior audit, which found 11 closed issues that had never actually been fixed.

---

## Deduped, Not Re-Reported

**Open issues confirmed still accurate, not re-filed**: #4525 (unshuffle discards queue edits — re-confirmed present and unchanged), #4610 (legacy `auralis/core/config.py` dead/shadowed), #4502 (PyO3 channel-count from unvalidated axis), #4520 (Rust HPSS panics on sub-frame audio), #4613 (`AdaptiveConfig.critical_bands` unwired), #4615 (`RealtimeAdaptiveEQ` unwired), #4672 (no NaN/Inf validation before the PCM_16 encoder — re-confirmed: `np.clip` passes NaN through at both write sites, and `soft_clip` routes NaN into the tanh branch), #4592 (4 test-only engine modules), #4622 (40 DSP entry points defaulting `sample_rate=44100`), #4565 (`optimization/parallel/` dead), #4599 (Rust `estimate_tempo` naive DFT), #4631, #4334, #4333, #4633, #4604/#4294/#4291 (`_session_scope()` adoption — tracked debt), #4509, #4638/#4508, #4510, #4243, #4405, #4511/#4248/#4073 (god-file splits), #3770, #2693, #4391, #4335, #4259, #3878 (backend `apply_crossfade` mislabel — see the ⚠ note under ENG-D1-10), #4630/#4629/#4626/#4625.

**Closed issues re-verified as still fixed (not regressed)**: #4107, #3437, #2680/#2713/#2889/#3358, #3684, #3660, #4298, #4494/#2292/#2402/#2429/#2157/#2515, #3752, #3688, #3750, #3308, #2614/#3427/#4309, #2448, #2450/#3658/#3659/#3685, #2512, #2611, #2513, #3468, #3471, #3687, #3742/#4507, #3747/#3788/#3789, #2682/#2202, #4225 (partially — see ENG-D1-9), #4597, #4496, #4497 (metadata path only — see ENG-D4-1), #4128, #4119/#4540, #4109, #3672/#3743, #3749, #2529, #3671/#4220 (see ENG-D4-2), #4524, #4596, #2890/#3433, #3355, #2888, #3351, #4595, #4538, #4539, #3463/#3445/#3719, #4212/#4100, #3656/#3359/#3717/#3712/#3669/#3781/#4126, #3785, #2406/#2516/#4236/#4641, #3683/#4224, #2065/#2453/#4223, #4523, #2905, #3708/#3312, #3452/#3344/#2235, #4598, #2066, #3769, #3715, #2528, #3657, #2587, #4105, #4104, #4237, #4211, #4217, #4106, #4129, #3440, #4573, #3791, #3787, #3830, #2314, #2692, #2249.

**One issue reported as a regression**: #3339 — see ENG-D7-2. The fix is present in the source but is a semantic no-op on SQLite, so the race it claims to close is still open.

---

*Report generated by `/audit-engine` (7 dimension agents, deep depth) as part of the `comprehensive` audit suite. No source files were modified; no GitHub issues were created.*

**Next step**: `/audit-publish docs/audits/AUDIT_ENGINE_2026-07-29.md`

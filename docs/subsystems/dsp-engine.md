# Subsystem: DSP / Audio Processing Engine

The audio engine takes decoded PCM audio and returns mastered audio. This document is the
developer map of that engine: the entry points, how the mode processors relate, how a
track-level mastering plan is derived and consumed, and the invariants you must not break.

> **Scope.** The Python engine under [`auralis/core/`](../../auralis/core/) and
> [`auralis/dsp/`](../../auralis/dsp/), the Rust crate under
> [`vendor/auralis-dsp/`](../../vendor/auralis-dsp/), and the engine-facing streaming layer
> under [`auralis-web/backend/core/`](../../auralis-web/backend/core/). The network side
> (routers, WebSocket protocol, chunk cache, lifecycle) is in [backend-api.md](backend-api.md);
> fingerprint extraction and storage are in [fingerprinting.md](fingerprinting.md); the player's
> own light DSP chain is in [player.md](player.md).

---

## 1. Two engines: the shipped one and an offline CLI

| Engine | Entry point | Used by |
|--------|-------------|---------|
| **Shipped engine** | [`auralis/core/hybrid_processor.py`](../../auralis/core/hybrid_processor.py)`::HybridProcessor.process` | Streaming playback (per chunk) and whole-file processing jobs |
| **Offline CLI master** | [`auralis/core/simple_mastering.py`](../../auralis/core/simple_mastering.py)`::SimpleMasteringPipeline.master_file` | The root `auto_master.py` script only. Not on the app's audio path (§3) |

They share the audio invariants (§7) and some primitives, and almost no other code. There is no
third path: `auralis.dsp` exports nothing at the top level, so there is no DSP-package entry point
to call.

---

## 2. HybridProcessor: the shipped engine

`HybridProcessor` is a thin orchestrator. Construction
([`hybrid_setup.py::build_hybrid_components`](../../auralis/core/hybrid_setup.py)) wires the
analyzers, the `PsychoacousticEQ` behind an `EQProcessor`, the output brick-wall limiter, and the
three mode processors. Process-wide, instances are held by three separate caches: the module-level
convenience cache behind `auralis.process_adaptive` / `process_reference`
([`hybrid_processor_singleton.py`](../../auralis/core/hybrid_processor_singleton.py), 10 entries),
the backend's `ProcessorFactory` for streams (§6) and its `ProcessorPool` for jobs (default 5).

### The `process()` contract

`HybridProcessor.process(target, reference=None)` takes **decoded audio, not a path**.
[`hybrid_stage_dispatch.py::validate_and_normalize_input`](../../auralis/core/hybrid_stage_dispatch.py)
enforces the input, in this order:

1. A float `np.ndarray` shaped `(samples,)` or `(samples, channels)`. Any other type, a non-float
   dtype, more than two dimensions, or a channels-first array (at most `MAX_CHANNELS` = 8 rows and at
   least `MIN_SAMPLES` columns) raises `ValueError`.
2. Mono is expanded to stereo `(N, 2)` once, here, before anything else.
3. Empty input, input shorter than `MIN_SAMPLES` = 1024 samples, and digital silence
   (`|x| <= 1e-10`) return an unprocessed **copy**. Non-finite samples raise first
   (`validate_audio_finite(repair=False)`); a non-finite `reference` raises too.
4. DC offset is removed before any measurement
   ([`auralis/dsp/dc_blocker.py::remove_dc`](../../auralis/dsp/dc_blocker.py): a causal 2nd-order
   Butterworth high-pass at 5 Hz, so a chunk's output depends only on audio before it).

**Buffer rules.** The caller's array is never modified. DC removal produces a new array, which is
the engine's own working buffer. In adaptive mode `HybridProcessor` passes it to `ContinuousMode`
with `consume_input=True`, so the stages overwrite it in place rather than each holding another
whole-track copy; this is disabled when `config.quality_gate_enabled` is on, because the quality
comparison reads the original after the stages run. Every other path copies before modifying.

**Output.** Sample count equals the (stereo-expanded) input count, and the dtype follows the input.
[`finish_mode_output`](../../auralis/core/hybrid_stage_dispatch.py) is the tail every mode ends
with: the brick-wall limiter (§4), then a `RuntimeError` if the shape changed, then a fail-fast
finite check on the result.

**State and locking.** `process()` and every public setter hold `HybridProcessor._process_lock`
(an `RLock`). The EQ's band-gain smoothing, the limiter's gain-reduction state and the last
analysis persist across calls so consecutive chunks of one track stay continuous;
`reset_for_new_input()` returns the instance to the state of a fresh one (used for pooled jobs,
shared-instance calls and warm stream leases).

### Modes

`config.adaptive.mode` is one of `reference`, `adaptive` (default) or `hybrid`
([`config/settings.py::PROCESSING_MODES`](../../auralis/core/config/settings.py)); the bodies live in
[`processing/mode_dispatch.py`](../../auralis/core/processing/mode_dispatch.py).

| Mode | Implementation | Role |
|------|----------------|------|
| `adaptive` | [`ContinuousMode`](../../auralis/core/processing/continuous_mode.py) | The app's mastering path: streaming and jobs. Derives everything from the 25D fingerprint |
| `reference` | [`processors/reference_mode.py::apply_reference_matching`](../../auralis/core/processors/reference_mode.py) | RMS match to a reference array (bounded gain). Without a reference the dispatch raises `ValueError` |
| `hybrid` | [`HybridMode`](../../auralis/core/processing/hybrid_mode.py) | Reference matching blended with [`AdaptiveMode`](../../auralis/core/processing/adaptive_mode.py) output at weight `adaptation_strength * 0.5` (default 0.8, so 0.4); with no reference it runs `AdaptiveMode` alone |

`AdaptiveMode` (content analysis, `SpectrumMapper`, `AdaptiveTargetGenerator`) is reachable only
through `hybrid`. Streaming only ever runs `adaptive`; whole-file jobs
([`core/job_execution.py`](../../auralis-web/backend/core/job_execution.py)) can run all three.

### Presets and intensity

The only enhancement preset is **`adaptive`**
([`schemas/enhancement.py::VALID_PRESETS`](../../auralis-web/backend/schemas/enhancement.py)): REST
rejects any other value and WebSocket play commands ignore it with a warning. Do not re-add
named presets; `create_preset_profiles` in
[`config/preset_profiles.py`](../../auralis/core/config/preset_profiles.py) deliberately holds one
entry. `ContinuousMode` does not read the preset profile at all: the preset only keys the
processor cache and feeds the `hybrid` path (`AdaptiveMode`, `AdaptiveTargetGenerator`).
**Intensity** is not an engine parameter: it is a dry/wet blend of the processor's output with its input applied by
[`AudioProcessingPipeline.apply_enhancement`](../../auralis-web/backend/core/audio_processing_pipeline.py).

### The track-level mastering plan

One law turns a 25D fingerprint into mastering targets for every render path (streams, jobs, the
per-chunk fallback):
[`processing/mastering_targets.py::generate_targets_from_fingerprint`](../../auralis/core/processing/mastering_targets.py)
returns `target_lufs`, `source_lufs`, `target_crest_db`, `eq_curve_db` and `compression`.

- **Loudness** (`plan_level`): a 60 % move toward the streaming target (`STREAMING_TARGET_LUFS`,
  -14 LUFS). A boost is capped at the track's headroom to the -0.3 dBFS ceiling plus
  `CREST_BUDGET_DB` (0.5 dB), so a master already at full scale is not driven into the limiter;
  the peak is estimated per channel (`channel_peak_offset_db` from `phase_correlation`), a boost
  is also capped at `MAX_NORMALIZATION_GAIN_DB` (24) and fades out across the silence floor
  (-50 LUFS plus a 5 dB knee). An attenuation is never limited.
- **EQ** ([`parameter_generator_eq.py::eq_curve_from_fingerprint`](../../auralis/core/processing/parameter_generator_eq.py)):
  five gains from each band's share against a **center**: the corpus medians
  (`CORPUS_BAND_CENTERS` in [`dsp/constants.py`](../../auralis/dsp/constants.py)) or, when a
  reference cloud exists, the soft k-NN target
  ([`reference_cloud.py::ReferenceCloud`](../../auralis/core/processing/reference_cloud.py) and
  [`target_derivation.py`](../../auralis/core/processing/target_derivation.py), refreshed on a 60 s
  TTL). Each gain is `limit * tanh(delta_dB / 6)`, then saturated per band (low shelf ±5 dB,
  low-mid ±3, mid ±2, high-mid ±4, 2-4 kHz cut doubled and boost halved). The high shelf is held
  flat because the fingerprint's air band stops at 11 kHz (tracked by #6721, open).
- **Dynamics:** `compression.amount` is 0.0, so the clip-blend compressor does not run.
- **Stereo width:** not planned; the width target is unity (a no-op).

#### Analysis happens once per whole track

Fingerprinting is a property of the entire track; chunks only render the plan.

- **Streams.** `ChunkedAudioProcessor` construction calls
  [`MasteringTargetService.load_fingerprint`](../../auralis-web/backend/core/mastering_target_service.py)
  *before chunk 0* (database, then `.25d` sidecar, then a whole-track extraction deduplicated
  across callers). The plan is installed on the stream's `HybridProcessor` with
  `set_fixed_mastering_targets`; every chunk then runs `ContinuousMode` on those fixed targets and
  does not fingerprint anything. Targets are re-derived from the fingerprint on load, never trusted
  from a sidecar, and are cached per `(track, file signature)`.
- **Whole-file jobs.** `ContinuousMode` fingerprints the buffer once
  ([`fingerprint_preloaded`](../../auralis/analysis/fingerprint/preloaded_fingerprint.py): the whole
  buffer up to 900 s, a body window plus two probes beyond) and runs the stages over the whole file.
- **The one exception:** when whole-track extraction returns nothing for a track, the processor
  gets no fixed targets and `ContinuousMode` fingerprints each chunk on its own; the client is told
  analysis failed. A broken engine (`FingerprintUnavailable`) fails the stream or job instead.

### ContinuousMode stage sequence

`ContinuousMode.process` ([`continuous_mode.py`](../../auralis/core/processing/continuous_mode.py))
resolves `ProcessingParameters` (from fixed targets, or fingerprint, reference-cloud centers and
the targets law), then
[`continuous_stages.py::ContinuousStagesMixin._apply_dsp_stages`](../../auralis/core/processing/continuous_stages.py)
runs the ordered stages EQ, dynamics, stereo width, final normalization. Every stage is
measured by a `PipelineJournal`; after EQ, dynamics and stereo a
`CrossDimensionalGuard` compensation keeps the stage from disturbing a dimension it was not asked
to touch, each ramping in across a knee ([`continuous_guards.py`](../../auralis/core/processing/continuous_guards.py)):

| After | Guard | Limit |
|-------|-------|-------|
| EQ | LUFS drift compensation (drift knee 1-2 dB) | correction capped at ±3 dB |
| Dynamics | Spectral-tilt correction | capped at ±2 dB |
| Stereo width | Phase-correlation protection | blends up to 50 % toward mid |

Guards run when `config.enable_cross_dimensional_guard` is on (default). **Final normalization**
(`_apply_final_normalization`) applies ONE gain, `target_lufs - source_lufs` (±24 dB), to every
chunk, so a quiet verse and a loud chorus keep their relative level; then a sample-local look-ahead
limiter holds -0.3 dBFS. Targets without `source_lufs` (legacy dicts) fall back to per-chunk
K-weighted normalization. The coordinates from
[`ProcessingSpaceMapper`](../../auralis/core/processing/continuous_space.py) (spectral balance and
dynamic range) are telemetry for the processing-parameters endpoint; no parameter is derived from them.

> **Intentional divergence.** `ContinuousMode` owns its dynamics
> (`CompressionStrategies.apply_clip_blend_compression`). Do **not** add a second dynamics stage:
> it would double-compress and fight the loudness plan. Wiring dynamics settings into the offline
> pipeline is tracked by #5098 (open).

---

## 3. SimpleMastering: the offline CLI master

`SimpleMasteringPipeline` and everything it drives (`core/mastering_*.py`, `core/mastering_branches/`,
`core/stages/`, `core/dsp/`, `recording_type_detector.py`) form a **deliberately kept** offline
subsystem whose only caller is `auto_master.py`; the Electron app never reaches it. Treat findings
there as offline-tool bugs, and do not re-file it as dead code.

`master_file` ([`simple_mastering.py`](../../auralis/core/simple_mastering.py)) first converts
FFmpeg-only formats and sources with more than two channels to a temporary stereo WAV, then:

1. [`mastering_prepare.py`](../../auralis/core/mastering_prepare.py): fingerprint (via
   `FingerprintService`), resonance-notch detection, BS.1770 LUFS and crest of a representative
   window, and a whole-song peak pre-scan.
2. [`mastering_chunk_loop.py`](../../auralis/core/mastering_chunk_loop.py): 30 s chunks with an
   equal-gain crossfade at the seams, then a two-pass peak correction. (This crossfade is the CLI's
   own; the streaming path has none, §6.)
3. [`mastering_process_chunk.py::process_chunk`](../../auralis/core/mastering_process_chunk.py): an
   effective intensity from smooth crest and loudness curves (`calculate_intensity`, a multiplier
   between 0.5 and 1.2), a clip-prevention peak reduction when the peak is near 0 dBFS, then the
   one processing branch, then `sanitize_audio`.

There is one branch and no classification: a whole-track label never chooses a path.
[`mastering_branches/continuous.py::ContinuousMasteringBranch.apply`](../../auralis/core/mastering_branches/continuous.py)
runs resonance notches, makeup gain, bass, sub-bass, transient shaper, mid warmth, harmonic
exciter, clarity, presence, air, adaptive soft clip, stereo expansion, the loudness maximizer, and
a final file-level gain to a peak target (the whole-song peak, so section levels keep their
relationship). Per-stage strength comes from fingerprint measurements through bounded smooth
curves, never a step.

### Loudness maximizer

[`stages/loudness_maximizer.py`](../../auralis/core/stages/loudness_maximizer.py) lifts quiet,
high-crest material by trading crest factor for level: a file-level pre-gain into a brick-wall
limiter. The push is a softplus of the gap to an anchor, scaled by a closure factor, with no
category boundary. Constants live in
[`mastering_presets.py::MasteringPresetDefaults`](../../auralis/core/mastering_presets.py):

| Constant | Value | Meaning |
|----------|-------|---------|
| `LOUDNESS_TARGET_LUFS` | -14.5 | Anchor of the gap response; not the output LUFS |
| `LOUDNESS_RESPONSE_SOFTNESS_DB` | 0.75 | Width of the softplus transition |
| `LOUDNESS_GAP_CLOSURE_FACTOR` | 0.5 | Closes about half the gap, so quiet recordings stay relatively quieter |
| `LOUDNESS_MIN_CREST_DB` | 11.0 | Crest floor the push may not cross |
| `LOUDNESS_MAX_CREST_REDUCTION_DB` | 4.0 | Cap on crest reduction |
| `LOUDNESS_MAX_PUSH_DB` | 10.0 | Cap on the push gain |
| `LOUDNESS_LIMITER_CEILING_DB` / `_RELEASE_MS` | -1.0 / 60 | The stage's own limiter |

`SimpleMasteringConfig.TARGET_LUFS` (-11, `LOUD_MASTER_TARGET_LUFS`) anchors the adaptive makeup
gain and the optional before/after evaluation, not the maximizer. The limiter restarts per chunk,
so `LOUDNESS_LIMITER_RELEASE_MS` and `CROSSFADE_DURATION_SEC` are coupled and checked together in
`SimpleMasteringConfig.__post_init__`.

---

## 4. DSP primitives (`auralis/dsp/`)

| Module | Provides |
|--------|----------|
| [`basic.py`](../../auralis/dsp/basic.py) | `rms`, `normalize` (dtype-preserving), `amplify` (always copies), `mid_side_encode` / `mid_side_decode` |
| [`dc_blocker.py`](../../auralis/dsp/dc_blocker.py) | `remove_dc`, `remove_dc_dual_mono` (§2) |
| [`eq/psychoacoustic_eq.py`](../../auralis/dsp/eq/psychoacoustic_eq.py) | `PsychoacousticEQ`: 25 Bark-scale critical bands |
| [`dynamics/brick_wall_limiter.py`](../../auralis/dsp/dynamics/brick_wall_limiter.py) | `BrickWallLimiter`, `create_brick_wall_limiter` |
| [`dynamics/soft_clipper.py`](../../auralis/dsp/dynamics/soft_clipper.py) | `soft_clip` (offline CLI) |
| [`dynamics/compressor.py`](../../auralis/dsp/dynamics/compressor.py) | `AdaptiveCompressor` (the player's auto-master, see [player.md](player.md)) |
| [`utils/loudness_targets.py`](../../auralis/dsp/utils/loudness_targets.py) | Named loudness anchors and the limiter constants |

### Psychoacoustic EQ and the WOLA constraint

Each band's gain is the target curve times the band's perceptual weight, clipped to ±12 dB,
adapted to the content profile, then smoothed across calls
([`spectrum_gains.py`](../../auralis/dsp/eq/spectrum_gains.py)); the frame's own spectrum plays no
part. The EQ runs through weighted overlap-add in
[`processing/eq_curve.py::process_with_psychoacoustic_eq`](../../auralis/core/processing/eq_curve.py):
`fft_size` frames (4096) at a **fixed 50 % hop**, a full-Hann synthesis window, and a division by the
accumulated window weight (which also restores the first half-frame). `apply_eq_gains`
([`eq/filters.py`](../../auralis/dsp/eq/filters.py)) is deliberately **un-windowed**: the window
belongs to the overlap-add, not the filter. **Do not** re-introduce a configurable overlap, or add
a global magnitude offset, without re-deriving the COLA condition.

### Brick-wall limiter

`BrickWallLimiter` is a look-ahead peak limiter: a sliding maximum over the look-ahead, a gain
reduction ramped in linearly so the attack is not a step, then an exponential release. The output
stage uses `OUTPUT_PEAK_CEILING_DB` = -0.3 dBFS, `LIMITER_LOOKAHEAD_MS` = 2 and
`LIMITER_RELEASE_MS` = 50. Its running gain persists across `process()` calls (chunk continuity)
and is cleared by `reset()`. `process(audio, input_gain=...)` applies a linear gain inside the
limiter, which is how final normalization avoids a separate full-length gain copy.

---

## 5. Rust DSP module (`vendor/auralis-dsp/`)

The crate serves one purpose: the 25D fingerprint. It is built with `maturin develop` into the
in-process Python module `auralis_dsp`, whose only function is `compute_fingerprint`. Crate
contents, the PyO3 boundary contract and build commands are in
[RUST_DSP_STATUS.md](../features/RUST_DSP_STATUS.md); the Python glue and the schema mapping are in
[fingerprinting.md §2](fingerprinting.md#2-extraction-the-analyzer). There is no Python fallback:
without the wheel every fingerprint and every adaptive master fails, and startup logs and
`/api/health` report it. Do not add a binding without a production Python caller.

---

## 6. Chunked streaming (`auralis-web/backend/core/`)

### Geometry: single source of truth

All chunk geometry comes from
[`chunk_boundaries.py`](../../auralis-web/backend/core/chunk_boundaries.py):

```python
CHUNK_DURATION   = 15.0                          # each chunk is rendered over 15 s
OVERLAP_DURATION = 5.0                           # adjacent chunks share 5 s
CHUNK_INTERVAL   = CHUNK_DURATION - OVERLAP_DURATION   # 10.0: chunks start every 10 s
CONTEXT_DURATION = 5.0                           # extra audio loaded around a chunk
```

Never count chunks with `ceil(duration / CHUNK_DURATION)`. Use the overlap-aware
`content_chunk_count(total_duration)` (`max(1, ceil((total_duration - OVERLAP_DURATION) / CHUNK_INTERVAL))`),
or `normal_chunk_count()` for the no-overlap unprocessed stream.

### Chunk seams: no crossfade

Each chunk is rendered with `CONTEXT_DURATION` of context and trimmed to the segment it newly
contributes, so the emitted segments tile the timeline exactly: chunk 0 emits `[0, 15)` and every
later chunk emits 10 s (`emitted_chunk_start`, `emitted_chunk_length`). The full-file reassembly
path is a plain concatenation; crossfading there would double-blend and shorten the output. Level
smoothing between chunks is a serve-time step on the stream, not part of the cached chunk
([`chunk_render.py::process_chunk_core`](../../auralis-web/backend/core/chunk_render.py)).

### Processor leases

[`processor_factory.py::ProcessorFactory`](../../auralis-web/backend/core/processor_factory.py) is a
singleton LRU of `HybridProcessor` instances (cap 32, env `AURALIS_PROCESSOR_CACHE_MAX`) keyed on
`ProcessorCacheKey(track_id, preset, config_hash, targets_hash)`. Intensity is not in the key (it is
applied after the processor). A stream **leases** its instance
([`processor_lease.py`](../../auralis-web/backend/core/processor_lease.py): `acquire` pops it out of
the cache, `release_lease` returns it, `discard_lease` drops one whose state is untrustworthy), so
two streams of one track never feed one instance interleaved chunks, while one stream keeps its EQ
smoothing and limiter state across its own chunks. A warm instance is reset on `acquire`. The
config carries the track's real sample rate (`UnifiedConfig(internal_sample_rate=...)`), because
the chunk loader does not resample.

---

## 7. Critical invariants

| Invariant | Where enforced |
|-----------|----------------|
| **Sample count preserved** | `RuntimeError` (a raise, not an assert) in `finish_mode_output` after the limiter, in every mode; `AudioProcessingPipeline.apply_enhancement` re-checks per chunk |
| **Copy before modify** | The caller's array is never mutated; `amplify` / `normalize` copy; early returns return copies; the only in-place path is the engine's own consumed working buffer (§2) |
| **dtype** | `normalize` and the stages cast back to the input dtype; filters that upcast (`sosfiltfilt`) cast back |
| **No NaN/Inf** | Input and mode output fail fast (`validate_audio_finite(repair=False)`); in-stage repairs are bounded by `MAX_IN_STAGE_REPAIR_FRACTION` so a mostly corrupt buffer raises instead of becoming silence; `sanitize_audio` repairs the CLI's final output |
| **Clipping ceiling** | Brick-wall limiter at -0.3 dBFS; the PCM writer ([`io/saver.py`](../../auralis/io/saver.py)) clamps before encoding |
| **Mono to stereo** | Expanded once, explicitly, at `validate_and_normalize_input` |
| **Minimum size** | Fewer than `MIN_SAMPLES` = 1024 samples is returned unprocessed, not rejected |

The `verify-dsp` skill checks these across the pipeline.

---

## 8. Concurrency

`ProcessorFactory` hands one instance to one stream at a time, but the instance can still be
reached from several threads (`to_thread` workers, a cancelled chunk's abandoned thread), so:

- `HybridProcessor._process_lock` (`RLock`) guards `process()` and every public setter.
- `PsychoacousticEQ._state_lock` guards the gain buffers it smooths and resets; the fingerprint
  reference cloud has its own lock.
- `SimpleMasteringPipeline._process_lock` serialises `master_file` calls on one instance, since the
  per-file notch list is instance state.
- Do not add a mutator that changes a leased processor's targets: targets enter through
  `acquire(..., mastering_targets=...)`, which is part of the cache key.

---

## 9. Configuration (`auralis/core/config/`)

[`unified_config.py::UnifiedConfig`](../../auralis/core/config/unified_config.py):

| Knob | Default | Effect |
|------|---------|--------|
| `internal_sample_rate` | 44100 (`DEFAULT_SAMPLE_RATE`) | Rate every stage's band-to-bin math and K-weighting assumes; streams pass the track's real rate |
| `fft_size` | 4096 | Power of two; the EQ's frame size |
| `adaptive.mode` | `"adaptive"` | `reference`, `adaptive` or `hybrid` (§2) |
| `adaptive.adaptation_strength` | 0.8 | The EQ's gain-smoothing speed (`EQSettings.adaptation_speed`) and the `hybrid` blend weight (halved) |
| `mastering_profile` | `"adaptive"` | The only preset |
| `enable_cross_dimensional_guard` | `True` | `ContinuousMode` per-stage compensation |
| `quality_gate_enabled` / `quality_gate_interval` | `False` / 5 | Opt-in advisory before/after measurement on every Nth call; nothing reads it in production |

---

## 10. Mastering recommendation (advisory)

[`auralis/analysis/adaptive_mastering_engine.py`](../../auralis/analysis/adaptive_mastering_engine.py)
`::AdaptiveMasteringEngine` classifies a track against seven built-in
[`MasteringProfile`](../../auralis/analysis/mastering_profile.py)s
([`mastering_profiles_builtin.py`](../../auralis/analysis/mastering_profiles_builtin.py)). The input is the
7-field `MasteringFingerprint` ([`mastering_fingerprint.py`](../../auralis/analysis/mastering_fingerprint.py):
loudness, peak, crest, centroid, rolloff, zero-crossing rate, spectral spread), not the 25D one.
`recommend_weighted` returns the best profile with a confidence score and, when confidence is below
the threshold (default 0.4), a confidence-weighted blend of the top profiles, with the predicted
loudness, crest and centroid change.

It is **advisory and does not drive processing**. Its one consumer is
`GET /api/player/mastering/recommendation/{track_id}`
([`services/recommendation_analysis.py`](../../auralis-web/backend/services/recommendation_analysis.py),
cached per track and threshold). The audio path takes its parameters from §2.
[`reference_profile.py`](../../auralis/analysis/reference_profile.py) (PLR, crest over time, per-band
width) is a separate measurement used by the reference bench script, not by the engine.

---

## 11. Where to start reading

1. [`hybrid_processor.py`](../../auralis/core/hybrid_processor.py) and
   [`hybrid_stage_dispatch.py`](../../auralis/core/hybrid_stage_dispatch.py): the orchestrator and
   the input contract.
2. [`mastering_targets.py`](../../auralis/core/processing/mastering_targets.py): the plan.
3. [`continuous_mode.py`](../../auralis/core/processing/continuous_mode.py) and
   [`continuous_stages.py`](../../auralis/core/processing/continuous_stages.py): the stages.
4. [`chunk_boundaries.py`](../../auralis-web/backend/core/chunk_boundaries.py): chunk geometry
   (small, foundational).

## 12. Deleted paths

Each was reachable-looking but unreachable or wrong to connect. The paths are italicised because
they no longer exist: "this looks like a missing wire-up" is the tempting wrong move on each.

| Deleted | Do not re-add because |
|---|---|
| `RealtimeDSPPipeline`, `RealtimeAdaptiveEQ`, `AdaptiveLimiter` (*auralis/dsp/realtime_adaptive_eq/*, *auralis/core/processing/realtime_dsp_pipeline.py*, *auralis/dsp/dynamics/limiter.py*) | Its EQ applied block FFT gain with no window and no overlap-add, so it was never WOLA-safe (#4873, #4615) |
| *auralis/dsp/stages.py::main()*, exported as `auralis.dsp.main` | A Matchering-lineage reference matcher with no caller in the app, the CLI, the scripts or any test (#4867) |
| `DynamicsProcessor`, `DynamicsManager`, `reset_dynamics()` | `HybridProcessor` had no `process()` caller for them; a second dynamics stage in `ContinuousMode` would double-compress against the loudness plan (#6201, #5098). Guarded by `tests/regression/test_dynamics_processor_wiring.py` |
| `MaterialClassifier` and its categorical branches (*compressed_loud*, *dynamic_loud*, *quiet*) | A whole-track label must not choose a path or gate processing; every source runs the one continuous branch |
| The `needs_output_normalize` third stage of `process_chunk` | The only branch self-normalizes; a second normalize double-normalizes |
| `ProcessingParameters` fields no stage read | Every field is pinned to a reader by `tests/auralis/core/test_processing_parameters_have_readers_5576.py` |

---

**Related:** [fingerprinting.md](fingerprinting.md) · [backend-api.md](backend-api.md) ·
[player.md](player.md) · [../architecture/data-flow.md](../architecture/data-flow.md)

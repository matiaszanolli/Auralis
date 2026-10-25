# Subsystem: DSP / Audio Processing Engine

The audio engine is the heart of Auralis: it takes decoded PCM audio and produces
mastered output, in both **offline** (whole-file) and **real-time** (streaming chunk)
modes. This document is the developer map of that engine — where the entry points are,
how the mode processors relate, and the invariants you must not break.

> **Scope.** Core Python engine under [`auralis/core/`](../../auralis/core/) and
> [`auralis/dsp/`](../../auralis/dsp/), the Rust DSP module under
> [`vendor/auralis-dsp/`](../../vendor/auralis-dsp/), and the streaming layer under
> [`auralis-web/backend/core/`](../../auralis-web/backend/core/). For how audio reaches
> the engine over the network, see [backend-api.md](backend-api.md).

---

## 1. Two top-level pipelines — do not conflate them

There are **two independent top-level engines**. They share the core invariants
(copy-before-modify, preserve sample count, return `np.ndarray`) but almost no code.

| Engine | Class | File | Used by |
|--------|-------|------|---------|
| **Streaming / real-time master** | `HybridProcessor` | [`auralis/core/hybrid_processor.py`](../../auralis/core/hybrid_processor.py) | Web backend, live playback |
| **Offline / batch file master** | `SimpleMasteringPipeline` | [`auralis/core/simple_mastering.py`](../../auralis/core/simple_mastering.py) | CLI / batch file mastering |

There is no third path. A legacy Matchering-derived reference matcher
(*auralis/dsp/stages.py::main()*) used to sit alongside these, exported as
`auralis.dsp.main`; #4867 deleted it after confirming it had no caller in the
app, the offline CLI, the scripts, or any test. A `RealtimeDSPPipeline` mode
also used to exist; #4873 deleted it — see [§ Deleted paths](#deleted-paths).

---

## 2. HybridProcessor — the streaming engine

`HybridProcessor` is a thin orchestrator. Its constructor
([`hybrid_processor.py::HybridProcessor.__init__`](../../auralis/core/hybrid_processor.py)) wires up the analysis
and DSP components and instantiates **three mode processors**:

```
HybridProcessor.process()            # offline, whole-signal
  └─ _process_impl                   # under self._process_lock (RLock)
       ├─ _process_reference_mode    # reference present
       ├─ _process_adaptive_mode     # adaptive
       │    └─ ContinuousMode.process()
       └─ _process_hybrid_mode       # reference + adaptive
```

### Mode processors (`auralis/core/processing/`)

| Mode | Class | File | Role |
|------|-------|------|------|
| **Continuous** (default adaptive) | `ContinuousMode` | [`continuous_mode.py`](../../auralis/core/processing/continuous_mode.py) | Maps the 25D fingerprint → 3D processing space → continuous `ProcessingParameters`. Used for the adaptive mode. |
| **Adaptive** (legacy) | `AdaptiveMode` | [`adaptive_mode.py`](../../auralis/core/processing/adaptive_mode.py) | Preset/spectrum-based component of the `hybrid` and `reference` modes. |
| **Hybrid** | `HybridMode` | [`hybrid_mode.py`](../../auralis/core/processing/hybrid_mode.py) | Blends reference matching with adaptive output at `adaptation_strength * 0.5`. |

**Mode selection** is one axis — `config.adaptive.mode` (`reference` / `adaptive` /
`hybrid`); adaptive runs `ContinuousMode`. (A second, "latency" axis
(`process_realtime_chunk()` → `RealtimeDSPPipeline`) used to exist; #4873 deleted it —
see [§ Deleted paths](#deleted-paths). The streaming hot path calls the same
`process()` per chunk, off the event loop via `asyncio.to_thread`.)

### ContinuousMode internals (the default path)

`ContinuousMode.process()`
([`continuous_mode.py::ContinuousMode.process`](../../auralis/core/processing/continuous_mode.py)) has:

- A **fast path** — if a `.25d` sidecar supplies `fixed_params`, it skips fingerprint
  extraction (~8× faster).
- A **full path** — extract fingerprint →
  `map_fingerprint_to_space` → optional reference-cloud target derivation →
  `generate_parameters`.

Each DSP stage (`_apply_dsp_stages`, [`continuous_stages.py::ContinuousStagesMixin`](../../auralis/core/processing/continuous_stages.py))
is followed by a **CrossDimensionalGuard** compensation step that caps unintended drift
(EQ LUFS drift ±1.5 dB / hard cap ±3 dB; dynamics spectral-tilt; stereo phase-correlation;
normalization crest-crush pullback), journaled via `PipelineJournal`. A sampled **quality
gate** runs every Nth chunk (`quality_gate_interval`).

> **Intentional divergence.** ContinuousMode uses its **own** offline dynamics
> (`CompressionStrategies.apply_clip_blend_compression`), *not* the real-time
> `DynamicsProcessor`. Routing the real-time processor (which targets −14 LUFS with makeup
> gain) into the offline chain would double-compress and fight the LUFS target (#2897).
> The clip-blend threshold/ceiling are fractions of the chunk's own peak (referenced to 1.0 for
> over-range peaks), so the compression follows the material's dynamics rather than the file's
> level (#5576); only `ratio` and `amount` drive it — the generated `threshold`/`attack`/`release`
> are reporting values.

---

## 3. SimpleMastering — the offline file masterer

`SimpleMasteringPipeline.master_file()`
([`simple_mastering.py::SimpleMasteringPipeline.master_file`](../../auralis/core/simple_mastering.py)) processes files in
chunks for memory efficiency. Each chunk flows through
`mastering_process_chunk.process_chunk`
([`mastering_process_chunk.py::process_chunk`](../../auralis/core/mastering_process_chunk.py)):

1. Unpack 25D fingerprint → `calculate_intensity` (2D crest × LUFS interpolation, clamped
   0.5–1.2).
2. **Stage 1** — gentle clip-prevention peak reduction.
3. **Stage 2** — `ContinuousMasteringBranch.apply` — one measurement-driven path, no
   classification step.
4. **Stage 3** — unified output normalize (only when `needs_output_normalize`).
5. `sanitize_audio`.

### The continuous path (`mastering_branches/`)

There is **one** branch. The former `MaterialClassifier` and its three categorical branches
(*compressed_loud*, *dynamic_loud*, *quiet*, selected by LUFS/crest thresholds) were
deleted — a whole-track label no longer chooses a path or gates processing. Every source
runs the same chain; per-stage strength is derived numerically from the fingerprint.

[`ContinuousMasteringBranch`](../../auralis/core/mastering_branches/continuous.py) applies,
in order:

1. Adaptive makeup gain → 2. bass enhancement → 3. sub-bass control → 4. mid warmth →
5. presence + air → 6. adaptive soft clipping (multi-dimensional) → 7. stereo width
expansion → 8. peak normalize to target LUFS.

Stage strengths come from `ProcessingSpaceMapper`
([`continuous_space.py`](../../auralis/core/processing/continuous_space.py)), which maps
the 25D fingerprint onto three continuous axes — spectral balance, dynamic range, energy
level. Each axis is mapped through a bounded `tanh` so no measurement can produce a step
change or an unbounded parameter.

> **Gotcha.** The continuous path **self-normalizes**: it ends in a branch-local
> `normalize` and therefore sets `needs_output_normalize = False`
> ([`continuous.py::ContinuousMasteringBranch.apply`](../../auralis/core/mastering_branches/continuous.py)). Stage 3 is
> consequently dormant for the only branch that exists. The Stage-3 mechanism in
> [`mastering_process_chunk.py`](../../auralis/core/mastering_process_chunk.py) is
> retained for future paths — a new branch that does *not* self-normalize must set the flag
> `True`, and one that does must not, or the output **double-normalizes**.

### Presets belong to HybridProcessor, not SimpleMastering

The named presets **Adaptive / Gentle / Warm / Bright / Punchy / Live** live in
[`auralis/core/config/preset_profiles.py::create_preset_profiles`](../../auralis/core/config/preset_profiles.py)
and are consumed by the **HybridProcessor** path. SimpleMastering is fingerprint/branch-driven
with a single `SimpleMasteringConfig` — its knobs are LUFS targets and tolerance bands, not
the named presets.

### The loudness maximizer (most-churned tuning area)

In `QuietBranch`, the loudness maximizer is the load-bearing tuning surface. Constants in
[`mastering_config.py`](../../auralis/core/mastering_config.py):

| Constant | Value | Meaning |
|----------|-------|---------|
| `TARGET_LUFS` | −11.0 | Overall SimpleMastering target |
| `LOUDNESS_COMPETITIVE_LUFS` | −14.0 | No-op at/above this |
| `LOUDNESS_TARGET_LUFS` | −14.5 | Push anchor (recalibrated 2026-07-10 from −12.5 to fix overdrive) |
| `LOUDNESS_GAP_CLOSURE_FACTOR` | 0.5 | Closes only ~50% of the source loudness gap |
| `LOUDNESS_MIN_CREST_DB` | 11.0 | Crest floor |
| `LOUDNESS_MAX_CREST_REDUCTION_DB` | 4.0 | Max crest reduction |

> **Why gap-closure = 0.5:** quiet/vintage recordings should stay *relatively* quieter, not
> converge to one target loudness. Closing only half the gap preserves era/recording
> character. This is deliberately *not* full normalization.

---

## 4. DSP primitives (`auralis/dsp/`)

| Module | Provides |
|--------|----------|
| [`basic.py`](../../auralis/dsp/basic.py) | `rms`, `normalize` (dtype-preserving), `amplify` (always `.copy()` first), `mid_side_encode` / `mid_side_decode` |
| [`advanced_dynamics.py`](../../auralis/dsp/advanced_dynamics.py) | `DynamicsProcessor` (gate + compressor + limiter, content-aware, RLock-guarded chain). Auto makeup-gain = `-threshold/ratio` capped at 12 dB |
| [`eq/psychoacoustic_eq.py`](../../auralis/dsp/eq/psychoacoustic_eq.py) | `PsychoacousticEQ` — 26 Bark-scale critical bands, masking model, adaptive gains clipped ±12 dB |

### The WOLA / COLA constraint (read before touching the EQ)

`PsychoacousticEQ` uses Weighted OverLap-Add reconstruction. The hop is **fixed at 50%**
with a full-Hann synthesis window for COLA-correct reconstruction (#4217). **Do not
re-introduce a configurable overlap** without re-deriving the COLA condition.

The analysis FFT is Hann-windowed **with coherent-gain compensation**, but `apply_eq_gains`
is deliberately **un-windowed** (#4101 / #3663). They process different frames; the asymmetry
is intentional — do not "fix" it. Adding a global magnitude offset re-triggers skewed
adaptive gains and fingerprint LUFS/crest errors (#3428 / #2518).

---

## 5. Rust DSP module (`vendor/auralis-dsp/`)

Built with `maturin develop` (PyO3 0.29 + numpy 0.29, crate `auralis_dsp`). Two separate
Rust surfaces existed; one is gone:

1. **In-process PyO3 module** `auralis_dsp` (the live one) — the full 25D `compute_fingerprint`
   (plus `process_chunks`, which is dead, #5738). The HPSS, YIN, tempo, envelope, compress/limit,
   multiband-EQ and onset bindings were removed in #5764 (no production caller). Registered in
   [`src/py_bindings.rs`](../../vendor/auralis-dsp/src/py_bindings.rs).
2. **Standalone gRPC fingerprint server** — **removed** (2026-07-11, streamlining
   #12). It was abandoned and non-functional (stub compute, gRPC-vs-HTTP client
   mismatch, never launched); `vendor/auralis-dsp/src/bin/` no longer exists.
   The PyO3 bindings above are the only fingerprint path. See
   [fingerprinting.md §7](fingerprinting.md#7-performance).

### The PyO3 boundary contract

- **dtype is per-function and strict.** `compute_fingerprint` takes a mono **f32** `(n,)` array (the caller
  passes the channel count); `process_chunks` takes **f64** channels-first `(channels, n)`.
- **Every** heavy wrapper releases the GIL (`py.allow_threads(...)`, #2447) and wraps compute
  in `catch_unwind`, converting Rust panics into a readable `PyRuntimeError` (#2225) rather
  than crashing the interpreter.

### No Python fallback

The Rust FFI entry point
([`auralis/analysis/fingerprint/rust_fingerprint.py`](../../auralis/analysis/fingerprint/rust_fingerprint.py))
is **Rust-only**. (It replaced the `DSPBackend` wrapper that lived in the fingerprint
utilities package, removed in streamlining #13 along with that whole package.) `initialize()` raises `RuntimeError` at import if `auralis_dsp` can't be
imported — the old librosa fallback was removed. `_validate_ffi_inputs` rejects empty arrays /
`sr <= 0` and coerces to float64 before every FFI call (#2521) to prevent Rust panics.

> If you see `RuntimeError: ... auralis_dsp` at startup, you skipped
> `cd vendor/auralis-dsp && maturin develop`.

---

## 6. Chunked streaming (`auralis-web/backend/core/`)

### Geometry — single source of truth

All chunk geometry comes from
[`chunk_boundaries.py`](../../auralis-web/backend/core/chunk_boundaries.py):

```python
CHUNK_DURATION  = 15.0   # each chunk covers 15 s
CHUNK_INTERVAL  = 10.0   # chunks start every 10 s
OVERLAP_DURATION = 5.0   # → adjacent chunks overlap 5 s
CONTEXT_DURATION = 5.0   # extra context loaded on each side
```

Chunk N covers `[N*10, N*10+15]`. **Never** count chunks with naive
`ceil(duration / CHUNK_DURATION)` — use the overlap-aware
`content_chunk_count(total_duration) = max(1, ceil((total_duration - OVERLAP_DURATION) / CHUNK_INTERVAL))`
([`chunk_boundaries.py::content_chunk_count`](../../auralis-web/backend/core/chunk_boundaries.py), #4124). It is
the authoritative counter.

### Chunk seams (no crossfade)

There is no crossfade math. Each chunk is rendered with `CONTEXT_DURATION` of
context and trimmed to a non-overlapping `CHUNK_INTERVAL` segment, so the emitted
segments tile the timeline exactly (#4642). The full-file reassembly path
(`get_full_processed_audio_path`) is a plain `np.concatenate` for the same reason;
crossfading there double-blended and shortened output by (N−1)×5 s (#2750). The
unused crossfade helper that survived #4642 was deleted in #5776.

### ProcessorFactory lifecycle

[`processor_factory.py::ProcessorFactory`](../../auralis-web/backend/core/processor_factory.py) is a
singleton LRU cache (cap 32, env `AURALIS_PROCESSOR_CACHE_MAX`) keyed on a 5-tuple
`ProcessorCacheKey(track_id, preset, intensity, config_hash, targets_hash)`. It hands the
**same HybridProcessor instance** to every chunk of a `(track, preset, intensity)` so
compressor envelope followers and EQ smoothing don't reset at chunk boundaries. Eviction
calls `.close()` to release the fingerprint analyzer's 5-thread executor (#3746).

> This shared-instance reuse is **why** the locking in §8 is load-bearing.

---

## 7. Critical invariants (enforced, not aspirational)

| Invariant | Where enforced |
|-----------|----------------|
| **Sample count preserved** | `RuntimeError` (raise, not assert — #5533) after the brick-wall limiter in every mode handler: `_process_adaptive_mode` / `_process_hybrid_mode` ([`hybrid_processor.py`](../../auralis/core/hybrid_processor.py)) and `process_reference_mode` ([`hybrid_stage_dispatch.py`](../../auralis/core/hybrid_stage_dispatch.py)) |
| **Copy before modify** | `amplify` / `normalize` copy; every branch `apply()` starts `processed = audio.copy()`; silent/empty early-returns return copies |
| **dtype propagation** | `normalize` explicit `astype(audio.dtype)` (#3687); spectral-tilt casts back after `sosfiltfilt` upcasts to f64; zero-pad/silence fallbacks preserve dtype |
| **No NaN/Inf** | `validate_audio_finite(repair=False)` fails fast on input and mastering output; `sanitize_audio` repairs realtime/streaming output; silence early-returns avoid `log(0)`→NaN |
| **Clipping ceiling** | Brick-wall limiter at −0.3 dB; continuous-mode emergency peak-limit to −0.3 dBFS; PCM clamp in [`auralis/io/results.py`](../../auralis/io/results.py) |
| **Mono → stereo** | Expanded once, explicitly, at `HybridProcessor` entry (`hybrid_stage_dispatch.py::validate_and_normalize_input`, before mode dispatch) |
| **Min buffer size** | Audio below `MIN_SAMPLES = 1024` (`hybrid_stage_dispatch.py`) is returned unprocessed, not rejected (#4520) — no Rust FFT panics to guard against since #5764 |

See [../development/verify-dsp](../../auralis/) — or run the `verify-dsp` skill — to check
these six invariants across the pipeline.

---

## 8. Concurrency (load-bearing)

Because `ProcessorFactory` shares one `HybridProcessor` across concurrent streams:

- `HybridProcessor._process_lock` (RLock) guards `process()` **and every public setter**
  (#3714 / #3787).
- The chunked path additionally acquires `processor._process_lock` when toggling
  `content_analyzer.use_fingerprint_analysis` because that flag is shared across
  `ChunkedAudioProcessor` instances (#3808).
- Inner components carry their own locks: `DynamicsProcessor._lock` (#3789),
  `PsychoacousticEQ._state_lock` (#3747), `RealtimeAdaptiveEQ._lock` (#3788).
- `SimpleMasteringPipeline._notches` is per-file mutable instance state, guarded by an RLock
  to prevent cross-file contamination between concurrent `master_file` calls (#3715).

There are **two separate processor caches**: the module-level convenience cache in
`hybrid_processor.py` (max 10) and the web backend's `ProcessorFactory` (max 32). Both call
`.close()` on eviction.

---

## 9. Configuration (`auralis/core/config/`)

`UnifiedConfig`
([`unified_config.py::UnifiedConfig`](../../auralis/core/config/unified_config.py)) — key knobs:

| Knob | Default | Effect |
|------|---------|--------|
| `internal_sample_rate` | 44100 | Internal processing rate |
| `fft_size` | 4096 | Asserted power of 2 |
| `mastering_profile` | `"adaptive"` | Named preset |
| `enable_cross_dimensional_guard` | `True` | ContinuousMode per-stage compensation |
| `quality_gate_enabled` / `quality_gate_interval` | `True` / 5 | Sampled quality gate |

---

## 10. Where to start reading

1. [`hybrid_processor.py`](../../auralis/core/hybrid_processor.py) — the orchestrator and
   mode dispatch.
2. [`continuous_mode.py`](../../auralis/core/processing/continuous_mode.py) — the default
   adaptive algorithm.
3. [`chunk_boundaries.py`](../../auralis-web/backend/core/chunk_boundaries.py) — chunk
   geometry (small, foundational).
4. [`mastering_branches/`](../../auralis/core/mastering_branches/) — the offline
   signal path and tuning constants: `base.py` (abstract contract), `continuous.py` (the
   single path), `soft_clip_params.py`.

## 11. Deleted paths

Both were reachable-looking but unreachable, and both are recorded here because
"this looks like a missing wire-up, let me connect it" is the tempting wrong
move on each.

| Path | Removed by | Why not wired up instead |
|---|---|---|
| `RealtimeDSPPipeline` + `RealtimeAdaptiveEQ` + `AdaptiveLimiter` (*auralis/dsp/realtime_adaptive_eq/*, *auralis/core/processing/realtime_dsp_pipeline.py*, *auralis/core/hybrid/realtime_manager.py*, *auralis/dsp/dynamics/limiter.py*) | #4873 | Its EQ applied block FFT gain with **no window and no overlap-add** (#4615) — never WOLA-safe, so it could not simply be switched on. See the COLA constraint above. |
| *auralis/dsp/stages.py::main()*, exported as `auralis.dsp.main` | #4867 | A Matchering-2.0-lineage reference matcher with zero callers in the app, the offline CLI, the scripts, or any test. Its only would-be test imported three class names that never existed in the file, so it skipped on every run. |

Deleting the realtime pipeline left `HybridProcessor.dynamics_processor` with no
`process()` caller — it survives only behind `reset_dynamics()` /
`set_dynamics_mode()` / `get_dynamics_info()`. Do **not** "fix" that by inserting
it into `ContinuousMode`: that would double-compress and fight the
continuous-space LUFS target. Guarded by
`tests/regression/test_dynamics_processor_wiring.py`.

---

**Related:** [fingerprinting.md](fingerprinting.md) ·
[backend-api.md](backend-api.md) · [../architecture/data-flow.md](../architecture/data-flow.md)

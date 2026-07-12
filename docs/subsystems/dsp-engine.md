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
| **Streaming / real-time master** | `HybridProcessor` | [`auralis/core/hybrid_processor.py:44`](../../auralis/core/hybrid_processor.py) | Web backend, live playback |
| **Offline / batch file master** | `SimpleMasteringPipeline` | [`auralis/core/simple_mastering.py:40`](../../auralis/core/simple_mastering.py) | CLI / batch file mastering |

A third, older path — [`auralis/dsp/stages.py:27`](../../auralis/dsp/stages.py) `main()` —
is the legacy Matchering-derived **reference matcher** (loudness/RMS/crest analysis →
gain match → soft-clip → normalize). It is largely standalone from the mode processors
below.

---

## 2. HybridProcessor — the streaming engine

`HybridProcessor` is a thin orchestrator. Its constructor
([`hybrid_processor.py:54`](../../auralis/core/hybrid_processor.py)) wires up the analysis
and DSP components and instantiates **four mode processors**:

```
HybridProcessor.process()            # offline, whole-signal  (hybrid_processor.py:220)
  └─ _process_impl                   # under self._process_lock (RLock)
       ├─ _process_reference_mode    # reference present      (:298)
       ├─ _process_adaptive_mode     # adaptive               (:323)
       │    ├─ ContinuousMode.process()   # default (use_continuous_space=True)
       │    └─ AdaptiveMode.process()     # legacy fallback
       └─ _process_hybrid_mode       # reference + adaptive    (:379)

HybridProcessor.process_realtime_chunk()   # real-time chunk   (:406)
  └─ RealtimeDSPPipeline.process_chunk()    # low-latency path
```

### Mode processors (`auralis/core/processing/`)

| Mode | Class | File | Role |
|------|-------|------|------|
| **Continuous** (default adaptive) | `ContinuousMode` | [`continuous_mode.py:83`](../../auralis/core/processing/continuous_mode.py) | Maps the 25D fingerprint → 3D processing space → continuous `ProcessingParameters`. Selected when `config.use_continuous_space=True`. |
| **Adaptive** (legacy) | `AdaptiveMode` | [`adaptive_mode.py:33`](../../auralis/core/processing/adaptive_mode.py) | Preset/spectrum-based path used only when `use_continuous_space=False`. |
| **Hybrid** | `HybridMode` | [`hybrid_mode.py:21`](../../auralis/core/processing/hybrid_mode.py) | Blends reference matching with adaptive output at `adaptation_strength * 0.5`. |
| **Realtime** | `RealtimeDSPPipeline` | [`realtime_dsp_pipeline.py:31`](../../auralis/core/processing/realtime_dsp_pipeline.py) | Quick content analysis → realtime adaptive EQ → dynamics. Low latency. |

**Mode selection** is two orthogonal axes:

- **Algorithm axis** — `config.adaptive.mode` (`reference` / `adaptive` / `hybrid`) plus
  `config.use_continuous_space` (Continuous vs legacy Adaptive).
- **Latency axis** — offline (`process()`) vs real-time (`process_realtime_chunk()`).

### ContinuousMode internals (the default path)

`ContinuousMode.process()`
([`continuous_mode.py:250`](../../auralis/core/processing/continuous_mode.py)) has:

- A **fast path** — if a `.25d` sidecar supplies `fixed_params`, it skips fingerprint
  extraction (~8× faster).
- A **full path** — extract fingerprint → `RecordingTypeDetector.detect` →
  `map_fingerprint_to_space` → optional reference-cloud target derivation →
  `generate_parameters`.

Each DSP stage (`_apply_dsp_stages`, [`:333`](../../auralis/core/processing/continuous_mode.py))
is followed by a **CrossDimensionalGuard** compensation step that caps unintended drift
(EQ LUFS drift ±1.5 dB / hard cap ±3 dB; dynamics spectral-tilt; stereo phase-correlation;
normalization crest-crush pullback), journaled via `PipelineJournal`. A sampled **quality
gate** runs every Nth chunk (`quality_gate_interval`).

> **Intentional divergence.** ContinuousMode uses its **own** offline dynamics
> (`CompressionStrategies.apply_clip_blend_compression`), *not* the real-time
> `DynamicsProcessor`. Routing the real-time processor (which targets −14 LUFS with makeup
> gain) into the offline chain would double-compress and fight the LUFS target (#2897).

---

## 3. SimpleMastering — the offline file masterer

`SimpleMasteringPipeline.master_file()`
([`simple_mastering.py:86`](../../auralis/core/simple_mastering.py)) processes files in
chunks for memory efficiency. Each chunk flows through
`mastering_process_chunk.process_chunk`
([`mastering_process_chunk.py:86`](../../auralis/core/mastering_process_chunk.py)):

1. Unpack 25D fingerprint → `calculate_intensity` (2D crest × LUFS interpolation, clamped
   0.5–1.2).
2. **Stage 1** — gentle clip-prevention peak reduction.
3. **Stage 2** — `MaterialClassifier.classify` → dispatch to one of three branches.
4. **Stage 3** — unified output normalize (only when `needs_output_normalize`).
5. `sanitize_audio`.

### Material branches (`mastering_branches.py`)

| Branch | Trigger | `needs_output_normalize` |
|--------|---------|--------------------------|
| `CompressedLoudBranch` ([`:216`](../../auralis/core/mastering_branches.py)) | LUFS > −12, crest < 13 | `True` |
| `DynamicLoudBranch` ([`:345`](../../auralis/core/mastering_branches.py)) | LUFS > −12, crest ≥ 13 | `True` |
| `QuietBranch` ([`:451`](../../auralis/core/mastering_branches.py)) | LUFS ≤ −12 | **`False` — self-normalizes** |

> **Gotcha.** `QuietBranch` self-normalizes (it is the mirror-opposite gain-staging chain
> ending in a branch-local `normalize`), while the loud branches defer to Stage 3. Mixing
> these up **double-normalizes**. This is an explicit contract documented at
> [`mastering_branches.py:136`](../../auralis/core/mastering_branches.py).

### Presets belong to HybridProcessor, not SimpleMastering

The named presets **Adaptive / Gentle / Warm / Bright / Punchy / Live** live in
[`auralis/core/config/preset_profiles.py:51`](../../auralis/core/config/preset_profiles.py)
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
| [`realtime_adaptive_eq/realtime_eq.py`](../../auralis/dsp/realtime_adaptive_eq/realtime_eq.py) | `RealtimeAdaptiveEQ` — buffers variable chunk sizes into fixed frames; a persistent FIFO guarantees exact-length output |

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

Built with `maturin develop` (PyO3 0.23 + numpy 0.23, crate `auralis_dsp`). Two separate
Rust surfaces exist:

1. **In-process PyO3 module** `auralis_dsp` (the live one) — HPSS, YIN pitch, Chroma, tempo,
   envelope follower, compress/limit, and the full 25D `compute_fingerprint`. Registered in
   [`src/py_bindings.rs`](../../vendor/auralis-dsp/src/py_bindings.rs).
2. **Standalone gRPC fingerprint server** —
   [`src/bin/grpc_fingerprint_server.rs`](../../vendor/auralis-dsp/src/bin/grpc_fingerprint_server.rs).
   **Abandoned/non-functional** (stub compute, gRPC-vs-HTTP client mismatch, never launched);
   slated for removal. See [fingerprinting.md §7](fingerprinting.md#7-performance).

### The PyO3 boundary contract

- **dtype is per-function and strict.** `hpss` / `yin` / `chroma_cqt` / `detect_tempo` /
  `apply_multiband_eq` / `detect_onsets` take **f64**; `envelope_follow` / `compress` /
  `limit` / `compute_fingerprint` take **f32**. Mono functions take shape `(n,)`;
  multiband/`process_chunks` take channels-first `(2, n)`.
- **Every** heavy wrapper releases the GIL (`py.allow_threads(...)`, #2447) and wraps compute
  in `catch_unwind`, converting Rust panics into a readable `PyRuntimeError` (#2225) rather
  than crashing the interpreter.

### No Python fallback

`DSPBackend`
([`auralis/analysis/fingerprint/utilities/dsp_backend.py:24`](../../auralis/analysis/fingerprint/utilities/dsp_backend.py))
is **Rust-only**. `initialize()` raises `RuntimeError` at import if `auralis_dsp` can't be
imported — the old librosa fallback was removed. `_validate_ffi_inputs` rejects empty arrays /
`sr <= 0` and coerces to float64 before every FFI call (#2521) to prevent Rust panics.

> If you see `RuntimeError: ... auralis_dsp` at startup, you skipped
> `cd vendor/auralis-dsp && maturin develop`.

---

## 6. Chunked streaming (`auralis-web/backend/core/`)

### Geometry — single source of truth

All chunk geometry comes from
[`chunk_boundaries.py:19`](../../auralis-web/backend/core/chunk_boundaries.py):

```python
CHUNK_DURATION  = 15.0   # each chunk covers 15 s
CHUNK_INTERVAL  = 10.0   # chunks start every 10 s
OVERLAP_DURATION = 5.0   # → adjacent chunks overlap 5 s
CONTEXT_DURATION = 5.0   # extra context loaded on each side
```

Chunk N covers `[N*10, N*10+15]`. **Never** count chunks with naive
`ceil(duration / CHUNK_DURATION)` — use the overlap-aware
`content_chunk_count(total_duration) = max(1, ceil((total_duration - OVERLAP_DURATION) / CHUNK_INTERVAL))`
([`chunk_boundaries.py:37`](../../auralis-web/backend/core/chunk_boundaries.py), #4124). It is
the authoritative counter.

### Crossfade math

`apply_crossfade_between_chunks`
([`chunked_processor.py:904`](../../auralis-web/backend/core/chunked_processor.py)) uses
**equal-power** sin²/cos² curves (`fade_out = cos(t)²`, `fade_in = sin(t)²`,
`t = linspace(0, π/2, N)`) to avoid the mid-point energy dip (#2080).

> **Subtle:** crossfade is applied only at the *streaming boundary*. The full-file
> reassembly path (`get_full_processed_audio_path`) uses plain `np.concatenate` because the
> extracted segments are already non-overlapping — crossfading there double-blended and
> shortened output by (N−1)×5 s (#2750).

### ProcessorFactory lifecycle

[`processor_factory.py:53`](../../auralis-web/backend/core/processor_factory.py) is a
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
| **Sample count preserved** | Asserted after the brick-wall limiter in all offline handlers ([`hybrid_processor.py:312,368,395`](../../auralis/core/hybrid_processor.py)); realtime chunk assert (`:443`); `RealtimeAdaptiveEQ` FIFO guarantees exact length (#4216) |
| **Copy before modify** | `amplify` / `normalize` copy; every branch `apply()` starts `processed = audio.copy()`; silent/empty early-returns return copies |
| **dtype propagation** | `normalize` explicit `astype(audio.dtype)` (#3687); spectral-tilt casts back after `sosfiltfilt` upcasts to f64; zero-pad/silence fallbacks preserve dtype |
| **No NaN/Inf** | `validate_audio_finite(repair=False)` fails fast on input and mastering output; `sanitize_audio` repairs realtime/streaming output; silence early-returns avoid `log(0)`→NaN |
| **Clipping ceiling** | Brick-wall limiter at −0.3 dB; continuous-mode emergency peak-limit to −0.3 dBFS; PCM clamp in [`auralis/io/results.py`](../../auralis/io/results.py) |
| **Mono → stereo** | Expanded once, explicitly, at HybridProcessor entry ([`:267`](../../auralis/core/hybrid_processor.py)) |
| **Min buffer size** | HybridProcessor raises below `MIN_SAMPLES = 1024` to prevent Rust FFT panics |

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
([`unified_config.py:22`](../../auralis/core/config/unified_config.py)) — key knobs:

| Knob | Default | Effect |
|------|---------|--------|
| `internal_sample_rate` | 44100 | Internal processing rate |
| `processing_sample_rate` | 48000 | I/O downsample target |
| `fft_size` | 4096 | Asserted power of 2 |
| `mastering_profile` | `"adaptive"` | Named preset |
| `use_continuous_space` | `True` | ContinuousMode vs legacy AdaptiveMode |
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
4. [`mastering_branches.py`](../../auralis/core/mastering_branches.py) — the offline
   branch logic and tuning constants.

**Related:** [fingerprinting.md](fingerprinting.md) ·
[backend-api.md](backend-api.md) · [../architecture/data-flow.md](../architecture/data-flow.md)

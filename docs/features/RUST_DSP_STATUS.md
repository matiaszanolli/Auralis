# Rust DSP Crate (`vendor/auralis-dsp/`)

## What the crate is for

One thing: the native 25D fingerprint, exposed to Python as `auralis_dsp.compute_fingerprint`. Its one
production call site is
[`auralis/analysis/fingerprint/rust_fingerprint.py`](../../auralis/analysis/fingerprint/rust_fingerprint.py)
(`compute_fingerprint_schema`); the backend's
[`fingerprint_generator.py`](../../auralis-web/backend/analysis/fingerprint_generator.py) only imports it
to learn whether the module is available. What each dimension means, how the glue maps the raw Rust
keys and units onto the schema, and which audio is analysed are in
[fingerprinting.md](../subsystems/fingerprinting.md).

Do not add a binding or a module without a production Python caller. HPSS, YIN, tempo, envelope,
compressor, limiter, multiband EQ, onset and chunk-processor bindings were deleted because nothing
called them: the Python implementations are what run.

## Module inventory

| Module | Purpose |
|---|---|
| `fingerprint_compute.rs` | `compute_complete_fingerprint`: assembles all 25 dimensions from the modules below; also the tempo estimate (spectral-flux onset autocorrelation) |
| `frequency_analysis.rs` | 7-band energy distribution and the bass/mid ratio, accumulated over the whole input frame by frame |
| `spectral_features.rs` | Spectral centroid, rolloff, flatness |
| `variation_analysis.rs` | Dynamic-range variation, loudness variation, peak consistency (whole 1 s frames only) |
| `stereo_analysis.rs` | Stereo width and phase correlation |
| `chroma.rs` | Constant-Q chromagram (the `chroma_energy` dimension) |
| `rhythm.rs` | Beat tracking for `rhythm_stability`, and `silence_ratio` |
| `dsp_math.rs` | Shared primitives: RMS, the RMS-proxy LUFS estimate, `hz_to_bin`, the f32 Hann weight, population standard deviation |
| `py_bindings.rs` | The `#[pymodule]` registering `compute_fingerprint` |

`lufs` is deliberately an RMS proxy, not BS.1770, so every fingerprint path agrees; use
`LoudnessMeter` where standards-compliant loudness matters.

## The PyO3 boundary

- `compute_fingerprint(audio, sample_rate, channels)`: `audio` is a 1-D C-contiguous **float32**
  array: mono `(n,)`, or for `channels == 2` interleaved L/R `(2n,)`. An empty array, a zero sample
  rate or a channel count other than 1 or 2 raises `ValueError`.
- The call releases the GIL (`py.detach`) and runs under `catch_unwind`, so a Rust panic surfaces as a
  `RuntimeError` instead of aborting the interpreter.
- It returns the raw 25 values under Rust's key names and units, not the schema's. Use
  `compute_fingerprint_schema`, never the raw call.
- There is no Python fallback: without the built module, fingerprinting and adaptive mastering fail
  loudly (see fingerprinting.md §2).

## Toolchain and dependencies

PyO3 and `numpy` (rust-numpy) 0.29, `ndarray` 0.16, `rustfft`, `rayon`; edition 2024, `rust-version` 1.85,
toolchain pinned in `rust-toolchain.toml`. `pyo3` and `numpy` are bumped together, and the module is
built against the full CPython 3.14 API (no `abi3`); the release build checks for that. Major-version
status for each dependency is in `vendor/auralis-dsp/UPGRADE_PLAN.md`.

## Build and test

```bash
cd vendor/auralis-dsp
maturin develop             # build and install the extension into the active venv (required before first run)
cargo check --tests         # fast compile check, no Python needed
cargo test --lib            # the crate's unit tests
```

Release wheels are built in CI with `maturin build --release --locked`. Python-side tests that call
`auralis_dsp` live under `tests/vendor/`.

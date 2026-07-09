# Rust DSP Library (`vendor/auralis-dsp/`) — Current Status

**Last verified**: 2026-07-09
**Supersedes**: `docs/guides/RUST_DSP_HPSS_IMPLEMENTATION_SUMMARY.md`, `RUST_DSP_PROJECT_STATUS.md`, `RUST_DSP_EXTRACTION_PLAN.md`

Those three docs describe the crate as it stood on 2025-11-24, when only HPSS was implemented and YIN/Chroma/PyO3 bindings were skeletons. That's no longer true — this doc replaces them as the status reference. The extraction plan's algorithm descriptions (STFT/median-filter/Wiener-mask chains, YIN autocorrelation, CQT chroma) are still accurate background reading and aren't repeated here.

## Module inventory (16 modules + 1 binary, 5,972 lines)

| Module | Lines | Unit tests | Purpose |
|---|---|---|---|
| `hpss.rs` | 400 | 6 | Harmonic/percussive source separation |
| `yin.rs` | 456 | 12 | Fundamental frequency (pitch) detection |
| `chroma.rs` | 502 | 15 | Constant-Q chromagram features |
| `tempo.rs` | 280 | 4 | Spectral-flux onset detection / tempo estimation |
| `envelope.rs` | 217 | 5 | Attack/release envelope follower |
| `compressor.rs` | 343 | 4 | Dynamic range compressor (peak/RMS/hybrid detection) |
| `limiter.rs` | 341 | 5 | Lookahead limiter with ISR/oversampling |
| `biquad_filter.rs` | 237 | 2 | Biquad filter (Direct Form II Transposed) |
| `onset_detector.rs` | 256 | 5 | Onset detection via spectral flux |
| `chunk_processor.rs` | 271 | 3 | Streaming chunk processing |
| `frequency_analysis.rs` | 230 | 5 | 7-band perceptual frequency distribution |
| `spectral_features.rs` | 222 | 6 | Spectral centroid/rolloff/flatness |
| `variation_analysis.rs` | 263 | 10 | Temporal variation (dynamic range, loudness, peak consistency) |
| `stereo_analysis.rs` | 256 | 9 | Stereo width / phase correlation |
| `fingerprint_compute.rs` | 632 | 3 | Orchestrates the full 25D fingerprint from the modules above |
| `py_bindings.rs` | 784 | 0 | Active `#[pymodule]` — 11 `#[pyfunction]` entries exposing the above to Python |
| `bin/grpc_fingerprint_server.rs` | 230 | — | Standalone gRPC server: Python streams audio in, Rust returns a computed 25D fingerprint over gRPC |

PyO3 is **not** disabled — `Cargo.toml` has `pyo3 = { version = "0.23", features = ["extension-module"] }` and `numpy = "0.23"` as active (non-commented) dependencies, and the crate builds as `crate-type = ["cdylib", "rlib"]` (Python extension + Rust library).

## Test status (`cargo test --release`, verified 2026-07-09)

**84 / 94 unit tests passing.** 10 pre-existing failures, unrelated to this doc fix (not investigated or fixed here):

- `compressor::tests::test_compress_loud_signal`
- `fingerprint_compute::tests::test_compute_complete_fingerprint_mono`
- `fingerprint_compute::tests::test_compute_complete_fingerprint_stereo`
- `onset_detector::tests::test_onset_detection`
- `spectral_features::tests::test_spectral_flatness_tone`
- `stereo_analysis::tests::test_compute_energy`
- `stereo_analysis::tests::test_is_stereo_wide`
- `stereo_analysis::tests::test_phase_correlation_opposite`
- `variation_analysis::tests::test_compute_dynamic_range_sine`
- `variation_analysis::tests::test_dynamic_range_variation_varied`

## Build

```bash
cd vendor/auralis-dsp
cargo build --release       # library + grpc-fingerprint-server binary
cargo test --release        # unit tests
maturin develop              # build + install as Python extension (see root CLAUDE.md)
```

# Rust DSP Library (`vendor/auralis-dsp/`) — Current Status

**Last verified**: 2026-10-22 (after #5764)
**Supersedes**: the 2025-11 planning docs (`RUST_DSP_PROJECT_STATUS.md`, `RUST_DSP_EXTRACTION_PLAN.md`, `README_RUST_DSP_INTEGRATION.md`), now under `docs/archive/development-history/`.

## What the crate is for

One thing: the native 25D fingerprint (`auralis_dsp.compute_fingerprint`), called from
`auralis-web/backend/analysis/fingerprint_generator.py` and
`auralis/analysis/fingerprint/rust_fingerprint.py`. The crate used to also expose HPSS, YIN,
tempo, envelope follower, compressor, limiter, multiband EQ and onset detection as Python
bindings. None had a production caller (the Python implementations are what run), so #5764
deleted the nine bindings and the modules only they used.

## Module inventory (10 modules, 3,486 lines)

| Module | Lines | Unit tests | Purpose |
|---|---|---|---|
| `fingerprint_compute.rs` | 846 | 9 | Orchestrates the full 25D fingerprint from the modules below |
| `frequency_analysis.rs` | 225 | 5 | 7-band perceptual frequency distribution |
| `spectral_features.rs` | 222 | 6 | Spectral centroid/rolloff/flatness |
| `variation_analysis.rs` | 240 | 10 | Temporal variation (dynamic range, loudness, peak consistency) |
| `stereo_analysis.rs` | 188 | 7 | Stereo width / phase correlation |
| `chroma.rs` | 502 | 15 | Constant-Q chromagram (harmonic dimensions of the fingerprint) |
| `rhythm.rs` | 700 | 6 | Beat tracking + silence ratio; feeds `rhythm_stability` / `silence_ratio` (ported from the deleted `fingerprint-server` crate, #4533) |
| `dsp_math.rs` | 44 | 0 | Shared RMS / LUFS-proxy primitives |
| `chunk_processor.rs` | 250 | 3 | Streaming chunk processing; **dead**, behind `process_chunks`, decision tracked in #5738 |
| `py_bindings.rs` | 228 | 0 | `#[pymodule]` registering `compute_fingerprint` and `process_chunks` |

## Test status (`cargo test --lib`, verified 2026-10-22)

**56 / 61 unit tests passing.** 5 pre-existing failures (they fail identically before #5764):

- `fingerprint_compute::tests::test_compute_complete_fingerprint_mono`
- `fingerprint_compute::tests::test_compute_complete_fingerprint_stereo`
- `spectral_features::tests::test_spectral_flatness_tone`
- `stereo_analysis::tests::test_compute_energy`
- `stereo_analysis::tests::test_phase_correlation_opposite`

## Build

```bash
cd vendor/auralis-dsp
cargo check --tests         # fast compile check, no Python needed
cargo test --lib            # unit tests
maturin develop             # build + install as Python extension (see root CLAUDE.md)
```

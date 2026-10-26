/// Auralis DSP - High-performance audio signal processing in Rust
///
/// The only entry point with a production caller is the 25D fingerprint
/// (`compute_fingerprint`), and this crate holds that dependency closure:
/// - Chroma: Constant-Q chromagram features
/// - Rhythm: silence ratio and rhythm stability
/// - Frequency / spectral / variation / stereo analysis
/// - Fingerprint: assembles the 25 dimensions
///
/// Do not add modules without a production Python caller: HPSS, YIN, tempo,
/// envelope follower, compressor, limiter, multiband EQ and onset detection
/// all lacked one and went (#5764). `chunk_processor` stays until #5738
/// decides it.

// Core DSP modules
pub mod chroma;
pub mod rhythm;
pub mod chunk_processor;

// Shared DSP math primitives (compute_rms, estimate_lufs) — #4022
pub(crate) mod dsp_math;

// Fingerprinting modules (25D audio analysis)
pub mod frequency_analysis;
pub mod spectral_features;
pub mod variation_analysis;
pub mod stereo_analysis;
pub mod fingerprint_compute;

// Python bindings
pub mod py_bindings;

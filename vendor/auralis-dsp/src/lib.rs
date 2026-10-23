/// Auralis DSP - High-performance audio signal processing in Rust
///
/// The only entry point with a production caller is the 25D fingerprint
/// (`compute_fingerprint`), and this crate holds that dependency closure:
/// - Chroma: Constant-Q chromagram features
/// - Rhythm: silence ratio and rhythm stability
/// - Frequency / spectral / variation / stereo analysis
/// - Fingerprint: assembles the 25 dimensions
///
/// HPSS, YIN, tempo, envelope follower, compressor, limiter, multiband EQ and
/// onset detection were removed in #5764: they had no production Python
/// caller, only validation and benchmark tests. `chunk_processor` stays until
/// #5738 decides it.

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

// Re-export main functions for convenience
pub use chroma::chroma_cqt;

// Fingerprinting exports
pub use frequency_analysis::compute_frequency_distribution;
pub use spectral_features::{compute_spectral_centroid, compute_spectral_rolloff, compute_spectral_flatness, audio_to_freq_domain};
pub use variation_analysis::{compute_dynamic_range_variation, compute_loudness_variation, compute_peak_consistency};
pub use stereo_analysis::{compute_stereo_width, compute_phase_correlation};
pub use fingerprint_compute::{AudioFingerprint, compute_complete_fingerprint};

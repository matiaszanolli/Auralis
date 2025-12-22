/// Auralis DSP - High-performance audio signal processing in Rust
///
/// Provides optimized implementations of librosa functions and DSP components:
/// - HPSS: Harmonic/Percussive Source Separation
/// - YIN: Fundamental frequency detection
/// - Chroma: Constant-Q chromagram features
/// - Tempo: Spectral flux onset detection for tempo estimation
/// - Envelope: Attack/release envelope follower for dynamics processing
/// - Compressor: Dynamic range compressor with peak/RMS/hybrid detection
/// - Limiter: Lookahead limiter with ISR and oversampling

// Core DSP modules
pub mod hpss;
pub mod yin;
pub mod chroma;
pub mod tempo;
pub mod median_filter;
pub mod envelope;
pub mod compressor;
pub mod limiter;
pub mod biquad_filter;
pub mod onset_detector;
pub mod chunk_processor;

// Fingerprinting modules (25D audio analysis)
pub mod frequency_analysis;
pub mod spectral_features;
pub mod variation_analysis;
pub mod stereo_analysis;
pub mod fingerprint_compute;

// Python bindings
pub mod py_bindings;

// Re-export main functions for convenience
pub use hpss::hpss;
pub use yin::yin;
pub use chroma::chroma_cqt;
pub use tempo::detect_tempo;
pub use envelope::{envelope_follow, EnvelopeFollower, EnvelopeConfig};
pub use compressor::{compress, Compressor, CompressorConfig, DetectionMode, CompressionInfo};
pub use limiter::{limit, Limiter, LimiterConfig, LimitingInfo};

// Fingerprinting exports
pub use frequency_analysis::compute_frequency_distribution;
pub use spectral_features::{compute_spectral_centroid, compute_spectral_rolloff, compute_spectral_flatness, audio_to_freq_domain};
pub use variation_analysis::{compute_dynamic_range_variation, compute_loudness_variation, compute_peak_consistency};
pub use stereo_analysis::{compute_stereo_width, compute_phase_correlation, is_stereo};
pub use fingerprint_compute::{AudioFingerprint, compute_complete_fingerprint};

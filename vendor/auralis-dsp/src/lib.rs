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

pub mod hpss;
pub mod yin;
pub mod chroma;
pub mod tempo;
pub mod median_filter;
pub mod envelope;
pub mod compressor;
pub mod limiter;
pub mod py_bindings;

// Re-export main functions for convenience
pub use hpss::hpss;
pub use yin::yin;
pub use chroma::chroma_cqt;
pub use tempo::detect_tempo;
pub use envelope::{envelope_follow, EnvelopeFollower, EnvelopeConfig};
pub use compressor::{compress, Compressor, CompressorConfig, DetectionMode, CompressionInfo};
pub use limiter::{limit, Limiter, LimiterConfig, LimitingInfo};

/// Auralis DSP - High-performance audio signal processing in Rust
///
/// Provides optimized implementations of librosa functions:
/// - HPSS: Harmonic/Percussive Source Separation
/// - YIN: Fundamental frequency detection
/// - Chroma: Constant-Q chromagram features
/// - Tempo: Spectral flux onset detection for tempo estimation

pub mod hpss;
pub mod yin;
pub mod chroma;
pub mod tempo;
pub mod median_filter;
pub mod py_bindings;

// Re-export main functions for convenience
pub use hpss::hpss;
pub use yin::yin;
pub use chroma::chroma_cqt;
pub use tempo::detect_tempo;

//! Shared low-level DSP math primitives (#4022).
//!
//! `compute_rms` and `estimate_lufs` were previously duplicated as private
//! functions in `fingerprint_compute.rs` and `variation_analysis.rs`. The two
//! `estimate_lufs` copies had silently diverged — different signatures
//! (`&[f32]` vs `&[f32], u32`) and different calibration constants (`-0.7` vs
//! `+1.0`) — so tuning one left the other computing a different loudness.
//! Consolidated here to a single implementation.

/// Compute RMS energy of a signal.
pub(crate) fn compute_rms(signal: &[f32]) -> f32 {
    if signal.is_empty() {
        return 0.0;
    }

    let sum_sq: f32 = signal.iter().map(|s| s * s).sum();
    (sum_sq / signal.len() as f32).sqrt()
}

/// Estimate LUFS (loudness units relative to full scale) from signal RMS.
///
/// This is a simplified RMS-based approximation, NOT ITU-R BS.1770 certified
/// (no K-weighting, gating, or integration — see #4123 for the planned proper
/// implementation).
///
/// The `-0.7` dB calibration constant is the one retained from the fingerprint
/// path, whose output is a reported *absolute* LUFS value. The variation path
/// only takes the standard deviation of per-frame results
/// (`compute_loudness_variation`), which is invariant to a constant offset, so
/// unifying on this constant leaves both callers' behaviour unchanged. The
/// old variation-path `sample_rate` parameter was unused and has been dropped.
pub(crate) fn estimate_lufs(signal: &[f32]) -> f32 {
    let rms = compute_rms(signal);
    if rms < 1e-10 {
        return -120.0;
    }

    let db = 20.0 * rms.log10() - 0.7; // Calibration constant (see doc comment)
    db.clamp(-120.0, 0.0)
}

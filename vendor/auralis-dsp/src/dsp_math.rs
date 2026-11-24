//! Shared low-level DSP math primitives (#4022).
//!
//! `compute_rms` and `estimate_lufs` were previously duplicated as private
//! functions in `fingerprint_compute.rs` and `variation_analysis.rs`. The two
//! `estimate_lufs` copies had silently diverged — different signatures
//! (`&[f32]` vs `&[f32], u32`) and different calibration constants (`-0.7` vs
//! `+1.0`) — so tuning one left the other computing a different loudness.
//! Consolidated here to a single implementation.
//!
//! Sums over a signal are f64 (#6362). `hz_to_bin`, the f32 Hann weight and the
//! population standard deviation moved
//! here in #6622 from the two to three copies each had in `fingerprint_compute`,
//! `frequency_analysis`, `spectral_features`, `stereo_analysis` and
//! `variation_analysis`. The f64 periodic Hann window in `rhythm.rs`
//! (`hann_periodic`) is a different expression in a different precision, not a
//! copy: unifying it would change the tempo path's numbers, so it stays there.

use std::f32::consts::PI;

/// Compute RMS energy of a signal.
///
/// Summed in f64: a whole track is up to ~20M samples, and an f32 running sum stops
/// absorbing small terms, so `lufs` and the crest factor drifted with track length (#6362).
pub(crate) fn compute_rms(signal: &[f32]) -> f32 {
    if signal.is_empty() {
        return 0.0;
    }

    let sum_sq: f64 = signal.iter().map(|&s| (s as f64) * (s as f64)).sum();
    (sum_sq / signal.len() as f64).sqrt() as f32
}

/// Estimate LUFS (loudness units relative to full scale) from signal RMS.
///
/// This is deliberately an RMS proxy, NOT ITU-R BS.1770 (no K-weighting,
/// gating or integration), and no BS.1770 port is planned. The fingerprint
/// `lufs` dimension is computed with this same `20*log10(rms)` formula on every
/// path, including the Python fallback in `windowed_compute._rms_lufs_crest`.
/// #4123 weighed porting K-weighting and gating here and chose to keep the
/// proxy so the paths agree (`b9751733`). Callers that need standards-compliant
/// loudness use `auralis.analysis.loudness_meter.LoudnessMeter` instead.
///
/// The `-0.7` dB calibration constant is the one retained from the fingerprint
/// path, whose output is a reported *absolute* LUFS value. The variation path
/// only takes the standard deviation of per-frame results
/// (`compute_loudness_variation`), which is invariant to a constant offset, so
/// unifying on this constant leaves both callers' behaviour unchanged.
pub(crate) fn estimate_lufs(signal: &[f32]) -> f32 {
    let rms = compute_rms(signal);
    if rms < 1e-10 {
        return -120.0;
    }

    let db = 20.0 * rms.log10() - 0.7; // Calibration constant (see doc comment)
    db.clamp(-120.0, 0.0)
}

/// FFT bin index of `hz`, clamped to the last bin.
///
/// The clamp is the `fingerprint_compute` form. `frequency_analysis` used to
/// carry an unclamped copy and relied on its one caller pre-clamping the
/// frequency to Nyquist; with the clamp here that no longer has to hold.
pub(crate) fn hz_to_bin(hz: f32, sample_rate: u32, fft_size: usize) -> usize {
    (((hz * fft_size as f32) / sample_rate as f32).floor() as usize).min(fft_size - 1)
}

/// Weight `i` of a Hann window of length `n`, as `0.5 * (1 - cos(2*pi*i/n))`.
///
/// The caller picks `n`: the frame length for a window over a zero-padded
/// frame (`frequency_analysis::windowed_into`), or the audio length for a
/// window over a whole signal (`spectral_features`).
pub(crate) fn hann_weight(i: usize, n: f32) -> f32 {
    0.5 * (1.0 - ((2.0 * PI * i as f32) / n).cos())
}

/// Population standard deviation of `values` about a `mean` the caller already
/// has (every caller needs the mean as well). `values` must not be empty.
pub(crate) fn std_dev_about(values: &[f32], mean: f32) -> f32 {
    let mean = mean as f64;
    let variance: f64 =
        values.iter().map(|&v| (v as f64 - mean).powi(2)).sum::<f64>() / values.len() as f64;
    variance.sqrt() as f32
}

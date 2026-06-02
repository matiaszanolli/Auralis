//! YIN Fundamental Frequency Detection + pitch stability.
//!
//! Direct port of `vendor/auralis-dsp/src/yin.rs` so the Rust fingerprint
//! server and the Python fallback (`harmonic_ops.calculate_pitch_stability`)
//! converge on the *same* algorithm (#4110). Keep this in sync with the
//! canonical implementation in `vendor/auralis-dsp/src/yin.rs`; it is copied
//! rather than shared because that crate is a pyo3 extension-module and cannot
//! be linked into this binary cleanly.
//!
//! Reference: de Cheveigné & Kawahara, "YIN, a fundamental frequency estimator
//! for speech and music." JASA 111, 2002.

use rayon::prelude::*;

/// Detect fundamental frequency using the YIN algorithm.
///
/// Returns per-frame f0 estimates (Hz); 0.0 marks an unvoiced frame.
/// Frame length 2048 (~46 ms @ 44.1 kHz), hop 512 (~11.6 ms).
pub fn yin(y: &[f64], sr: usize, fmin: f64, fmax: f64) -> Vec<f64> {
    const FRAME_LENGTH: usize = 2048;
    const HOP_LENGTH: usize = 512;
    const TROUGH_THRESHOLD: f64 = 0.15;

    if y.len() < FRAME_LENGTH {
        return vec![0.0];
    }

    let n_frames = (y.len() - FRAME_LENGTH) / HOP_LENGTH + 1;

    let min_lag = ((sr as f64) / fmax) as usize;
    let max_lag = ((sr as f64) / fmin) as usize;

    let min_lag = min_lag.max(2);
    let max_lag = max_lag.min(FRAME_LENGTH - 1);

    if min_lag >= max_lag {
        return vec![0.0; n_frames];
    }

    (0..n_frames)
        .into_par_iter()
        .map(|frame_idx| {
            let start = frame_idx * HOP_LENGTH;
            let end = (start + FRAME_LENGTH).min(y.len());
            let frame_len = end - start;

            if frame_len < FRAME_LENGTH {
                let mut frame = vec![0.0; FRAME_LENGTH];
                frame[..frame_len].copy_from_slice(&y[start..end]);
                process_frame(&frame, sr as f64, min_lag, max_lag, TROUGH_THRESHOLD)
            } else {
                process_frame(&y[start..end], sr as f64, min_lag, max_lag, TROUGH_THRESHOLD)
            }
        })
        .collect()
}

fn process_frame(frame: &[f64], sr: f64, min_lag: usize, max_lag: usize, threshold: f64) -> f64 {
    let df = compute_difference_function(frame);
    let aacf = cumulative_mean_normalization(&df);

    match find_trough(&aacf, min_lag, max_lag, threshold) {
        Some(tau) => {
            let refined_lag = parabolic_interpolate(&aacf, tau);
            let frequency = sr / refined_lag;
            if frequency.is_finite() && frequency > 0.0 {
                frequency
            } else {
                0.0
            }
        }
        None => 0.0,
    }
}

/// Difference function: `DF[τ] = Σ(y[n] - y[n+τ])²`.
fn compute_difference_function(frame: &[f64]) -> Vec<f64> {
    let n = frame.len();
    let mut df = vec![0.0; n];
    df[0] = 0.0;
    for tau in 1..n {
        let mut error = 0.0;
        for i in 0..(n - tau) {
            let diff = frame[i] - frame[i + tau];
            error += diff * diff;
        }
        df[tau] = error;
    }
    df
}

/// Cumulative mean normalization: DF → AACF in `[0, 2]`.
fn cumulative_mean_normalization(df: &[f64]) -> Vec<f64> {
    let n = df.len();
    let mut aacf = vec![0.0; n];
    aacf[0] = 1.0;

    let mut running_sum = df[0];
    for tau in 1..n {
        running_sum += df[tau];
        if running_sum > 1e-10 {
            aacf[tau] = 2.0 * df[tau] / running_sum;
        } else {
            aacf[tau] = 2.0;
        }
        aacf[tau] = aacf[tau].min(2.0).max(0.0);
    }
    aacf
}

/// First lag in `[min_lag, max_lag)` whose AACF drops below `threshold`.
fn find_trough(aacf: &[f64], min_lag: usize, max_lag: usize, threshold: f64) -> Option<usize> {
    if min_lag >= aacf.len() || min_lag >= max_lag {
        return None;
    }
    let search_end = max_lag.min(aacf.len());
    (min_lag..search_end).find(|&tau| aacf[tau] < threshold)
}

/// Parabolic interpolation for sub-sample lag refinement.
fn parabolic_interpolate(aacf: &[f64], tau: usize) -> f64 {
    if tau == 0 || tau >= aacf.len() - 1 {
        return tau as f64;
    }
    let x = tau as f64;
    let y1 = aacf[tau - 1];
    let y2 = aacf[tau];
    let y3 = aacf[tau + 1];

    let denom = 2.0 * (y1 - 2.0 * y2 + y3);
    if denom.abs() < 1e-10 {
        return x;
    }
    let offset = ((y1 - y3) / denom).clamp(-0.5, 0.5);
    x + offset
}

/// Pitch stability (0-1) from a YIN f0 contour, mirroring the Python path
/// (`StabilityMetrics.from_values(voiced_f0, scale=10.0)`).
///
/// Voiced frames (f0 > 0) are kept; with fewer than 10 the result is the
/// neutral fallback 0.5. Otherwise stability = `1 / (1 + CV * scale)` where
/// `CV = std/mean` of the voiced f0 values — lower variation ⇒ higher stability.
pub fn pitch_stability(samples: &[f64], sample_rate: u32) -> f64 {
    // C2 (65.41 Hz) .. C7 (2093.00 Hz), matching harmonic_ops.py.
    const FMIN: f64 = 65.41;
    const FMAX: f64 = 2093.00;
    const SCALE: f64 = 10.0;
    const EPSILON: f64 = 1e-10;
    const FALLBACK: f64 = 0.5;

    let f0 = yin(samples, sample_rate as usize, FMIN, FMAX);
    let voiced: Vec<f64> = f0.into_iter().filter(|&x| x > 0.0).collect();

    if voiced.len() < 10 {
        return FALLBACK;
    }

    let n = voiced.len() as f64;
    let mean = voiced.iter().sum::<f64>() / n;
    if mean <= EPSILON {
        return FALLBACK;
    }

    // Population standard deviation (matches numpy's np.std default ddof=0).
    let variance = voiced.iter().map(|&v| (v - mean) * (v - mean)).sum::<f64>() / n;
    let std = variance.sqrt();

    let cv = std / mean;
    (1.0 / (1.0 + cv * SCALE)).clamp(0.0, 1.0)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::f64::consts::PI;

    fn sine(freq: f64, sr: usize, secs: f64) -> Vec<f64> {
        let n = (sr as f64 * secs) as usize;
        (0..n).map(|i| (2.0 * PI * freq * i as f64 / sr as f64).sin()).collect()
    }

    #[test]
    fn stable_tone_matches_python_path() {
        // Parity check: the Python fallback
        // (harmonic_ops.calculate_pitch_stability) returns 1.000000 for a pure
        // 440 Hz / 220 Hz / 330 Hz sine (constant f0 -> CV=0 -> stability=1).
        // This verbatim port must agree within tolerance.
        for freq in [440.0, 220.0, 330.0] {
            let audio = sine(freq, 44100, 1.0);
            let stability = pitch_stability(&audio, 44100);
            assert!(
                (stability - 1.0).abs() < 0.02,
                "{freq} Hz sine: expected ~1.0 (Python parity), got {stability}"
            );
        }
    }

    #[test]
    fn silence_returns_fallback() {
        // Silence is all-unvoiced -> fewer than 10 voiced frames -> 0.5.
        let audio = vec![0.0; 44100];
        assert_eq!(pitch_stability(&audio, 44100), 0.5);
    }

    #[test]
    fn noise_is_less_stable_than_tone() {
        let tone = sine(220.0, 44100, 1.0);
        let mut noise = vec![0.0; 44100];
        let mut seed: u64 = 12345;
        for s in noise.iter_mut() {
            seed = seed.wrapping_mul(1664525).wrapping_add(1013904223);
            *s = (seed as f64 / u64::MAX as f64 - 0.5) * 0.5;
        }
        let tone_stability = pitch_stability(&tone, 44100);
        let noise_stability = pitch_stability(&noise, 44100);
        assert!(
            noise_stability < tone_stability,
            "noise ({noise_stability}) should be less stable than tone ({tone_stability})"
        );
    }

    #[test]
    fn result_in_unit_range() {
        let audio = sine(330.0, 44100, 0.6);
        let s = pitch_stability(&audio, 44100);
        assert!((0.0..=1.0).contains(&s));
    }
}

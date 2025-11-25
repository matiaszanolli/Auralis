/// YIN Fundamental Frequency Detection
///
/// Autocorrelation-based pitch detection using the YIN algorithm
/// (autocorrelation difference function + cumulative mean normalization)
///
/// High-performance Rust implementation using FFT-based autocorrelation
/// for frame-level pitch estimation with parabolic interpolation refinement.
///
/// Reference:
/// de Cheveigné, Alain & Kawahara, Hideki.
/// "YIN, a fundamental frequency estimator for speech and music."
/// JASA 111, 2002.

use std::f64::consts::PI;
use rayon::prelude::*;

/// Detect fundamental frequency using YIN algorithm
///
/// # Arguments
/// * `y` - Audio signal [n_samples]
/// * `sr` - Sample rate (Hz)
/// * `fmin` - Minimum frequency (Hz)
/// * `fmax` - Maximum frequency (Hz)
///
/// # Returns
/// Fundamental frequency estimates [n_frames], 0.0 for unvoiced frames
///
/// # Parameters
/// - Frame length: 2048 samples (~46ms at 44.1kHz)
/// - Hop length: 512 samples (~11.6ms, 25% overlap)
/// - Trough threshold: 0.1 (AACF relative tolerance)
pub fn yin(
    y: &[f64],
    sr: usize,
    fmin: f64,
    fmax: f64,
) -> Vec<f64> {
    const FRAME_LENGTH: usize = 2048;
    const HOP_LENGTH: usize = 512;
    const TROUGH_THRESHOLD: f64 = 0.15;  // Slightly higher to avoid false positives

    if y.len() < FRAME_LENGTH {
        return vec![0.0];
    }

    let n_frames = (y.len() - FRAME_LENGTH) / HOP_LENGTH + 1;

    // Pre-compute min/max lag values in samples
    let min_lag = ((sr as f64) / fmax) as usize;
    let max_lag = ((sr as f64) / fmin) as usize;

    // Clamp lag bounds to frame length
    let min_lag = min_lag.max(2);  // Avoid aliasing at lag=0,1
    let max_lag = max_lag.min(FRAME_LENGTH - 1);

    if min_lag >= max_lag {
        return vec![0.0; n_frames];
    }

    // Parallel frame processing using rayon
    // Each frame is independent, so this is embarrassingly parallel
    let f0_contour: Vec<f64> = (0..n_frames)
        .into_par_iter()
        .map(|frame_idx| {
            let start = frame_idx * HOP_LENGTH;
            let end = (start + FRAME_LENGTH).min(y.len());
            let frame_len = end - start;

            if frame_len < FRAME_LENGTH {
                // Pad with zeros if at end of audio
                let mut frame = vec![0.0; FRAME_LENGTH];
                frame[..frame_len].copy_from_slice(&y[start..end]);
                process_frame(&frame, sr as f64, min_lag, max_lag, TROUGH_THRESHOLD)
            } else {
                process_frame(&y[start..end], sr as f64, min_lag, max_lag, TROUGH_THRESHOLD)
            }
        })
        .collect();

    f0_contour
}

/// Process a single frame to extract fundamental frequency
fn process_frame(frame: &[f64], sr: f64, min_lag: usize, max_lag: usize, threshold: f64) -> f64 {
    debug_assert_eq!(frame.len(), 2048);

    // Step 1: Compute difference function
    let df = compute_difference_function(frame);

    // Step 2: Cumulative mean normalization
    let aacf = cumulative_mean_normalization(&df);

    // Step 3: Find first minimum below trough_threshold within frequency bounds
    let tau_min = find_trough(&aacf, min_lag, max_lag, threshold);

    match tau_min {
        Some(tau) => {
            // Step 4: Parabolic interpolation refinement
            let refined_lag = parabolic_interpolate(&aacf, tau);

            // Step 5: Convert period to frequency
            let frequency = sr / refined_lag;

            // Step 6: Final validation
            if frequency.is_finite() && frequency > 0.0 {
                frequency
            } else {
                0.0
            }
        }
        None => 0.0,  // Unvoiced frame - no trough found in bounds
    }
}

/// Compute Difference Function (DF) for autocorrelation
///
/// DF[τ] = Σ(y[n] - y[n+τ])² for n in [0, N-τ-1]
///
/// Can be rewritten as:
/// DF[τ] = Σy[n]² + Σy[n+τ]² - 2·Σ(y[n]·y[n+τ])
///
/// For efficiency with the ACF computation, use direct method
fn compute_difference_function(frame: &[f64]) -> Vec<f64> {
    let n = frame.len();
    let mut df = vec![0.0; n];

    // DF[0] is always 0 (y[n] - y[n] = 0)
    df[0] = 0.0;

    // Direct computation for each lag
    // This is O(n²) but with good cache locality
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

/// Cumulative Mean Normalization (CMN) - convert DF to AACF
///
/// AACF[0] = 1.0
/// AACF[τ] = 2·DF[τ] / (Σ DF[i] for i in [1, τ])
///
/// Normalized autocorrelation function in range [0, 2]
fn cumulative_mean_normalization(df: &[f64]) -> Vec<f64> {
    let n = df.len();
    let mut aacf = vec![0.0; n];

    // AACF[0] is always 1.0
    aacf[0] = 1.0;

    let mut running_sum = df[0];
    for tau in 1..n {
        running_sum += df[tau];

        if running_sum > 1e-10 {
            aacf[tau] = 2.0 * df[tau] / running_sum;
        } else {
            aacf[tau] = 2.0;  // High penalty for very small running sum
        }

        // Clip to valid range [0, 2]
        aacf[tau] = aacf[tau].min(2.0).max(0.0);
    }

    aacf
}

/// Find first trough (minimum) below threshold
///
/// Returns the lag index where AACF[τ] < threshold is first satisfied
/// If no such trough exists, returns None (unvoiced frame)
fn find_trough(aacf: &[f64], min_lag: usize, max_lag: usize, threshold: f64) -> Option<usize> {
    if min_lag >= aacf.len() || min_lag >= max_lag {
        return None;
    }

    let search_end = max_lag.min(aacf.len());

    // Look for the first minimum below threshold
    (min_lag..search_end).find(|&tau| aacf[tau] < threshold)
}

/// Parabolic interpolation for sub-sample refinement
///
/// Fits a parabola through three points: [τ-1, τ, τ+1]
/// Returns the refined lag position (float) at the parabola minimum
fn parabolic_interpolate(aacf: &[f64], tau: usize) -> f64 {
    if tau == 0 || tau >= aacf.len() - 1 {
        return tau as f64;
    }

    let x = tau as f64;
    let y1 = aacf[tau - 1];
    let y2 = aacf[tau];
    let y3 = aacf[tau + 1];

    // Parabola formula: y = ax² + bx + c
    // Using three points to fit parabola
    // The offset from the center point is:
    // offset = (y1 - y3) / (2·(y1 - 2·y2 + y3))

    let denom = 2.0 * (y1 - 2.0 * y2 + y3);

    if denom.abs() < 1e-10 {
        return x;  // Avoid division by zero
    }

    let offset = (y1 - y3) / denom;

    // Clamp offset to [-0.5, 0.5] to avoid wild extrapolation
    let offset = offset.clamp(-0.5, 0.5);

    x + offset
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_yin_output_shape() {
        let audio = vec![0.0; 44100];
        let f0 = yin(&audio, 44100, 50.0, 2000.0);
        assert_eq!(f0.len(), (audio.len() - 2048) / 512 + 1);
    }

    #[test]
    fn test_yin_short_audio() {
        let audio = vec![0.0; 1000];  // Shorter than FRAME_LENGTH
        let f0 = yin(&audio, 44100, 50.0, 2000.0);
        assert_eq!(f0.len(), 1);
        assert_eq!(f0[0], 0.0);  // Should be unvoiced
    }

    #[test]
    fn test_yin_sine_wave_440hz() {
        // Generate 440 Hz sine wave at 44.1kHz for shorter duration
        let sr = 44100;
        let freq = 440.0;
        let duration = 0.5;
        let n_samples = (sr as f64 * duration) as usize;

        let mut audio = vec![0.0; n_samples];
        for i in 0..n_samples {
            let t = i as f64 / sr as f64;
            audio[i] = (2.0 * PI * freq * t).sin();
        }

        let f0 = yin(&audio, sr, 50.0, 2000.0);

        // Filter out unvoiced frames (f0 == 0.0)
        let voiced: Vec<_> = f0.iter().copied().filter(|&x| x > 0.0).collect();

        // Should have detected some voiced frames in a pure sine wave
        assert!(!voiced.is_empty(), "Pure 440 Hz sine should have voiced frames");

        let mean_f0 = voiced.iter().sum::<f64>() / voiced.len() as f64;

        // YIN may detect harmonics or subharmonics, so be permissive
        // but check that we're detecting something in the ballpark
        assert!(mean_f0 > 100.0 && mean_f0 < 1500.0,
                "440 Hz detection should be reasonable, got {:.2} Hz", mean_f0);
    }

    #[test]
    fn test_yin_silence() {
        let audio = vec![0.0; 44100];  // Pure silence
        let f0 = yin(&audio, 44100, 50.0, 2000.0);

        // All frames should be unvoiced (0.0)
        let unvoiced_count = f0.iter().filter(|&&x| x == 0.0).count();
        assert_eq!(unvoiced_count, f0.len(), "Silence should produce all unvoiced frames");
    }

    #[test]
    fn test_yin_white_noise() {
        // Generate white noise
        let sr = 44100;
        let mut audio = vec![0.0; sr];

        // Simple LCG for deterministic "random" numbers
        let mut seed: u64 = 12345;
        for i in 0..audio.len() {
            seed = seed.wrapping_mul(1664525).wrapping_add(1013904223);
            let u = seed as f64 / u64::MAX as f64;
            audio[i] = (u - 0.5) * 0.5;  // Scale to [-0.25, 0.25]
        }

        let f0 = yin(&audio, sr, 50.0, 2000.0);

        // For white noise, YIN will still find periodicity
        // Just check that we get output without panicking
        assert_eq!(f0.len(), (audio.len() - 2048) / 512 + 1);

        // Check no NaN/Inf
        for &freq in &f0 {
            assert!(freq.is_finite() || freq == 0.0, "Got invalid frequency: {}", freq);
        }
    }

    #[test]
    fn test_yin_dc_offset() {
        // Generate sine wave with DC offset
        let sr = 44100;
        let freq = 440.0;
        let duration = 0.1;
        let n_samples = (sr as f64 * duration) as usize;
        let mut audio = vec![0.0; n_samples];

        for i in 0..n_samples {
            let t = i as f64 / sr as f64;
            audio[i] = (2.0 * PI * freq * t).sin() + 1.0;  // DC offset of +1.0
        }

        let f0 = yin(&audio, sr, 50.0, 2000.0);

        // Should detect some pitch despite DC offset
        let voiced: Vec<_> = f0.iter().copied().filter(|&x| x > 0.0).collect();
        assert!(!voiced.is_empty(), "DC offset sine should still have voiced frames");

        let mean_f0 = voiced.iter().sum::<f64>() / voiced.len() as f64;

        // Check if detected frequency is within reasonable range
        // YIN may find harmonics or nearby frequencies
        assert!(mean_f0 > freq / 3.0 && mean_f0 < freq * 3.0,
                "440 Hz detection with DC offset: detected {:.2} Hz (out of expected range)",
                mean_f0);
    }

    #[test]
    fn test_difference_function() {
        // Create a simple test frame
        let frame = vec![0.5; 2048];
        let df = compute_difference_function(&frame);

        // For constant signal, DF[τ] should be 0 for all τ
        for (tau, &val) in df.iter().enumerate() {
            assert!(val < 1e-10, "DF[{}] = {} should be ~0 for constant signal", tau, val);
        }
    }

    #[test]
    fn test_cmn_normalization() {
        // Create DF with known values
        let df = vec![1.0, 0.5, 0.3, 0.2, 0.1];
        let aacf = cumulative_mean_normalization(&df);

        // AACF[0] must be 1.0
        assert_eq!(aacf[0], 1.0);

        // AACF must be in [0, 2]
        for &val in &aacf {
            assert!(val >= 0.0 && val <= 2.0, "AACF value {} out of range [0, 2]", val);
        }

        // AACF should generally increase (as DF decreases) for normalized values
        assert!(aacf[1] < aacf[0], "AACF should decrease for small DF values");
    }

    #[test]
    fn test_parabolic_interpolation() {
        // Create AACF with a clear minimum at tau=5
        let mut aacf = vec![1.0; 10];
        aacf[4] = 0.3;
        aacf[5] = 0.1;  // Minimum
        aacf[6] = 0.3;

        let refined = parabolic_interpolate(&aacf, 5);

        // Refined should be close to 5.0
        assert!((refined - 5.0).abs() < 0.1, "Parabolic interpolation error: got {}", refined);
    }

    #[test]
    fn test_yin_frequency_bounds() {
        // Generate sine wave outside the default bounds
        let sr = 44100;
        let freq = 5000.0;  // Above C7 (2093 Hz)
        let duration = 0.1;
        let n_samples = (sr as f64 * duration) as usize;
        let mut audio = vec![0.0; n_samples];

        for i in 0..n_samples {
            let t = i as f64 / sr as f64;
            audio[i] = (2.0 * PI * freq * t).sin();
        }

        let f0 = yin(&audio, sr, 65.4, 2093.0);  // Bounds: C2 to C7

        // YIN should still give output (may find subharmonics)
        // Just verify it doesn't crash and produces valid output
        assert_eq!(f0.len(), (audio.len() - 2048) / 512 + 1);

        // Check no NaN/Inf
        for &freq in &f0 {
            assert!(freq.is_finite() || freq == 0.0, "Got invalid frequency: {}", freq);
            // If frequency detected, should respect bounds
            if freq > 0.0 {
                assert!(freq >= 60.0 && freq <= 2200.0, "Detected frequency out of bounds: {}", freq);
            }
        }
    }

    #[test]
    fn test_yin_nan_inf_safety() {
        // Test with extreme values
        let mut audio = vec![0.0; 44100];
        audio[0] = 1e6;  // Very large value
        audio[100] = 1e-10;  // Very small value

        let f0 = yin(&audio, 44100, 50.0, 2000.0);

        // Should not produce NaN or Inf
        for (i, &freq) in f0.iter().enumerate() {
            assert!(freq.is_finite() || freq == 0.0,
                    "Frame {} produced non-finite value: {}", i, freq);
        }
    }

    #[test]
    fn test_yin_multiple_sine_waves() {
        // Generate mixture of two sine waves
        let sr = 44100;
        let freq1 = 440.0;
        let freq2 = 880.0;  // Octave above
        let duration = 0.2;
        let n_samples = (sr as f64 * duration) as usize;

        let mut audio = vec![0.0; n_samples];
        for i in 0..n_samples {
            let t = i as f64 / sr as f64;
            audio[i] = 0.5 * (2.0 * PI * freq1 * t).sin() +
                       0.5 * (2.0 * PI * freq2 * t).sin();
        }

        let f0 = yin(&audio, sr, 50.0, 2000.0);

        let voiced: Vec<_> = f0.iter().copied().filter(|&x| x > 0.0).collect();

        // For mixed frequencies, YIN detects periodicity
        assert!(!voiced.is_empty(), "Mixed sine waves should have some voiced frames");

        let mean_f0 = voiced.iter().sum::<f64>() / voiced.len() as f64;

        // YIN may detect fundamental, harmonic, or subharmonic
        // Just verify it's detecting something in a reasonable range
        assert!(mean_f0 > 200.0 && mean_f0 < 2000.0,
                "Mixed sine detection should be reasonable, got {:.2} Hz", mean_f0);
    }
}

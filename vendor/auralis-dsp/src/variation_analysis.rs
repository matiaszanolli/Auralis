/// Temporal variation analysis
/// Measures how audio characteristics vary over time

/// Compute dynamic range in decibels
fn compute_dynamic_range_db(signal: &[f32]) -> f32 {
    if signal.is_empty() {
        return 0.0;
    }

    let max_abs = signal.iter().map(|s| s.abs()).fold(0.0f32, f32::max);
    let min_nonzero = signal
        .iter()
        .map(|s| s.abs())
        .filter(|&s| s > 1e-10)
        .fold(f32::INFINITY, f32::min);

    if max_abs < 1e-10 || min_nonzero == f32::INFINITY {
        return 0.0;
    }

    20.0 * (max_abs / min_nonzero).log10()
}

/// Compute RMS level of signal
fn compute_rms(signal: &[f32]) -> f32 {
    if signal.is_empty() {
        return 0.0;
    }

    let sum_sq: f32 = signal.iter().map(|s| s * s).sum();
    (sum_sq / signal.len() as f32).sqrt()
}

/// Estimate LUFS (approximate, uses RMS + loudness weighting)
fn estimate_lufs(signal: &[f32], sample_rate: u32) -> f32 {
    let rms = compute_rms(signal);
    if rms < 1e-10 {
        return -120.0;
    }

    // Simple LUFS approximation (not ITU-1771 certified)
    // True LUFS uses frequency weighting, gate, and integration
    let db = 20.0 * rms.log10() + 1.0; // Arbitrary calibration

    db.max(-120.0).min(0.0) // Clamp to reasonable range
}

/// Divide signal into frames and compute metric for each
fn frame_analysis<F>(signal: &[f32], sample_rate: u32, frame_duration: f32, mut metric_fn: F) -> Vec<f32>
where
    F: FnMut(&[f32]) -> f32,
{
    let frame_size = ((frame_duration * sample_rate as f32) as usize).max(1);
    let mut results = Vec::new();

    for chunk in signal.chunks(frame_size) {
        results.push(metric_fn(chunk));
    }

    results
}

/// Compute standard deviation of a sequence
fn compute_std_dev(values: &[f32]) -> f32 {
    if values.len() < 2 {
        return 0.0;
    }

    let mean: f32 = values.iter().sum::<f32>() / values.len() as f32;
    let variance: f32 = values
        .iter()
        .map(|&v| (v - mean).powi(2))
        .sum::<f32>()
        / values.len() as f32;

    variance.sqrt()
}

/// Compute coefficient of variation (std dev / mean)
fn compute_cv(values: &[f32]) -> f32 {
    if values.is_empty() {
        return 0.0;
    }

    let mean: f32 = values.iter().sum::<f32>() / values.len() as f32;
    if mean.abs() < 1e-10 {
        return 0.0;
    }

    let std_dev = compute_std_dev(values);
    std_dev / mean.abs()
}

/// Compute dynamic range variation (std dev of per-frame dynamic range)
/// Higher = more varying dynamics
/// Range: 0.0 to ~20.0 dB
///
/// # Arguments
/// * `audio` - Audio samples
/// * `sample_rate` - Sample rate in Hz
///
/// # Returns
/// Standard deviation of dynamic range across 1-second frames (dB)
pub fn compute_dynamic_range_variation(audio: &[f32], sample_rate: u32) -> f32 {
    if audio.is_empty() {
        return 0.0;
    }

    // Analyze 1-second frames
    let frame_duration = 1.0; // 1 second per frame
    let dynamic_ranges = frame_analysis(audio, sample_rate, frame_duration, |frame| {
        compute_dynamic_range_db(frame)
    });

    if dynamic_ranges.is_empty() {
        return 0.0;
    }

    // Return standard deviation (0 = consistent, high = variable)
    compute_std_dev(&dynamic_ranges).clamp(0.0, 50.0)
}

/// Compute loudness variation (std dev of per-frame LUFS)
/// Higher = more varying loudness
/// Range: 0.0 to ~20.0 LUFS
///
/// # Arguments
/// * `audio` - Audio samples
/// * `sample_rate` - Sample rate in Hz
///
/// # Returns
/// Standard deviation of loudness across 1-second frames (LUFS)
pub fn compute_loudness_variation(audio: &[f32], sample_rate: u32) -> f32 {
    if audio.is_empty() {
        return 0.0;
    }

    let frame_duration = 1.0;
    let loudness_values = frame_analysis(audio, sample_rate, frame_duration, |frame| {
        estimate_lufs(frame, sample_rate)
    });

    if loudness_values.is_empty() {
        return 0.0;
    }

    compute_std_dev(&loudness_values).clamp(0.0, 50.0)
}

/// Compute peak consistency (coefficient of variation of peak levels)
/// Lower = consistent peaks, Higher = variable peaks
/// Range: 0.0 to ~2.0
///
/// # Arguments
/// * `audio` - Audio samples
/// * `sample_rate` - Sample rate in Hz
///
/// # Returns
/// Coefficient of variation of peak levels across 1-second frames
pub fn compute_peak_consistency(audio: &[f32], sample_rate: u32) -> f32 {
    if audio.is_empty() {
        return 0.0;
    }

    let frame_duration = 1.0;
    let peak_levels = frame_analysis(audio, sample_rate, frame_duration, |frame| {
        frame.iter().map(|s| s.abs()).fold(0.0f32, f32::max)
    });

    if peak_levels.is_empty() {
        return 0.0;
    }

    // Coefficient of variation (lower = more consistent)
    compute_cv(&peak_levels).clamp(0.0, 2.0)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_compute_dynamic_range_silence() {
        let audio = vec![0.0; 48000];
        let dr = compute_dynamic_range_db(&audio);
        assert_eq!(dr, 0.0);
    }

    #[test]
    fn test_compute_dynamic_range_sine() {
        let audio: Vec<f32> = (0..48000)
            .map(|i| ((i as f32 * 0.01).sin() * 0.5).abs())
            .collect();
        let dr = compute_dynamic_range_db(&audio);
        assert!(dr > 0.0 && dr < 20.0);
    }

    #[test]
    fn test_compute_rms() {
        let audio = vec![0.1, 0.1, 0.1, 0.1];
        let rms = compute_rms(&audio);
        assert!((rms - 0.1).abs() < 0.01);
    }

    #[test]
    fn test_dynamic_range_variation_constant() {
        // Constant amplitude
        let audio = vec![0.5; 96000]; // 2 seconds at 48kHz
        let variation = compute_dynamic_range_variation(&audio, 48000);
        assert!(variation < 1.0); // Should be very low
    }

    #[test]
    fn test_dynamic_range_variation_varied() {
        // Varying amplitude
        let mut audio = Vec::new();
        for i in 0..96000 {
            let amplitude = if (i / 48000) % 2 == 0 { 0.9 } else { 0.1 };
            audio.push(amplitude);
        }
        let variation = compute_dynamic_range_variation(&audio, 48000);
        assert!(variation > 1.0); // Should be higher
    }

    #[test]
    fn test_loudness_variation() {
        let audio = vec![0.1; 96000]; // 2 seconds constant
        let variation = compute_loudness_variation(&audio, 48000);
        assert!(variation < 1.0);
    }

    #[test]
    fn test_peak_consistency_constant() {
        let audio = vec![0.5; 96000];
        let consistency = compute_peak_consistency(&audio, 48000);
        assert!(consistency < 0.1);
    }

    #[test]
    fn test_peak_consistency_varied() {
        let mut audio = Vec::new();
        for i in 0..96000 {
            let peak = if (i / 48000) % 2 == 0 { 0.9 } else { 0.1 };
            audio.push(peak);
        }
        let consistency = compute_peak_consistency(&audio, 48000);
        assert!(consistency > 0.5);
    }

    #[test]
    fn test_compute_std_dev() {
        let values = vec![1.0, 2.0, 3.0, 4.0, 5.0];
        let std_dev = compute_std_dev(&values);
        assert!((std_dev - 1.414).abs() < 0.01); // sqrt(2) ≈ 1.414
    }

    #[test]
    fn test_compute_cv() {
        let values = vec![2.0, 2.0, 2.0, 2.0];
        let cv = compute_cv(&values);
        assert!(cv < 0.01); // Should be ~0 (no variation)
    }
}

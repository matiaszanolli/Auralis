/// Temporal variation analysis
/// Measures how audio characteristics vary over time
use crate::dsp_math::{compute_rms, estimate_lufs, std_dev_about};
use crate::rhythm::SILENT_FRAME_RMS_RATIO;

/// Compute crest factor in decibels.
///
/// Crest factor compares the frame peak with its RMS energy. Unlike the
/// previous peak/minimum-sample ratio, it is stable in the presence of
/// zero-crossings and numerical noise.
fn compute_dynamic_range_db(signal: &[f32]) -> f32 {
    if signal.is_empty() {
        return 0.0;
    }

    let peak = signal.iter().map(|s| s.abs()).fold(0.0f32, f32::max);
    let rms = compute_rms(signal);

    if peak < 1e-10 || rms < 1e-10 {
        return 0.0;
    }

    20.0 * (peak / rms).log10()
}

/// Divide signal into whole frames and compute metric for each audible one.
///
/// A trailing partial frame is not scored: it would count as much as a full
/// second in the standard deviation / coefficient of variation, so one extra
/// sample (or the same audio read at another sample rate) could move the result
/// by a factor of two on a short track. A signal shorter than one frame yields
/// no frames, which the callers report as 0.0 (a single value has no variation).
///
/// Silent frames (RMS more than 40 dB below the loudest frame, the
/// `silence_ratio` gate) are not scored either (#6113): a digitally silent
/// second reads -120 LUFS, 0 dB crest and 0 peak, so one gap or rest made a
/// steady-level track look wildly dynamic. Silence is `silence_ratio`'s to report.
fn frame_analysis<F>(
    signal: &[f32],
    sample_rate: u32,
    frame_duration: f32,
    mut metric_fn: F,
) -> Vec<f32>
where
    F: FnMut(&[f32]) -> f32,
{
    let frame_size = ((frame_duration * sample_rate as f32) as usize).max(1);
    let frames: Vec<(&[f32], f32)> = signal
        .chunks_exact(frame_size)
        .map(|frame| (frame, compute_rms(frame)))
        .collect();
    let loudest = frames.iter().map(|&(_, rms)| rms).fold(0.0f32, f32::max);
    let gate = loudest * SILENT_FRAME_RMS_RATIO as f32;

    frames
        .into_iter()
        .filter(|&(_, rms)| rms > 0.0 && rms >= gate)
        .map(|(frame, _)| metric_fn(frame))
        .collect()
}

/// Compute standard deviation of a sequence
fn compute_std_dev(values: &[f32]) -> f32 {
    if values.len() < 2 {
        return 0.0;
    }

    let mean: f32 = values.iter().sum::<f32>() / values.len() as f32;
    std_dev_about(values, mean)
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
        estimate_lufs(frame)
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
        let audio: Vec<f32> = (0..48000).map(|i| (i as f32 * 0.01).sin() * 0.5).collect();
        let dr = compute_dynamic_range_db(&audio);
        assert!((dr - 3.01).abs() < 0.1);
    }

    #[test]
    fn test_compute_rms() {
        let audio = vec![0.1, 0.1, 0.1, 0.1];
        let rms = crate::dsp_math::compute_rms(&audio);
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
        // One dense frame followed by a sparse, transient frame. Changing
        // amplitude alone would not change crest factor.
        let mut audio = vec![0.5; 48000];
        for i in 0..48000 {
            audio.push(if i % 100 == 0 { 0.9 } else { 0.0 });
        }
        let variation = compute_dynamic_range_variation(&audio, 48000);
        assert!(variation > 5.0);
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

    /// Three seconds of a steady tone, so every whole frame has the same crest
    /// factor, loudness and peak.
    fn steady_tone(seconds: usize) -> Vec<f32> {
        (0..48000 * seconds)
            .map(|i| (i as f32 * 0.05).sin() * 0.5)
            .collect()
    }

    #[test]
    fn test_partial_trailing_frame_does_not_move_the_variation_metrics() {
        // A one-sample tail has crest factor 0 dB, a different loudness and a
        // different peak from the tone. Scored as a frame it dominated the
        // statistics of a short track (#6322).
        let whole = steady_tone(3);
        for tail in [vec![0.9f32], vec![0.0f32; 7], vec![0.9f32; 20000]] {
            let mut audio = whole.clone();
            audio.extend_from_slice(&tail);
            assert_eq!(
                compute_dynamic_range_variation(&audio, 48000),
                compute_dynamic_range_variation(&whole, 48000)
            );
            assert_eq!(
                compute_loudness_variation(&audio, 48000),
                compute_loudness_variation(&whole, 48000)
            );
            assert_eq!(
                compute_peak_consistency(&audio, 48000),
                compute_peak_consistency(&whole, 48000)
            );
        }
    }

    #[test]
    fn test_same_audio_at_two_rates_agrees_on_a_steady_signal() {
        // 3.5 s at 44.1 kHz and at 48 kHz: the rates leave different partial
        // tails, which used to give different answers for identical content.
        for rate in [44100u32, 48000u32] {
            let audio: Vec<f32> = (0..(rate as usize * 7 / 2))
                .map(|i| (i as f32 / rate as f32 * 440.0 * std::f32::consts::TAU).sin() * 0.5)
                .collect();
            assert!(compute_loudness_variation(&audio, rate) < 0.5);
            assert!(compute_dynamic_range_variation(&audio, rate) < 0.5);
            assert!(compute_peak_consistency(&audio, rate) < 0.05);
        }
    }

    #[test]
    fn test_signal_shorter_than_one_frame_reports_no_variation() {
        let audio = steady_tone(1)[..30000].to_vec();
        assert_eq!(compute_dynamic_range_variation(&audio, 48000), 0.0);
        assert_eq!(compute_loudness_variation(&audio, 48000), 0.0);
        assert_eq!(compute_peak_consistency(&audio, 48000), 0.0);
    }

    /// Deterministic white-ish noise at a constant level (LCG, no rand crate).
    fn steady_noise(seconds: usize, rate: usize) -> Vec<f32> {
        let mut state = 0x2545_F491_u32;
        (0..rate * seconds)
            .map(|_| {
                state = state.wrapping_mul(1_664_525).wrapping_add(1_013_904_223);
                (state as f32 / u32::MAX as f32 - 0.5) * 0.4
            })
            .collect()
    }

    #[test]
    fn test_silent_seconds_do_not_inflate_the_variation_metrics() {
        // #6113: 60 s of constant-level noise with 1/3/10 s of zeros at t=20 s read
        // loudness_variation 0.05 -> 12.7/21.6/37.0 dB. Must stay within 10%
        // of the no-gap values (plus a tiny absolute slack for near-zero values).
        let rate = 8000;
        let base = steady_noise(60, rate);
        let reference = [
            compute_loudness_variation(&base, rate as u32),
            compute_dynamic_range_variation(&base, rate as u32),
            compute_peak_consistency(&base, rate as u32),
        ];
        for gap in [1usize, 3, 10] {
            let mut audio = base[..20 * rate].to_vec();
            audio.extend(std::iter::repeat(0.0f32).take(gap * rate));
            audio.extend_from_slice(&base[20 * rate..]);
            let got = [
                compute_loudness_variation(&audio, rate as u32),
                compute_dynamic_range_variation(&audio, rate as u32),
                compute_peak_consistency(&audio, rate as u32),
            ];
            for (g, r) in got.iter().zip(reference.iter()) {
                assert!((g - r).abs() <= 0.1 * r + 0.01, "gap {gap}s: {got:?} vs {reference:?}");
            }
        }
    }

    #[test]
    fn test_all_silent_signal_reports_no_variation() {
        let audio = vec![0.0f32; 48000 * 3];
        assert_eq!(compute_loudness_variation(&audio, 48000), 0.0);
        assert_eq!(compute_dynamic_range_variation(&audio, 48000), 0.0);
        assert_eq!(compute_peak_consistency(&audio, 48000), 0.0);
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

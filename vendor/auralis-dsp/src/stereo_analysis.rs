/// Stereo field analysis
/// Measures stereo width and phase correlation between channels
use crate::dsp_math::compute_rms;

/// Compute mid-side decomposition
/// mid = (L + R) / 2
/// side = (L - R) / 2
fn compute_midside(left: &[f32], right: &[f32]) -> (Vec<f32>, Vec<f32>) {
    let mut mid = Vec::new();
    let mut side = Vec::new();

    for (l, r) in left.iter().zip(right.iter()) {
        mid.push((l + r) * 0.5);
        side.push((l - r) * 0.5);
    }

    (mid, side)
}

/// Compute stereo width (mid-side energy ratio)
/// Width = 1.0 - (mid_energy / (mid_energy + side_energy))
/// Range: 0.0 (mono, no side info) to 1.0 (pure side, no mid)
///
/// # Arguments
/// * `left` - Left channel samples
/// * `right` - Right channel samples
///
/// # Returns
/// Stereo width value 0.0-1.0
pub fn compute_stereo_width(left: &[f32], right: &[f32]) -> f32 {
    if left.is_empty() || left.len() != right.len() {
        return 0.0;
    }

    // Compute mid-side
    let (mid, side) = compute_midside(left, right);

    let mid_energy = compute_rms(&mid);
    let side_energy = compute_rms(&side);
    let total_energy = mid_energy + side_energy;

    if total_energy < 1e-10 {
        return 0.0;
    }

    // Stereo width = side / total
    // 0.0 = pure mono (no side info)
    // 1.0 = pure side (no mid info, unrealistic)
    (side_energy / total_energy).clamp(0.0, 1.0)
}

/// Compute phase correlation between channels
/// Measures how "in-phase" the channels are
/// Range: -1.0 (opposite/inverted) to 1.0 (identical)
///
/// # Arguments
/// * `left` - Left channel samples
/// * `right` - Right channel samples
///
/// # Returns
/// Phase correlation -1.0 to 1.0
pub fn compute_phase_correlation(left: &[f32], right: &[f32]) -> f32 {
    if left.is_empty() || left.len() != right.len() {
        return 1.0; // Assume mono = perfect correlation
    }

    // Pearson correlation, two passes in f64 (#6362): the f32 sums over a whole track
    // biased it (0.9026 vs 0.8823 on 900 s), and normalising each channel first only
    // allocated two track-length copies the coefficient does not need.
    let n = left.len() as f64;
    let mean_left = left.iter().map(|&s| s as f64).sum::<f64>() / n;
    let mean_right = right.iter().map(|&s| s as f64).sum::<f64>() / n;
    let (mut sum_product, mut sum_left2, mut sum_right2) = (0.0f64, 0.0f64, 0.0f64);
    for (&l, &r) in left.iter().zip(right) {
        let (a, b) = (l as f64 - mean_left, r as f64 - mean_right);
        sum_product += a * b;
        sum_left2 += a * a;
        sum_right2 += b * b;
    }

    // A constant channel has no correlation to measure: treat it as mono.
    if sum_left2 == 0.0 || sum_right2 == 0.0 {
        return 1.0;
    }

    ((sum_product / (sum_left2 * sum_right2).sqrt()) as f32).clamp(-1.0, 1.0)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_stereo_width_mono() {
        let left = vec![0.1, 0.2, 0.3, 0.4];
        let right = vec![0.1, 0.2, 0.3, 0.4]; // Same as left
        let width = compute_stereo_width(&left, &right);
        assert!(width < 0.1); // Should be very low (mono)
    }

    #[test]
    fn test_stereo_width_stereo() {
        let left = vec![0.5, 0.5, 0.5, 0.5];
        let right = vec![-0.5, -0.5, -0.5, -0.5]; // Opposite
        let width = compute_stereo_width(&left, &right);
        assert!(width > 0.5); // Should be high (stereo)
    }

    #[test]
    fn test_phase_correlation_mono() {
        let left = vec![0.1, 0.2, 0.3, 0.4];
        let right = vec![0.1, 0.2, 0.3, 0.4]; // Identical
        let correlation = compute_phase_correlation(&left, &right);
        assert!((correlation - 1.0).abs() < 0.01); // Should be ~1.0
    }

    #[test]
    fn test_phase_correlation_opposite() {
        // An inverted AC signal (#5859: the old constant ±0.5 input has zero
        // variance, where the correlation is undefined and falls back to 1.0).
        let left = vec![0.5, -0.3, 0.2, -0.4];
        let right: Vec<f32> = left.iter().map(|s| -s).collect();
        let correlation = compute_phase_correlation(&left, &right);
        assert!((correlation + 1.0).abs() < 0.01); // Should be ~-1.0
    }

    #[test]
    fn test_phase_correlation_constant_channels_fall_back_to_one() {
        // Zero-variance (DC) channels have no defined correlation; treated as mono.
        let correlation = compute_phase_correlation(&[0.5; 4], &[-0.5; 4]);
        assert_eq!(correlation, 1.0);
    }

    #[test]
    fn test_phase_correlation_uncorrelated() {
        let left = vec![0.1, 0.3, 0.5, 0.7];
        let right = vec![0.9, 0.1, 0.8, 0.2]; // Different
        let correlation = compute_phase_correlation(&left, &right);
        assert!(correlation.abs() < 0.8); // Should be somewhere in between
    }

    #[test]
    fn test_compute_rms() {
        // RMS: sqrt((0.09 + 0.16) / 2) = sqrt(0.125) ≈ 0.3536 (#5859: the old
        // expectation divided the root by N instead of the sum).
        let signal = vec![0.3, 0.4];
        let energy = compute_rms(&signal);
        assert!((energy - 0.125f32.sqrt()).abs() < 1e-6);
    }

    #[test]
    fn test_phase_correlation_ignores_gain_and_offset() {
        // What the removed per-channel normalisation guaranteed: correlation does not
        // depend on either channel's level or DC offset.
        let left = vec![0.1, -0.4, 0.3, 0.2, -0.1, 0.5];
        let right = vec![0.2, -0.3, 0.1, 0.4, -0.2, 0.3];
        let reference = compute_phase_correlation(&left, &right);
        let scaled: Vec<f32> = right.iter().map(|s| s * 0.01 + 0.25).collect();
        assert!((compute_phase_correlation(&left, &scaled) - reference).abs() < 1e-5);
    }

    #[test]
    fn test_phase_correlation_of_a_long_input_is_exact() {
        // #6362: f32 sums over 900 s read 0.9026 where the truth was 0.8823. Left and
        // right share one deterministic source plus independent parts of known power, so
        // the correlation is known in closed form: 1 / (1 + 0.25) = 0.8 for equal levels.
        let n = 22050 * 900;
        let mut state = 0x9E37_79B9_u32;
        let mut next = || {
            state = state.wrapping_mul(1_664_525).wrapping_add(1_013_904_223);
            (state as f32 / u32::MAX as f32 - 0.5) * 2.0
        };
        let (mut left, mut right) = (Vec::with_capacity(n), Vec::with_capacity(n));
        for _ in 0..n {
            let common = next();
            left.push(0.4 * common + 0.2 * next());
            right.push(0.4 * common + 0.2 * next());
        }
        let correlation = compute_phase_correlation(&left, &right);
        assert!((correlation - 0.8).abs() < 0.002, "{correlation}");
    }
}

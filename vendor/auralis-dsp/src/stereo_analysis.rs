/// Stereo field analysis
/// Measures stereo width and phase correlation between channels

/// Check if audio is stereo (has significant difference between channels)
fn is_stereo_signals(left: &[f32], right: &[f32]) -> bool {
    if left.len() != right.len() {
        return false;
    }

    if left.is_empty() {
        return false;
    }

    // Compute correlation coefficient
    let mut sum_xy = 0.0f32;
    let mut sum_x = 0.0f32;
    let mut sum_y = 0.0f32;
    let mut sum_x2 = 0.0f32;
    let mut sum_y2 = 0.0f32;

    for (x, y) in left.iter().zip(right.iter()) {
        sum_xy += x * y;
        sum_x += x;
        sum_y += y;
        sum_x2 += x * x;
        sum_y2 += y * y;
    }

    let n = left.len() as f32;
    let correlation = (n * sum_xy - sum_x * sum_y)
        / ((n * sum_x2 - sum_x * sum_x) * (n * sum_y2 - sum_y * sum_y)).sqrt();

    // If correlation is close to 1.0, channels are nearly identical (mono)
    correlation.abs() < 0.95
}

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

/// Compute RMS energy
fn compute_energy(signal: &[f32]) -> f32 {
    if signal.is_empty() {
        return 0.0;
    }

    let sum_sq: f32 = signal.iter().map(|s| s * s).sum();
    (sum_sq / signal.len() as f32).sqrt()
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

    let mid_energy = compute_energy(&mid);
    let side_energy = compute_energy(&side);
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

    // Normalize to [-1, 1]
    let left_norm = normalize_signal(left);
    let right_norm = normalize_signal(right);

    // Compute correlation coefficient
    let mut sum_product = 0.0f32;
    let mut sum_left2 = 0.0f32;
    let mut sum_right2 = 0.0f32;

    for (l, r) in left_norm.iter().zip(right_norm.iter()) {
        sum_product += l * r;
        sum_left2 += l * l;
        sum_right2 += r * r;
    }

    let denominator = (sum_left2 * sum_right2).sqrt();
    if denominator < 1e-10 {
        return 1.0;
    }

    (sum_product / denominator).clamp(-1.0, 1.0)
}

/// Normalize signal to zero mean and unit variance
fn normalize_signal(signal: &[f32]) -> Vec<f32> {
    if signal.is_empty() {
        return vec![];
    }

    let mean: f32 = signal.iter().sum::<f32>() / signal.len() as f32;
    let variance: f32 = signal
        .iter()
        .map(|&s| (s - mean).powi(2))
        .sum::<f32>()
        / signal.len() as f32;

    let std_dev = variance.sqrt().max(1e-10);

    signal
        .iter()
        .map(|&s| (s - mean) / std_dev)
        .collect()
}

/// Detect if signal is mono (very high correlation) or stereo
/// This is a convenience function
///
/// # Arguments
/// * `channels` - Number of channels
/// * `audio` - Interleaved audio samples (for stereo: L, R, L, R, ...)
///
/// # Returns
/// true if stereo, false if mono
pub fn is_stereo(channels: u32, audio: &[f32]) -> bool {
    if channels != 2 || audio.is_empty() {
        return channels > 1;
    }

    // Extract left and right channels
    let left: Vec<f32> = audio.iter().step_by(2).copied().collect();
    let right: Vec<f32> = audio.iter().skip(1).step_by(2).copied().collect();

    is_stereo_signals(&left, &right)
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
        let left = vec![0.5, 0.5, 0.5, 0.5];
        let right = vec![-0.5, -0.5, -0.5, -0.5]; // Opposite
        let correlation = compute_phase_correlation(&left, &right);
        assert!((correlation + 1.0).abs() < 0.01); // Should be ~-1.0
    }

    #[test]
    fn test_phase_correlation_uncorrelated() {
        let left = vec![0.1, 0.3, 0.5, 0.7];
        let right = vec![0.9, 0.1, 0.8, 0.2]; // Different
        let correlation = compute_phase_correlation(&left, &right);
        assert!(correlation.abs() < 0.8); // Should be somewhere in between
    }

    #[test]
    fn test_is_stereo_mono() {
        let audio = vec![0.1, 0.1, 0.2, 0.2, 0.3, 0.3]; // L=0.1, R=0.1, etc.
        let stereo = is_stereo(2, &audio);
        assert!(!stereo);
    }

    #[test]
    fn test_is_stereo_wide() {
        let audio = vec![0.5, -0.5, 0.5, -0.5, 0.5, -0.5]; // L=0.5, R=-0.5
        let stereo = is_stereo(2, &audio);
        assert!(stereo);
    }

    #[test]
    fn test_compute_energy() {
        let signal = vec![0.3, 0.4]; // sqrt(0.09 + 0.16) / 2 = sqrt(0.25) / 2 = 0.25
        let energy = compute_energy(&signal);
        assert!((energy - 0.25).abs() < 0.01);
    }

    #[test]
    fn test_normalize_signal() {
        let signal = vec![1.0, 2.0, 3.0, 4.0, 5.0];
        let normalized = normalize_signal(&signal);

        // Mean of normalized should be ~0
        let mean: f32 = normalized.iter().sum::<f32>() / normalized.len() as f32;
        assert!(mean.abs() < 0.01);

        // Std dev of normalized should be ~1
        let variance: f32 = normalized
            .iter()
            .map(|&s| s * s)
            .sum::<f32>()
            / normalized.len() as f32;
        assert!((variance.sqrt() - 1.0).abs() < 0.01);
    }
}

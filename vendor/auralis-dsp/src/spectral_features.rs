/// Spectral feature analysis (centroid, rolloff, flatness)
/// These features describe the "shape" and "color" of the audio spectrum

use std::f32::consts::PI;

/// Compute spectral centroid (center of mass of spectrum)
/// Higher values = brighter/more high-frequency content
/// Range: 0.0 - Nyquist frequency (Hz)
///
/// # Arguments
/// * `psd` - Power spectral density (from FFT)
/// * `freqs` - Frequency values for each bin (Hz)
///
/// # Returns
/// Spectral centroid in Hz
pub fn compute_spectral_centroid(psd: &[f32], freqs: &[f32]) -> f32 {
    if psd.is_empty() || psd.len() != freqs.len() {
        return 0.0;
    }

    let total_power: f32 = psd.iter().sum();
    if total_power < 1e-10 {
        return 0.0;
    }

    let weighted_sum: f32 = psd
        .iter()
        .zip(freqs.iter())
        .map(|(power, freq)| power * freq)
        .sum();

    weighted_sum / total_power
}

/// Compute spectral rolloff (frequency containing 85% of energy)
/// Lower = more concentrated energy, Higher = spread energy
/// Range: 0.0 - Nyquist frequency (Hz)
///
/// # Arguments
/// * `psd` - Power spectral density
/// * `freqs` - Frequency values for each bin
/// * `rolloff` - Threshold percentage (0.0 - 1.0), typically 0.85
///
/// # Returns
/// Rolloff frequency in Hz
pub fn compute_spectral_rolloff(psd: &[f32], freqs: &[f32], rolloff: f32) -> f32 {
    if psd.is_empty() || psd.len() != freqs.len() {
        return 0.0;
    }

    let total_power: f32 = psd.iter().sum();
    if total_power < 1e-10 {
        return 0.0;
    }

    let threshold = rolloff * total_power;
    let mut cumulative = 0.0;

    for (power, freq) in psd.iter().zip(freqs.iter()) {
        cumulative += power;
        if cumulative >= threshold {
            return *freq;
        }
    }

    freqs[freqs.len() - 1]
}

/// Compute spectral flatness (Wiener entropy)
/// Measures noisiness vs tonality
/// Range: 0.0 (pure tone) to 1.0 (white noise)
///
/// Flatness = (geometric_mean) / (arithmetic_mean)
/// where geometric_mean = exp(mean(log(psd)))
///       arithmetic_mean = mean(psd)
///
/// # Arguments
/// * `psd` - Power spectral density
///
/// # Returns
/// Spectral flatness (0.0 = tone, 1.0 = noise)
pub fn compute_spectral_flatness(psd: &[f32]) -> f32 {
    if psd.is_empty() {
        return 0.0;
    }

    // Filter out zeros to avoid log(0)
    let nonzero_psd: Vec<f32> = psd.iter().filter(|&&p| p > 1e-10).copied().collect();
    if nonzero_psd.is_empty() {
        return 0.0;
    }

    // Geometric mean = exp(mean(log(psd)))
    let log_sum: f32 = nonzero_psd.iter().map(|&p| p.ln()).sum();
    let geometric_mean = (log_sum / nonzero_psd.len() as f32).exp();

    // Arithmetic mean
    let arithmetic_mean: f32 = nonzero_psd.iter().sum::<f32>() / nonzero_psd.len() as f32;

    if arithmetic_mean < 1e-10 {
        return 0.0;
    }

    // Flatness = geometric / arithmetic (0 to 1)
    (geometric_mean / arithmetic_mean).clamp(0.0, 1.0)
}

/// Helper: Convert audio to frequency domain
/// Returns (frequencies, psd)
pub fn audio_to_freq_domain(audio: &[f32], sample_rate: u32) -> (Vec<f32>, Vec<f32>) {
    use rustfft::num_complex::Complex;
    use rustfft::FftPlanner;

    if audio.is_empty() {
        return (vec![], vec![]);
    }

    // FFT setup
    let fft_size = (audio.len() as f32).log2().ceil() as u32;
    let fft_size = 2usize.pow(fft_size);

    let mut fft_input: Vec<Complex<f32>> = vec![Complex { re: 0.0, im: 0.0 }; fft_size];
    for (i, &sample) in audio.iter().enumerate() {
        fft_input[i].re = sample;
    }

    // Apply Hann window
    let n = audio.len() as f32;
    for (i, sample) in fft_input.iter_mut().enumerate().take(audio.len()) {
        let window = 0.5 * (1.0 - ((2.0 * PI * i as f32) / n).cos());
        sample.re *= window;
    }

    // Compute FFT
    let mut planner = FftPlanner::new();
    let fft = planner.plan_fft_forward(fft_size);
    fft.process(&mut fft_input);

    // Compute PSD
    let psd: Vec<f32> = fft_input
        .iter()
        .map(|c| c.norm_sqr() / (fft_size as f32).powi(2))
        .collect();

    // Compute frequencies
    let freqs: Vec<f32> = (0..fft_size / 2)
        .map(|i| (i as f32 * sample_rate as f32) / fft_size as f32)
        .collect();

    (freqs, psd[..fft_size / 2].to_vec())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_spectral_centroid_bass() {
        // Bass dominated spectrum
        let mut freqs = vec![];
        let mut psd = vec![];

        for i in 0..100 {
            freqs.push(i as f32 * 10.0);
            psd.push(if i < 20 { 1.0 } else { 0.1 }); // Bass concentrated
        }

        let centroid = compute_spectral_centroid(&psd, &freqs);
        assert!(centroid < 500.0); // Should be in bass range
    }

    #[test]
    fn test_spectral_centroid_treble() {
        // Treble dominated spectrum
        let mut freqs = vec![];
        let mut psd = vec![];

        for i in 0..100 {
            freqs.push(i as f32 * 100.0);
            psd.push(if i > 80 { 1.0 } else { 0.1 }); // Treble concentrated
        }

        let centroid = compute_spectral_centroid(&psd, &freqs);
        assert!(centroid > 5000.0); // Should be in treble range
    }

    #[test]
    fn test_spectral_rolloff() {
        let freqs: Vec<f32> = (0..100).map(|i| i as f32 * 100.0).collect();
        let psd: Vec<f32> = (0..100).map(|_| 1.0).collect(); // Uniform spectrum

        let rolloff = compute_spectral_rolloff(&psd, &freqs, 0.85);
        // 85% should be around 85% of max frequency
        assert!(rolloff > 7000.0 && rolloff < 9000.0);
    }

    #[test]
    fn test_spectral_flatness_tone() {
        // Single frequency (tone) - low flatness
        let mut psd = vec![0.0; 100];
        psd[20] = 1.0; // Single peak

        let flatness = compute_spectral_flatness(&psd);
        assert!(flatness < 0.5); // Should be low (tone-like)
    }

    #[test]
    fn test_spectral_flatness_white_noise() {
        // Uniform spectrum (white noise) - high flatness
        let psd = vec![1.0; 100];

        let flatness = compute_spectral_flatness(&psd);
        assert!(flatness > 0.9); // Should be high (noise-like)
    }

    #[test]
    fn test_spectral_flatness_empty() {
        let psd = vec![];
        let flatness = compute_spectral_flatness(&psd);
        assert_eq!(flatness, 0.0);
    }
}

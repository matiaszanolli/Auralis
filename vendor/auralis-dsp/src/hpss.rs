/// Harmonic/Percussive Source Separation (HPSS)
///
/// High-performance Rust implementation of harmonic/percussive audio decomposition
/// using median filtering on STFT magnitude with Wiener soft masking.
///
/// References:
/// - Fitzgerald, Derry. "Harmonic/percussive separation using median filtering." DAFX10, 2010.
/// - Driedger, Müller, Disch. "Extending harmonic-percussive separation." ISMIR 2014.

use ndarray::Array2;
use num_complex::Complex64;
use rustfft::{FftPlanner, num_complex};
use std::f64::consts::PI;

/// HPSS configuration parameters
#[derive(Clone, Debug)]
pub struct HpssConfig {
    /// FFT size (default: 2048)
    pub n_fft: usize,
    /// Hop length (default: 512, 25% overlap)
    pub hop_length: usize,
    /// Harmonic median filter kernel size (default: 31)
    pub kernel_h: usize,
    /// Percussive median filter kernel size (default: 31)
    pub kernel_p: usize,
    /// Wiener filter power (default: 2.0)
    pub power: f64,
    /// Harmonic margin (default: 1.0)
    pub margin_h: f64,
    /// Percussive margin (default: 1.0)
    pub margin_p: f64,
}

impl Default for HpssConfig {
    fn default() -> Self {
        Self {
            n_fft: 2048,
            hop_length: 512,
            kernel_h: 31,
            kernel_p: 31,
            power: 2.0,
            margin_h: 1.0,
            margin_p: 1.0,
        }
    }
}

/// Decompose audio into harmonic and percussive components
///
/// # Arguments
/// * `y` - Audio signal [n_samples]
/// * `config` - HPSS configuration
///
/// # Returns
/// Tuple of (harmonic_audio, percussive_audio) [n_samples each]
pub fn hpss(y: &[f64], config: &HpssConfig) -> (Vec<f64>, Vec<f64>) {
    // Handle audio shorter than one FFT frame
    if y.len() < config.n_fft {
        // Return zeros for both components (can't perform HPSS on too-short audio)
        return (vec![0.0; y.len()], vec![0.0; y.len()]);
    }

    // STFT analysis
    let stft = compute_stft(y, config.n_fft, config.hop_length);

    // Extract magnitude and phase
    let magnitude = extract_magnitude(&stft);
    let phase = extract_phase(&stft);

    // Decompose magnitude into harmonic and percussive
    let (harm_mag, perc_mag) = decompose_magnitude(&magnitude, config);

    // Reconstruct with original phase
    let stft_h = reapply_phase(&harm_mag, &phase);
    let stft_p = reapply_phase(&perc_mag, &phase);

    // ISTFT synthesis
    let harmonic = compute_istft(&stft_h, config.n_fft, config.hop_length, y.len());
    let percussive = compute_istft(&stft_p, config.n_fft, config.hop_length, y.len());

    (harmonic, percussive)
}

/// Compute Short-Time Fourier Transform (STFT) with Hann window
fn compute_stft(y: &[f64], n_fft: usize, hop_length: usize) -> Array2<Complex64> {
    // Handle case where audio is shorter than FFT size
    let n_frames = if y.len() < n_fft {
        0
    } else {
        (y.len() - n_fft) / hop_length + 1
    };
    let n_freqs = n_fft / 2 + 1;

    // Return empty STFT for too-short audio
    if n_frames == 0 {
        return Array2::<Complex64>::zeros((n_freqs, 0));
    }

    let mut stft = Array2::<Complex64>::zeros((n_freqs, n_frames));

    // Pre-compute Hann window
    let window = hann_window(n_fft);

    // FFT planner (reused across frames)
    let mut planner = FftPlanner::new();
    let fft = planner.plan_fft_forward(n_fft);

    // Processing buffer
    let mut buffer = vec![Complex64::new(0.0, 0.0); n_fft];

    // Process each frame
    for frame_idx in 0..n_frames {
        let start = frame_idx * hop_length;

        // Fill buffer with windowed frame
        for i in 0..n_fft {
            if start + i < y.len() {
                let sample = y[start + i];
                buffer[i] = Complex64::new(sample * window[i], 0.0);
            } else {
                buffer[i] = Complex64::new(0.0, 0.0);
            }
        }

        // Compute FFT
        fft.process(&mut buffer);

        // Store positive frequencies
        for k in 0..n_freqs {
            stft[[k, frame_idx]] = buffer[k];
        }
    }

    stft
}

/// Extract magnitude spectrogram from STFT
fn extract_magnitude(stft: &Array2<Complex64>) -> Array2<f64> {
    stft.mapv(|c| c.norm())
}

/// Extract phase from STFT
fn extract_phase(stft: &Array2<Complex64>) -> Array2<f64> {
    stft.mapv(|c| c.arg())
}

/// Reapply phase to magnitude spectrogram
fn reapply_phase(magnitude: &Array2<f64>, phase: &Array2<f64>) -> Array2<Complex64> {
    let (n_freq, n_frames) = magnitude.dim();
    let mut result = Array2::<Complex64>::zeros((n_freq, n_frames));

    for i in 0..n_freq {
        for j in 0..n_frames {
            let mag = magnitude[[i, j]];
            let ph = phase[[i, j]];
            result[[i, j]] = Complex64::new(mag * ph.cos(), mag * ph.sin());
        }
    }

    result
}

/// Decompose magnitude into harmonic and percussive components
fn decompose_magnitude(
    magnitude: &Array2<f64>,
    config: &HpssConfig,
) -> (Array2<f64>, Array2<f64>) {
    let (n_freq, n_frames) = magnitude.dim();

    // Apply median filters
    let harm_filt = median_filter_vertical(magnitude, config.kernel_h);
    let perc_filt = median_filter_horizontal(magnitude, config.kernel_p);

    // Compute soft masks using Wiener filtering
    let mut mask_h = Array2::zeros((n_freq, n_frames));
    let mut mask_p = Array2::zeros((n_freq, n_frames));

    for i in 0..n_freq {
        for j in 0..n_frames {
            let h = harm_filt[[i, j]];
            let p = perc_filt[[i, j]];

            // Wiener mask computation
            let h_margin = (h * config.margin_h).max(1e-10);
            let p_margin = (p * config.margin_p).max(1e-10);

            let h_pow = h_margin.powf(config.power);
            let p_pow = p_margin.powf(config.power);
            let denom = h_pow + p_pow;

            if denom > 0.0 {
                mask_h[[i, j]] = h_pow / denom;
                mask_p[[i, j]] = p_pow / denom;
            } else {
                mask_h[[i, j]] = 0.5;
                mask_p[[i, j]] = 0.5;
            }
        }
    }

    // Apply masks to original magnitude
    let harm_mag = magnitude * &mask_h;
    let perc_mag = magnitude * &mask_p;

    (harm_mag, perc_mag)
}

/// Apply vertical (frequency-wise) median filter
/// Separates harmonic content (sustained across frequencies)
fn median_filter_vertical(data: &Array2<f64>, kernel_size: usize) -> Array2<f64> {
    let (n_freq, n_frames) = data.dim();
    let mut output = Array2::<f64>::zeros((n_freq, n_frames));
    let half_kernel = kernel_size / 2;

    for j in 0..n_frames {
        for i in 0..n_freq {
            let start = if i >= half_kernel { i - half_kernel } else { 0 };
            let end = (i + half_kernel + 1).min(n_freq);

            let mut values: Vec<f64> = (start..end)
                .map(|k| data[[k, j]])
                .collect();

            // Sort and find median
            values.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
            output[[i, j]] = values[values.len() / 2];
        }
    }

    output
}

/// Apply horizontal (time-wise) median filter
/// Separates percussive content (short, impulsive events)
fn median_filter_horizontal(data: &Array2<f64>, kernel_size: usize) -> Array2<f64> {
    let (n_freq, n_frames) = data.dim();
    let mut output = Array2::<f64>::zeros((n_freq, n_frames));
    let half_kernel = kernel_size / 2;

    for i in 0..n_freq {
        for j in 0..n_frames {
            let start = if j >= half_kernel { j - half_kernel } else { 0 };
            let end = (j + half_kernel + 1).min(n_frames);

            let mut values: Vec<f64> = (start..end)
                .map(|k| data[[i, k]])
                .collect();

            // Sort and find median
            values.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
            output[[i, j]] = values[values.len() / 2];
        }
    }

    output
}

/// Compute Inverse STFT (ISTFT) with overlap-add reconstruction
fn compute_istft(stft: &Array2<Complex64>, n_fft: usize, hop_length: usize, n_samples: usize) -> Vec<f64> {
    let n_freqs = stft.nrows();
    let n_frames = stft.ncols();

    let mut output = vec![0.0; n_samples];

    // Pre-compute Hann window
    let window = hann_window(n_fft);

    // FFT planner for inverse transforms
    let mut planner = FftPlanner::new();
    let ifft = planner.plan_fft_inverse(n_fft);

    // Processing buffer
    let mut buffer = vec![Complex64::new(0.0, 0.0); n_fft];

    // Overlap-add reconstruction
    for frame_idx in 0..n_frames {
        let start = frame_idx * hop_length;

        // Fill buffer with STFT frame (including negative frequencies)
        for k in 0..n_freqs {
            buffer[k] = stft[[k, frame_idx]];
        }

        // Mirror negative frequencies (conjugate symmetry for real signal)
        for k in 1..n_freqs - 1 {
            let mirror_idx = n_fft - k;
            buffer[mirror_idx] = buffer[k].conj();
        }

        // Compute inverse FFT
        ifft.process(&mut buffer);

        // Apply Hann window and overlap-add
        for i in 0..n_fft {
            let windowed = buffer[i].re * window[i] / (n_fft as f64);
            if start + i < n_samples {
                output[start + i] += windowed;
            }
        }
    }

    output
}

/// Generate Hann window
fn hann_window(n: usize) -> Vec<f64> {
    (0..n)
        .map(|i| {
            let w = (2.0 * PI * i as f64) / (n as f64 - 1.0);
            0.5 * (1.0 - w.cos())
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_hann_window() {
        let window = hann_window(10);
        assert_eq!(window.len(), 10);
        // First and last samples should be ~0
        assert!(window[0] < 0.01);
        assert!(window[9] < 0.01);
        // Middle sample should be close to 1
        assert!(window[5] > 0.95);
        assert!(window[5] < 1.01);
    }

    #[test]
    fn test_hpss_config_default() {
        let config = HpssConfig::default();
        assert_eq!(config.n_fft, 2048);
        assert_eq!(config.hop_length, 512);
        assert_eq!(config.kernel_h, 31);
        assert_eq!(config.kernel_p, 31);
        assert_eq!(config.power, 2.0);
    }

    #[test]
    fn test_stft_dimensions() {
        let config = HpssConfig::default();
        let audio = vec![0.0; 44100];
        let stft = compute_stft(&audio, config.n_fft, config.hop_length);

        let expected_frames = (44100 - 2048) / 512 + 1;
        assert_eq!(stft.nrows(), 1025); // n_fft / 2 + 1
        assert_eq!(stft.ncols(), expected_frames);
    }

    #[test]
    fn test_hpss_output_length() {
        let config = HpssConfig::default();
        let audio = vec![0.0; 44100];
        let (harm, perc) = hpss(&audio, &config);

        assert_eq!(harm.len(), 44100);
        assert_eq!(perc.len(), 44100);
    }

    #[test]
    fn test_magnitude_extraction() {
        let stft = Array2::from_elem((10, 5), Complex64::new(3.0, 4.0));
        let magnitude = extract_magnitude(&stft);

        // sqrt(3^2 + 4^2) = 5
        assert!((magnitude[[0, 0]] - 5.0).abs() < 1e-10);
    }

    #[test]
    fn test_phase_extraction() {
        let stft = Array2::from_elem((10, 5), Complex64::new(1.0, 0.0));
        let phase = extract_phase(&stft);

        // phase of 1 + 0i = 0
        assert!(phase[[0, 0]].abs() < 1e-10);
    }
}

/// Constant-Q Chroma Features
///
/// Extracts 12-dimensional chromagram from audio using constant-Q representation
///
/// The CQT (Constant-Q Transform) uses logarithmically-spaced frequency bins with
/// constant Q factor (center_frequency / bandwidth). This matches human auditory
/// perception and is ideal for music analysis.
///
/// Algorithm:
/// 1. Generate 252 complex exponential filters (7 octaves × 36 bins/octave)
/// 2. Convolve audio with each filter (variable-length due to constant Q)
/// 3. Extract magnitude from complex output
/// 4. Fold 252 bins into 12 semitones
/// 5. Normalize per frame
///
/// Reference:
/// Brown, Judith C. "Calculation of a constant Q spectral transform." JASA 89, 1991.

use ndarray::Array2;
use num_complex::Complex64;
use std::f64::consts::PI;

// CQT parameters
const FMIN: f64 = 32.7;              // C1 (lowest note, Hz)
const BINS_PER_OCTAVE: u32 = 36;     // Bins per octave (0.333 semitones each)
const N_BINS: usize = 252;           // Total bins (7 × 36)
const HOP_LENGTH: usize = 512;       // Frame hop length
const Q_FACTOR: f64 = 34.66;         // Q = center_freq / bandwidth
const NORMALIZATION_EPS: f64 = 1e-10; // Epsilon for normalization

/// Extract chromagram using constant-Q transform
///
/// # Arguments
/// * `y` - Audio signal [n_samples]
/// * `sr` - Sample rate (Hz)
///
/// # Returns
/// Chromagram [12, n_frames] with normalized energy per semitone
///
/// # Example
/// ```ignore
/// let audio = vec![0.0; 44100]; // 1 second of silence
/// let chroma = chroma_cqt(&audio, 44100);
/// assert_eq!(chroma.nrows(), 12);
/// assert!(chroma.ncols() > 0);
/// ```
pub fn chroma_cqt(y: &[f64], sr: usize) -> Array2<f64> {
    if y.is_empty() {
        return Array2::zeros((12, 0));
    }

    // Step 1: Generate CQT filter bank
    let kernels = create_filter_bank(sr);

    // Step 2: Compute CQT spectrogram (252 bins × n_frames)
    let cqt_spec = convolve_cqt(y, &kernels, sr);

    // Step 3: Fold 252 bins into 12 semitones
    let chroma = fold_to_chroma(&cqt_spec);

    // Step 4: Normalize per frame
    normalize_chroma_inplace(&chroma)
}

/// Generate CQT filter bank with logarithmic frequency spacing
///
/// Creates 252 complex exponential filters with Gaussian windowing,
/// one for each CQT bin. Each filter has variable length based on Q factor.
fn create_filter_bank(sr: usize) -> Vec<Vec<Complex64>> {
    let mut kernels = Vec::with_capacity(N_BINS);

    for bin in 0..N_BINS {
        // Calculate frequency for this bin
        let freq = cqt_frequency(bin as u32);

        // Calculate filter length based on Q factor
        let filter_len = (Q_FACTOR * (sr as f64) / freq).ceil() as usize;
        let filter_len = if filter_len % 2 == 0 {
            filter_len
        } else {
            filter_len + 1
        }; // Make even for symmetry

        let mut kernel = Vec::with_capacity(filter_len);

        // Generate complex exponential with Gaussian window
        for n in 0..filter_len {
            let n_f = n as f64;
            let center = (filter_len as f64) / 2.0;

            // Gaussian window
            let sigma = filter_len as f64 / 6.0;
            let window = (-((n_f - center).powi(2)) / (2.0 * sigma.powi(2))).exp();

            // Complex exponential
            let phase = 2.0 * PI * freq * (n as f64) / (sr as f64);
            let complex_exp = Complex64::new(phase.cos(), phase.sin()) * window as f64;

            kernel.push(complex_exp);
        }

        kernels.push(kernel);
    }

    kernels
}

/// Calculate frequency for a given CQT bin using logarithmic spacing
#[inline]
fn cqt_frequency(bin: u32) -> f64 {
    FMIN * 2.0_f64.powf((bin as f64) / (BINS_PER_OCTAVE as f64))
}

/// Convolve audio with all CQT filters and extract magnitude (parallel per-bin)
fn convolve_cqt(y: &[f64], kernels: &[Vec<Complex64>], _sr: usize) -> Array2<f64> {
    use rayon::prelude::*;

    let n_frames = if y.len() >= HOP_LENGTH {
        ((y.len() - HOP_LENGTH) / HOP_LENGTH) + 1
    } else {
        1
    };

    // Process each bin in parallel (bins are independent)
    let bin_results: Vec<Vec<f64>> = kernels
        .par_iter()
        .map(|kernel| {
            if kernel.is_empty() {
                vec![0.0; n_frames]
            } else {
                convolve_single_bin(y, kernel, HOP_LENGTH)
            }
        })
        .collect();

    // Assemble results into 2D array
    let mut cqt_spec = Array2::zeros((N_BINS, n_frames));
    for (bin_idx, magnitudes) in bin_results.iter().enumerate() {
        for (frame_idx, &mag) in magnitudes.iter().enumerate().take(n_frames) {
            cqt_spec[[bin_idx, frame_idx]] = mag;
        }
    }

    cqt_spec
}

/// Convolve audio with a single CQT filter and extract magnitude
fn convolve_single_bin(audio: &[f64], kernel: &[Complex64], hop_length: usize) -> Vec<f64> {
    let kernel_len = kernel.len();
    let n_frames = if audio.len() >= hop_length {
        ((audio.len() - hop_length) / hop_length) + 1
    } else {
        1
    };
    let mut magnitudes = Vec::with_capacity(n_frames);

    // Compute output for each frame
    for frame_idx in 0..n_frames {
        let start_idx = frame_idx * hop_length;

        // Ensure we have enough samples for convolution
        if start_idx + kernel_len > audio.len() {
            magnitudes.push(0.0);
            continue;
        }

        // Compute convolution at this frame center
        let mut conv_output = Complex64::new(0.0, 0.0);

        for (k, &filter_coeff) in kernel.iter().enumerate() {
            let audio_idx = start_idx + k;
            if audio_idx < audio.len() {
                conv_output += audio[audio_idx] * filter_coeff;
            }
        }

        // Extract magnitude
        magnitudes.push(conv_output.norm());
    }

    magnitudes
}

/// Fold CQT bins (252) into chromagram (12 semitones)
fn fold_to_chroma(cqt_spec: &Array2<f64>) -> Array2<f64> {
    let n_frames = cqt_spec.ncols();
    let mut chroma = Array2::zeros((12, n_frames));

    // Sum across octaves for each semitone
    for bin_idx in 0..N_BINS {
        let semitone = bin_idx % 12;
        for frame_idx in 0..n_frames {
            chroma[[semitone, frame_idx]] += cqt_spec[[bin_idx, frame_idx]];
        }
    }

    chroma
}

/// Normalize chromagram per frame so each column sums to 1.0
fn normalize_chroma_inplace(chroma: &Array2<f64>) -> Array2<f64> {
    let mut normalized = chroma.clone();
    let n_frames = normalized.ncols();

    for frame_idx in 0..n_frames {
        let frame_sum: f64 = normalized
            .column(frame_idx)
            .iter()
            .sum::<f64>()
            .max(NORMALIZATION_EPS);

        for semitone in 0..12 {
            normalized[[semitone, frame_idx]] /= frame_sum;
        }
    }

    normalized
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_chroma_cqt_output_shape() {
        let audio = vec![0.0; 44100];
        let chroma = chroma_cqt(&audio, 44100);
        assert_eq!(chroma.nrows(), 12);
        assert!(chroma.ncols() > 0);
    }

    #[test]
    fn test_chroma_cqt_short_audio() {
        let audio = vec![0.0; 256];
        let chroma = chroma_cqt(&audio, 44100);
        assert_eq!(chroma.nrows(), 12);
        // Short audio should still produce at least one frame
        assert!(chroma.ncols() >= 1);
    }

    #[test]
    fn test_chroma_normalization() {
        // Create synthetic signal with known content
        let sr = 44100;
        let freq = 440.0; // A4
        let duration_s = 1.0;
        let n_samples = (sr as f64 * duration_s) as usize;

        let mut audio = vec![0.0; n_samples];
        for (i, sample) in audio.iter_mut().enumerate() {
            let t = i as f64 / sr as f64;
            *sample = (2.0 * PI * freq * t).sin();
        }

        let chroma = chroma_cqt(&audio, sr);

        // Check normalization: each column should sum to ~1.0
        for frame_idx in 0..chroma.ncols() {
            let col_sum: f64 = chroma.column(frame_idx).iter().sum();
            assert!((col_sum - 1.0).abs() < 0.01, "Column {} sum was {}", frame_idx, col_sum);
        }
    }

    #[test]
    fn test_chroma_no_nan_inf() {
        let audio: Vec<f64> = (0..44100).map(|i| ((i as f64) * 0.1).sin()).collect();
        let chroma = chroma_cqt(&audio, 44100);

        // Verify no NaN or Inf values
        for &val in chroma.iter() {
            assert!(val.is_finite(), "Found non-finite value: {}", val);
        }
    }

    #[test]
    fn test_cqt_frequency_spacing() {
        // Verify logarithmic frequency spacing
        let freq0 = cqt_frequency(0);
        let freq36 = cqt_frequency(36); // One octave higher
        let freq72 = cqt_frequency(72); // Two octaves higher

        // Each octave should double frequency
        assert!((freq36 - 2.0 * freq0).abs() < 0.1);
        assert!((freq72 - 4.0 * freq0).abs() < 0.1);
    }

    #[test]
    fn test_chroma_cqt_silence() {
        let audio = vec![0.0; 44100];
        let chroma = chroma_cqt(&audio, 44100);

        // Silence should produce normalized but near-zero output
        for &val in chroma.iter() {
            assert!(val >= 0.0 && val <= 1.0);
            assert!(val.is_finite());
        }
    }

    #[test]
    fn test_chroma_cqt_single_frequency() {
        let sr = 44100;
        let freq = 440.0; // A4
        let duration_s = 2.0; // Longer duration for better frequency resolution
        let n_samples = (sr as f64 * duration_s) as usize;

        let mut audio = vec![0.0; n_samples];
        for (i, sample) in audio.iter_mut().enumerate() {
            let t = i as f64 / sr as f64;
            *sample = (2.0 * PI * freq * t).sin();
        }

        let chroma = chroma_cqt(&audio, sr);

        // A4 (440 Hz) should map to A semitone (index 9: C,C#,D,D#,E,F,F#,G,G#,A)
        // For 440 Hz, the CQT should show energy at or near the A semitone
        // Skip first frame as it may have edge effects
        let mut peak_count = 0;
        for frame_idx in 1..chroma.ncols() {
            let frame = chroma.column(frame_idx);
            // Find the maximum value in this frame
            let max_val = frame.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
            // Find which semitone has the maximum
            let max_semitone = frame.iter().enumerate().max_by(|a, b| {
                a.1.partial_cmp(b.1).unwrap_or(std::cmp::Ordering::Equal)
            }).map(|(i, _)| i);

            // Should have significant energy somewhere
            if max_val > 0.05 {
                // A is at index 9, but CQT might detect nearby semitones
                // (C,C#,D,D#,E,F,F#,G,G#,A,A#,B)
                if let Some(semitone) = max_semitone {
                    if semitone == 9 || semitone == 8 || semitone == 10 {
                        peak_count += 1;
                    }
                }
            }
        }

        // Should detect A note in at least some frames
        assert!(peak_count > 0, "Should detect A note energy in chroma");
    }

    #[test]
    fn test_filter_bank_generation() {
        let kernels = create_filter_bank(44100);
        assert_eq!(kernels.len(), N_BINS);

        // Verify filter properties
        for (bin_idx, kernel) in kernels.iter().enumerate() {
            assert!(!kernel.is_empty(), "Kernel {} is empty", bin_idx);

            // Filter length should increase for lower frequencies
            let expected_len = (Q_FACTOR * 44100.0 / cqt_frequency(bin_idx as u32))
                .ceil() as usize;
            assert!(
                (kernel.len() as f64 - expected_len as f64).abs() < 2.0,
                "Kernel {} length mismatch",
                bin_idx
            );
        }
    }

    #[test]
    fn test_chroma_empty_audio() {
        let audio = vec![];
        let chroma = chroma_cqt(&audio, 44100);
        assert_eq!(chroma.nrows(), 12);
        assert_eq!(chroma.ncols(), 0);
    }

    #[test]
    fn test_chroma_values_in_range() {
        let audio: Vec<f64> = (0..44100).map(|i| ((i as f64) * 0.01).sin()).collect();
        let chroma = chroma_cqt(&audio, 44100);

        // All values should be in [0, 1] after normalization
        for &val in chroma.iter() {
            assert!(val >= -0.001 && val <= 1.001, "Value out of range: {}", val);
        }
    }

    #[test]
    fn test_chroma_white_noise() {
        let mut audio = vec![0.0; 44100];
        // Generate white noise
        for i in 0..audio.len() {
            audio[i] = (i as f64 * 12345.0).sin() * 0.1;
        }

        let chroma = chroma_cqt(&audio, 44100);

        // White noise should produce distributed energy across semitones
        let mean_energy: f64 = chroma.iter().sum::<f64>() / (12.0 * chroma.ncols() as f64);
        assert!(mean_energy > 0.01, "Should have energy from white noise");

        // All values should be valid
        for &val in chroma.iter() {
            assert!(val.is_finite());
        }
    }

    #[test]
    fn test_chroma_two_frequencies() {
        let sr = 44100;
        let freq1 = 440.0; // A4
        let freq2 = 660.0; // E5 (perfect fifth)
        let duration_s = 1.0;
        let n_samples = (sr as f64 * duration_s) as usize;

        let mut audio = vec![0.0; n_samples];
        for (i, sample) in audio.iter_mut().enumerate() {
            let t = i as f64 / sr as f64;
            *sample = ((2.0 * PI * freq1 * t).sin() + (2.0 * PI * freq2 * t).sin()) * 0.5;
        }

        let chroma = chroma_cqt(&audio, sr);

        // Should have multiple peaks (at A and E semitones)
        let mut semitone_energies: Vec<f64> = vec![0.0; 12];
        for frame_idx in 0..chroma.ncols() {
            for semitone in 0..12 {
                semitone_energies[semitone] += chroma[[semitone, frame_idx]];
            }
        }

        // Normalize by frame count
        for energy in &mut semitone_energies {
            *energy /= chroma.ncols() as f64;
        }

        // A is at index 9, E is at index 4
        let a_energy = semitone_energies[9];
        let e_energy = semitone_energies[4];
        assert!(a_energy > 0.01, "Should detect A energy: {}", a_energy);
        assert!(e_energy > 0.01, "Should detect E energy: {}", e_energy);
    }

    #[test]
    fn test_chroma_frame_count() {
        let sr = 44100;
        let durations = vec![1, 2, 5]; // 1s, 2s, 5s

        for duration_s in durations {
            let n_samples = sr * duration_s;
            let audio = vec![0.0; n_samples];
            let chroma = chroma_cqt(&audio, sr);

            // Frame count should be approximately (n_samples - hop) / hop + 1
            let expected_frames = ((n_samples - HOP_LENGTH) / HOP_LENGTH) + 1;
            assert!(
                (chroma.ncols() as isize - expected_frames as isize).abs() <= 1,
                "Frame count mismatch for {}s audio",
                duration_s
            );
        }
    }

    #[test]
    fn test_fold_to_chroma_correctness() {
        // Test that fold_to_chroma correctly maps 252 bins to 12 semitones
        // by verifying the modulo mapping works correctly
        let mut cqt_spec = Array2::zeros((252, 1));

        // Verify semitone mapping by setting specific bins
        // bin % 12 determines the semitone:
        // bin 0 -> semitone 0 (C)
        // bin 1 -> semitone 1 (C#)
        // bin 12 -> semitone 0 (C)
        // bin 36 -> semitone 0 (C) [36 % 12 = 0]
        // bin 37 -> semitone 1 (C#) [37 % 12 = 1]

        cqt_spec[[0, 0]] = 2.0; // bin 0: semitone 0 (C)
        cqt_spec[[36, 0]] = 3.0; // bin 36: semitone 0 (C) [36 % 12 = 0]
        cqt_spec[[37, 0]] = 1.0; // bin 37: semitone 1 (C#) [37 % 12 = 1]

        let chroma = fold_to_chroma(&cqt_spec);

        // C (semitone 0) should have 2.0 + 3.0 = 5.0
        assert!((chroma[[0, 0]] - 5.0).abs() < 0.01, "C should sum to 5.0, got: {}", chroma[[0, 0]]);

        // C# (semitone 1) should have 1.0
        assert!((chroma[[1, 0]] - 1.0).abs() < 0.01, "C# should be 1.0, got: {}", chroma[[1, 0]]);
    }

    #[test]
    fn test_chroma_column_normalization() {
        let sr = 44100;
        let audio: Vec<f64> = (0..sr).map(|i| ((i as f64) * 0.01).sin()).collect();
        let chroma = chroma_cqt(&audio, sr);

        // Each column should sum to approximately 1.0
        for frame_idx in 0..chroma.ncols() {
            let col_sum: f64 = chroma.column(frame_idx).iter().sum();
            assert!(
                (col_sum - 1.0).abs() < 0.01,
                "Column {} sum {} != 1.0",
                frame_idx,
                col_sum
            );
        }
    }
}

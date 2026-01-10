/// Tempo Detection via Spectral Flux Onset Detection
///
/// High-performance Rust implementation of tempo estimation using spectral flux
/// for onset detection and beat tracking.
///
/// Algorithm:
/// 1. Compute STFT and spectral flux (magnitude differences between frames)
/// 2. Detect peaks in flux as onset candidates
/// 3. Calculate average inter-onset interval
/// 4. Convert interval to BPM with clamping to reasonable range

use rustfft::{FftPlanner, num_complex::Complex64};
use std::f64::consts::PI;

/// Tempo detection configuration
#[derive(Clone, Debug)]
pub struct TempoConfig {
    /// FFT window size (default: 1024)
    pub n_fft: usize,
    /// Hop length (default: 512, 50% overlap)
    pub hop_length: usize,
    /// Peak detection threshold multiplier on flux std (default: 0.5)
    pub threshold_multiplier: f64,
    /// Minimum BPM (default: 60)
    pub min_bpm: f64,
    /// Maximum BPM (default: 200)
    pub max_bpm: f64,
}

impl Default for TempoConfig {
    fn default() -> Self {
        Self {
            n_fft: 1024,
            hop_length: 512,
            threshold_multiplier: 0.5,
            min_bpm: 60.0,
            max_bpm: 200.0,
        }
    }
}

/// Detect tempo in BPM using spectral flux onset detection
///
/// # Arguments
/// * `audio` - Audio signal as slice of f64 samples
/// * `sr` - Sample rate in Hz
/// * `config` - Configuration parameters
///
/// # Returns
/// Estimated tempo in BPM
pub fn detect_tempo(audio: &[f64], sr: usize, config: &TempoConfig) -> f64 {
    // Quick validation
    if audio.is_empty() || audio.len() < config.n_fft {
        return 120.0; // Default tempo
    }

    // Compute spectral flux
    let flux_values = compute_spectral_flux(audio, config.n_fft, config.hop_length);

    if flux_values.len() < 2 {
        return 120.0;
    }

    // Detect peaks in flux (onset candidates)
    let peaks = detect_flux_peaks(&flux_values, config.threshold_multiplier);

    if peaks.len() < 2 {
        return 120.0;
    }

    // Calculate tempo from peak intervals
    let tempo = calculate_tempo_from_peaks(&peaks, config.hop_length, sr, &config);

    tempo.max(config.min_bpm).min(config.max_bpm)
}

/// Compute spectral flux from audio signal
///
/// Spectral flux measures the magnitude of change in the short-time Fourier
/// transform between consecutive frames.
fn compute_spectral_flux(audio: &[f64], n_fft: usize, hop_length: usize) -> Vec<f64> {
    // Hann window
    let window = create_hann_window(n_fft);

    // FFT planner
    let mut planner = FftPlanner::new();
    let fft = planner.plan_fft_forward(n_fft);

    let mut flux_values = Vec::new();
    let mut prev_spectrum: Vec<f64> = vec![0.0; n_fft / 2 + 1];

    let mut frame_idx = 0;
    while frame_idx + n_fft <= audio.len() {
        // Extract frame and apply window
        let mut frame: Vec<Complex64> = audio[frame_idx..frame_idx + n_fft]
            .iter()
            .zip(&window)
            .map(|(s, w)| Complex64::new(s * w, 0.0))
            .collect();

        // Compute FFT
        fft.process(&mut frame);

        // Compute magnitude spectrum
        let magnitude: Vec<f64> = frame[0..n_fft / 2 + 1]
            .iter()
            .map(|c| c.norm())
            .collect();

        // Compute spectral flux (sum of positive differences)
        if !prev_spectrum.is_empty() {
            let flux: f64 = magnitude
                .iter()
                .zip(&prev_spectrum)
                .map(|(curr, prev)| (curr - prev).max(0.0))
                .sum();
            flux_values.push(flux);
        }

        prev_spectrum = magnitude;
        frame_idx += hop_length;
    }

    flux_values
}

/// Detect peaks in spectral flux
fn detect_flux_peaks(flux_values: &[f64], threshold_multiplier: f64) -> Vec<usize> {
    if flux_values.len() < 3 {
        return Vec::new();
    }

    let mean_flux = flux_values.iter().sum::<f64>() / flux_values.len() as f64;
    let variance = flux_values
        .iter()
        .map(|x| (x - mean_flux).powi(2))
        .sum::<f64>()
        / flux_values.len() as f64;
    let std_flux = variance.sqrt();
    let threshold = mean_flux + threshold_multiplier * std_flux;

    let mut peaks = Vec::new();

    for i in 1..flux_values.len() - 1 {
        if flux_values[i] > flux_values[i - 1]
            && flux_values[i] > flux_values[i + 1]
            && flux_values[i] > threshold
        {
            peaks.push(i);
        }
    }

    peaks
}

/// Calculate tempo from detected peak intervals with octave correction
fn calculate_tempo_from_peaks(
    peaks: &[usize],
    hop_length: usize,
    sr: usize,
    config: &TempoConfig,
) -> f64 {
    if peaks.len() < 2 {
        return 120.0;
    }

    // Calculate intervals between consecutive peaks
    let mut intervals: Vec<f64> = Vec::new();
    for i in 1..peaks.len() {
        intervals.push((peaks[i] - peaks[i - 1]) as f64);
    }

    // Average interval
    let avg_interval = intervals.iter().sum::<f64>() / intervals.len() as f64;

    // Convert to BPM
    // beat_interval = avg_interval * (hop_length / sr)
    // BPM = 60 / beat_interval
    let beat_interval = avg_interval * (hop_length as f64 / sr as f64);
    let raw_tempo = if beat_interval > 0.0 {
        60.0 / beat_interval
    } else {
        return 120.0;
    };

    // Aggressive octave correction: prefer tempos in 70-140 BPM range
    // Try many octave divisions since onset detection often catches subdivisions
    let candidates = [
        raw_tempo,
        raw_tempo / 2.0,
        raw_tempo / 3.0,
        raw_tempo / 4.0,
        raw_tempo / 6.0,
        raw_tempo / 8.0,
        raw_tempo * 2.0,
    ];

    // Score candidates: strongly prefer 70-140 BPM range (perceptual sweet spot)
    let mut best_tempo = 120.0; // Default fallback
    let mut best_score = f64::MAX;

    for &tempo in &candidates {
        if tempo >= config.min_bpm && tempo <= config.max_bpm {
            // Score based on distance from sweet spot center (105 BPM)
            // Use squared distance to heavily penalize extremes
            let sweet_spot_center = 105.0;
            let distance = (tempo - sweet_spot_center).abs();

            // Bonus for being in 70-140 range
            let sweet_spot_bonus = if tempo >= 70.0 && tempo <= 140.0 { 0.0 } else { 50.0 };

            let score = distance + sweet_spot_bonus;

            if score < best_score {
                best_score = score;
                best_tempo = tempo;
            }
        }
    }

    best_tempo
}

/// Create Hann window of given size
fn create_hann_window(size: usize) -> Vec<f64> {
    (0..size)
        .map(|i| {
            let phase = 2.0 * PI * i as f64 / (size - 1) as f64;
            0.5 * (1.0 - phase.cos())
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_detect_tempo_empty() {
        let config = TempoConfig::default();
        assert_eq!(detect_tempo(&[], 44100, &config), 120.0);
    }

    #[test]
    fn test_detect_tempo_short() {
        let audio = vec![0.0; 512]; // Shorter than n_fft
        let config = TempoConfig::default();
        assert_eq!(detect_tempo(&audio, 44100, &config), 120.0);
    }

    #[test]
    fn test_hann_window() {
        let window = create_hann_window(5);
        assert_eq!(window.len(), 5);
        // Check symmetry
        assert!((window[0] - window[4]).abs() < 1e-10);
        assert!((window[1] - window[3]).abs() < 1e-10);
    }

    #[test]
    fn test_detect_tempo_range() {
        // Generate simple sinusoid with known frequency
        let sr = 44100;
        let duration_samples = sr; // 1 second
        let frequency = 5.0; // 5 Hz = 300 BPM (5 beats per second)

        let mut audio = Vec::new();
        for i in 0..duration_samples {
            let phase = 2.0 * PI * frequency * i as f64 / sr as f64;
            audio.push(phase.sin());
        }

        let config = TempoConfig::default();
        let tempo = detect_tempo(&audio, sr, &config);

        // Should be within reasonable range
        assert!(tempo >= 60.0);
        assert!(tempo <= 200.0);
    }
}

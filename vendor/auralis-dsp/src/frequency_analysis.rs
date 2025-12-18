/// FFT-based frequency distribution analysis
/// Divides the audio spectrum into 7 perceptual frequency bands

use rustfft::num_complex::Complex;
use rustfft::FftPlanner;
use std::f32::consts::PI;

/// Frequency bands for distribution analysis
/// These are aligned with perceptual audio frequency ranges
#[derive(Debug, Clone, Copy)]
pub struct FrequencyBands {
    pub sub_bass: f32,    // 20-60 Hz
    pub bass: f32,        // 60-250 Hz
    pub low_mid: f32,     // 250-500 Hz
    pub mid: f32,         // 500-2000 Hz
    pub upper_mid: f32,   // 2000-4000 Hz
    pub presence: f32,    // 4000-8000 Hz
    pub air: f32,         // 8000-20000 Hz
}

impl FrequencyBands {
    pub fn to_array(&self) -> [f32; 7] {
        [
            self.sub_bass,
            self.bass,
            self.low_mid,
            self.mid,
            self.upper_mid,
            self.presence,
            self.air,
        ]
    }

    pub fn sum(&self) -> f32 {
        self.sub_bass + self.bass + self.low_mid + self.mid + self.upper_mid + self.presence + self.air
    }
}

/// Apply Hann window to reduce spectral leakage
fn apply_hann_window(signal: &mut [Complex<f32>]) {
    let n = signal.len() as f32;
    for (i, sample) in signal.iter_mut().enumerate() {
        let window = 0.5 * (1.0 - ((2.0 * PI * i as f32) / n).cos());
        sample.re *= window;
        sample.im *= window;
    }
}

/// Compute power spectral density from frequency bins
fn compute_psd(spectrum: &[Complex<f32>]) -> Vec<f32> {
    spectrum
        .iter()
        .map(|c| (c.norm_sqr() / (spectrum.len() as f32).powi(2)).max(1e-10))
        .collect()
}

/// Find frequency index for a given Hz value
fn hz_to_bin(hz: f32, sample_rate: u32, fft_size: usize) -> usize {
    ((hz * fft_size as f32) / sample_rate as f32).floor() as usize
}

/// Integrate power across frequency range
fn integrate_power_range(psd: &[f32], start_bin: usize, end_bin: usize) -> f32 {
    if start_bin >= psd.len() {
        return 0.0;
    }
    let end = end_bin.min(psd.len());
    psd[start_bin..end].iter().sum::<f32>()
}

/// Compute frequency distribution across 7 perceptual bands
///
/// # Arguments
/// * `audio` - Audio samples in float32 format
/// * `sample_rate` - Sample rate in Hz
///
/// # Returns
/// Array of 7 normalized frequency distribution values (sum = 1.0)
///
/// # Panics
/// If audio is empty or sample_rate is 0
pub fn compute_frequency_distribution(audio: &[f32], sample_rate: u32) -> FrequencyBands {
    if audio.is_empty() {
        return FrequencyBands {
            sub_bass: 1.0 / 7.0,
            bass: 1.0 / 7.0,
            low_mid: 1.0 / 7.0,
            mid: 1.0 / 7.0,
            upper_mid: 1.0 / 7.0,
            presence: 1.0 / 7.0,
            air: 1.0 / 7.0,
        };
    }

    // Use first 30 seconds for analysis (representative sample)
    let analysis_len = ((30.0 * sample_rate as f32) as usize).min(audio.len());
    let analysis_audio = &audio[..analysis_len];

    // Find next power of 2 FFT size
    let fft_size = (analysis_len as f32).log2().ceil() as u32;
    let fft_size = 2usize.pow(fft_size);

    // Prepare FFT input (pad with zeros)
    let mut fft_input: Vec<Complex<f32>> = vec![Complex { re: 0.0, im: 0.0 }; fft_size];
    for (i, &sample) in analysis_audio.iter().enumerate() {
        fft_input[i].re = sample;
    }

    // Apply Hann window to reduce spectral leakage
    apply_hann_window(&mut fft_input);

    // Compute FFT
    let mut planner = FftPlanner::new();
    let fft = planner.plan_fft_forward(fft_size);
    fft.process(&mut fft_input);

    // Compute power spectral density
    let psd = compute_psd(&fft_input);

    // Map frequency bands
    let nyquist = sample_rate as f32 / 2.0;
    let freqs = [20.0, 60.0, 250.0, 500.0, 2000.0, 4000.0, 8000.0, 20000.0];

    let mut bins = [0usize; 8];
    for (i, &freq) in freqs.iter().enumerate() {
        bins[i] = hz_to_bin((freq as f32).min(nyquist), sample_rate, fft_size);
    }

    // Integrate power in each band
    let mut distribution = [0.0f32; 7];
    for i in 0..7 {
        distribution[i] = integrate_power_range(&psd, bins[i], bins[i + 1]);
    }

    // Normalize
    let total: f32 = distribution.iter().sum();
    if total > 0.0 {
        for band in &mut distribution {
            *band /= total;
        }
    } else {
        // All zeros - return uniform distribution
        for band in &mut distribution {
            *band = 1.0 / 7.0;
        }
    }

    FrequencyBands {
        sub_bass: distribution[0],
        bass: distribution[1],
        low_mid: distribution[2],
        mid: distribution[3],
        upper_mid: distribution[4],
        presence: distribution[5],
        air: distribution[6],
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_frequency_distribution_empty() {
        let distribution = compute_frequency_distribution(&[], 48000);
        assert!((distribution.sum() - 1.0).abs() < 0.01);
    }

    #[test]
    fn test_frequency_distribution_silence() {
        let audio = vec![0.0; 48000]; // 1 second silence
        let distribution = compute_frequency_distribution(&audio, 48000);
        assert!((distribution.sum() - 1.0).abs() < 0.01);
    }

    #[test]
    fn test_frequency_distribution_sine_bass() {
        // Generate 100 Hz sine wave (bass)
        let sample_rate = 48000;
        let freq = 100.0;
        let duration = 2.0; // 2 seconds
        let samples = (duration * sample_rate as f32) as usize;
        let audio: Vec<f32> = (0..samples)
            .map(|i| {
                let t = i as f32 / sample_rate as f32;
                (2.0 * PI * freq * t).sin()
            })
            .collect();

        let distribution = compute_frequency_distribution(&audio, sample_rate);

        // Bass band should have most energy
        assert!(distribution.bass > distribution.sub_bass);
        assert!(distribution.bass > distribution.presence);
        assert!((distribution.sum() - 1.0).abs() < 0.01);
    }

    #[test]
    fn test_frequency_distribution_sine_presence() {
        // Generate 5 kHz sine wave (presence)
        let sample_rate = 48000;
        let freq = 5000.0;
        let duration = 2.0;
        let samples = (duration * sample_rate as f32) as usize;
        let audio: Vec<f32> = (0..samples)
            .map(|i| {
                let t = i as f32 / sample_rate as f32;
                (2.0 * PI * freq * t).sin()
            })
            .collect();

        let distribution = compute_frequency_distribution(&audio, sample_rate);

        // Presence band should have most energy
        assert!(distribution.presence > distribution.sub_bass);
        assert!(distribution.presence > distribution.bass);
        assert!((distribution.sum() - 1.0).abs() < 0.01);
    }

    #[test]
    fn test_frequency_distribution_normalized() {
        let audio: Vec<f32> = (0..48000)
            .map(|i| (i as f32 * 0.01).sin())
            .collect();
        let distribution = compute_frequency_distribution(&audio, 48000);

        // Sum should be ~1.0 (normalized)
        assert!((distribution.sum() - 1.0).abs() < 0.01);
    }
}

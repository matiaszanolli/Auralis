/// FFT-based frequency distribution analysis
/// Divides the audio spectrum into 7 perceptual frequency bands

use rustfft::num_complex::Complex;
use rustfft::FftPlanner;
use std::f32::consts::PI;

/// Longest FFT frame the band analysis uses (3 s at 22.05 kHz): bounded memory, and
/// 0.34 Hz bins are far finer than the 20 Hz lower edge of the first band needs.
const MAX_FRAME_SAMPLES: usize = 65536;

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
    pub fn sum(&self) -> f32 {
        self.sub_bass + self.bass + self.low_mid + self.mid + self.upper_mid + self.presence + self.air
    }
}

/// Compute power spectral density from frequency bins.
///
/// #5570: no per-bin floor. The old absolute `1e-10` floor set most bins on
/// quiet material, making the 7-band fractions depend on loudness instead of
/// spectral shape (pink noise at -37 dBFS read air=0.24 vs 0.05 at -14 dBFS).
/// The consumer normalises by the band sum, which is guarded by
/// `total > 0.0` (pure silence falls back to the uniform distribution), so
/// the floor bought nothing but level dependence.
fn compute_psd(spectrum: &[Complex<f32>]) -> Vec<f32> {
    spectrum
        .iter()
        .map(|c| c.norm_sqr() / (spectrum.len() as f32).powi(2))
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

    // Analyse the WHOLE input, not a head sample. This used to read only the first
    // 30 s as one FFT ("representative sample"); the fingerprint hands in the whole
    // track, and an intro (a quiet 35 s opening with no bass) is not the track.
    // Energy is accumulated frame by frame, so memory stays at one frame however long
    // the track is.
    let fft_size = audio.len().next_power_of_two().min(MAX_FRAME_SAMPLES);
    let mut planner = FftPlanner::new();
    let fft = planner.plan_fft_forward(fft_size);

    // Map frequency bands
    let nyquist = sample_rate as f32 / 2.0;
    let freqs = [20.0, 60.0, 250.0, 500.0, 2000.0, 4000.0, 8000.0, 20000.0];

    let mut bins = [0usize; 8];
    for (i, &freq) in freqs.iter().enumerate() {
        bins[i] = hz_to_bin((freq as f32).min(nyquist), sample_rate, fft_size);
    }

    // f64 accumulators: thousands of frames of f32 power would lose the quiet bands.
    let mut distribution = [0.0f64; 7];
    let mut fft_input: Vec<Complex<f32>> = vec![Complex { re: 0.0, im: 0.0 }; fft_size];
    for (index, frame) in audio.chunks(fft_size).enumerate() {
        // A tail shorter than half a frame is mostly zero padding: it adds leakage and
        // no information. Keep it only when it is all there is.
        if index > 0 && frame.len() < fft_size / 2 {
            break;
        }
        // Hann window over the actual frame length, zero padded to the FFT size.
        let n = frame.len() as f32;
        for (i, slot) in fft_input.iter_mut().enumerate() {
            *slot = match frame.get(i) {
                Some(&sample) => {
                    let window = 0.5 * (1.0 - ((2.0 * PI * i as f32) / n).cos());
                    Complex { re: sample * window, im: 0.0 }
                }
                None => Complex { re: 0.0, im: 0.0 },
            };
        }
        fft.process(&mut fft_input);

        let psd = compute_psd(&fft_input);
        for i in 0..7 {
            distribution[i] += integrate_power_range(&psd, bins[i], bins[i + 1]) as f64;
        }
    }

    // Normalize
    let total: f64 = distribution.iter().sum();
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
        sub_bass: distribution[0] as f32,
        bass: distribution[1] as f32,
        low_mid: distribution[2] as f32,
        mid: distribution[3] as f32,
        upper_mid: distribution[4] as f32,
        presence: distribution[5] as f32,
        air: distribution[6] as f32,
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

    #[test]
    fn test_frequency_distribution_sees_music_after_a_silent_intro() {
        // 35 s of silence, then 25 s of a 100 Hz tone. A head-only analysis read
        // only the silence and returned the uniform fallback.
        let sample_rate = 22050;
        let mut audio = vec![0.0f32; 35 * sample_rate as usize];
        audio.extend((0..25 * sample_rate as usize).map(|i| {
            (2.0 * PI * 100.0 * i as f32 / sample_rate as f32).sin() * 0.5
        }));

        let distribution = compute_frequency_distribution(&audio, sample_rate);

        assert!(distribution.bass > 0.9, "bass {} (uniform fallback is 0.143)", distribution.bass);
        assert!((distribution.sum() - 1.0).abs() < 0.01);
    }

    #[test]
    fn test_frequency_distribution_weights_the_whole_track_by_energy() {
        // 40 s of a quiet 3 kHz tone, then 40 s of a 100 Hz tone 20 dB louder: the
        // louder half dominates, and the head's tone is still counted.
        let sample_rate = 22050;
        let mut audio: Vec<f32> = (0..40 * sample_rate as usize)
            .map(|i| (2.0 * PI * 3000.0 * i as f32 / sample_rate as f32).sin() * 0.05)
            .collect();
        audio.extend((0..40 * sample_rate as usize).map(|i| {
            (2.0 * PI * 100.0 * i as f32 / sample_rate as f32).sin() * 0.5
        }));

        let distribution = compute_frequency_distribution(&audio, sample_rate);

        assert!(distribution.bass > 0.9);
        assert!(distribution.upper_mid > 0.0001, "the 3 kHz head is part of the track");
    }
}

/// FFT-based frequency distribution analysis
/// Divides the audio spectrum into 7 perceptual frequency bands

use crate::dsp_math::{hann_weight, hz_to_bin};
use rustfft::num_complex::Complex;
use rustfft::FftPlanner;

/// Longest FFT frame the band analysis uses (3 s at 22.05 kHz): bounded memory, and
/// 0.34 Hz bins are far finer than the 20 Hz lower edge of the first band needs.
pub(crate) const MAX_FRAME_SAMPLES: usize = 65536;

/// FFT size for an input of `len` samples: the next power of two, bounded.
pub(crate) fn frame_size(len: usize) -> usize {
    len.next_power_of_two().min(MAX_FRAME_SAMPLES)
}

/// The frames both band analyses (`compute_frequency_distribution` and the bass/mid ratio)
/// read: consecutive runs of `fft_size` samples. A tail shorter than half a frame is mostly
/// zero padding: it adds leakage and no information, so it is dropped unless it is all there
/// is. One iterator for both, so the two dimensions of a fingerprint cannot disagree about
/// which part of the track they describe (#6341).
pub(crate) fn analysis_frames(audio: &[f32], fft_size: usize) -> impl Iterator<Item = &[f32]> {
    audio
        .chunks(fft_size)
        .enumerate()
        .take_while(move |(index, frame)| *index == 0 || frame.len() >= fft_size / 2)
        .map(|(_, frame)| frame)
}

/// Load `frame` into `out`: Hann window over the frame's actual length, zero padded to
/// `out.len()`.
pub(crate) fn windowed_into(frame: &[f32], out: &mut [Complex<f32>]) {
    let n = frame.len() as f32;
    for (i, slot) in out.iter_mut().enumerate() {
        *slot = match frame.get(i) {
            Some(&sample) => {
                let window = hann_weight(i, n);
                Complex { re: sample * window, im: 0.0 }
            }
            None => Complex { re: 0.0, im: 0.0 },
        };
    }
}

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

/// The power spectrum of `audio` summed over its analysis frames, in f64, and the frame size.
///
/// Bins `0..=fft_size / 2` (DC to Nyquist), unnormalised: every consumer reads ratios
/// (band shares, bass/mid, centroid, rolloff), so the scale cancels. One spectrum feeds all
/// of them, so they describe the same frames (#6341) and the same whole track (#6363). The
/// sum is f64 because a track is thousands of frames: an f32 running sum stops absorbing
/// the quiet bins and drifts with track length (#6362). An empty input gives an all-zero
/// spectrum.
///
/// #5570: no per-bin floor. An absolute floor on quiet material made the band shares depend
/// on loudness instead of spectral shape; consumers guard their own zero totals.
pub(crate) fn accumulated_power(audio: &[f32]) -> (Vec<f64>, usize) {
    let fft_size = frame_size(audio.len().max(2));
    let mut power = vec![0.0f64; fft_size / 2 + 1];
    if audio.is_empty() {
        return (power, fft_size);
    }
    let fft = FftPlanner::new().plan_fft_forward(fft_size);
    let mut buf: Vec<Complex<f32>> = vec![Complex { re: 0.0, im: 0.0 }; fft_size];
    for frame in analysis_frames(audio, fft_size) {
        windowed_into(frame, &mut buf);
        fft.process(&mut buf);
        for (p, c) in power.iter_mut().zip(&buf) {
            *p += c.norm_sqr() as f64;
        }
    }
    (power, fft_size)
}

/// Sum of `power` over bins `start..end`, clamped to the spectrum.
pub(crate) fn band_power(power: &[f64], start: usize, end: usize) -> f64 {
    let end = end.min(power.len());
    if start >= end {
        return 0.0;
    }
    power[start..end].iter().sum()
}

/// Compute frequency distribution across 7 perceptual bands
///
/// # Arguments
/// * `audio` - Audio samples in float32 format
/// * `sample_rate` - Sample rate in Hz
///
/// # Returns
/// Array of 7 normalized frequency distribution values (sum = 1.0)
pub fn compute_frequency_distribution(audio: &[f32], sample_rate: u32) -> FrequencyBands {
    let (power, fft_size) = accumulated_power(audio);
    band_distribution(&power, fft_size, sample_rate)
}

/// The 7 band shares of an accumulated spectrum (see `accumulated_power`). A spectrum with
/// no energy (empty or silent input) gives the uniform distribution.
pub(crate) fn band_distribution(power: &[f64], fft_size: usize, sample_rate: u32) -> FrequencyBands {
    let nyquist = sample_rate as f32 / 2.0;
    let freqs = [20.0f32, 60.0, 250.0, 500.0, 2000.0, 4000.0, 8000.0, 20000.0];
    let bins = freqs.map(|freq| hz_to_bin(freq.min(nyquist), sample_rate, fft_size));

    let mut distribution = [0.0f64; 7];
    for i in 0..7 {
        distribution[i] = band_power(power, bins[i], bins[i + 1]);
    }
    let total: f64 = distribution.iter().sum();
    for band in &mut distribution {
        *band = if total > 0.0 { *band / total } else { 1.0 / 7.0 };
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
    use std::f32::consts::PI;

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

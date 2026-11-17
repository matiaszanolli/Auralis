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

/// Lower edge of the flatness scale: a mean frame flatness this far below 0 dB
/// (strongly tonal: orchestral, solo instruments) maps to 0.0, 0 dB to 1.0.
const FLATNESS_DB_RANGE: f64 = 30.0;
/// Bins measured: above the sub-bass, below a typical codec low-pass. Empty
/// bins past a low-pass or past Nyquist on a hi-res file used to decide the value.
const FLATNESS_LOW_HZ: f64 = 50.0;
const FLATNESS_HIGH_HZ: f64 = 16_000.0;
/// Per-bin floor relative to the frame's loudest bin (-100 dB), only so log()
/// stays finite. Relative, so scaling the audio cannot change which bins count.
const BIN_FLOOR_RELATIVE: f64 = 1e-10;

/// Spectral flatness (Wiener entropy), 0.0 = tonal .. 1.0 = noise.
///
/// Per STFT frame (2048 / hop 512, periodic Hann: the rhythm module's frames),
/// flatness is the geometric over the arithmetic mean of the bin powers in
/// 50 Hz - 16 kHz (capped at 0.95 x Nyquist). Frames more than 40 dB below the
/// loudest are skipped (the `silence_ratio` gate). The mean over frames is
/// mapped from dB onto 0-1 across `FLATNESS_DB_RANGE`: white noise reads about
/// 0.92, distorted guitars about 0.6, hip-hop 0.5, jazz 0.4, orchestral 0.2.
///
/// #6112: this replaced one whole-track FFT whose bins were dropped below an
/// ABSOLUTE 1e-10. Which bins survived depended on the playback level, so the
/// same audio read 0.08 at -24 dBFS and 0.96 at -64 dBFS; with any level-free
/// floor that measure is ~0.005 for all music (the spectral tilt dominates a
/// whole-track spectrum), which is why it is now per frame.
pub fn compute_spectral_flatness(audio: &[f32], sample_rate: u32) -> f32 {
    use crate::rhythm::{hann_periodic, HOP, N_FFT, SILENT_FRAME_RMS_RATIO};
    use rustfft::num_complex::Complex;
    use rustfft::FftPlanner;

    if audio.len() < N_FFT || sample_rate == 0 {
        return 0.0;
    }
    let bin_hz = sample_rate as f64 / N_FFT as f64;
    let high = FLATNESS_HIGH_HZ.min(0.95 * sample_rate as f64 / 2.0);
    let first = (FLATNESS_LOW_HZ / bin_hz).ceil() as usize;
    let last = ((high / bin_hz).floor() as usize).min(N_FFT / 2);
    if last <= first {
        return 0.0;
    }

    let window = hann_periodic(N_FFT);
    let fft = FftPlanner::<f64>::new().plan_fft_forward(N_FFT);
    let mut buf = vec![Complex { re: 0.0, im: 0.0 }; N_FFT];
    let mut power = vec![0.0f64; last - first + 1];
    // (frame energy, frame flatness): the gate needs the loudest frame first.
    let mut frames: Vec<(f64, f64)> = Vec::new();
    for start in (0..=audio.len() - N_FFT).step_by(HOP) {
        let frame = &audio[start..start + N_FFT];
        for ((slot, &sample), w) in buf.iter_mut().zip(frame).zip(&window) {
            *slot = Complex { re: sample as f64 * w, im: 0.0 };
        }
        fft.process(&mut buf);
        for (p, c) in power.iter_mut().zip(&buf[first..=last]) {
            *p = c.norm_sqr();
        }
        let energy: f64 = frame.iter().map(|&s| (s as f64) * (s as f64)).sum();
        frames.push((energy, frame_flatness(&power)));
    }

    let loudest = frames.iter().map(|f| f.0).fold(0.0f64, f64::max);
    if loudest <= 0.0 {
        return 0.0;
    }
    let gate = loudest * SILENT_FRAME_RMS_RATIO * SILENT_FRAME_RMS_RATIO; // energy, not RMS
    let kept: Vec<f64> = frames.iter().filter(|f| f.0 >= gate).map(|f| f.1).collect();
    let mean = kept.iter().sum::<f64>() / kept.len() as f64; // the loudest frame is always kept
    let db = 10.0 * mean.max(1e-30).log10();
    ((db + FLATNESS_DB_RANGE) / FLATNESS_DB_RANGE).clamp(0.0, 1.0) as f32
}

/// Geometric over arithmetic mean of one frame's bin powers, each floored
/// relative to the frame's loudest bin.
fn frame_flatness(power: &[f64]) -> f64 {
    let loudest = power.iter().cloned().fold(0.0f64, f64::max);
    if loudest <= 0.0 {
        return 0.0;
    }
    let floor = loudest * BIN_FLOOR_RELATIVE;
    let (log_sum, sum) = power.iter().fold((0.0, 0.0), |(l, s), &p| {
        let q = p.max(floor);
        (l + q.ln(), s + q)
    });
    let n = power.len() as f64;
    (log_sum / n).exp() / (sum / n)
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

    /// Deterministic white-ish noise (LCG, no rand crate).
    fn noise(n: usize, amplitude: f32) -> Vec<f32> {
        let mut state = 0x1234_5678_u32;
        (0..n)
            .map(|_| {
                state = state.wrapping_mul(1_664_525).wrapping_add(1_013_904_223);
                (state as f32 / u32::MAX as f32 - 0.5) * 2.0 * amplitude
            })
            .collect()
    }

    fn tone(n: usize, rate: u32, hz: f32, amplitude: f32) -> Vec<f32> {
        (0..n)
            .map(|i| (i as f32 / rate as f32 * hz * std::f32::consts::TAU).sin() * amplitude)
            .collect()
    }

    #[test]
    fn test_spectral_flatness_white_noise_is_high() {
        let flatness = compute_spectral_flatness(&noise(44100 * 5, 0.3), 44100);
        assert!(flatness > 0.85, "{flatness}");
    }

    #[test]
    fn test_spectral_flatness_tone_is_low() {
        let flatness = compute_spectral_flatness(&tone(44100 * 5, 44100, 440.0, 0.5), 44100);
        assert!(flatness < 0.1, "{flatness}");
    }

    #[test]
    fn test_spectral_flatness_does_not_depend_on_level() {
        // #6112: the absolute per-bin floor made the same audio read 0.08 at
        // -24 dBFS and 0.96 at -64 dBFS. Scaled copies must agree.
        let mut mix = tone(44100 * 5, 44100, 220.0, 0.4);
        for (m, n) in mix.iter_mut().zip(noise(44100 * 5, 0.05)) {
            *m += n;
        }
        let reference = compute_spectral_flatness(&mix, 44100);
        for gain_db in [-20.0f32, -40.0, -60.0] {
            let gain = 10f32.powf(gain_db / 20.0);
            let scaled: Vec<f32> = mix.iter().map(|s| s * gain).collect();
            let got = compute_spectral_flatness(&scaled, 44100);
            assert!((got - reference).abs() < 0.02, "{gain_db} dB: {got} vs {reference}");
        }
    }

    #[test]
    fn test_spectral_flatness_ignores_silent_frames_and_empty_input() {
        let rate = 44100;
        let body = noise(rate * 4, 0.3);
        let mut gapped = body[..rate * 2].to_vec();
        gapped.extend(std::iter::repeat(0.0f32).take(rate * 2));
        gapped.extend_from_slice(&body[rate * 2..]);
        let (a, b) = (compute_spectral_flatness(&body, 44100), compute_spectral_flatness(&gapped, 44100));
        assert!((a - b).abs() < 0.02, "{a} vs {b}");
        assert_eq!(compute_spectral_flatness(&[], 44100), 0.0);
        assert_eq!(compute_spectral_flatness(&vec![0.0f32; rate], 44100), 0.0);
    }
}

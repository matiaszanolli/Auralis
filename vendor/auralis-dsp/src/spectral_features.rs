/// Spectral feature analysis (centroid, rolloff, flatness)
/// These features describe the "shape" and "color" of the audio spectrum

/// Compute spectral centroid (center of mass of spectrum)
/// Higher values = brighter/more high-frequency content
/// Range: 0.0 - Nyquist frequency (Hz)
///
/// # Arguments
/// * `power` - Power per bin from DC, accumulated over the track's frames
///   (`frequency_analysis::accumulated_power`)
/// * `bin_hz` - Width of one bin in Hz
///
/// # Returns
/// Spectral centroid in Hz
///
/// #6362/#6363: this used one whole-track f32 FFT (up to 2^25 points) with f32 sums, which
/// described the middle of the track (the Hann window) and drifted with its length; it now
/// reads the band shares' f64 frame spectrum.
pub fn compute_spectral_centroid(power: &[f64], bin_hz: f64) -> f32 {
    let total: f64 = power.iter().sum();
    if total <= 0.0 {
        return 0.0;
    }
    let weighted: f64 = power.iter().enumerate().map(|(k, p)| p * k as f64 * bin_hz).sum();
    (weighted / total) as f32
}

/// Compute spectral rolloff (frequency below which `rolloff` of the energy lies)
/// Lower = more concentrated energy, Higher = spread energy
/// Range: 0.0 - Nyquist frequency (Hz)
///
/// # Arguments
/// * `power` - Power per bin from DC (see `compute_spectral_centroid`)
/// * `bin_hz` - Width of one bin in Hz
/// * `rolloff` - Threshold fraction (0.0 - 1.0), typically 0.85
///
/// # Returns
/// Rolloff frequency in Hz
pub fn compute_spectral_rolloff(power: &[f64], bin_hz: f64, rolloff: f64) -> f32 {
    let total: f64 = power.iter().sum();
    if total <= 0.0 {
        return 0.0;
    }
    let threshold = rolloff * total;
    let mut cumulative = 0.0f64;
    for (k, p) in power.iter().enumerate() {
        cumulative += p;
        if cumulative >= threshold {
            return (k as f64 * bin_hz) as f32;
        }
    }
    ((power.len() - 1) as f64 * bin_hz) as f32
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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_spectral_centroid_bass() {
        // Bass dominated spectrum, 10 Hz bins
        let power: Vec<f64> = (0..100).map(|i| if i < 20 { 1.0 } else { 0.1 }).collect();
        assert!(compute_spectral_centroid(&power, 10.0) < 500.0);
    }

    #[test]
    fn test_spectral_centroid_treble() {
        // Treble dominated spectrum, 100 Hz bins
        let power: Vec<f64> = (0..100).map(|i| if i > 80 { 1.0 } else { 0.1 }).collect();
        assert!(compute_spectral_centroid(&power, 100.0) > 5000.0);
    }

    #[test]
    fn test_spectral_rolloff() {
        // Uniform spectrum: 85% of the energy lies below 85% of the top bin
        let power = vec![1.0f64; 100];
        let rolloff = compute_spectral_rolloff(&power, 100.0, 0.85);
        assert!(rolloff > 7000.0 && rolloff < 9000.0);
    }

    #[test]
    fn test_centroid_and_rolloff_of_silence_are_zero() {
        assert_eq!(compute_spectral_centroid(&[0.0; 16], 10.0), 0.0);
        assert_eq!(compute_spectral_rolloff(&[0.0; 16], 10.0, 0.85), 0.0);
        assert_eq!(compute_spectral_centroid(&[], 10.0), 0.0);
    }

    #[test]
    fn test_centroid_and_rolloff_do_not_drift_with_length() {
        // #6362: the f32 whole-track path read 900 s of pink noise 50% low. The frame
        // spectrum is a per-frame sum, so a long input must read like a short one.
        let short = noise(22050 * 30, 0.3);
        let long: Vec<f32> = short.iter().cycle().take(22050 * 600).copied().collect();
        let read = |audio: &[f32]| {
            let (power, fft_size) = crate::frequency_analysis::accumulated_power(audio);
            let bin_hz = 22050.0 / fft_size as f64;
            (compute_spectral_centroid(&power, bin_hz), compute_spectral_rolloff(&power, bin_hz, 0.85))
        };
        let ((c_short, r_short), (c_long, r_long)) = (read(&short), read(&long));
        assert!((c_long / c_short - 1.0).abs() < 0.01, "centroid {c_short} -> {c_long}");
        assert!((r_long / r_short - 1.0).abs() < 0.01, "rolloff {r_short} -> {r_long}");
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

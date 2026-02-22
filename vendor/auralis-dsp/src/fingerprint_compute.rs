/// Unified 25D audio fingerprinting
/// Orchestrates all fingerprint dimensions from specialized modules

use crate::frequency_analysis;
use crate::spectral_features;
use crate::variation_analysis;
use crate::stereo_analysis;

/// Complete 25D audio fingerprint
/// Dimensions broken down by perceptual/acoustic category
#[derive(Debug, Clone, Copy)]
pub struct AudioFingerprint {
    // Frequency Distribution (7D) - Perceptual frequency bands
    pub sub_bass: f32,    // 20-60 Hz energy
    pub bass: f32,        // 60-250 Hz energy
    pub low_mid: f32,     // 250-500 Hz energy
    pub mid: f32,         // 500-2000 Hz energy
    pub upper_mid: f32,   // 2000-4000 Hz energy
    pub presence: f32,    // 4000-8000 Hz energy
    pub air: f32,         // 8000-20000 Hz energy

    // Dynamics (3D) - Dynamic range, loudness, frequency balance
    pub lufs: f32,          // Integrated loudness estimate
    pub crest_db: f32,      // Peak-to-RMS ratio
    pub bass_mid_ratio: f32,// Bass energy vs mid energy

    // Temporal (4D) - Time-domain characteristics
    pub tempo_bpm: f32,           // Estimated tempo
    pub rhythm_stability: f32,    // How stable the rhythm is
    pub transient_density: f32,   // Sharpness/percussive content
    pub silence_ratio: f32,       // Proportion of silence

    // Spectral (3D) - Spectrum shape characteristics
    pub spectral_centroid: f32,   // "Brightness" (center of mass)
    pub spectral_rolloff: f32,    // 85% energy frequency
    pub spectral_flatness: f32,   // Tonality vs noisiness

    // Harmonic (3D) - Harmonic content and pitch
    pub harmonic_ratio: f32,      // Harmonic vs percussive energy
    pub pitch_stability: f32,     // Consistency of fundamental frequency
    pub chroma_energy: f32,       // Overall harmonic richness

    // Variation (3D) - Temporal variation
    pub dynamic_range_variation: f32, // Std dev of dynamic range
    pub loudness_variation: f32,      // Std dev of loudness
    pub peak_consistency: f32,        // Consistency of peak levels

    // Stereo (2D) - Spatial characteristics
    pub stereo_width: f32,         // Width of stereo field
    pub phase_correlation: f32,    // Phase relationship of channels
}

impl AudioFingerprint {
    /// Convert to dictionary format for Python/JSON serialization
    pub fn to_dict(&self) -> std::collections::HashMap<String, f32> {
        let mut dict = std::collections::HashMap::new();

        // Frequency (7D)
        dict.insert("sub_bass".to_string(), self.sub_bass);
        dict.insert("bass".to_string(), self.bass);
        dict.insert("low_mid".to_string(), self.low_mid);
        dict.insert("mid".to_string(), self.mid);
        dict.insert("upper_mid".to_string(), self.upper_mid);
        dict.insert("presence".to_string(), self.presence);
        dict.insert("air".to_string(), self.air);

        // Dynamics (3D)
        dict.insert("lufs".to_string(), self.lufs);
        dict.insert("crest_db".to_string(), self.crest_db);
        dict.insert("bass_mid_ratio".to_string(), self.bass_mid_ratio);

        // Temporal (4D)
        dict.insert("tempo_bpm".to_string(), self.tempo_bpm);
        dict.insert("rhythm_stability".to_string(), self.rhythm_stability);
        dict.insert("transient_density".to_string(), self.transient_density);
        dict.insert("silence_ratio".to_string(), self.silence_ratio);

        // Spectral (3D)
        dict.insert("spectral_centroid".to_string(), self.spectral_centroid);
        dict.insert("spectral_rolloff".to_string(), self.spectral_rolloff);
        dict.insert("spectral_flatness".to_string(), self.spectral_flatness);

        // Harmonic (3D)
        dict.insert("harmonic_ratio".to_string(), self.harmonic_ratio);
        dict.insert("pitch_stability".to_string(), self.pitch_stability);
        dict.insert("chroma_energy".to_string(), self.chroma_energy);

        // Variation (3D)
        dict.insert("dynamic_range_variation".to_string(), self.dynamic_range_variation);
        dict.insert("loudness_variation".to_string(), self.loudness_variation);
        dict.insert("peak_consistency".to_string(), self.peak_consistency);

        // Stereo (2D)
        dict.insert("stereo_width".to_string(), self.stereo_width);
        dict.insert("phase_correlation".to_string(), self.phase_correlation);

        dict
    }
}

/// Compute RMS energy of signal
fn compute_rms(signal: &[f32]) -> f32 {
    if signal.is_empty() {
        return 0.0;
    }

    let sum_sq: f32 = signal.iter().map(|s| s * s).sum();
    (sum_sq / signal.len() as f32).sqrt()
}

/// Estimate peak-to-RMS ratio (crest factor)
fn compute_crest_factor(signal: &[f32]) -> f32 {
    if signal.is_empty() {
        return 0.0;
    }

    let peak = signal.iter().map(|s| s.abs()).fold(0.0f32, f32::max);
    let rms = compute_rms(signal);

    if rms < 1e-10 {
        return 0.0;
    }

    // Convert to dB
    20.0 * (peak / rms).log10()
}

/// Estimate LUFS (loudness units relative to full scale)
fn estimate_lufs(signal: &[f32]) -> f32 {
    let rms = compute_rms(signal);
    if rms < 1e-10 {
        return -120.0;
    }

    // Simplified LUFS (not ITU-1771 certified)
    let db = 20.0 * rms.log10() - 0.7; // Calibration constant

    db.max(-120.0).min(0.0)
}

/// Compute bass/mid energy ratio
fn compute_bass_mid_ratio(audio: &[f32], sample_rate: u32) -> f32 {
    use rustfft::num_complex::Complex;
    use rustfft::FftPlanner;
    use std::f32::consts::PI;

    if audio.is_empty() {
        return 0.5;
    }

    let fft_size = (audio.len().next_power_of_two()).min(65536);
    let mut fft_input: Vec<Complex<f32>> = vec![Complex { re: 0.0, im: 0.0 }; fft_size];

    for (i, &sample) in audio.iter().enumerate().take(fft_size) {
        fft_input[i].re = sample;
    }

    // Apply Hann window
    let n = audio.len().min(fft_size) as f32;
    for (i, sample) in fft_input.iter_mut().enumerate().take(audio.len().min(fft_size)) {
        let window = 0.5 * (1.0 - ((2.0 * PI * i as f32) / n).cos());
        sample.re *= window;
    }

    // FFT
    let mut planner = FftPlanner::new();
    let fft = planner.plan_fft_forward(fft_size);
    fft.process(&mut fft_input);

    // Energy distribution
    let bass_bin = hz_to_bin(200.0, sample_rate, fft_size);
    let mid_bin = hz_to_bin(2000.0, sample_rate, fft_size);

    let bass_energy: f32 = fft_input[..bass_bin]
        .iter()
        .map(|c| c.norm_sqr())
        .sum();
    let mid_energy: f32 = fft_input[bass_bin..mid_bin]
        .iter()
        .map(|c| c.norm_sqr())
        .sum();

    let total = bass_energy + mid_energy;
    if total < 1e-10 {
        return 0.5;
    }

    (bass_energy / total).clamp(0.0, 1.0)
}

/// Convert Hz to FFT bin index
fn hz_to_bin(hz: f32, sample_rate: u32, fft_size: usize) -> usize {
    (((hz * fft_size as f32) / sample_rate as f32)
        .floor() as usize)
        .min(fft_size - 1)
}

/// Estimate silence ratio (percentage of signal below -40 dB threshold)
fn compute_silence_ratio(audio: &[f32]) -> f32 {
    if audio.is_empty() {
        return 1.0;
    }

    let threshold = 10f32.powf(-40.0 / 20.0); // -40 dB in linear
    let silent_samples = audio.iter().filter(|&&s| s.abs() < threshold).count();

    (silent_samples as f32 / audio.len() as f32).clamp(0.0, 1.0)
}

/// Compute complete 25D fingerprint
///
/// # Arguments
/// * `audio` - Audio samples (float32)
/// * `sample_rate` - Sample rate in Hz
/// * `channels` - Number of channels (1 = mono, 2 = stereo)
///
/// # Returns
/// Result with AudioFingerprint or error message
pub fn compute_complete_fingerprint(
    audio: &[f32],
    sample_rate: u32,
    channels: u32,
) -> Result<AudioFingerprint, Box<dyn std::error::Error>> {
    if audio.is_empty() {
        return Err("Audio is empty".into());
    }

    if sample_rate == 0 {
        return Err("Sample rate must be > 0".into());
    }

    if sample_rate < 8_000 || sample_rate > 384_000 {
        return Err(format!(
            "Sample rate {} Hz is out of supported range [8000, 384000]",
            sample_rate
        ).into());
    }

    // Handle mono vs stereo
    let (mono_audio, left_channel, right_channel) = if channels == 2 {
        // Stereo: downmix to mono for most analysis
        let mut mono = vec![0.0f32; audio.len() / 2];
        for i in 0..mono.len() {
            mono[i] = (audio[i * 2] + audio[i * 2 + 1]) * 0.5;
        }
        let left: Vec<f32> = audio.iter().step_by(2).copied().collect();
        let right: Vec<f32> = audio.iter().skip(1).step_by(2).copied().collect();
        (mono, Some(left), Some(right))
    } else {
        (audio.to_vec(), None, None)
    };

    // 1. Frequency Distribution (7D) - Real FFT
    let freq_dist = frequency_analysis::compute_frequency_distribution(&mono_audio, sample_rate);

    // 2. Dynamics (3D)
    let lufs = estimate_lufs(&mono_audio);
    let crest_db = compute_crest_factor(&mono_audio);
    let bass_mid_ratio = compute_bass_mid_ratio(&mono_audio, sample_rate);

    // 3. Temporal (4D)
    let silence_ratio = compute_silence_ratio(&mono_audio);
    let tempo_bpm = estimate_tempo(&mono_audio, sample_rate);
    let rhythm_stability = estimate_rhythm_stability(&mono_audio, sample_rate);
    let transient_density = estimate_transient_density(&mono_audio, sample_rate);

    // 4. Spectral (3D)
    let (freqs, psd) = spectral_features::audio_to_freq_domain(&mono_audio, sample_rate);
    let spectral_centroid = spectral_features::compute_spectral_centroid(&psd, &freqs);
    let spectral_rolloff = spectral_features::compute_spectral_rolloff(&psd, &freqs, 0.85);
    let spectral_flatness = spectral_features::compute_spectral_flatness(&psd);

    // 5. Harmonic (3D)
    let harmonic_ratio = estimate_harmonic_ratio(&mono_audio, sample_rate);
    let pitch_stability = estimate_pitch_stability(&mono_audio, sample_rate);
    let chroma_energy = estimate_chroma_energy(&mono_audio, sample_rate);

    // 6. Variation (3D)
    let dynamic_range_variation = variation_analysis::compute_dynamic_range_variation(&mono_audio, sample_rate);
    let loudness_variation = variation_analysis::compute_loudness_variation(&mono_audio, sample_rate);
    let peak_consistency = variation_analysis::compute_peak_consistency(&mono_audio, sample_rate);

    // 7. Stereo (2D)
    let (stereo_width, phase_correlation) = if let (Some(left), Some(right)) = (left_channel, right_channel) {
        let width = stereo_analysis::compute_stereo_width(&left, &right);
        let phase = stereo_analysis::compute_phase_correlation(&left, &right);
        (width, phase)
    } else {
        // Mono
        (0.0, 1.0)
    };

    Ok(AudioFingerprint {
        // Frequency
        sub_bass: freq_dist.sub_bass,
        bass: freq_dist.bass,
        low_mid: freq_dist.low_mid,
        mid: freq_dist.mid,
        upper_mid: freq_dist.upper_mid,
        presence: freq_dist.presence,
        air: freq_dist.air,

        // Dynamics
        lufs,
        crest_db,
        bass_mid_ratio,

        // Temporal
        tempo_bpm,
        rhythm_stability,
        transient_density,
        silence_ratio,

        // Spectral
        spectral_centroid,
        spectral_rolloff,
        spectral_flatness,

        // Harmonic
        harmonic_ratio,
        pitch_stability,
        chroma_energy,

        // Variation
        dynamic_range_variation,
        loudness_variation,
        peak_consistency,

        // Stereo
        stereo_width,
        phase_correlation,
    })
}

/// Estimate tempo via spectral-flux onset detection and autocorrelation.
///
/// Computes an onset-strength envelope from spectral flux, then finds the
/// dominant periodicity via autocorrelation in the BPM range [60, 200].
fn estimate_tempo(audio: &[f32], sample_rate: u32) -> f32 {
    let hop = 512usize;
    let frame_size = 1024usize;

    if audio.len() < frame_size * 2 {
        return 120.0; // Not enough data for reliable estimation
    }

    // Compute magnitude spectrum per frame (half-spectrum)
    let n_frames = (audio.len().saturating_sub(frame_size)) / hop + 1;
    if n_frames < 2 {
        return 120.0;
    }

    let half = frame_size / 2 + 1;
    let mut prev_mag = vec![0.0f32; half];
    let mut onset_env = Vec::with_capacity(n_frames);

    for i in 0..n_frames {
        let start = i * hop;
        let end = (start + frame_size).min(audio.len());
        let frame = &audio[start..end];

        // Simple DFT magnitude for low bins (cheap approximation)
        let mut mag = vec![0.0f32; half];
        for k in 0..half {
            let mut re = 0.0f32;
            let mut im = 0.0f32;
            for (n, &s) in frame.iter().enumerate() {
                let angle = -2.0 * std::f32::consts::PI * k as f32 * n as f32 / frame_size as f32;
                re += s * angle.cos();
                im += s * angle.sin();
            }
            mag[k] = (re * re + im * im).sqrt();
        }

        // Spectral flux (only positive differences = onsets)
        let flux: f32 = mag.iter().zip(prev_mag.iter())
            .map(|(&cur, &prev)| (cur - prev).max(0.0))
            .sum();
        onset_env.push(flux);
        prev_mag = mag;
    }

    if onset_env.len() < 4 {
        return 120.0;
    }

    // Autocorrelation of onset envelope to find dominant period
    let onset_sr = sample_rate as f32 / hop as f32; // frames per second
    let min_lag = (onset_sr * 60.0 / 200.0).ceil() as usize; // 200 BPM
    let max_lag = (onset_sr * 60.0 / 60.0).floor() as usize;  // 60 BPM
    let max_lag = max_lag.min(onset_env.len() / 2);

    if min_lag >= max_lag {
        return 120.0;
    }

    let mut best_lag = min_lag;
    let mut best_corr = f32::NEG_INFINITY;

    for lag in min_lag..=max_lag {
        let mut corr = 0.0f32;
        let n = onset_env.len() - lag;
        for i in 0..n {
            corr += onset_env[i] * onset_env[i + lag];
        }
        if corr > best_corr {
            best_corr = corr;
            best_lag = lag;
        }
    }

    let bpm = 60.0 * onset_sr / best_lag as f32;
    bpm.clamp(60.0, 200.0)
}

/// Estimate rhythm stability from inter-onset-interval (IOI) variance.
///
/// Low variance = stable, repetitive rhythm → value near 1.0.
/// High variance = free-time / rubato → value near 0.0.
fn estimate_rhythm_stability(audio: &[f32], sample_rate: u32) -> f32 {
    let hop = 512usize;
    let frame_size = 1024usize;

    if audio.len() < frame_size * 4 {
        return 0.5; // Not enough data
    }

    // Compute simple energy envelope
    let n_frames = (audio.len().saturating_sub(frame_size)) / hop + 1;
    let mut energies = Vec::with_capacity(n_frames);
    for i in 0..n_frames {
        let start = i * hop;
        let end = (start + frame_size).min(audio.len());
        let e: f32 = audio[start..end].iter().map(|s| s * s).sum::<f32>() / (end - start) as f32;
        energies.push(e);
    }

    // Find onsets via energy peaks (simple threshold-based)
    let mean_energy: f32 = energies.iter().sum::<f32>() / energies.len() as f32;
    let threshold = mean_energy * 1.5;

    let mut onset_frames = Vec::new();
    let mut in_onset = false;
    for (i, &e) in energies.iter().enumerate() {
        if e > threshold && !in_onset {
            onset_frames.push(i);
            in_onset = true;
        } else if e <= mean_energy {
            in_onset = false;
        }
    }

    if onset_frames.len() < 3 {
        return 0.5; // Not enough onsets to assess stability
    }

    // Compute IOIs (inter-onset intervals)
    let iois: Vec<f32> = onset_frames.windows(2)
        .map(|w| (w[1] - w[0]) as f32)
        .collect();

    let mean_ioi: f32 = iois.iter().sum::<f32>() / iois.len() as f32;
    if mean_ioi < 1e-6 {
        return 0.5;
    }

    // Coefficient of variation (std / mean) — lower = more stable
    let variance: f32 = iois.iter().map(|&ioi| (ioi - mean_ioi).powi(2)).sum::<f32>() / iois.len() as f32;
    let cv = variance.sqrt() / mean_ioi;

    // Map CV to 0-1 stability: CV=0 → 1.0, CV=1 → 0.0
    (1.0 - cv).clamp(0.0, 1.0)
}

/// Estimate pitch stability via zero-crossing rate variance across frames.
///
/// Stable pitch → consistent ZCR → value near 1.0.
/// Varying pitch → varying ZCR → value near 0.0.
fn estimate_pitch_stability(audio: &[f32], sample_rate: u32) -> f32 {
    let frame_size = 2048usize;
    let hop = 1024usize;

    if audio.len() < frame_size * 3 {
        return 0.5;
    }

    let n_frames = (audio.len().saturating_sub(frame_size)) / hop + 1;
    let mut zcrs = Vec::with_capacity(n_frames);

    for i in 0..n_frames {
        let start = i * hop;
        let end = (start + frame_size).min(audio.len());
        let frame = &audio[start..end];

        // Zero-crossing rate
        let crossings = frame.windows(2)
            .filter(|w| (w[0] >= 0.0) != (w[1] >= 0.0))
            .count();
        zcrs.push(crossings as f32 / (end - start) as f32);
    }

    if zcrs.len() < 2 {
        return 0.5;
    }

    let mean_zcr: f32 = zcrs.iter().sum::<f32>() / zcrs.len() as f32;
    if mean_zcr < 1e-8 {
        return 0.5; // Silent audio
    }

    let variance: f32 = zcrs.iter().map(|&z| (z - mean_zcr).powi(2)).sum::<f32>() / zcrs.len() as f32;
    let cv = variance.sqrt() / mean_zcr;

    // Map CV to stability: CV=0 → 1.0, CV≥1 → 0.0
    (1.0 - cv).clamp(0.0, 1.0)
}

/// Estimate transient density (percussive content)
fn estimate_transient_density(audio: &[f32], sample_rate: u32) -> f32 {
    if audio.len() < 2 {
        return 0.0;
    }

    // Compute high-frequency content as proxy for transient density
    let frame_size = (sample_rate as usize).max(512); // At least 1 second of analysis
    let mut energy = 0.0f32;
    let mut prev = 0.0f32;

    let diff_count = audio
        .windows(2)
        .take(frame_size.min(audio.len() - 1))
        .filter(|w| {
            let diff = (w[1] - w[0]).abs();
            diff > 0.01 // Significant change
        })
        .count();

    // Normalize to 0-1
    (diff_count as f32 / frame_size as f32).clamp(0.0, 1.0)
}

/// Estimate harmonic ratio (harmonic vs percussive energy)
fn estimate_harmonic_ratio(audio: &[f32], sample_rate: u32) -> f32 {
    // Simplified: high spectral flatness = more noise/less harmonic
    let (_, psd) = spectral_features::audio_to_freq_domain(audio, sample_rate);
    let flatness = spectral_features::compute_spectral_flatness(&psd);

    // Harmonic ratio = inverse of flatness (0 = noise, 1 = pure tone)
    (1.0 - flatness).clamp(0.0, 1.0)
}

/// Estimate chroma energy (harmonic richness)
fn estimate_chroma_energy(audio: &[f32], sample_rate: u32) -> f32 {
    // Simplified: RMS energy normalized
    let rms = compute_rms(audio);

    // Normalize to 0-1 (assuming max -20 dB)
    let db = 20.0 * rms.log10() + 20.0; // Shift so 0 dB = 1.0
    (db / 40.0).clamp(0.0, 1.0)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_compute_complete_fingerprint_mono() {
        let audio = vec![0.1; 48000]; // 1 second at 48kHz
        let fp = compute_complete_fingerprint(&audio, 48000, 1).unwrap();

        // Check that all fields are reasonable
        assert!(fp.lufs >= -120.0 && fp.lufs <= 0.0);
        assert!(fp.crest_db >= 0.0 && fp.crest_db <= 50.0);
        assert!(fp.bass_mid_ratio >= 0.0 && fp.bass_mid_ratio <= 1.0);
        assert!(fp.tempo_bpm > 0.0);
        assert!(fp.spectral_centroid >= 0.0);
        assert!(fp.spectral_flatness >= 0.0 && fp.spectral_flatness <= 1.0);
        assert!(fp.stereo_width == 0.0); // Mono
        assert!(fp.phase_correlation == 1.0); // Mono = perfect correlation
    }

    #[test]
    fn test_compute_complete_fingerprint_stereo() {
        let mut audio = Vec::new();
        for _ in 0..48000 {
            audio.push(0.1); // Left
            audio.push(0.05); // Right (different)
        }

        let fp = compute_complete_fingerprint(&audio, 48000, 2).unwrap();

        assert!(fp.stereo_width > 0.0); // Should be stereo
        assert!(fp.phase_correlation < 1.0); // Not perfect correlation
    }

    #[test]
    fn test_to_dict() {
        let fp = AudioFingerprint {
            sub_bass: 0.1,
            bass: 0.15,
            low_mid: 0.15,
            mid: 0.25,
            upper_mid: 0.2,
            presence: 0.1,
            air: 0.05,
            lufs: -20.0,
            crest_db: 12.0,
            bass_mid_ratio: 0.5,
            tempo_bpm: 120.0,
            rhythm_stability: 0.8,
            transient_density: 0.3,
            silence_ratio: 0.05,
            spectral_centroid: 2000.0,
            spectral_rolloff: 8000.0,
            spectral_flatness: 0.5,
            harmonic_ratio: 0.7,
            pitch_stability: 0.8,
            chroma_energy: 0.6,
            dynamic_range_variation: 2.0,
            loudness_variation: 1.5,
            peak_consistency: 0.8,
            stereo_width: 0.5,
            phase_correlation: 0.95,
        };

        let dict = fp.to_dict();
        assert_eq!(dict.len(), 25);
        assert_eq!(dict.get("sub_bass"), Some(&0.1));
        assert_eq!(dict.get("lufs"), Some(&-20.0));
        assert_eq!(dict.get("stereo_width"), Some(&0.5));
    }
}

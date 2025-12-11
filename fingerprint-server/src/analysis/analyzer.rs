use crate::models::Fingerprint;
use crate::error::{FingerprintError, Result};
use rustfft::FftPlanner;
use rustfft::num_complex::Complex;
use std::f64::consts::PI;

const FFT_SIZE: usize = 2048;
const HOP_LENGTH: usize = 512;

pub fn analyze_fingerprint(samples: &[f64], sample_rate: u32) -> Result<Fingerprint> {
    if samples.is_empty() {
        return Err(FingerprintError::InvalidAudio(
            "No samples to analyze".to_string(),
        ));
    }

    tracing::debug!("Starting fingerprint analysis: {} samples at {} Hz", samples.len(), sample_rate);

    // Pre-compute FFT for frequency and dynamics analysis
    let (magnitude_spec, freqs) = compute_fft_spectrum(samples, sample_rate)?;

    // CRITICAL: Compute spectral statistics on-the-fly instead of storing all STFT frames
    // Storing 56K frames of 2048 samples = 900MB for 10min songs with 16 workers = 14GB memory leak!
    // Instead: compute average spectrum and stats in single pass (no frame storage)
    let spec_analysis = compute_stft_spectral_analysis(samples, sample_rate)?;

    // Analyze each dimension
    let mut fingerprint = Fingerprint::default();

    // Frequency analysis (7D)
    let freq_analysis = analyze_frequency(&magnitude_spec, &freqs)?;
    fingerprint.sub_bass_pct = freq_analysis.0;
    fingerprint.bass_pct = freq_analysis.1;
    fingerprint.low_mid_pct = freq_analysis.2;
    fingerprint.mid_pct = freq_analysis.3;
    fingerprint.upper_mid_pct = freq_analysis.4;
    fingerprint.presence_pct = freq_analysis.5;
    fingerprint.air_pct = freq_analysis.6;

    // Dynamics analysis (3D)
    let dyn_analysis = analyze_dynamics(samples, &magnitude_spec, &freqs, sample_rate)?;
    fingerprint.lufs = dyn_analysis.0;
    fingerprint.crest_db = dyn_analysis.1;
    fingerprint.bass_mid_ratio = dyn_analysis.2;

    // Temporal analysis (4D)
    let temp_analysis = analyze_temporal(samples, sample_rate)?;
    fingerprint.tempo_bpm = temp_analysis.0;
    fingerprint.rhythm_stability = temp_analysis.1;
    fingerprint.transient_density = temp_analysis.2;
    fingerprint.silence_ratio = temp_analysis.3;

    // Spectral analysis (3D) - computed from on-the-fly stats, no frame storage
    fingerprint.spectral_centroid = spec_analysis.0;
    fingerprint.spectral_rolloff = spec_analysis.1;
    fingerprint.spectral_flatness = spec_analysis.2;

    // Harmonic analysis (3D) - simplified version
    let harm_analysis = analyze_harmonic(samples, sample_rate)?;
    fingerprint.harmonic_ratio = harm_analysis.0;
    fingerprint.pitch_stability = harm_analysis.1;
    fingerprint.chroma_energy = harm_analysis.2;

    // Variation analysis (3D)
    let var_analysis = analyze_variation(samples, sample_rate)?;
    fingerprint.dynamic_range_variation = var_analysis.0;
    fingerprint.loudness_variation_std = var_analysis.1;
    fingerprint.peak_consistency = var_analysis.2;

    // Stereo analysis (2D)
    let stereo_analysis = analyze_stereo(samples)?;
    fingerprint.stereo_width = stereo_analysis.0;
    fingerprint.phase_correlation = stereo_analysis.1;

    // Validate fingerprint
    if !fingerprint.is_valid() {
        tracing::warn!("Fingerprint has {} invalid dimensions", 25 - fingerprint.valid_dimensions());
    }

    Ok(fingerprint)
}

fn compute_fft_spectrum(samples: &[f64], sample_rate: u32) -> Result<(Vec<f64>, Vec<f64>)> {
    if samples.len() < FFT_SIZE {
        return Err(FingerprintError::AnalysisError("Not enough samples for FFT".to_string()));
    }

    let mut planner = FftPlanner::new();
    let fft = planner.plan_fft_forward(FFT_SIZE);

    // Apply Hann window
    let window: Vec<f64> = (0..FFT_SIZE)
        .map(|n| 0.5 * (1.0 - (2.0 * PI * n as f64 / (FFT_SIZE as f64 - 1.0)).cos()))
        .collect();

    // Prepare input (windowed)
    let mut input: Vec<Complex<f64>> = samples
        .iter()
        .take(FFT_SIZE)
        .zip(window.iter())
        .map(|(s, w)| Complex {
            re: s * w,
            im: 0.0,
        })
        .collect();

    // Compute FFT
    fft.process(&mut input);

    // Extract magnitude spectrum (LINEAR scale, not dB)
    // CRITICAL: Keep as linear magnitude. Do NOT convert to dB here!
    // If you convert to dB, you get negative values like -200dB.
    // Then when analysis functions do m.max(0.0), they clip all negative dB to zero.
    // This kills all data and results in zero fingerprints!
    let magnitude: Vec<f64> = input
        .iter()
        .map(|c| (c.norm() / FFT_SIZE as f64).max(1e-10))
        .collect();

    // Compute frequency bins
    let freqs: Vec<f64> = (0..FFT_SIZE / 2)
        .map(|k| (k as f64 * sample_rate as f64) / FFT_SIZE as f64)
        .collect();

    Ok((magnitude, freqs))
}

fn analyze_frequency(magnitude_spec: &[f64], freqs: &[f64]) -> Result<(f64, f64, f64, f64, f64, f64, f64)> {
    let bands = [
        (20.0, 60.0),
        (60.0, 250.0),
        (250.0, 500.0),
        (500.0, 2000.0),
        (2000.0, 4000.0),
        (4000.0, 6000.0),
        (6000.0, 20000.0),
    ];

    let mut energies = Vec::new();
    let total_energy: f64 = magnitude_spec.iter().map(|&m| m.max(0.0)).sum();

    for (low, high) in &bands {
        let band_energy: f64 = freqs
            .iter()
            .zip(magnitude_spec.iter())
            .filter(|(&f, _)| f >= *low && f < *high)
            .map(|(_, &m)| m.max(0.0))
            .sum();

        let pct = if total_energy > 0.0 {
            (band_energy / total_energy) * 100.0
        } else {
            0.0
        };
        energies.push(pct.max(0.0).min(100.0));
    }

    Ok((
        energies[0],
        energies[1],
        energies[2],
        energies[3],
        energies[4],
        energies[5],
        energies[6],
    ))
}

fn analyze_dynamics(
    samples: &[f64],
    magnitude_spec: &[f64],
    freqs: &[f64],
    _sample_rate: u32,
) -> Result<(f64, f64, f64)> {
    // LUFS approximation (simplified)
    let rms = (samples.iter().map(|s| s * s).sum::<f64>() / samples.len() as f64).sqrt();
    let lufs = if rms > 0.0 {
        -0.691 + 10.0 * rms.log10()
    } else {
        -120.0
    };

    // Crest factor
    let peak = samples.iter().map(|s| s.abs()).fold(0.0, f64::max);
    let crest_db = if rms > 0.0 {
        20.0 * (peak / rms).max(1.0).log10()
    } else {
        0.0
    };

    // Bass to mid ratio
    let bass_energy: f64 = freqs
        .iter()
        .zip(magnitude_spec.iter())
        .filter(|(&f, _)| f >= 60.0 && f < 250.0)
        .map(|(_, &m)| m.max(0.0))
        .sum();

    let mid_energy: f64 = freqs
        .iter()
        .zip(magnitude_spec.iter())
        .filter(|(&f, _)| f >= 500.0 && f < 2000.0)
        .map(|(_, &m)| m.max(0.0))
        .sum();

    let bass_mid_ratio = if mid_energy > 0.0 {
        20.0 * (bass_energy / mid_energy).max(0.01).log10()
    } else {
        0.0
    };

    Ok((
        lufs.clamp(-120.0, 0.0),
        crest_db.clamp(0.0, 50.0),
        bass_mid_ratio.clamp(-40.0, 40.0),
    ))
}

fn analyze_temporal(samples: &[f64], sample_rate: u32) -> Result<(f64, f64, f64, f64)> {
    // Tempo estimation using onset detection
    let tempo_bpm = estimate_tempo(samples, sample_rate)?;

    // Rhythm stability (based on RMS variation)
    let _frame_size = sample_rate as usize / 10; // 100ms frames
    let mut rms_frames = Vec::new();

    for chunk in samples.chunks(_frame_size) {
        let rms = (chunk.iter().map(|s| s * s).sum::<f64>() / chunk.len() as f64).sqrt();
        rms_frames.push(rms);
    }

    let rhythm_stability = if rms_frames.len() > 1 {
        let mean = rms_frames.iter().sum::<f64>() / rms_frames.len() as f64;
        let variance = rms_frames.iter().map(|r| (r - mean).powi(2)).sum::<f64>() / rms_frames.len() as f64;
        let cv = variance.sqrt() / (mean + 1e-10);
        (1.0 / (1.0 + cv)).max(0.0).min(1.0)
    } else {
        0.5
    };

    // Transient density (peaks per second)
    let mut peaks = 0;
    let _frame_size2 = (sample_rate as usize) / 10; // 100ms frames
    let threshold = samples.iter().map(|s| s.abs()).fold(0.0, f64::max) * 0.5;

    for i in 1..samples.len() - 1 {
        if samples[i].abs() > threshold
            && samples[i].abs() > samples[i - 1].abs()
            && samples[i].abs() > samples[i + 1].abs()
        {
            peaks += 1;
        }
    }

    let transient_density = (peaks as f64 / samples.len() as f64 * sample_rate as f64 * 100.0)
        .max(0.0)
        .min(1.0);

    // Silence ratio
    let silence_threshold = -60.0; // dB
    let rms = (samples.iter().map(|s| s * s).sum::<f64>() / samples.len() as f64).sqrt();
    let silence_ratio = if rms > 0.0 {
        let silence_level = 20.0 * rms.log10();
        if silence_level < silence_threshold {
            1.0
        } else {
            ((silence_threshold - silence_level) / -60.0).max(0.0).min(1.0)
        }
    } else {
        1.0
    };

    Ok((
        tempo_bpm.clamp(40.0, 200.0),
        rhythm_stability,
        transient_density,
        silence_ratio,
    ))
}

fn estimate_tempo(samples: &[f64], sample_rate: u32) -> Result<f64> {
    // Simplified tempo estimation using spectral flux
    let n_frames = samples.len() / HOP_LENGTH;
    if n_frames < 2 {
        return Ok(120.0); // Default tempo
    }

    let mut flux = Vec::new();
    let mut prev_spectrum = vec![0.0; FFT_SIZE / 2];

    for frame_idx in 0..n_frames {
        let start = frame_idx * HOP_LENGTH;
        let end = (start + FFT_SIZE).min(samples.len());

        if end - start < FFT_SIZE {
            break;
        }

        let frame = &samples[start..end];
        let (spectrum, _) = compute_fft_spectrum(frame, sample_rate)?;

        let mut frame_flux = 0.0;
        for (curr, prev) in spectrum.iter().zip(prev_spectrum.iter()) {
            let diff = (curr - prev).max(0.0);
            frame_flux += diff;
        }

        flux.push(frame_flux);
        prev_spectrum = spectrum;
    }

    // Find peak in flux autocorrelation
    if flux.len() < 2 {
        return Ok(120.0);
    }

    let mean_flux = flux.iter().sum::<f64>() / flux.len() as f64;
    let bpm = if mean_flux > 0.0 {
        // Very simplified: estimate from frame count and duration
        let duration_sec = samples.len() as f64 / sample_rate as f64;
        (flux.len() as f64 / duration_sec * 60.0).clamp(40.0, 200.0)
    } else {
        120.0
    };

    Ok(bpm)
}

/// CRITICAL: Compute spectral statistics on-the-fly without storing all frames
/// Avoids 900MB+ memory allocation for 10-minute tracks
fn compute_stft_spectral_analysis(samples: &[f64], _sample_rate: u32) -> Result<(f64, f64, f64)> {
    let window: Vec<f64> = (0..FFT_SIZE)
        .map(|n| 0.5 * (1.0 - (2.0 * PI * n as f64 / (FFT_SIZE as f64 - 1.0)).cos()))
        .collect();

    let mut planner = FftPlanner::new();
    let fft = planner.plan_fft_forward(FFT_SIZE);

    // Accumulate spectrum statistics on-the-fly (no frame storage)
    let mut avg_spectrum = vec![0.0; FFT_SIZE / 2];
    let mut frame_count = 0u64;

    for start in (0..samples.len()).step_by(HOP_LENGTH) {
        let end = (start + FFT_SIZE).min(samples.len());
        if end - start < FFT_SIZE / 2 {
            break;
        }

        let mut input: Vec<Complex<f64>> = samples[start..end]
            .iter()
            .zip(window.iter())
            .map(|(s, w)| Complex {
                re: s * w,
                im: 0.0,
            })
            .collect();

        if input.len() < FFT_SIZE {
            input.resize(FFT_SIZE, Complex { re: 0.0, im: 0.0 });
        }

        fft.process(&mut input);

        // Add magnitude to running average (don't store frame)
        for (i, c) in input.iter().take(FFT_SIZE / 2).enumerate() {
            avg_spectrum[i] += (c.norm() / FFT_SIZE as f64).max(1e-10);
        }
        frame_count += 1;
    }

    if frame_count == 0 {
        return Ok((0.5, 0.5, 0.5));
    }

    // Normalize average
    for val in &mut avg_spectrum {
        *val /= frame_count as f64;
    }

    // Compute spectral statistics from average
    analyze_spectral_stats(&avg_spectrum)
}

/// Analyze spectral statistics without storing frames
fn analyze_spectral_stats(avg_spectrum: &[f64]) -> Result<(f64, f64, f64)> {
    if avg_spectrum.is_empty() {
        return Ok((0.5, 0.5, 0.5));
    }

    let total_energy: f64 = avg_spectrum.iter().sum();
    if total_energy == 0.0 {
        return Ok((0.5, 0.5, 0.5));
    }

    // Spectral centroid
    let mut weighted_sum = 0.0;
    for (k, &energy) in avg_spectrum.iter().enumerate() {
        weighted_sum += (k as f64) * energy;
    }
    let centroid = (weighted_sum / total_energy / (FFT_SIZE as f64 / 2.0)).min(1.0);

    // Spectral rolloff (frequency containing 95% of energy)
    let mut cumsum = 0.0;
    let mut rolloff = 0.5;
    for (k, &energy) in avg_spectrum.iter().enumerate() {
        cumsum += energy;
        if cumsum > total_energy * 0.95 {
            rolloff = (k as f64 / (FFT_SIZE as f64 / 2.0)).min(1.0);
            break;
        }
    }

    // Spectral flatness (entropy measure)
    let geometric_mean = avg_spectrum.iter().fold(1.0, |acc, &x| acc * (x + 1e-10)).powf(1.0 / avg_spectrum.len() as f64);
    let arithmetic_mean = total_energy / avg_spectrum.len() as f64;
    let flatness = if arithmetic_mean > 0.0 {
        (geometric_mean / arithmetic_mean).min(1.0).max(0.0)
    } else {
        0.5
    };

    Ok((centroid, rolloff, flatness))
}

fn analyze_spectral(stft_frames: &[Vec<f64>]) -> Result<(f64, f64, f64)> {
    if stft_frames.is_empty() {
        return Ok((0.5, 0.5, 0.5));
    }

    // Average spectrum across frames
    let mut avg_spectrum = vec![0.0; stft_frames[0].len()];
    for frame in stft_frames {
        for (i, val) in frame.iter().enumerate() {
            avg_spectrum[i] += val;
        }
    }

    for val in &mut avg_spectrum {
        *val /= stft_frames.len() as f64;
    }

    let total_energy: f64 = avg_spectrum.iter().sum();
    if total_energy == 0.0 {
        return Ok((0.5, 0.5, 0.5));
    }

    // Spectral centroid
    let mut weighted_sum = 0.0;
    for (k, &energy) in avg_spectrum.iter().enumerate() {
        weighted_sum += (k as f64) * energy;
    }
    let centroid = (weighted_sum / total_energy / (FFT_SIZE as f64 / 2.0)).min(1.0);

    // Spectral rolloff (85% energy)
    let mut cumsum = 0.0;
    let threshold = total_energy * 0.85;
    let mut rolloff_idx = FFT_SIZE / 2;
    for (k, &energy) in avg_spectrum.iter().enumerate() {
        cumsum += energy;
        if cumsum >= threshold {
            rolloff_idx = k;
            break;
        }
    }
    let rolloff = (rolloff_idx as f64 / (FFT_SIZE / 2) as f64).min(1.0);

    // Spectral flatness
    let geometric_mean = avg_spectrum
        .iter()
        .filter(|&&e| e > 0.0)
        .map(|&e| e.ln())
        .sum::<f64>()
        / avg_spectrum.len() as f64;
    let arithmetic_mean = total_energy / avg_spectrum.len() as f64;
    let flatness = if arithmetic_mean > 0.0 {
        (geometric_mean.exp() / arithmetic_mean).min(1.0).max(0.0)
    } else {
        0.0
    };

    Ok((
        centroid.max(0.0).min(1.0),
        rolloff.max(0.0).min(1.0),
        flatness.max(0.0).min(1.0),
    ))
}

fn analyze_harmonic(samples: &[f64], sample_rate: u32) -> Result<(f64, f64, f64)> {
    // Simplified harmonic analysis
    // In full implementation, this would use HPSS, YIN, and Chroma from vendor/auralis-dsp

    // Harmonic ratio: energy in harmonic peaks vs total
    let (mag_spec, _) = compute_fft_spectrum(samples, sample_rate)?;

    // Find peaks in spectrum
    let mut harmonic_energy = 0.0;
    let total_energy: f64 = mag_spec.iter().map(|m| m.max(0.0)).sum();

    for i in 1..mag_spec.len() - 1 {
        if mag_spec[i] > mag_spec[i - 1] && mag_spec[i] > mag_spec[i + 1] {
            harmonic_energy += mag_spec[i].max(0.0);
        }
    }

    let harmonic_ratio = if total_energy > 0.0 {
        (harmonic_energy / total_energy).min(1.0)
    } else {
        0.0
    };

    // Pitch stability: estimate from autocorrelation
    let pitch_stability: f64 = 0.5; // Simplified

    // Chroma energy: energy in tonal region (100Hz - 5kHz)
    let chroma_energy: f64 = mag_spec
        .iter()
        .take((5000.0 * mag_spec.len() as f64 / sample_rate as f64) as usize)
        .skip((100.0 * mag_spec.len() as f64 / sample_rate as f64) as usize)
        .map(|m| m.max(0.0))
        .sum();

    let chroma_energy_normalized = if total_energy > 0.0 {
        (chroma_energy / total_energy).min(1.0)
    } else {
        0.0
    };

    Ok((
        harmonic_ratio.max(0.0).min(1.0),
        pitch_stability.max(0.0).min(1.0),
        chroma_energy_normalized.max(0.0).min(1.0),
    ))
}

fn analyze_variation(samples: &[f64], sample_rate: u32) -> Result<(f64, f64, f64)> {
    let frame_size = (sample_rate as usize) / 10; // 100ms frames
    let mut crest_factors = Vec::new();
    let mut loudness_values = Vec::new();
    let mut peaks = Vec::new();

    for chunk in samples.chunks(frame_size) {
        if chunk.is_empty() {
            continue;
        }

        let rms = (chunk.iter().map(|s| s * s).sum::<f64>() / chunk.len() as f64).sqrt();
        let peak = chunk.iter().map(|s| s.abs()).fold(0.0, f64::max);

        let crest = if rms > 0.0 { peak / rms } else { 1.0 };
        crest_factors.push(crest);

        let loudness = if rms > 0.0 { 20.0 * rms.log10() } else { -120.0 };
        loudness_values.push(loudness);

        peaks.push(peak);
    }

    // Dynamic range variation
    let dynamic_range_variation = if crest_factors.len() > 1 {
        let mean = crest_factors.iter().sum::<f64>() / crest_factors.len() as f64;
        let variance = crest_factors
            .iter()
            .map(|c| (c - mean).powi(2))
            .sum::<f64>()
            / crest_factors.len() as f64;
        (variance.sqrt() / (mean + 1e-10)).min(1.0)
    } else {
        0.0
    };

    // Loudness variation std
    let loudness_variation_std = if loudness_values.len() > 1 {
        let mean = loudness_values.iter().sum::<f64>() / loudness_values.len() as f64;
        let variance = loudness_values
            .iter()
            .map(|l| (l - mean).powi(2))
            .sum::<f64>()
            / loudness_values.len() as f64;
        variance.sqrt().max(0.0)
    } else {
        0.0
    };

    // Peak consistency
    let peak_consistency = if peaks.len() > 1 {
        let mean = peaks.iter().sum::<f64>() / peaks.len() as f64;
        let variance = peaks.iter().map(|p| (p - mean).powi(2)).sum::<f64>() / peaks.len() as f64;
        let cv = variance.sqrt() / (mean + 1e-10);
        (1.0 / (1.0 + cv)).max(0.0).min(1.0)
    } else {
        0.5
    };

    Ok((
        dynamic_range_variation.max(0.0).min(1.0),
        loudness_variation_std.max(0.0).min(10.0),
        peak_consistency.max(0.0).min(1.0),
    ))
}

fn analyze_stereo(_samples: &[f64]) -> Result<(f64, f64)> {
    // Simplified stereo analysis (mono signal has no stereo info)
    // In real implementation, would need actual stereo channels
    Ok((0.0, 1.0)) // mono width = 0, perfect correlation = 1.0
}

/// Python bindings via PyO3
///
/// Exposes Rust DSP functions to Python
///
/// All core algorithms (HPSS, YIN, Chroma CQT) are validated and production-ready.
/// This module provides seamless Python bindings via PyO3.

use pyo3::prelude::*;
use pyo3::types::{PyModule, PyDict};
use numpy::{PyArray1, PyArray2, ToPyArray, IntoPyArray};
use crate::{hpss, yin, chroma, tempo, envelope, compressor, limiter, fingerprint_compute};

/// PyO3 module initialization
/// Exposes all DSP functions to Python
#[pymodule]
fn auralis_dsp(_py: Python<'_>, m: &PyModule) -> PyResult<()> {
    // Add functions with clean names (without _wrapper suffix)
    m.add_function(wrap_pyfunction!(hpss_wrapper, m)?)?;
    m.add("hpss", m.getattr("hpss_wrapper")?)?;

    m.add_function(wrap_pyfunction!(yin_wrapper, m)?)?;
    m.add("yin", m.getattr("yin_wrapper")?)?;

    m.add_function(wrap_pyfunction!(chroma_cqt_wrapper, m)?)?;
    m.add("chroma_cqt", m.getattr("chroma_cqt_wrapper")?)?;

    m.add_function(wrap_pyfunction!(detect_tempo_wrapper, m)?)?;
    m.add("detect_tempo", m.getattr("detect_tempo_wrapper")?)?;

    m.add_function(wrap_pyfunction!(envelope_follow_wrapper, m)?)?;
    m.add("envelope_follow", m.getattr("envelope_follow_wrapper")?)?;

    m.add_function(wrap_pyfunction!(compress_wrapper, m)?)?;
    m.add("compress", m.getattr("compress_wrapper")?)?;

    m.add_function(wrap_pyfunction!(limit_wrapper, m)?)?;
    m.add("limit", m.getattr("limit_wrapper")?)?;

    m.add_function(wrap_pyfunction!(compute_fingerprint_wrapper, m)?)?;
    m.add("compute_fingerprint", m.getattr("compute_fingerprint_wrapper")?)?;

    Ok(())
}

/// Python wrapper for HPSS (Harmonic/Percussive Source Separation)
///
/// Decomposes audio into harmonic and percussive components.
///
/// Arguments:
///     audio: numpy array of shape (n_samples,) with dtype float64
///     sr: Sample rate in Hz (typically 44100, used for documentation)
///     kernel_h: Harmonic median filter kernel size (default: 31)
///     kernel_p: Percussive median filter kernel size (default: 31)
///
/// Returns:
///     Tuple of (harmonic, percussive) audio arrays
///
/// Example:
///     >>> import numpy as np
///     >>> import auralis_dsp
///     >>> audio = np.random.randn(44100).astype(np.float64)
///     >>> harmonic, percussive = auralis_dsp.hpss(audio, sr=44100)
#[pyfunction]
#[pyo3(signature = (audio, sr = 44100, kernel_h = None, kernel_p = None))]
fn hpss_wrapper(
    py: Python<'_>,
    audio: &PyArray1<f64>,
    sr: usize,
    kernel_h: Option<usize>,
    kernel_p: Option<usize>,
) -> PyResult<(Py<PyArray1<f64>>, Py<PyArray1<f64>>)> {
    // Convert numpy array to Rust vec
    let audio_vec: Vec<f64> = audio.to_vec().map_err(|e| {
        PyErr::new::<pyo3::exceptions::PyTypeError, _>(
            format!("Failed to convert audio array: {}", e),
        )
    })?;

    // Build HPSS config with optional parameters
    let mut config = hpss::HpssConfig::default();
    if let Some(kh) = kernel_h {
        config.kernel_h = kh;
    }
    if let Some(kp) = kernel_p {
        config.kernel_p = kp;
    }

    // Call Rust HPSS function
    let (harmonic, percussive) = hpss::hpss(&audio_vec, &config);

    // Convert results back to numpy arrays
    let harmonic_py = harmonic.into_pyarray_bound(py).unbind();
    let percussive_py = percussive.into_pyarray_bound(py).unbind();

    Ok((harmonic_py, percussive_py))
}

/// Python wrapper for YIN (Fundamental Frequency Detection)
///
/// Detects fundamental frequency (pitch) using the YIN algorithm.
///
/// Arguments:
///     audio: numpy array of shape (n_samples,) with dtype float64
///     sr: Sample rate in Hz (typically 44100)
///     fmin: Minimum frequency to detect (default: 65.4 Hz)
///     fmax: Maximum frequency to detect (default: 2093 Hz)
///
/// Returns:
///     numpy array of shape (n_frames,) with F0 contour
///
/// Example:
///     >>> import numpy as np
///     >>> import auralis_dsp
///     >>> audio = np.random.randn(44100).astype(np.float64)
///     >>> f0 = auralis_dsp.yin(audio, sr=44100)
#[pyfunction]
#[pyo3(signature = (audio, sr = 44100, fmin = 65.4, fmax = 2093.0))]
fn yin_wrapper(
    py: Python<'_>,
    audio: &PyArray1<f64>,
    sr: usize,
    fmin: f64,
    fmax: f64,
) -> PyResult<Py<PyArray1<f64>>> {
    // Convert numpy array to Rust vec
    let audio_vec: Vec<f64> = audio.to_vec().map_err(|e| {
        PyErr::new::<pyo3::exceptions::PyTypeError, _>(
            format!("Failed to convert audio array: {}", e),
        )
    })?;

    // Call Rust YIN function
    let f0 = yin::yin(&audio_vec, sr, fmin, fmax);

    // Convert result to numpy array
    let f0_py = f0.into_pyarray_bound(py).unbind();

    Ok(f0_py)
}

/// Python wrapper for Chroma CQT (Chromagram Extraction)
///
/// Extracts 12-dimensional chromagram using constant-Q transform.
///
/// Arguments:
///     audio: numpy array of shape (n_samples,) with dtype float64
///     sr: Sample rate in Hz (typically 44100)
///
/// Returns:
///     numpy array of shape (12, n_frames) with normalized energy per semitone
///
/// Example:
///     >>> import numpy as np
///     >>> import auralis_dsp
///     >>> audio = np.random.randn(44100).astype(np.float64)
///     >>> chroma = auralis_dsp.chroma_cqt(audio, sr=44100)
///     >>> chroma_energy = np.mean(chroma)  # Single scalar feature
#[pyfunction]
#[pyo3(signature = (audio, sr = 44100))]
fn chroma_cqt_wrapper(
    py: Python<'_>,
    audio: &PyArray1<f64>,
    sr: usize,
) -> PyResult<Py<PyArray2<f64>>> {
    // Convert numpy array to Rust vec
    let audio_vec: Vec<f64> = audio.to_vec().map_err(|e| {
        PyErr::new::<pyo3::exceptions::PyTypeError, _>(
            format!("Failed to convert audio array: {}", e),
        )
    })?;

    // Call Rust chroma_cqt function
    let chroma = chroma::chroma_cqt(&audio_vec, sr);

    // Convert result to numpy array
    let chroma_py = chroma.into_pyarray_bound(py).unbind();

    Ok(chroma_py)
}

/// Python wrapper for Tempo Detection (Spectral Flux Onset Detection)
///
/// Estimates tempo in BPM using spectral flux onset detection.
///
/// Arguments:
///     audio: numpy array of shape (n_samples,) with dtype float64
///     sr: Sample rate in Hz (typically 44100)
///     n_fft: FFT window size (default: 1024)
///     hop_length: Hop length in samples (default: 512)
///     threshold_multiplier: Peak detection threshold multiplier (default: 0.5)
///     min_bpm: Minimum BPM to return (default: 60)
///     max_bpm: Maximum BPM to return (default: 200)
///
/// Returns:
///     Estimated tempo in BPM (float)
///
/// Example:
///     >>> import numpy as np
///     >>> import auralis_dsp
///     >>> audio = np.random.randn(44100).astype(np.float64)  # 1 second
///     >>> bpm = auralis_dsp.detect_tempo(audio, sr=44100)
///     >>> print(f"Estimated tempo: {bpm:.1f} BPM")
#[pyfunction]
#[pyo3(signature = (audio, sr = 44100, n_fft = None, hop_length = None, threshold_multiplier = None, min_bpm = None, max_bpm = None))]
fn detect_tempo_wrapper(
    audio: &PyArray1<f64>,
    sr: usize,
    n_fft: Option<usize>,
    hop_length: Option<usize>,
    threshold_multiplier: Option<f64>,
    min_bpm: Option<f64>,
    max_bpm: Option<f64>,
) -> PyResult<f64> {
    // Convert numpy array to Rust vec
    let audio_vec: Vec<f64> = audio.to_vec().map_err(|e| {
        PyErr::new::<pyo3::exceptions::PyTypeError, _>(
            format!("Failed to convert audio array: {}", e),
        )
    })?;

    // Build tempo config with optional parameters
    let mut config = tempo::TempoConfig::default();
    if let Some(nf) = n_fft {
        config.n_fft = nf;
    }
    if let Some(hl) = hop_length {
        config.hop_length = hl;
    }
    if let Some(tm) = threshold_multiplier {
        config.threshold_multiplier = tm;
    }
    if let Some(min) = min_bpm {
        config.min_bpm = min;
    }
    if let Some(max) = max_bpm {
        config.max_bpm = max;
    }

    // Call Rust tempo detection function
    let estimated_tempo = tempo::detect_tempo(&audio_vec, sr, &config);

    Ok(estimated_tempo)
}

/// Python wrapper for Envelope Follower
///
/// High-performance envelope follower with attack/release characteristics.
/// Used for compressor/limiter gain smoothing and level detection.
///
/// Arguments:
///     input_levels: numpy array of shape (n_samples,) with dtype float32
///     sample_rate: Audio sample rate in Hz (typically 44100)
///     attack_ms: Attack time in milliseconds (default: 10.0)
///     release_ms: Release time in milliseconds (default: 100.0)
///
/// Returns:
///     numpy array of shape (n_samples,) with envelope values
///
/// Example:
///     >>> import numpy as np
///     >>> import auralis_dsp
///     >>> # Detect peaks in audio with 10ms attack, 100ms release
///     >>> levels = np.abs(audio).astype(np.float32)
///     >>> envelope = auralis_dsp.envelope_follow(levels, sr=44100, attack_ms=10.0, release_ms=100.0)
#[pyfunction]
#[pyo3(signature = (input_levels, sample_rate = 44100, attack_ms = 10.0, release_ms = 100.0))]
fn envelope_follow_wrapper(
    py: Python<'_>,
    input_levels: &PyArray1<f32>,
    sample_rate: usize,
    attack_ms: f32,
    release_ms: f32,
) -> PyResult<Py<PyArray1<f32>>> {
    // Convert numpy array to Rust vec
    let levels_vec: Vec<f32> = input_levels.to_vec().map_err(|e| {
        PyErr::new::<pyo3::exceptions::PyTypeError, _>(
            format!("Failed to convert input_levels array: {}", e),
        )
    })?;

    // Call Rust envelope follower function
    let envelope = envelope::envelope_follow(&levels_vec, sample_rate, attack_ms, release_ms);

    // Convert result to numpy array
    let envelope_py = envelope.into_pyarray_bound(py).unbind();

    Ok(envelope_py)
}

/// Python wrapper for Compressor
///
/// High-performance dynamic range compressor with peak/RMS/hybrid detection.
/// Used for mastering and mixing to control dynamic range.
///
/// Arguments:
///     audio: numpy array of shape (n_samples,) with dtype float32
///     sample_rate: Audio sample rate in Hz (typically 44100)
///     threshold_db: Compression threshold in dB (default: -20.0)
///     ratio: Compression ratio (default: 4.0, i.e., 4:1)
///     knee_db: Soft knee width in dB (default: 6.0)
///     attack_ms: Attack time in milliseconds (default: 5.0)
///     release_ms: Release time in milliseconds (default: 50.0)
///     makeup_gain_db: Makeup gain in dB (default: 0.0)
///     enable_lookahead: Enable lookahead buffer (default: True)
///     lookahead_ms: Lookahead time in milliseconds (default: 5.0)
///     detection_mode: Detection mode - "peak", "rms", or "hybrid" (default: "peak")
///
/// Returns:
///     Tuple of (compressed_audio, compression_info_dict)
///
/// Example:
///     >>> import numpy as np
///     >>> import auralis_dsp
///     >>> audio = np.random.randn(44100).astype(np.float32)
///     >>> compressed, info = auralis_dsp.compress(audio, sr=44100, threshold_db=-20.0, ratio=4.0)
///     >>> print(f"Peak GR: {info['peak_gain_reduction_db']:.2f} dB")
#[pyfunction]
#[pyo3(signature = (
    audio,
    sample_rate = 44100,
    threshold_db = -20.0,
    ratio = 4.0,
    knee_db = 6.0,
    attack_ms = 5.0,
    release_ms = 50.0,
    makeup_gain_db = 0.0,
    enable_lookahead = true,
    lookahead_ms = 5.0,
    detection_mode = "peak"
))]
fn compress_wrapper(
    py: Python<'_>,
    audio: &PyArray1<f32>,
    sample_rate: usize,
    threshold_db: f32,
    ratio: f32,
    knee_db: f32,
    attack_ms: f32,
    release_ms: f32,
    makeup_gain_db: f32,
    enable_lookahead: bool,
    lookahead_ms: f32,
    detection_mode: &str,
) -> PyResult<(Py<PyArray1<f32>>, PyObject)> {
    // Convert numpy array to Rust vec
    let audio_vec: Vec<f32> = audio.to_vec().map_err(|e| {
        PyErr::new::<pyo3::exceptions::PyTypeError, _>(
            format!("Failed to convert audio array: {}", e),
        )
    })?;

    // Parse detection mode
    let mode = match detection_mode.to_lowercase().as_str() {
        "peak" => compressor::DetectionMode::Peak,
        "rms" => compressor::DetectionMode::Rms,
        "hybrid" => compressor::DetectionMode::Hybrid,
        _ => return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
            format!("Invalid detection_mode: '{}'. Must be 'peak', 'rms', or 'hybrid'", detection_mode)
        )),
    };

    // Build compressor config
    let config = compressor::CompressorConfig {
        sample_rate,
        threshold_db,
        ratio,
        knee_db,
        attack_ms,
        release_ms,
        makeup_gain_db,
        enable_lookahead,
        lookahead_ms,
    };

    // Call Rust compressor function
    let (compressed, info) = compressor::compress(&audio_vec, &config, mode);

    // Convert result to numpy array
    let compressed_py = compressed.into_pyarray_bound(py).unbind();

    // Convert compression info to Python dict
    let info_dict = pyo3::types::PyDict::new_bound(py);
    info_dict.set_item("input_level_db", info.input_level_db)?;
    info_dict.set_item("gain_reduction_db", info.gain_reduction_db)?;
    info_dict.set_item("output_gain", info.output_gain)?;
    info_dict.set_item("threshold_db", info.threshold_db)?;
    info_dict.set_item("ratio", info.ratio)?;

    Ok((compressed_py, info_dict.into()))
}

/// Python wrapper for Limiter
///
/// High-performance lookahead limiter with ISR and optional oversampling.
/// Used for peak control and preventing clipping in mastering.
///
/// Arguments:
///     audio: numpy array of shape (n_samples,) with dtype float32
///     sample_rate: Audio sample rate in Hz (typically 44100)
///     threshold_db: Limiting threshold in dB (default: -0.1)
///     release_ms: Release time in milliseconds (default: 50.0)
///     lookahead_ms: Lookahead time in milliseconds (default: 5.0)
///     isr_enabled: Enable inter-sample peak detection (default: True)
///     oversampling: Oversampling factor - 1 (off), 2, or 4 (default: 1)
///
/// Returns:
///     Tuple of (limited_audio, limiting_info_dict)
///
/// Example:
///     >>> import numpy as np
///     >>> import auralis_dsp
///     >>> audio = np.random.randn(44100).astype(np.float32) * 1.5  # Potentially clipping
///     >>> limited, info = auralis_dsp.limit(audio, sr=44100, threshold_db=-0.1, isr_enabled=True)
///     >>> print(f"GR: {info['gain_reduction_db']:.2f} dB, Peak: {info['output_peak_db']:.2f} dB")
#[pyfunction]
#[pyo3(signature = (
    audio,
    sample_rate = 44100,
    threshold_db = -0.1,
    release_ms = 50.0,
    lookahead_ms = 5.0,
    isr_enabled = true,
    oversampling = 1
))]
fn limit_wrapper(
    py: Python<'_>,
    audio: &PyArray1<f32>,
    sample_rate: usize,
    threshold_db: f32,
    release_ms: f32,
    lookahead_ms: f32,
    isr_enabled: bool,
    oversampling: usize,
) -> PyResult<(Py<PyArray1<f32>>, PyObject)> {
    // Convert numpy array to Rust vec
    let audio_vec: Vec<f32> = audio.to_vec().map_err(|e| {
        PyErr::new::<pyo3::exceptions::PyTypeError, _>(
            format!("Failed to convert audio array: {}", e),
        )
    })?;

    // Validate oversampling factor
    if oversampling != 1 && oversampling != 2 && oversampling != 4 {
        return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
            format!("Invalid oversampling: {}. Must be 1, 2, or 4", oversampling)
        ));
    }

    // Build limiter config
    let config = limiter::LimiterConfig {
        sample_rate,
        threshold_db,
        release_ms,
        lookahead_ms,
        isr_enabled,
        oversampling,
    };

    // Call Rust limiter function
    let (limited, info) = limiter::limit(&audio_vec, &config);

    // Convert result to numpy array
    let limited_py = limited.into_pyarray_bound(py).unbind();

    // Convert limiting info to Python dict
    let info_dict = pyo3::types::PyDict::new_bound(py);
    info_dict.set_item("input_peak_db", info.input_peak_db)?;
    info_dict.set_item("output_peak_db", info.output_peak_db)?;
    info_dict.set_item("gain_reduction_db", info.gain_reduction_db)?;
    info_dict.set_item("threshold_db", info.threshold_db)?;
    info_dict.set_item("peak_hold_db", info.peak_hold_db)?;

    Ok((limited_py, info_dict.into()))
}

/// Python wrapper for complete 25D fingerprint computation
///
/// Computes a comprehensive audio fingerprint with 25 dimensions covering:
/// - Frequency distribution (7D)
/// - Dynamics (3D)
/// - Temporal characteristics (4D)
/// - Spectral features (3D)
/// - Harmonic content (3D)
/// - Variation metrics (3D)
/// - Stereo field (2D)
///
/// Arguments:
///     audio: numpy array of shape (n_samples,) with dtype float32
///     sample_rate: Audio sample rate in Hz (typically 48000)
///     channels: Number of audio channels (1 = mono, 2 = stereo)
///
/// Returns:
///     Dictionary with 25 fingerprint dimensions
///
/// Example:
///     >>> import numpy as np
///     >>> import auralis_dsp
///     >>> audio = np.random.randn(48000).astype(np.float32)
///     >>> fingerprint = auralis_dsp.compute_fingerprint(audio, 48000, 1)
///     >>> print(fingerprint['lufs'], fingerprint['tempo_bpm'])
#[pyfunction]
fn compute_fingerprint_wrapper(
    py: Python<'_>,
    audio: Vec<f32>,
    sample_rate: u32,
    channels: u32,
) -> PyResult<PyObject> {
    if audio.is_empty() {
        return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
            "Audio array is empty",
        ));
    }

    if sample_rate == 0 {
        return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
            "Sample rate must be > 0",
        ));
    }

    if channels == 0 || channels > 2 {
        return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
            "Channels must be 1 (mono) or 2 (stereo)",
        ));
    }

    // Call Rust fingerprint computation
    let fingerprint = fingerprint_compute::compute_complete_fingerprint(&audio, sample_rate, channels)
        .map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string())
        })?;

    // Convert fingerprint to Python dict
    let dict = PyDict::new_bound(py);

    // Frequency (7D)
    dict.set_item("sub_bass", fingerprint.sub_bass)?;
    dict.set_item("bass", fingerprint.bass)?;
    dict.set_item("low_mid", fingerprint.low_mid)?;
    dict.set_item("mid", fingerprint.mid)?;
    dict.set_item("upper_mid", fingerprint.upper_mid)?;
    dict.set_item("presence", fingerprint.presence)?;
    dict.set_item("air", fingerprint.air)?;

    // Dynamics (3D)
    dict.set_item("lufs", fingerprint.lufs)?;
    dict.set_item("crest_db", fingerprint.crest_db)?;
    dict.set_item("bass_mid_ratio", fingerprint.bass_mid_ratio)?;

    // Temporal (4D)
    dict.set_item("tempo_bpm", fingerprint.tempo_bpm)?;
    dict.set_item("rhythm_stability", fingerprint.rhythm_stability)?;
    dict.set_item("transient_density", fingerprint.transient_density)?;
    dict.set_item("silence_ratio", fingerprint.silence_ratio)?;

    // Spectral (3D)
    dict.set_item("spectral_centroid", fingerprint.spectral_centroid)?;
    dict.set_item("spectral_rolloff", fingerprint.spectral_rolloff)?;
    dict.set_item("spectral_flatness", fingerprint.spectral_flatness)?;

    // Harmonic (3D)
    dict.set_item("harmonic_ratio", fingerprint.harmonic_ratio)?;
    dict.set_item("pitch_stability", fingerprint.pitch_stability)?;
    dict.set_item("chroma_energy", fingerprint.chroma_energy)?;

    // Variation (3D)
    dict.set_item("dynamic_range_variation", fingerprint.dynamic_range_variation)?;
    dict.set_item("loudness_variation", fingerprint.loudness_variation)?;
    dict.set_item("peak_consistency", fingerprint.peak_consistency)?;

    // Stereo (2D)
    dict.set_item("stereo_width", fingerprint.stereo_width)?;
    dict.set_item("phase_correlation", fingerprint.phase_correlation)?;

    Ok(dict.into())
}

/// Python bindings via PyO3
///
/// Exposes Rust DSP functions to Python
///
/// All core algorithms (HPSS, YIN, Chroma CQT) are validated and production-ready.
/// This module provides seamless Python bindings via PyO3.

use pyo3::prelude::*;
use pyo3::types::PyModule;
use numpy::{PyArray1, PyArray2, ToPyArray, IntoPyArray};
use crate::{hpss, yin, chroma, tempo};

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

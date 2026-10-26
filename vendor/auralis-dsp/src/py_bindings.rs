/// Python bindings via PyO3
///
/// Exposes Rust DSP functions to Python
///
/// Only `compute_fingerprint` has a production caller. `process_chunks` is
/// dead and tracked in #5738. Do not add bindings without a production
/// Python caller.

use pyo3::prelude::*;
use pyo3::types::{PyModule, PyDict};
use numpy::{PyReadonlyArray1, PyReadonlyArray2, IntoPyArray};
use crate::{fingerprint_compute, chunk_processor};

/// Extract a human-readable message from a Rust panic payload (issue #2225).
fn format_panic(e: Box<dyn std::any::Any + Send>) -> String {
    if let Some(s) = e.downcast_ref::<&str>() {
        (*s).to_string()
    } else if let Some(s) = e.downcast_ref::<String>() {
        s.clone()
    } else {
        "unknown panic".to_string()
    }
}

/// PyO3 module initialization
/// Exposes all DSP functions to Python
#[pymodule]
fn auralis_dsp(_py: Python<'_>, m: &Bound<'_, PyModule>) -> PyResult<()> {
    // Add functions with clean names (without _wrapper suffix)
    // Fingerprint - register directly
    m.add_function(wrap_pyfunction!(compute_fingerprint_wrapper, m)?)?;

    // Also add under clean name
    let wrapper_fn = m.getattr("compute_fingerprint_wrapper")?;
    m.add("compute_fingerprint", wrapper_fn)?;

    m.add_function(wrap_pyfunction!(process_chunks_wrapper, m)?)?;
    m.add("process_chunks", m.getattr("process_chunks_wrapper")?)?;

    Ok(())
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
    audio: PyReadonlyArray1<'_, f32>,
    sample_rate: u32,
    channels: u32,
) -> PyResult<Py<PyDict>> {
    // Convert numpy array to Rust vec
    let audio_vec: Vec<f32> = audio.as_array().to_vec();

    if audio_vec.is_empty() {
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

    // Release GIL during CPU-bound computation (#2447).
    // The inner Result uses Box<dyn Error> which is not Send/Ungil, so convert
    // to String (which is) before the detach boundary.
    let fingerprint = py.detach(|| std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
        fingerprint_compute::compute_complete_fingerprint(&audio_vec, sample_rate, channels)
            .map_err(|e| e.to_string())
    })))
    .map_err(|e| {
        PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
            format!("Rust DSP panic in compute_fingerprint: {}", format_panic(e)),
        )
    })?
    .map_err(|e| {
        PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e)
    })?;

    // Convert fingerprint to Python dict
    let dict = PyDict::new(py);

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

/// Python wrapper for chunk processing
///
/// Process audio in optimized chunks for streaming
///
/// Arguments:
///     audio: numpy array of shape (2, n_samples) for stereo
///     chunk_size: Size of each chunk (default: 131072)
///     overlap: Overlap between chunks (default: 2205)
///
/// Returns:
///     Dictionary with 'output' (the processed samples, shape (channels, n)),
///     'chunk_size', and 'overlap'. (The docstring used to promise a 'peaks'
///     key that does not exist — fixed in #5537.)
///
/// UNREACHABLE from production: the engine's chunked mastering loop is the
/// same-named Python function in auralis/core/mastering_chunk_loop.py, and
/// the only Python caller of this binding is a PyO3 boundary smoke test
/// (tests/test_pyo3_channel_axis_guards_4502.py) — noted earlier in #4989.
/// TODO(#5738): either wire this into the engine (it takes f64 while the
/// engine's chunk loop works in f32, so a caller needs an explicit cast) or
/// remove the binding, chunk_processor.rs, and the smoke-test cases together.
///
/// Note: This is a simplified wrapper. For custom processing, use the Rust API directly.
#[pyfunction]
#[pyo3(signature = (audio, chunk_size = 131072, overlap = 2205))]
fn process_chunks_wrapper(
    py: Python<'_>,
    audio: PyReadonlyArray2<'_, f64>,
    chunk_size: usize,
    overlap: usize,
) -> PyResult<Py<PyDict>> {
    // Convert to ndarray
    let audio_array = audio.as_array().to_owned();

    // Same channel-axis guard as compute_fingerprint_wrapper above (#4502):
    // num_channels sizes per-channel state in ChunkProcessor.
    let num_channels = audio_array.shape()[0];
    if num_channels == 0 || num_channels > 2 {
        return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
            format!(
                "Channels must be 1 (mono) or 2 (stereo), got {};                  audio must be shaped (channels, samples), not (samples, channels)",
                num_channels
            ),
        ));
    }

    let config = chunk_processor::ChunkConfig {
        chunk_size,
        overlap,
        num_channels,
        crossfade_samples: 2205,
    };

    let mut processor = chunk_processor::ChunkProcessor::new(config);

    // Release GIL during CPU-bound computation (#2447).
    let output = py.detach(|| std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
        processor.process_chunks(&audio_array.view(), |chunk| chunk.to_owned())
    })))
    .map_err(|e| {
        PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
            format!("Rust DSP panic in process_chunks: {}", format_panic(e)),
        )
    })?;

    // Collect stats
    let dict = PyDict::new(py);
    dict.set_item("output", output.into_pyarray(py))?;
    dict.set_item("chunk_size", chunk_size)?;
    dict.set_item("overlap", overlap)?;

    Ok(dict.into())
}

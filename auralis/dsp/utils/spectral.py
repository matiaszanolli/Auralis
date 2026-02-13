"""
Spectral Analysis Utilities
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Spectral feature extraction and analysis functions

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np

from ...utils.logging import debug


def spectral_centroid(audio: np.ndarray, sample_rate: int = 44100) -> float:
    """
    Calculate spectral centroid (brightness measure)

    The spectral centroid indicates where the "center of mass" of the spectrum
    is located. Higher values indicate brighter sounds.

    Args:
        audio: Input audio signal
        sample_rate: Sample rate in Hz

    Returns:
        Spectral centroid in Hz
    """
    if audio.ndim == 2:
        audio = np.mean(audio, axis=1)

    # Use a window to focus on the middle part of the signal
    if len(audio) > 4096:
        start = len(audio) // 4
        end = 3 * len(audio) // 4
        audio_segment = audio[start:end]
        # Use a power-of-2 size for FFT efficiency
        fft_size = min(4096, len(audio_segment))
        audio_segment = audio_segment[:fft_size]
    else:
        audio_segment = audio

    # Apply window to reduce spectral leakage
    window = np.hanning(len(audio_segment))
    windowed_audio = audio_segment * window

    # Compute magnitude spectrum
    fft = np.fft.rfft(windowed_audio)
    magnitude = np.abs(fft)

    # Frequency bins
    freqs = np.linspace(0, sample_rate // 2, len(magnitude))

    # Calculate centroid
    if np.sum(magnitude) > 1e-10:
        centroid = np.sum(freqs * magnitude) / np.sum(magnitude)
    else:
        centroid = sample_rate // 4  # Default to quarter of sample rate

    return float(centroid)


def spectral_rolloff(audio: np.ndarray,
                    sample_rate: int = 44100,
                    rolloff_percent: float = 0.85) -> float:
    """
    Calculate spectral rolloff frequency

    The frequency below which a certain percentage of the total spectral
    energy is contained.

    Args:
        audio: Input audio signal
        sample_rate: Sample rate in Hz
        rolloff_percent: Percentage of energy for rolloff calculation (0-1)

    Returns:
        Rolloff frequency in Hz
    """
    if audio.ndim == 2:
        audio = np.mean(audio, axis=1)

    # Compute magnitude spectrum
    fft = np.fft.rfft(audio)
    magnitude = np.abs(fft) ** 2  # Power spectrum

    # Frequency bins
    freqs = np.linspace(0, sample_rate // 2, len(magnitude))

    # Calculate rolloff
    total_energy = np.sum(magnitude)
    if total_energy > 0:
        cumulative_energy = np.cumsum(magnitude)
        rolloff_threshold = rolloff_percent * total_energy
        rolloff_idx = np.where(cumulative_energy >= rolloff_threshold)[0]
        if len(rolloff_idx) > 0:
            return float(freqs[rolloff_idx[0]])

    return float(sample_rate // 2)  # Default to Nyquist frequency


def zero_crossing_rate(audio: np.ndarray) -> float:
    """
    Calculate zero crossing rate

    The rate at which the signal changes from positive to negative or back.
    Higher values indicate more high-frequency content.

    Args:
        audio: Input audio signal

    Returns:
        Zero crossing rate (0-1)
    """
    if audio.ndim == 2:
        audio = np.mean(audio, axis=1)

    # Count zero crossings
    zero_crossings = np.sum(np.diff(np.sign(audio)) != 0)
    return float(zero_crossings / (2 * len(audio)))


def crest_factor(audio: np.ndarray) -> float:
    """
    Calculate crest factor (peak-to-RMS ratio)

    Indicates the ratio between peak and average levels.
    Higher values indicate more dynamic content.

    Args:
        audio: Input audio signal

    Returns:
        Crest factor in dB
    """
    from ..basic import rms
    from .conversion import to_db

    peak = np.max(np.abs(audio))
    rms_value = rms(audio)

    if rms_value > 0:
        return to_db(peak / rms_value)
    else:
        return 0.0


def energy_profile(audio: np.ndarray, window_size: int = 1024) -> np.ndarray:
    """
    Calculate energy profile of audio signal

    Returns the energy envelope over time using overlapping windows.

    Args:
        audio: Input audio signal
        window_size: Size of analysis window in samples

    Returns:
        Array of energy values over time
    """
    if audio.ndim == 2:
        audio = np.mean(audio, axis=1)

    # Calculate energy in overlapping windows
    hop_size = window_size // 2
    energy_values = []

    for i in range(0, len(audio) - window_size, hop_size):
        window = audio[i:i + window_size]
        energy = np.sum(window ** 2)
        energy_values.append(energy)

    return np.array(energy_values)


def tempo_estimate(audio: np.ndarray, sample_rate: int = 44100) -> float:
    """
    Rough tempo estimation using onset detection

    Uses spectral flux to detect onsets and estimate tempo.
    Tries high-performance Rust implementation first with Python fallback.

    Args:
        audio: Input audio signal
        sample_rate: Sample rate in Hz

    Returns:
        Estimated tempo in BPM
    """
    # Try Rust implementation first (3-5x faster)
    try:
        from ...optimization.rust_integration import try_import_rust_module
        rust_dsp = try_import_rust_module()

        if rust_dsp is not None:
            # Convert stereo to mono if needed
            if audio.ndim == 2:
                mono_audio = np.mean(audio, axis=1)
            else:
                mono_audio = audio

            # Ensure float64 for Rust
            mono_audio = mono_audio.astype(np.float64)

            try:
                tempo_bpm = rust_dsp.detect_tempo(mono_audio, sample_rate)
                if 40 <= tempo_bpm <= 300:  # Sanity check
                    return float(tempo_bpm)
            except Exception as e:
                debug(f"Rust tempo detection failed, falling back to Python: {e}")
    except Exception as e:
        debug(f"Could not import Rust DSP module: {e}")

    # Python fallback implementation
    return _tempo_estimate_python(audio, sample_rate)


def _tempo_estimate_python(audio: np.ndarray, sample_rate: int = 44100) -> float:
    """
    Python fallback for tempo estimation using spectral flux.

    This is the original pure-Python implementation, used when Rust module
    is unavailable.
    """
    if audio.ndim == 2:
        audio = np.mean(audio, axis=1)

    # Simple onset detection using spectral flux
    window_size = 1024
    hop_size = 512

    # Calculate spectral flux
    flux_values = []
    prev_spectrum = None

    for i in range(0, len(audio) - window_size, hop_size):
        window = audio[i:i + window_size]
        spectrum = np.abs(np.fft.rfft(window))

        if prev_spectrum is not None:
            flux = np.sum(np.maximum(0, spectrum - prev_spectrum))
            flux_values.append(flux)

        prev_spectrum = spectrum

    if len(flux_values) < 2:
        return 120.0  # Default tempo

    # Find peaks in flux (rough onset detection)
    flux_array = np.array(flux_values)
    mean_flux = np.mean(flux_array)
    std_flux = np.std(flux_array)
    threshold = mean_flux + 0.5 * std_flux

    peaks = []
    for i in range(1, len(flux_array) - 1):
        if (flux_array[i] > flux_array[i-1] and
            flux_array[i] > flux_array[i+1] and
            flux_array[i] > threshold):
            peaks.append(i)

    if len(peaks) < 2:
        return 120.0  # Default tempo

    # Calculate average interval between peaks
    intervals = np.diff(peaks)
    if len(intervals) > 0:
        avg_interval = np.mean(intervals)
        # Convert to BPM
        time_per_hop = hop_size / sample_rate
        beat_interval = avg_interval * time_per_hop
        if beat_interval > 0:
            bpm = 60.0 / beat_interval
            # Constrain to reasonable range
            return float(np.clip(bpm, 60, 200))

    return 120.0  # Default tempo

"""
Audio Processing
~~~~~~~~~~~~~~~~

Audio validation and processing utilities

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""


import numpy as np

from ..utils.audio_validation import sanitize_audio
from ..utils.logging import Code, ModuleError, debug, warning


def validate_audio(audio_data: np.ndarray, sample_rate: int, file_type: str) -> tuple[np.ndarray, int]:
    """Validate loaded audio data"""

    # Check if audio is empty
    if audio_data.size == 0:
        raise ModuleError(f"{Code.ERROR_EMPTY_AUDIO}: No audio data found")

    # Check sample rate
    if sample_rate <= 0:
        raise ModuleError(f"{Code.ERROR_INVALID_SAMPLE_RATE}: {sample_rate}")

    # Sanitize NaN/Inf samples from corrupt source files (#3472). HybridProcessor
    # fails fast on non-finite input, but the chunked playback path streams
    # loader output directly — a single NaN would poison whole chunks and
    # downstream limiters would propagate it. Replace with silence and warn.
    # Must run BEFORE the amplitude checks below, otherwise np.max(np.abs(...))
    # on NaN returns NaN and the silence/clipping branches misfire.
    audio_data = sanitize_audio(audio_data, context=f"loaded {file_type} audio")

    if sample_rate < 8000:
        warning(f"Very low sample rate: {sample_rate} Hz")
    elif sample_rate > 192000:
        warning(f"Very high sample rate: {sample_rate} Hz")

    # Check audio length
    duration_seconds = len(audio_data) / sample_rate
    if duration_seconds < 1.0:
        warning(f"Very short audio: {duration_seconds:.2f} seconds")
    elif duration_seconds > 30 * 60:  # 30 minutes
        warning(f"Very long audio: {duration_seconds/60:.1f} minutes")

    # Check for silence
    max_amplitude = np.max(np.abs(audio_data))
    if max_amplitude < 1e-6:
        warning(f"Audio appears to be silent (peak: {max_amplitude:.2e})")

    # Check for clipping
    if max_amplitude >= 0.99:
        clipped_samples = np.sum(np.abs(audio_data) >= 0.99)
        clipping_percentage = (clipped_samples / audio_data.size) * 100
        if clipping_percentage > 0.1:
            warning(f"Audio may be clipped ({clipping_percentage:.2f}% of samples)")

    # Ensure proper data type
    if audio_data.dtype != np.float32 and audio_data.dtype != np.float64:
        audio_data = audio_data.astype(np.float32)
        debug(f"Converted audio to float32")

    return audio_data, sample_rate


def resample_audio(audio_data: np.ndarray, original_rate: int, target_rate: int) -> np.ndarray:
    """Resample audio to target sample rate"""
    if original_rate == target_rate:
        return audio_data

    try:
        import resampy
        debug(f"Resampling from {original_rate} Hz to {target_rate} Hz using resampy")

        input_dtype = audio_data.dtype  # Preserve caller's dtype (fixes #2227)
        if audio_data.ndim == 1:
            return np.asarray(resampy.resample(audio_data, original_rate, target_rate), dtype=input_dtype)
        else:
            # Resample each channel separately
            resampled_channels = []
            for channel in range(audio_data.shape[1]):
                resampled_channel = resampy.resample(
                    audio_data[:, channel], original_rate, target_rate
                )
                resampled_channels.append(resampled_channel)
            return np.column_stack(resampled_channels).astype(input_dtype, copy=False)

    except ImportError:
        # Fallback to simple linear interpolation (less quality but no dependency)
        warning("resampy not available, using simple interpolation")
        return simple_resample(audio_data, original_rate, target_rate)


def simple_resample(audio_data: np.ndarray, original_rate: int, target_rate: int) -> np.ndarray:
    """Simple resampling using linear interpolation.

    Output dtype matches the input dtype (fixes #2227).
    """
    input_dtype = audio_data.dtype
    ratio = target_rate / original_rate
    new_length = int(len(audio_data) * ratio)

    if audio_data.ndim == 1:
        # Mono audio
        old_indices = np.linspace(0, len(audio_data) - 1, new_length)
        return np.asarray(np.interp(old_indices, np.arange(len(audio_data)), audio_data), dtype=input_dtype)
    else:
        # Multi-channel audio
        resampled_channels = []
        for channel in range(audio_data.shape[1]):
            old_indices = np.linspace(0, len(audio_data) - 1, new_length)
            resampled_channel = np.interp(
                old_indices, np.arange(len(audio_data)), audio_data[:, channel]
            )
            resampled_channels.append(resampled_channel)
        return np.column_stack(resampled_channels).astype(input_dtype, copy=False)


def downmix_to_stereo(audio_data: np.ndarray) -> np.ndarray:
    """
    #3743 — downmix multi-channel audio to stereo using ITU-R BS.775.

    The two native Python loader paths (`loader.py` for WAV and
    `soundfile_loader.py`) used to do `audio_data[:, :2].copy()` for
    any input with more than two channels — a hard truncation that
    drops Center (vocals/dialogue), LFE, and surround content. The
    FFmpeg path (#3672) already applies the standard matrix via `-ac 2`;
    this function keeps the native paths consistent with that behavior.

    Mapping (BS.775-3):
        L_out = L + 0.707·C + 0.707·Ls
        R_out = R + 0.707·C + 0.707·Rs
    LFE is omitted from the stereo image (the standard mixes it ±10 dB
    into either channel optionally; we treat it as discardable for a
    music-master downmix). Channels past the canonical surround layout
    are summed equally into both outputs so we don't lose energy from
    atypical layouts (e.g. 7.1 side channels).

    After downmixing the matrix sum can exceed ±1.0, so the result is
    rescaled so its peak ≤ the original input peak (no surprise
    clipping introduced by the downmix). The input dtype is preserved.

    Args:
        audio_data: 2-D array shaped (samples, channels). Mono / stereo
                    inputs pass through unchanged for caller convenience.

    Returns:
        Stereo 2-D array shaped (samples, 2), same dtype as input.
    """
    if audio_data.ndim != 2:
        raise ValueError(
            f"downmix_to_stereo expects 2-D input; got ndim={audio_data.ndim}"
        )
    n_channels = audio_data.shape[1]
    if n_channels == 2:
        return audio_data.copy()
    if n_channels < 2:
        return np.column_stack([audio_data[:, 0], audio_data[:, 0]])

    input_dtype = audio_data.dtype
    # Promote to float32 for the matrix sum so int sources don't
    # overflow; cast back at the end.
    audio = audio_data.astype(np.float32, copy=False)

    L = audio[:, 0]
    R = audio[:, 1]
    C = audio[:, 2] if n_channels >= 3 else None

    # Surround channels: 5.1 / 7.1 conventions vary; treat indices 4 and
    # 5 as Ls/Rs when present (typical WAV WAVEFORMATEXTENSIBLE: L, R,
    # C, LFE, Ls, Rs, [Lsr, Rsr]). LFE at index 3 is dropped.
    Ls = audio[:, 4] if n_channels >= 5 else None
    Rs = audio[:, 5] if n_channels >= 6 else None

    _SQ = np.float32(0.7071067811865476)  # 1/sqrt(2)
    L_out = L.copy()
    R_out = R.copy()
    if C is not None:
        L_out += _SQ * C
        R_out += _SQ * C
    if Ls is not None:
        L_out += _SQ * Ls
    if Rs is not None:
        R_out += _SQ * Rs

    # Side / rear channels beyond Rs (index 5) get summed equally into
    # both outputs — preserves their energy without inventing a
    # placement decision.
    if n_channels > 6:
        extra = audio[:, 6:].sum(axis=1)
        L_out += _SQ * extra
        R_out += _SQ * extra

    stereo = np.column_stack([L_out, R_out])

    # Renormalize so the downmix peak doesn't exceed the input peak —
    # prevents surprise clipping when the matrix sum pushes a sample
    # above ±1.0 (or above the int range for integer sources).
    input_peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    out_peak = float(np.max(np.abs(stereo))) if stereo.size else 0.0
    if out_peak > 0.0 and out_peak > input_peak > 0.0:
        stereo = stereo * np.float32(input_peak / out_peak)

    return stereo.astype(input_dtype, copy=False)

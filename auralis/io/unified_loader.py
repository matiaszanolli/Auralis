"""
Unified Audio Loader
~~~~~~~~~~~~~~~~~~~~

Enhanced audio file loading supporting multiple formats and processing modes

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)

Unified audio loading system combining Matchering and Auralis capabilities
"""

import json
import subprocess
import threading
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf

from ..utils.logging import Code, ModuleError, debug, info, warning
from .formats import FFMPEG_FORMATS, SUPPORTED_FORMATS
from .loaders import (
    FFPROBE_TIMEOUT_S,
    SUBPROCESS_TEXT_KWARGS,
    check_ffprobe,
    ffprobe_command,
    load_with_ffmpeg,
    load_with_soundfile,
    redact_subprocess_output,
)
from .processing import peak_amplitude, resample_audio, validate_audio

from .audio_probe import (  # noqa: F401  (pre-split import paths, #6273)
    _get_info_with_ffprobe,
    _get_info_with_soundfile,
    _reject_oversize_probe,
    get_audio_info,
)

# SUPPORTED_FORMATS / FFMPEG_FORMATS live in auralis.io.formats (the single
# source of truth) and are re-exported here for existing importers.


def load_audio(
    file_path: str | Path,
    file_type: str = "audio",
    temp_folder: str | None = None,
    target_sample_rate: int | None = None,
    force_stereo: bool = False,
    normalize_on_load: bool = False,
    cancel_event: "threading.Event | None" = None,
) -> tuple[np.ndarray, int]:
    """
    Load an audio file with format detection and conversion

    Args:
        file_path: Path to the audio file
        file_type: Type of file being loaded ("target", "reference", or "audio")
        temp_folder: Temporary folder for FFmpeg conversions
        target_sample_rate: Resample to this sample rate (optional)
        force_stereo: Convert mono to stereo if True
        normalize_on_load: Normalize audio on loading
        cancel_event: Optional cooperative cancellation token. When set from
            another thread during an FFmpeg decode, the FFmpeg child is
            terminated promptly and ``asyncio.CancelledError`` is raised (#4496).
            Ignored for natively-decodable formats (no subprocess to cancel).

    Returns:
        tuple: (audio_data, sample_rate)

    Raises:
        ModuleError: If file cannot be loaded or is invalid
    """
    file_path = Path(file_path)

    # Absolute path at DEBUG only (#4366) -- also covers every ModuleError
    # raised below in this function: none of them repeat the path in their
    # own string form, since it's already on record here (#4806).
    debug(f"Loading {file_type} audio file: {file_path}")

    # Validate file exists
    if not file_path.exists():
        raise ModuleError(Code.ERROR_FILE_NOT_FOUND, path=str(file_path))

    # Check file size
    file_size = file_path.stat().st_size
    if file_size == 0:
        raise ModuleError(Code.ERROR_EMPTY_FILE, path=str(file_path))

    debug(f"File size: {file_size / (1024*1024):.2f} MB")

    # Get file extension
    file_ext = file_path.suffix.lower()

    if file_ext not in SUPPORTED_FORMATS:
        raise ModuleError(f"{Code.ERROR_UNSUPPORTED_FORMAT}: {file_ext}")

    info(f"Detected format: {SUPPORTED_FORMATS[file_ext]}")

    # Load audio based on format
    if file_ext in FFMPEG_FORMATS:
        audio_data, sample_rate = load_with_ffmpeg(
            file_path, temp_folder, cancel_event=cancel_event
        )
    else:
        audio_data, sample_rate = load_with_soundfile(file_path)

    # #3671: enforce the same duration ceiling that loader.py applies for
    # FFmpeg-routed formats. load_with_ffmpeg now also enforces it pre-decode
    # (#3671 again, in ffmpeg_loader.py), but this post-decode guard also
    # covers the soundfile path (long WAV/FLAC) and any future caller of
    # load_audio() that bypasses the FFmpeg pipeline.
    from auralis.io.loader import MAX_DURATION_SECONDS, oversize_decode_detail
    duration = len(audio_data) / max(sample_rate, 1)
    if duration > MAX_DURATION_SECONDS:
        raise ModuleError(
            f"{Code.ERROR_CORRUPTED}: Audio file exceeds maximum duration "
            f"({duration:.0f}s > {MAX_DURATION_SECONDS}s)",
            path=str(file_path),
        )
    # Backstop for the same blind spot (#4875). The buffer is already resident
    # here, so this cannot prevent that allocation — but it still stops the
    # downstream validate/sanitize/resample copies, each of which multiplies
    # an already-oversized buffer, and it covers any caller reaching
    # load_audio() without passing one of the pre-decode guards.
    channels = audio_data.shape[1] if audio_data.ndim > 1 else 1
    detail = oversize_decode_detail(duration, sample_rate, channels)
    if detail:
        raise ModuleError(f"{Code.ERROR_CORRUPTED}: {detail}", path=str(file_path))

    # Validate audio data
    audio_data, sample_rate = validate_audio(audio_data, sample_rate, file_type)

    # Apply post-processing options
    if target_sample_rate and target_sample_rate != sample_rate:
        # Only downsample, never upsample (resampling reduces quality)
        if target_sample_rate < sample_rate:
            original_sr = sample_rate
            audio_data = resample_audio(audio_data, sample_rate, target_sample_rate)
            sample_rate = target_sample_rate
            debug(f"Downsampled from {original_sr} Hz to {target_sample_rate} Hz")
        else:
            debug(f"Skipping upsample: target {target_sample_rate} Hz >= current {sample_rate} Hz (would degrade quality)")

    if force_stereo and audio_data.ndim == 1:
        audio_data = np.column_stack([audio_data, audio_data])
        debug("Converted mono to stereo")

    if normalize_on_load:
        # #3749: dtype-preserving normalize. A numpy-scalar peak (float64
        # even on float32 input) can silently promote under older NumPy
        # promotion rules, so `peak` is cast to the input dtype defensively —
        # same drift class as #3658 / #3659 / #3744 / #3752.
        # peak_amplitude also avoids the full-size np.abs temporary (#5591).
        peak = peak_amplitude(audio_data)
        if peak > 0:
            peak_typed = audio_data.dtype.type(peak)
            audio_data = audio_data / peak_typed * audio_data.dtype.type(0.98)
            debug("Normalized audio on load")

    info(f"Successfully loaded {file_type}: {audio_data.shape[0]} samples, "
         f"{sample_rate} Hz, {audio_data.ndim} channels")

    return audio_data, sample_rate



def load_reference(file_path: str | Path, **kwargs: Any) -> tuple[np.ndarray, int]:
    """Load reference audio file"""
    return load_audio(file_path, file_type="reference", **kwargs)


def is_audio_file(file_path: str | Path) -> bool:
    """Check if file is a supported audio format"""
    return Path(file_path).suffix.lower() in SUPPORTED_FORMATS


def get_supported_formats() -> list[str]:
    """Get list of supported audio formats"""
    return list(SUPPORTED_FORMATS.keys())
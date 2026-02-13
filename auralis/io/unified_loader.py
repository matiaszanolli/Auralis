"""
Unified Audio Loader
~~~~~~~~~~~~~~~~~~~~

Enhanced audio file loading supporting multiple formats and processing modes

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.

Unified audio loading system combining Matchering and Auralis capabilities
"""

import subprocess
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf

from ..utils.logging import Code, ModuleError, debug, info, warning
from .loaders import check_ffmpeg, load_with_ffmpeg, load_with_soundfile
from .processing import resample_audio, validate_audio

# Supported audio formats
SUPPORTED_FORMATS = {
    '.wav': 'WAV',
    '.flac': 'FLAC',
    '.mp3': 'MP3',
    '.m4a': 'M4A',
    '.aac': 'AAC',
    '.ogg': 'OGG',
    '.wma': 'WMA'
}

# Formats that require FFmpeg conversion
FFMPEG_FORMATS = {'.mp3', '.m4a', '.aac', '.ogg', '.wma'}


def load_audio(
    file_path: str | Path,
    file_type: str = "audio",
    temp_folder: str | None = None,
    target_sample_rate: int | None = None,
    force_stereo: bool = False,
    normalize_on_load: bool = False
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

    Returns:
        tuple: (audio_data, sample_rate)

    Raises:
        ModuleError: If file cannot be loaded or is invalid
    """
    file_path = Path(file_path)

    debug(f"Loading {file_type} audio file: {file_path}")

    # Validate file exists
    if not file_path.exists():
        raise ModuleError(f"{Code.ERROR_FILE_NOT_FOUND}: {file_path}")

    # Check file size
    file_size = file_path.stat().st_size
    if file_size == 0:
        raise ModuleError(f"{Code.ERROR_EMPTY_FILE}: {file_path}")  # type: ignore[attr-defined]

    debug(f"File size: {file_size / (1024*1024):.2f} MB")

    # Get file extension
    file_ext = file_path.suffix.lower()

    if file_ext not in SUPPORTED_FORMATS:
        raise ModuleError(f"{Code.ERROR_UNSUPPORTED_FORMAT}: {file_ext}")  # type: ignore[attr-defined]

    info(f"Detected format: {SUPPORTED_FORMATS[file_ext]}")

    # Load audio based on format
    if file_ext in FFMPEG_FORMATS:
        audio_data, sample_rate = load_with_ffmpeg(file_path, temp_folder)
    else:
        audio_data, sample_rate = load_with_soundfile(file_path)

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
        peak = np.max(np.abs(audio_data))
        if peak > 0:
            audio_data = audio_data / peak * 0.98
            debug("Normalized audio on load")

    info(f"Successfully loaded {file_type}: {audio_data.shape[0]} samples, "
         f"{sample_rate} Hz, {audio_data.ndim} channels")

    return audio_data, sample_rate


def get_audio_info(file_path: str | Path) -> dict[str, Any]:
    """
    Get information about an audio file without fully loading it

    Args:
        file_path: Path to the audio file

    Returns:
        Dictionary containing audio file information
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise ModuleError(f"{Code.ERROR_FILE_NOT_FOUND}: {file_path}")

    file_ext = file_path.suffix.lower()
    file_size = file_path.stat().st_size

    info_dict = {
        'file_path': str(file_path),
        'file_size_bytes': file_size,
        'file_size_mb': file_size / (1024 * 1024),
        'format': SUPPORTED_FORMATS.get(file_ext, 'Unknown'),
        'extension': file_ext
    }

    try:
        if file_ext in FFMPEG_FORMATS:
            # Use FFprobe for non-native formats
            audio_info = _get_info_with_ffprobe(file_path)
        else:
            # Use soundfile for native formats
            audio_info = _get_info_with_soundfile(file_path)

        info_dict.update(audio_info)

    except Exception as e:
        info_dict['error'] = str(e)
        warning(f"Could not get audio info for {file_path}: {e}")

    return info_dict


def _get_info_with_soundfile(file_path: Path) -> dict[str, Any]:
    """Get audio info using soundfile"""
    info = sf.info(str(file_path))

    return {
        'sample_rate': info.samplerate,
        'channels': info.channels,
        'frames': info.frames,
        'duration_seconds': info.duration,
        'format': info.format,
        'subtype': info.subtype
    }


def _get_info_with_ffprobe(file_path: Path) -> dict[str, Any]:
    """Get audio info using FFprobe"""
    if not check_ffmpeg():
        raise ModuleError(f"{Code.ERROR_FFMPEG_NOT_FOUND}: FFprobe required")

    try:
        ffprobe_cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            str(file_path)
        ]

        result = subprocess.run(
            ffprobe_cmd,
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            raise ModuleError(f"FFprobe failed: {result.stderr}")

        import json
        probe_data = json.loads(result.stdout)

        # Find audio stream
        audio_stream = None
        for stream in probe_data.get('streams', []):
            if stream.get('codec_type') == 'audio':
                audio_stream = stream
                break

        if not audio_stream:
            raise ModuleError("No audio stream found")

        duration = float(probe_data.get('format', {}).get('duration', 0))

        return {
            'sample_rate': int(audio_stream.get('sample_rate', 0)),
            'channels': int(audio_stream.get('channels', 0)),
            'duration_seconds': duration,
            'codec': audio_stream.get('codec_name', 'Unknown'),
            'bit_rate': int(audio_stream.get('bit_rate', 0))
        }

    except subprocess.TimeoutExpired:
        raise ModuleError("FFprobe timed out")
    except json.JSONDecodeError:
        raise ModuleError("Invalid FFprobe output")


def batch_load_info(file_paths: list[str | Path]) -> list[dict[str, Any]]:
    """
    Get information for multiple audio files

    Args:
        file_paths: List of file paths

    Returns:
        List of audio info dictionaries
    """
    info_list = []

    for file_path in file_paths:
        try:
            info_dict = get_audio_info(file_path)
            info_list.append(info_dict)
        except Exception as e:
            info_list.append({
                'file_path': str(file_path),
                'error': str(e)
            })

    return info_list


# Convenience functions
def load_target(file_path: str | Path, **kwargs: Any) -> tuple[np.ndarray, int]:
    """Load target audio file"""
    return load_audio(file_path, file_type="target", **kwargs)


def load_reference(file_path: str | Path, **kwargs: Any) -> tuple[np.ndarray, int]:
    """Load reference audio file"""
    return load_audio(file_path, file_type="reference", **kwargs)


def is_audio_file(file_path: str | Path) -> bool:
    """Check if file is a supported audio format"""
    return Path(file_path).suffix.lower() in SUPPORTED_FORMATS


def get_supported_formats() -> list[str]:
    """Get list of supported audio formats"""
    return list(SUPPORTED_FORMATS.keys())
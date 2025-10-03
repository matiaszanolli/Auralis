# -*- coding: utf-8 -*-

"""
Unified Audio Loader
~~~~~~~~~~~~~~~~~~~~

Enhanced audio file loading supporting multiple formats and processing modes

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.

Unified audio loading system combining Matchering and Auralis capabilities
"""

import os
import numpy as np
import soundfile as sf
import subprocess
import tempfile
from pathlib import Path
from typing import Tuple, Optional, Union, List

from ..utils.logging import debug, info, warning, Code, ModuleError


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
    file_path: Union[str, Path],
    file_type: str = "audio",
    temp_folder: Optional[str] = None,
    target_sample_rate: Optional[int] = None,
    force_stereo: bool = False,
    normalize_on_load: bool = False
) -> Tuple[np.ndarray, int]:
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
        raise ModuleError(f"{Code.ERROR_EMPTY_FILE}: {file_path}")

    debug(f"File size: {file_size / (1024*1024):.2f} MB")

    # Get file extension
    file_ext = file_path.suffix.lower()

    if file_ext not in SUPPORTED_FORMATS:
        raise ModuleError(f"{Code.ERROR_UNSUPPORTED_FORMAT}: {file_ext}")

    info(f"Detected format: {SUPPORTED_FORMATS[file_ext]}")

    # Load audio based on format
    if file_ext in FFMPEG_FORMATS:
        audio_data, sample_rate = _load_with_ffmpeg(file_path, temp_folder)
    else:
        audio_data, sample_rate = _load_with_soundfile(file_path)

    # Validate audio data
    audio_data, sample_rate = _validate_audio(audio_data, sample_rate, file_type)

    # Apply post-processing options
    if target_sample_rate and target_sample_rate != sample_rate:
        audio_data = _resample_audio(audio_data, sample_rate, target_sample_rate)
        sample_rate = target_sample_rate
        debug(f"Resampled to {target_sample_rate} Hz")

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


def _load_with_soundfile(file_path: Path) -> Tuple[np.ndarray, int]:
    """Load audio using soundfile library"""
    try:
        audio_data, sample_rate = sf.read(str(file_path), always_2d=False)

        # Ensure proper shape
        if audio_data.ndim == 1:
            # Mono audio
            pass
        elif audio_data.ndim == 2:
            # Multi-channel audio
            if audio_data.shape[1] > 2:
                # Convert to stereo by taking first two channels
                audio_data = audio_data[:, :2]
                warning(f"Converted {audio_data.shape[1]} channels to stereo")
        else:
            raise ModuleError(f"{Code.ERROR_INVALID_AUDIO}: Invalid audio dimensions")

        return audio_data, int(sample_rate)

    except Exception as e:
        raise ModuleError(f"{Code.ERROR_LOADING}: {str(e)}")


def _load_with_ffmpeg(file_path: Path, temp_folder: Optional[str] = None) -> Tuple[np.ndarray, int]:
    """Load audio using FFmpeg conversion to WAV"""

    # Check if FFmpeg is available
    if not _check_ffmpeg():
        raise ModuleError(f"{Code.ERROR_FFMPEG_NOT_FOUND}: FFmpeg required for {file_path.suffix}")

    # Create temporary WAV file
    if temp_folder:
        temp_dir = Path(temp_folder)
        temp_dir.mkdir(exist_ok=True)
    else:
        temp_dir = Path(tempfile.gettempdir())

    temp_wav = temp_dir / f"auralis_temp_{os.getpid()}_{file_path.stem}.wav"

    try:
        # Convert to WAV using FFmpeg
        debug(f"Converting {file_path} to WAV using FFmpeg")

        ffmpeg_cmd = [
            'ffmpeg',
            '-i', str(file_path),
            '-acodec', 'pcm_s16le',  # 16-bit PCM
            '-ar', '44100',          # 44.1 kHz
            '-ac', '2',              # Stereo
            '-y',                    # Overwrite output
            str(temp_wav)
        ]

        result = subprocess.run(
            ffmpeg_cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )

        if result.returncode != 0:
            raise ModuleError(f"{Code.ERROR_FFMPEG_CONVERSION}: {result.stderr}")

        # Load the converted WAV file
        audio_data, sample_rate = _load_with_soundfile(temp_wav)

        return audio_data, sample_rate

    except subprocess.TimeoutExpired:
        raise ModuleError(f"{Code.ERROR_FFMPEG_TIMEOUT}: Conversion timed out")
    except Exception as e:
        raise ModuleError(f"{Code.ERROR_FFMPEG_CONVERSION}: {str(e)}")
    finally:
        # Clean up temporary file
        if temp_wav.exists():
            try:
                temp_wav.unlink()
                debug(f"Cleaned up temporary file: {temp_wav}")
            except Exception:
                warning(f"Failed to clean up temporary file: {temp_wav}")


def _check_ffmpeg() -> bool:
    """Check if FFmpeg is available"""
    try:
        result = subprocess.run(
            ['ffmpeg', '-version'],
            capture_output=True,
            timeout=10
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _validate_audio(audio_data: np.ndarray, sample_rate: int, file_type: str) -> Tuple[np.ndarray, int]:
    """Validate loaded audio data"""

    # Check if audio is empty
    if audio_data.size == 0:
        raise ModuleError(f"{Code.ERROR_EMPTY_AUDIO}: No audio data found")

    # Check sample rate
    if sample_rate <= 0:
        raise ModuleError(f"{Code.ERROR_INVALID_SAMPLE_RATE}: {sample_rate}")

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


def _resample_audio(audio_data: np.ndarray, original_rate: int, target_rate: int) -> np.ndarray:
    """Resample audio to target sample rate"""
    if original_rate == target_rate:
        return audio_data

    try:
        import resampy
        debug(f"Resampling from {original_rate} Hz to {target_rate} Hz using resampy")

        if audio_data.ndim == 1:
            return resampy.resample(audio_data, original_rate, target_rate)
        else:
            # Resample each channel separately
            resampled_channels = []
            for channel in range(audio_data.shape[1]):
                resampled_channel = resampy.resample(
                    audio_data[:, channel], original_rate, target_rate
                )
                resampled_channels.append(resampled_channel)
            return np.column_stack(resampled_channels)

    except ImportError:
        # Fallback to simple linear interpolation (less quality but no dependency)
        warning("resampy not available, using simple interpolation")
        return _simple_resample(audio_data, original_rate, target_rate)


def _simple_resample(audio_data: np.ndarray, original_rate: int, target_rate: int) -> np.ndarray:
    """Simple resampling using linear interpolation"""
    ratio = target_rate / original_rate
    new_length = int(len(audio_data) * ratio)

    if audio_data.ndim == 1:
        # Mono audio
        old_indices = np.linspace(0, len(audio_data) - 1, new_length)
        return np.interp(old_indices, np.arange(len(audio_data)), audio_data)
    else:
        # Multi-channel audio
        resampled_channels = []
        for channel in range(audio_data.shape[1]):
            old_indices = np.linspace(0, len(audio_data) - 1, new_length)
            resampled_channel = np.interp(
                old_indices, np.arange(len(audio_data)), audio_data[:, channel]
            )
            resampled_channels.append(resampled_channel)
        return np.column_stack(resampled_channels)


def get_audio_info(file_path: Union[str, Path]) -> dict:
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


def _get_info_with_soundfile(file_path: Path) -> dict:
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


def _get_info_with_ffprobe(file_path: Path) -> dict:
    """Get audio info using FFprobe"""
    if not _check_ffmpeg():
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


def batch_load_info(file_paths: List[Union[str, Path]]) -> List[dict]:
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
def load_target(file_path: Union[str, Path], **kwargs) -> Tuple[np.ndarray, int]:
    """Load target audio file"""
    return load_audio(file_path, file_type="target", **kwargs)


def load_reference(file_path: Union[str, Path], **kwargs) -> Tuple[np.ndarray, int]:
    """Load reference audio file"""
    return load_audio(file_path, file_type="reference", **kwargs)


def is_audio_file(file_path: Union[str, Path]) -> bool:
    """Check if file is a supported audio format"""
    return Path(file_path).suffix.lower() in SUPPORTED_FORMATS


def get_supported_formats() -> List[str]:
    """Get list of supported audio formats"""
    return list(SUPPORTED_FORMATS.keys())
"""
FFmpeg Loader
~~~~~~~~~~~~~

Audio loading using FFmpeg for MP3/M4A/AAC/OGG/WMA

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import os
import subprocess
import tempfile
from pathlib import Path

import numpy as np

from ...utils.logging import Code, ModuleError, debug, warning
from .soundfile_loader import load_with_soundfile


def check_ffmpeg() -> bool:
    """Check if FFmpeg is available"""
    try:
        result = subprocess.run(
            ['ffmpeg', '-version'],
            capture_output=True,
            timeout=10
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _probe_audio(file_path: Path) -> dict:
    """
    Probe audio file with ffprobe.

    Returns a dict with keys:
        duration    float | None  – total duration in seconds
        sample_rate int  | None  – native sample rate (Hz)
        channels    int  | None  – number of channels
    """
    result_dict: dict = {'duration': None, 'sample_rate': None, 'channels': None}
    try:
        import json

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
            warning(f"ffprobe failed: {result.stderr}")
            return result_dict

        probe_data = json.loads(result.stdout)

        duration = probe_data.get('format', {}).get('duration')
        if duration:
            result_dict['duration'] = float(duration)

        for stream in probe_data.get('streams', []):
            if stream.get('codec_type') == 'audio':
                sr = stream.get('sample_rate')
                ch = stream.get('channels')
                if sr:
                    result_dict['sample_rate'] = int(sr)
                if ch:
                    result_dict['channels'] = int(ch)
                break

    except (subprocess.TimeoutExpired, json.JSONDecodeError, ValueError, Exception) as e:
        warning(f"Could not probe audio with ffprobe: {e}")

    return result_dict


def load_with_ffmpeg(file_path: Path, temp_folder: str | None = None) -> tuple[np.ndarray, int]:
    """Load audio using FFmpeg conversion to WAV"""

    # Check if FFmpeg is available
    if not check_ffmpeg():
        raise ModuleError(f"{Code.ERROR_FFMPEG_NOT_FOUND}: FFmpeg required for {file_path.suffix}")

    # Ensure the input path is a regular file and not a URL/protocol
    file_path = Path(file_path)
    if not file_path.exists() or not file_path.is_file():
        raise ModuleError(f"{Code.ERROR_FILE_NOT_FOUND}: {file_path}")
    # Basic guard against ffmpeg protocol URLs (e.g., http://, pipe:, etc.)
    file_path_str = str(file_path)
    if "://" in file_path_str:
        raise ModuleError(f"{Code.ERROR_UNSUPPORTED_FORMAT}: URL/protocol inputs are not allowed ({file_path_str})")

    # Probe source format: duration, sample rate, and channel count
    probe = _probe_audio(file_path)
    expected_duration = probe['duration']
    source_sample_rate = probe['sample_rate'] or 44100
    source_channels = probe['channels'] or 2
    if probe['sample_rate'] is None or probe['channels'] is None:
        warning(f"Could not probe sample rate/channels for {file_path}; defaulting to {source_sample_rate} Hz / {source_channels} ch")

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
            '-i', file_path_str,
            '-acodec', 'pcm_s16le',            # 16-bit PCM
            '-ar', str(source_sample_rate),    # Preserve native sample rate
            '-ac', str(source_channels),       # Preserve native channel count
            '-y',                              # Overwrite output
            str(temp_wav)
        ]
        debug(f"FFmpeg: converting at {source_sample_rate} Hz, {source_channels} ch")

        result = subprocess.run(
            ffmpeg_cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )

        if result.returncode != 0:
            raise ModuleError(f"{Code.ERROR_FFMPEG_CONVERSION}: {result.stderr}")

        # Load the converted WAV file
        audio_data, sample_rate = load_with_soundfile(temp_wav)

        # Validate duration against original file metadata
        if expected_duration is not None:
            actual_duration = len(audio_data) / sample_rate
            duration_percentage = (actual_duration / expected_duration) * 100

            if duration_percentage < 10:
                # Severely truncated - raise error
                raise ModuleError(
                    f"{Code.ERROR_TRUNCATED_FILE}: File is severely truncated "
                    f"({duration_percentage:.1f}% complete, expected {expected_duration:.2f}s, got {actual_duration:.2f}s)"
                )
            elif duration_percentage < 90:
                # Moderately truncated - log warning
                warning(
                    f"{Code.WARNING_TRUNCATED_FILE}: File appears truncated "
                    f"({duration_percentage:.1f}% complete, expected {expected_duration:.2f}s, got {actual_duration:.2f}s)"
                )

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

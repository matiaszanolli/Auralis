# -*- coding: utf-8 -*-

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
from typing import Optional, Tuple

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


def load_with_ffmpeg(file_path: Path, temp_folder: Optional[str] = None) -> Tuple[np.ndarray, int]:
    """Load audio using FFmpeg conversion to WAV"""

    # Check if FFmpeg is available
    if not check_ffmpeg():
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
        audio_data, sample_rate = load_with_soundfile(temp_wav)

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

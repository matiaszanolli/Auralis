"""
Auralis Audio Loader
~~~~~~~~~~~~~~~~~~~~

Audio file loading and validation

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.

Refactored from Matchering 2.0 by Sergree and contributors
"""


from pathlib import Path

import numpy as np
import soundfile as sf

from ..utils.logging import debug, info, warning
from .loaders import load_with_ffmpeg
from .unified_loader import FFMPEG_FORMATS


def load(file_path: str, file_type: str = "audio") -> tuple[np.ndarray, int]:
    """
    Load an audio file

    Args:
        file_path: Path to the audio file
        file_type: Type of file being loaded ("target", "reference", or "audio")

    Returns:
        tuple: (audio_data, sample_rate)
    """
    debug(f"Loading {file_type} file: {file_path}")

    try:
        # Route FFmpeg-required formats (M4A, AAC, WMA, OPUS, MP3, OGG)
        # through FFmpeg; use SoundFile for natively supported formats
        file_ext = Path(file_path).suffix.lower()
        if file_ext in FFMPEG_FORMATS:
            audio_data, sample_rate = load_with_ffmpeg(Path(file_path))
        else:
            file_info = sf.info(file_path)
            audio_data, sample_rate = sf.read(file_path, dtype=np.float32, always_2d=True)
            if len(audio_data) < file_info.frames:
                warning(
                    f"Truncated audio file '{file_path}': "
                    f"expected {file_info.frames} frames, got {len(audio_data)}"
                )

        # Ensure float32
        if audio_data.dtype != np.float32:
            audio_data = audio_data.astype(np.float32)

        # Ensure stereo (2D)
        if audio_data.ndim == 1:
            # Mono 1D → stereo 2D
            audio_data = np.column_stack([audio_data, audio_data])
        elif audio_data.shape[1] == 1:
            # Mono 2D → stereo 2D
            audio_data = np.column_stack([audio_data[:, 0], audio_data[:, 0]])
        elif audio_data.shape[1] > 2:
            # Multi-channel → stereo (take first two channels)
            audio_data = audio_data[:, :2].copy()

        info(f"Loaded {file_type}: {audio_data.shape[0]} samples, {sample_rate} Hz")
        return audio_data, sample_rate

    except Exception as e:
        raise RuntimeError(f"Failed to load {file_type} file '{file_path}': {e}")
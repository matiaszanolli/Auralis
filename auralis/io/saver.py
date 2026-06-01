"""
Auralis Audio Saver
~~~~~~~~~~~~~~~~~~~

Audio file saving and export

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.

Refactored from Matchering 2.0 by Sergree and contributors
"""

import numpy as np
import soundfile as sf

from ..utils.logging import debug, info


def save(file_path: str, audio_data: np.ndarray, sample_rate: int, subtype: str = 'PCM_16') -> None:
    """
    Save audio data to file

    Args:
        file_path: Output file path
        audio_data: Audio data to save
        sample_rate: Sample rate for output
        subtype: Audio format subtype
    """
    debug(f"Saving audio to: {file_path} ({subtype}, {sample_rate} Hz)")

    try:
        # Ensure audio is in the correct format
        if audio_data.dtype != np.float32:
            audio_data = audio_data.astype(np.float32)

        # Clamp to the PCM-valid range before encoding. libsndfile clamps
        # out-of-range PCM samples in current builds, but historically
        # wrapped on some. wav_encoder.py already clips defensively; this
        # matches the project's audio invariants and makes encode-boundary
        # clipping deterministic across libsndfile builds (#3471).
        audio_data = np.clip(audio_data, -1.0, 1.0)

        # Save the audio file
        sf.write(file_path, audio_data, sample_rate, subtype=subtype)

        info(f"Saved: {file_path} ({audio_data.shape[0]} samples)")

    except Exception as e:
        raise RuntimeError(f"Failed to save audio to '{file_path}': {e}")
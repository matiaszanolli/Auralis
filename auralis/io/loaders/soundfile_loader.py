"""
Soundfile Loader
~~~~~~~~~~~~~~~

Audio loading using soundfile library for WAV/FLAC

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from pathlib import Path

import numpy as np
import soundfile as sf

from ...utils.logging import Code, ModuleError, warning


def load_with_soundfile(file_path: Path) -> tuple[np.ndarray, int]:
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

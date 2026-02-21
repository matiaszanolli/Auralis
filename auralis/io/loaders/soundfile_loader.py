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
        # Get expected frame count from file metadata
        info = sf.info(str(file_path))
        expected_frames = info.frames

        # Load audio data
        audio_data, sample_rate = sf.read(str(file_path), always_2d=False)

        # Validate frame count (detect truncated files)
        actual_frames = len(audio_data)
        if actual_frames < expected_frames:
            frame_percentage = (actual_frames / expected_frames) * 100
            missing_frames = expected_frames - actual_frames
            missing_duration = missing_frames / sample_rate

            if frame_percentage < 10:
                # Severely truncated - raise error
                raise ModuleError(
                    f"{Code.ERROR_TRUNCATED_FILE}: File is severely truncated "
                    f"({frame_percentage:.1f}% complete, missing {missing_duration:.2f}s)"
                )
            elif frame_percentage < 90:
                # Moderately truncated - log warning
                warning(
                    f"{Code.WARNING_TRUNCATED_FILE}: File appears truncated "
                    f"({frame_percentage:.1f}% complete, missing {missing_duration:.2f}s)"
                )

        # Ensure proper shape
        if audio_data.ndim == 1:
            # Mono audio
            pass
        elif audio_data.ndim == 2:
            # Multi-channel audio
            if audio_data.shape[1] > 2:
                # Convert to stereo by taking first two channels
                original_channels = audio_data.shape[1]
                audio_data = audio_data[:, :2]
                warning(f"Converted {original_channels} channels to stereo")
        else:
            raise ModuleError(f"{Code.ERROR_INVALID_AUDIO}: Invalid audio dimensions")

        return audio_data, int(sample_rate)

    except ModuleError:
        # Re-raise our own errors
        raise
    except Exception as e:
        raise ModuleError(f"{Code.ERROR_LOADING}: {str(e)}")

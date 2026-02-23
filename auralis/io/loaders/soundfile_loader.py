"""
Soundfile Loader
~~~~~~~~~~~~~~~

Audio loading using soundfile library for WAV/FLAC

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import struct
from pathlib import Path

import numpy as np
import soundfile as sf

from ...utils.logging import Code, ModuleError, warning


def _get_wav_declared_size(file_path: Path) -> int | None:
    """Read WAV RIFF header to get declared file size.

    Returns the declared total file size, or None if not a valid WAV header.
    libsndfile auto-adjusts frame counts to the actual data available,
    so we must inspect the raw header to detect truncation.
    """
    try:
        with open(file_path, 'rb') as f:
            header = f.read(12)
        if len(header) < 12 or header[:4] != b'RIFF' or header[8:12] != b'WAVE':
            return None
        chunk_size = struct.unpack('<I', header[4:8])[0]
        return chunk_size + 8  # 8 bytes for RIFF tag + size field itself
    except Exception:
        return None


def load_with_soundfile(file_path: Path) -> tuple[np.ndarray, int]:
    """Load audio using soundfile library"""
    try:
        # Check WAV header for truncation before loading.
        # libsndfile silently adjusts frame counts to actual data, so
        # sf.info().frames == len(sf.read()) even for truncated files.
        # We compare the RIFF-declared size to the real file size instead.
        actual_file_size = file_path.stat().st_size
        declared_size = _get_wav_declared_size(file_path)
        if declared_size is not None and actual_file_size < declared_size:
            completeness = (actual_file_size / declared_size) * 100

            if completeness < 10:
                raise ModuleError(
                    f"{Code.ERROR_TRUNCATED_FILE}: File is severely truncated "
                    f"({completeness:.1f}% complete)"
                )
            elif completeness < 90:
                warning(
                    f"{Code.WARNING_TRUNCATED_FILE}: File appears truncated "
                    f"({completeness:.1f}% complete)"
                )

        # Load audio data
        audio_data, sample_rate = sf.read(str(file_path), always_2d=False)

        # Ensure proper shape
        if audio_data.ndim == 1:
            # Mono audio
            pass
        elif audio_data.ndim == 2:
            # Multi-channel audio
            if audio_data.shape[1] > 2:
                # Convert to stereo by taking first two channels
                original_channels = audio_data.shape[1]
                audio_data = audio_data[:, :2].copy()
                warning(f"Converted {original_channels} channels to stereo")
        else:
            raise ModuleError(f"{Code.ERROR_INVALID_AUDIO}: Invalid audio dimensions")

        return audio_data, int(sample_rate)

    except ModuleError:
        # Re-raise our own errors
        raise
    except Exception as e:
        raise ModuleError(f"{Code.ERROR_LOADING}: {str(e)}")

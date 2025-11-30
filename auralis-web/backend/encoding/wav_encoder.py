"""
WAV Audio Encoder - Browser-Compatible Format
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Encodes audio to WAV format which is natively supported by Web Audio API's decodeAudioData().
This replaces WebM/Opus for streaming since browsers can decode WAV directly.

WAV format advantages for streaming:
- Universal browser support (all browsers support WAV decoding)
- Simple format (no separate decoder library needed)
- Fast encoding (minimal processing)
- Works with Web Audio API decodeAudioData()

Trade-off:
- Larger file size than WebM/Opus (16-bit PCM = 88 kB/s @ 44.1 kHz)
- But 15-second chunks = only ~1.3 MB per chunk (acceptable)

:copyright: (C) 2025 Auralis Team
:license: GPLv3
"""

import logging
import numpy as np
from pathlib import Path
from typing import Optional
import io

logger = logging.getLogger(__name__)


class WAVEncoderError(Exception):
    """Raised when WAV encoding fails"""
    pass


def encode_to_wav(audio: np.ndarray, sample_rate: int = 44100, output_path: Optional[str] = None) -> bytes:
    """
    Encode audio to WAV format compatible with Web Audio API.

    Args:
        audio: NumPy array of audio samples (float32, normalized -1.0 to 1.0)
        sample_rate: Sample rate in Hz (default: 44100)
        output_path: Optional file path to save WAV. If None, returns bytes only.

    Returns:
        bytes: WAV encoded audio data

    Raises:
        WAVEncoderError: If encoding fails
    """
    try:
        import soundfile as sf

        # Ensure audio is float32 (Web Audio API requirement)
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32, copy=True)

        # Ensure audio is in valid range for PCM_16 encoding [-1.0, 1.0]
        # Clip to prevent distortion
        audio = np.clip(audio, -1.0, 1.0)

        # Encode to WAV in memory
        wav_buffer = io.BytesIO()
        sf.write(wav_buffer, audio, sample_rate, format='WAV', subtype='PCM_16')
        wav_bytes = wav_buffer.getvalue()

        # Optionally save to file
        if output_path:
            with open(output_path, 'wb') as f:
                f.write(wav_bytes)
            logger.info(f"WAV encoded: {output_path} ({len(wav_bytes)} bytes, {len(audio)/sample_rate:.1f}s)")

        return wav_bytes

    except ImportError as e:
        raise WAVEncoderError(f"soundfile module not available: {e}") from e
    except Exception as e:
        raise WAVEncoderError(f"WAV encoding failed: {e}") from e


def get_wav_chunk(audio: np.ndarray, sample_rate: int = 44100) -> bytes:
    """
    Quick helper to encode audio chunk to WAV format.

    Args:
        audio: Audio data (float32, -1.0 to 1.0)
        sample_rate: Sample rate in Hz

    Returns:
        bytes: WAV encoded audio

    Raises:
        WAVEncoderError: If encoding fails
    """
    return encode_to_wav(audio, sample_rate)

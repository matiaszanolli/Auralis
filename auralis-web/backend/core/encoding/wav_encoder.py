"""
WAV Encoder

Handles WAV PCM encoding and file output for audio chunks.
Encapsulates bit depth options, file naming, and I/O operations.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

import logging
import numpy as np
from pathlib import Path
from typing import Literal, Dict, Any

from auralis.io.saver import save as save_audio

logger = logging.getLogger(__name__)


class WAVEncoder:
    """
    Encodes and saves audio chunks as WAV PCM files.

    Features:
    - Support for multiple PCM bit depths (16-bit, 24-bit)
    - Consistent file naming with signatures for cache integrity
    - Chunk directory management
    - File path generation for cache lookups
    """

    # Supported PCM subtypes for WAV files
    SUPPORTED_SUBTYPES = {
        'PCM_16': 'Signed 16-bit PCM',
        'PCM_24': 'Signed 24-bit PCM',
        'PCM_32': 'Signed 32-bit PCM (float)',
    }

    # Default bit depth
    DEFAULT_SUBTYPE = 'PCM_16'

    def __init__(self, chunk_dir: Path, default_subtype: str = 'PCM_16'):
        """
        Initialize WAV encoder.

        Args:
            chunk_dir: Directory to save WAV chunks
            default_subtype: Default PCM subtype (PCM_16, PCM_24, PCM_32)

        Raises:
            ValueError: If unsupported subtype specified
        """
        self.chunk_dir = Path(chunk_dir)
        self.chunk_dir.mkdir(parents=True, exist_ok=True)

        if default_subtype not in self.SUPPORTED_SUBTYPES:
            raise ValueError(
                f"Unsupported subtype: {default_subtype}. "
                f"Supported: {', '.join(self.SUPPORTED_SUBTYPES.keys())}"
            )

        self.default_subtype = default_subtype
        logger.debug(f"WAVEncoder initialized with chunk_dir={chunk_dir}, subtype={default_subtype}")

    def get_chunk_path(
        self,
        track_id: int,
        file_signature: str,
        preset: str,
        intensity: float,
        chunk_index: int
    ) -> Path:
        """
        Generate consistent file path for audio chunk.

        Path includes file signature to prevent serving wrong audio
        if track file is modified or replaced.

        Args:
            track_id: Track ID
            file_signature: File signature for cache integrity
            preset: Processing preset (adaptive, gentle, etc.)
            intensity: Processing intensity (0.0-1.0)
            chunk_index: Chunk index (0-based)

        Returns:
            Path object for chunk file
        """
        filename = (
            f"track_{track_id}_{file_signature}_{preset}_{intensity}_chunk_{chunk_index}.wav"
        )
        return self.chunk_dir / filename

    def encode_and_save(
        self,
        audio: np.ndarray,
        sample_rate: int,
        chunk_path: Path,
        subtype: str | None = None
    ) -> None:
        """
        Encode audio chunk as WAV PCM and save to disk.

        Args:
            audio: Audio samples (samples,) or (samples, channels) array
            sample_rate: Sample rate in Hz
            chunk_path: Output file path
            subtype: PCM subtype (uses default if None)

        Raises:
            ValueError: If audio invalid
            IOError: If write fails
        """
        if subtype is None:
            subtype = self.default_subtype

        # Validate audio
        if not isinstance(audio, np.ndarray):
            raise ValueError(f"Expected ndarray, got {type(audio)}")

        if audio.size == 0:
            raise ValueError("Cannot encode empty audio array")

        if not np.isfinite(audio).all():
            raise ValueError("Audio contains non-finite values (NaN/Inf)")

        # Log operation
        channels = 1 if audio.ndim == 1 else audio.shape[1]
        duration_sec = len(audio) / sample_rate
        logger.debug(
            f"Encoding WAV: {chunk_path.name} "
            f"(sr={sample_rate}Hz, ch={channels}, duration={duration_sec:.2f}s, subtype={subtype})"
        )

        try:
            # Save using auralis I/O
            save_audio(str(chunk_path), audio, sample_rate, subtype=subtype)
            logger.debug(f"WAV saved: {chunk_path}")

        except Exception as e:
            logger.error(f"Failed to save WAV chunk: {e}")
            raise IOError(f"WAV encoding failed: {e}") from e

    def encode_and_save_from_path(
        self,
        audio: np.ndarray,
        sample_rate: int,
        track_id: int,
        file_signature: str,
        preset: str,
        intensity: float,
        chunk_index: int,
        subtype: str | None = None
    ) -> Path:
        """
        Generate path, encode audio, and save in one operation.

        Convenience method combining path generation and encoding.

        Args:
            audio: Audio samples to encode
            sample_rate: Sample rate in Hz
            track_id: Track ID
            file_signature: File signature for integrity
            preset: Processing preset
            intensity: Processing intensity
            chunk_index: Chunk index
            subtype: PCM subtype (uses default if None)

        Returns:
            Path to saved file
        """
        chunk_path = self.get_chunk_path(
            track_id=track_id,
            file_signature=file_signature,
            preset=preset,
            intensity=intensity,
            chunk_index=chunk_index
        )

        self.encode_and_save(audio, sample_rate, chunk_path, subtype)
        return chunk_path

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get encoder statistics.

        Returns:
            Dictionary with chunk count, total size, etc.
        """
        wav_files = list(self.chunk_dir.glob("*.wav"))
        total_size = sum(f.stat().st_size for f in wav_files)

        return {
            "chunk_count": len(wav_files),
            "total_size_bytes": total_size,
            "total_size_mb": total_size / (1024 * 1024),
            "chunk_dir": str(self.chunk_dir),
            "default_subtype": self.default_subtype,
        }

    def cleanup_track_chunks(
        self,
        track_id: int,
        file_signature: str
    ) -> int:
        """
        Delete all chunks for a track.

        Args:
            track_id: Track ID
            file_signature: File signature

        Returns:
            Number of files deleted
        """
        pattern = f"track_{track_id}_{file_signature}_*.wav"
        files = list(self.chunk_dir.glob(pattern))
        deleted_count = 0

        for f in files:
            try:
                f.unlink()
                deleted_count += 1
            except Exception as e:
                logger.warning(f"Failed to delete chunk file {f}: {e}")

        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} chunk file(s) for track {track_id}")

        return deleted_count

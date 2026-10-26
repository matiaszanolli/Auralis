"""
WAV Encoder

Handles WAV PCM encoding and file output for audio chunks.
Encapsulates bit depth options, file naming, and I/O operations.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
from pathlib import Path

import numpy as np
import soundfile as sf

from auralis.io.saver import save as save_audio

from ..intensity_key import intensity_cache_key
from ..targets_hash import NO_TARGETS
from .atomic_io import atomic_save_audio, is_partial_path

logger = logging.getLogger(__name__)


class WAVEncoderError(Exception):
    """Raised when WAV encoding fails.

    #5147: previously defined in auralis-web/backend/encoding/wav_encoder.py,
    a module that survived only to host this class — its encode_to_wav() had
    no production callers. It was reached from here and from two core/ modules
    via a bare ``from encoding.wav_encoder import ...``, an absolute import
    that resolved only because pytest.ini and uvicorn happen to put
    auralis-web/backend on sys.path. It now lives beside the WAVEncoder that
    raises it and is re-exported from core.encoding.
    """


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

    # Cache version - increment when chunk processing logic OR the filename
    # key schema changes. This invalidates all disk-cached chunks when we fix
    # bugs in extraction/processing, or when the identity a filename encodes
    # changes shape.
    # v5 (#5948): the file holds the RAW emitted segment; level smoothing moved to
    #     serve time. v4 files have a gain baked in relative to whichever chunk
    #     the writing processor rendered before them, so they must not be served.
    # v4 (#4666): filename now includes the mastering-targets hash
    # v3: Added _extract_chunk_segment to process_chunk for proper overlap handling
    CACHE_VERSION = 5

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
        chunk_index: int,
        targets_hash: str = NO_TARGETS,
    ) -> Path:
        """
        Generate consistent file path for audio chunk.

        Path includes file signature to prevent serving wrong audio
        if track file is modified or replaced. Also includes CACHE_VERSION
        to invalidate stale chunks when processing logic changes.

        Args:
            track_id: Track ID
            file_signature: File signature for cache integrity
            preset: Processing preset ('adaptive')
            intensity: Processing intensity (0.0-1.0)
            chunk_index: Chunk index (0-based)
            targets_hash: Content hash of the mastering targets this chunk was
                rendered with (core/targets_hash.get_targets_hash), "none" when
                absent. #4666: this must move in lockstep with
                ChunkCacheManager.get_chunk_cache_key — the on-disk tier is
                consulted by a bare path existence check, so folding targets
                into the in-memory key alone would still serve a stale
                un-targeted WAV from disk.

        Returns:
            Path object for chunk file
        """
        # Include CACHE_VERSION in filename to invalidate stale chunks.
        # intensity goes through the canonical intensity_cache_key so the
        # filename moves in lockstep with ChunkCacheManager.get_chunk_cache_key
        # for off-grid / float-noise intensities too (#5474; the #4792/#4666
        # lockstep requirement).
        filename = (
            f"v{self.CACHE_VERSION}_track_{track_id}_{file_signature}_"
            f"{preset}_{intensity_cache_key(intensity)}_{targets_hash}_chunk_{chunk_index}.wav"
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
            WAVEncoderError: If the write fails (#4919 — was a bare OSError,
                misclassified by job_error_mapping._ERROR_CATEGORIES as a
                read failure since WAVEncoderError is checked first there).
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
            # Save via a staged temp file + os.replace (#4576). Writing straight
            # to the destination left a truncated file at a canonical cache path
            # on any unclean exit, and the cache-hit path could not tell it from
            # a good one. The validation above all runs *before* the write, so
            # it cannot detect a partial write either.
            atomic_save_audio(
                chunk_path,
                lambda staged: save_audio(staged, audio, sample_rate, subtype=subtype),
            )
            logger.debug(f"WAV saved: {chunk_path}")

        except Exception as e:
            logger.error(f"Failed to save WAV chunk: {e}")
            raise WAVEncoderError(f"WAV encoding failed: {e}") from e

    def encode_and_save_from_path(
        self,
        audio: np.ndarray,
        sample_rate: int,
        track_id: int,
        file_signature: str,
        preset: str,
        intensity: float,
        chunk_index: int,
        subtype: str | None = None,
        targets_hash: str = NO_TARGETS,
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
            targets_hash: Mastering-targets content hash (#4666) — must match
                what the lookup side (ChunkPathCache) resolves, or the write
                lands at a path no reader will ever check.

        Returns:
            Path to saved file
        """
        chunk_path = self.get_chunk_path(
            track_id=track_id,
            file_signature=file_signature,
            preset=preset,
            intensity=intensity,
            chunk_index=chunk_index,
            targets_hash=targets_hash,
        )

        self.encode_and_save(audio, sample_rate, chunk_path, subtype)
        return chunk_path

def read_chunk_wav(path: str | Path) -> np.ndarray:
    """Read a cached chunk WAV back exactly as it was rendered (#5947).

    Chunk WAVs are our own flat PCM files, written with the source's native
    channel count. ``load_audio()`` is the whole-file contract (FFmpeg routing,
    layout-aware downmix of >2 channels, mono as 1-D), so a cache hit read
    through it came back with a different shape than the cache miss of the same
    chunk. This returns ``(frames, channels)`` float32 — always 2-D — like the
    miss path's source read.
    """
    audio: np.ndarray = sf.read(str(path), dtype='float32', always_2d=True)[0]
    return audio


def delete_chunk_files(
    chunk_dir: Path,
    track_id: int | None = None,
    file_signature: str | None = None,
) -> int:
    """Delete published chunk WAVs from *chunk_dir* (#5340).

    The on-disk chunk cache is found by name alone (``get_chunk_path`` +
    ``Path.exists()``), whoever wrote the file — live playback, the streamlined
    worker or pre-warm — so clearing it means sweeping the directory, not just
    the paths a cache tier recorded. Scoped to one track (optionally one file
    signature) or, with ``track_id`` None, every chunk.

    In-progress staged writes (#4576) are left alone: deleting one would make
    its writer's ``os.replace()`` fail mid-stream. A missing directory is
    simply nothing to delete.

    Returns:
        Number of files deleted
    """
    if track_id is None:
        patterns = ["*.wav"]
    else:
        # The trailing "_" keeps track 1 from matching track 12's files.
        signature = f"{file_signature}_" if file_signature is not None else ""
        patterns = [
            f"track_{track_id}_{signature}*.wav",  # Pre-versioning format
            f"v*_track_{track_id}_{signature}*.wav",  # Versioned format
        ]
    files = {
        f
        for pattern in patterns
        for f in chunk_dir.glob(pattern)
        if not is_partial_path(f)
    }

    deleted_count = 0
    for f in files:
        try:
            f.unlink()
            deleted_count += 1
        except FileNotFoundError:
            pass  # Removed concurrently (another clear, or the size pruner)
        except OSError as e:
            logger.warning(f"Failed to delete chunk file {f}: {e}")

    if deleted_count > 0:
        scope = "all tracks" if track_id is None else f"track {track_id}"
        logger.info(f"Cleaned up {deleted_count} chunk file(s) for {scope}")

    return deleted_count

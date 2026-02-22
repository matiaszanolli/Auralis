"""
Fingerprint Generator - On-Demand Fingerprint Generation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Manages fingerprint generation via PyO3 Rust bindings when fingerprints are not cached.
Handles async generation, database storage, and graceful fallback on failure.

**Process Isolation**: Uses ProcessPoolExecutor to run fingerprinting in a separate
process, ensuring that CPU-intensive Rust/PyO3 operations never block playback threads.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import atexit
import logging
import os
from concurrent.futures import ProcessPoolExecutor
from typing import Any
from collections.abc import Callable

import numpy as np
import soundfile as sf
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Try to import Rust fingerprinting via PyO3
try:
    from auralis_dsp import compute_fingerprint
    RUST_AVAILABLE = True
    logger.info("✅ Rust fingerprinting (PyO3) module available")
except ImportError:
    RUST_AVAILABLE = False
    compute_fingerprint = None  # type: ignore
    logger.warning("⚠️  Rust fingerprinting module not available, fingerprint generation will fail")


# =============================================================================
# PROCESS POOL EXECUTOR FOR FINGERPRINTING
# =============================================================================
# Uses a separate process to run CPU-intensive fingerprinting operations.
# This ensures playback threads are NEVER blocked by fingerprint computation.
# ProcessPoolExecutor requires functions to be defined at module level for pickling.

# Number of worker processes for fingerprinting (1-2 is sufficient, keeps memory low)
_FINGERPRINT_WORKERS = min(2, (os.cpu_count() or 4) // 2)

# Module-level ProcessPoolExecutor (lazy initialized)
_fingerprint_executor: ProcessPoolExecutor | None = None


def _get_fingerprint_executor() -> ProcessPoolExecutor:
    """Get or create the fingerprint ProcessPoolExecutor (lazy initialization)."""
    global _fingerprint_executor
    if _fingerprint_executor is None:
        _fingerprint_executor = ProcessPoolExecutor(
            max_workers=_FINGERPRINT_WORKERS,
            mp_context=None,  # Use default spawn method (safest for PyO3)
        )
        logger.info(f"🔧 Created fingerprint ProcessPoolExecutor with {_FINGERPRINT_WORKERS} workers")
    return _fingerprint_executor


def shutdown_fingerprint_executor() -> None:
    """Shutdown the fingerprint executor gracefully."""
    global _fingerprint_executor
    if _fingerprint_executor is not None:
        logger.info("🛑 Shutting down fingerprint ProcessPoolExecutor...")
        _fingerprint_executor.shutdown(wait=False, cancel_futures=True)
        _fingerprint_executor = None


# Register cleanup on exit
atexit.register(shutdown_fingerprint_executor)


def _compute_fingerprint_in_process(
    audio_data: np.ndarray,
    sample_rate: int,
    channels: int
) -> dict[str, Any] | None:
    """
    Module-level function to compute fingerprint in a separate process.

    Must be at module level for ProcessPoolExecutor pickling to work.
    This function runs in a subprocess, completely isolated from the main process.

    Args:
        audio_data: Audio samples as float32 numpy array
        sample_rate: Sample rate in Hz
        channels: Number of audio channels

    Returns:
        Dict with 25 fingerprint dimensions, or None if computation fails
    """
    # Import inside function to ensure it's available in the subprocess
    try:
        from auralis_dsp import compute_fingerprint as rust_compute
        return rust_compute(audio_data, sample_rate, channels)
    except Exception as e:
        # Log in subprocess (will be captured)
        import logging
        logging.getLogger(__name__).error(f"Fingerprint computation failed in subprocess: {e}")
        return None


class FingerprintGenerator:
    """
    Manages fingerprint generation via PyO3 Rust bindings.

    Provides async fingerprint generation with:
    - Database caching (reuse existing fingerprints)
    - PyO3 Rust function calls (direct, no server process needed)
    - Timeout handling (10 seconds max per fingerprint)
    - Graceful fallback (proceed without fingerprint if generation fails)
    - Database storage (cache for future use)
    - **Process isolation** (ProcessPoolExecutor ensures fingerprinting never blocks playback)

    **Process Isolation**: CPU-intensive fingerprint computation runs in a separate
    subprocess via ProcessPoolExecutor. This guarantees that playback threads are
    never blocked by fingerprinting operations, even under heavy load.
    """

    # Generation timeout (seconds) - PyO3 calls are fast
    TIMEOUT = 10

    def __init__(self, session_factory: Callable[[], Session], get_repository_factory: Callable[..., Any]) -> None:
        """
        Initialize fingerprint generator.

        Args:
            session_factory: SQLAlchemy session factory
            get_repository_factory: Callable that returns RepositoryFactory instance
        """
        self.session_factory = session_factory
        self.get_repository_factory = get_repository_factory

    async def get_or_generate(
        self,
        track_id: int,
        filepath: str
    ) -> dict[str, Any] | None:
        """
        Get fingerprint from database, or generate via PyO3 Rust if missing.

        Returns fingerprint data as dict with 25 dimensions, or None if generation fails.

        Args:
            track_id: ID of the track
            filepath: Path to audio file

        Returns:
            Dict with 25 fingerprint dimensions, or None if not available
        """

        # 1. Check database first (fastest - cached result)
        try:
            repo_factory = self.get_repository_factory()
            fingerprint_repo = repo_factory.fingerprints

            fp_record = fingerprint_repo.get_by_track_id(track_id)
            if fp_record:
                logger.info(f"✅ Loaded fingerprint from database for track {track_id} (cache hit)")
                return self._record_to_dict(fp_record)
        except Exception as e:
            logger.debug(f"Database fingerprint lookup failed for track {track_id}: {e}")

        # 2. Check if Rust module is available
        if not RUST_AVAILABLE:
            logger.warning(f"⚠️  Rust fingerprinting module not available, cannot generate fingerprint for track {track_id}")
            return None

        # 3. Generate via PyO3 Rust if not cached
        logger.info(f"📊 Fingerprint not cached for track {track_id}, generating via PyO3 Rust...")
        fingerprint_data = await self._generate_via_rust(filepath, track_id)

        if fingerprint_data is None:
            logger.warning(f"⚠️  Fingerprint generation failed for track {track_id}, proceeding without mastering optimization")
            return None

        # 4. Store in database for future use
        try:
            repo_factory = self.get_repository_factory()
            fingerprint_repo = repo_factory.fingerprints

            fingerprint_repo.add(track_id, fingerprint_data)
            logger.info(f"✅ Generated and cached fingerprint for track {track_id} (25D: {list(fingerprint_data.keys())[:5]}...)")
        except Exception as e:
            logger.warning(f"Failed to store fingerprint in database: {e}, but continuing with generated fingerprint")

        return fingerprint_data

    async def _generate_via_rust(
        self,
        filepath: str,
        track_id: int
    ) -> dict[str, Any] | None:
        """
        Call PyO3 Rust fingerprinting function to generate fingerprint.

        **Process Isolation**: Runs in a separate process via ProcessPoolExecutor,
        ensuring CPU-intensive fingerprinting never blocks playback threads.

        Args:
            filepath: Path to audio file
            track_id: Track ID (for logging)

        Returns:
            Dict with 25 fingerprint dimensions, or None if generation fails
        """

        try:
            # Load audio file (this is I/O bound, fine in main process)
            logger.debug(f"Loading audio file: {filepath}")
            audio, sample_rate = sf.read(filepath, dtype='float32')

            # Handle stereo/mono
            if audio.ndim == 1:
                channels = 1
                audio_array = audio
            else:
                channels = audio.shape[1] if audio.ndim == 2 else 1
                # For stereo, interleave L,R channels
                if channels == 2 and audio.ndim == 2:
                    audio_array = audio.flatten(order='F')  # Interleave: L1,R1,L2,R2...
                else:
                    audio_array = audio

            # Ensure proper dtype (float32)
            audio_array = np.asarray(audio_array, dtype=np.float32)
            logger.debug(f"Audio loaded: {len(audio_array)} samples, SR={sample_rate}, CH={channels}, dtype={audio_array.dtype}")

            # Get the ProcessPoolExecutor for fingerprinting (separate process)
            executor = _get_fingerprint_executor()
            loop = asyncio.get_running_loop()

            # Run fingerprint computation in a SEPARATE PROCESS
            # This ensures playback threads are never blocked by CPU-intensive Rust operations
            logger.debug(f"🔄 Submitting fingerprint computation to ProcessPoolExecutor for track {track_id}")

            fingerprint = await asyncio.wait_for(
                loop.run_in_executor(
                    executor,  # Use ProcessPoolExecutor (separate process!)
                    _compute_fingerprint_in_process,  # Module-level function for pickling
                    audio_array.copy(),  # Pass a copy (will be pickled to subprocess)
                    int(sample_rate),
                    int(channels)
                ),
                timeout=self.TIMEOUT
            )

            if fingerprint is None:
                logger.error(f"Fingerprint computation returned None for track {track_id}")
                return None

            logger.info(f"✅ PyO3 Rust generated fingerprint for track {track_id} in <{self.TIMEOUT}s (subprocess)")
            return fingerprint

        except FileNotFoundError:
            logger.error(f"Audio file not found: {filepath}")
            return None
        except TimeoutError:
            logger.error(f"Fingerprint generation timeout (>{self.TIMEOUT}s) for track {track_id}")
            return None
        except RuntimeError as e:
            logger.error(f"Rust fingerprinting error for track {track_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during fingerprint generation for track {track_id}: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None

    @staticmethod
    def _record_to_dict(fp_record: Any) -> dict[str, Any]:
        """
        Convert TrackFingerprint database record to dictionary.

        Args:
            fp_record: TrackFingerprint ORM object from database

        Returns:
            Dict with all fingerprint dimensions
        """
        # Extract all fingerprint dimensions from the record
        # This handles the 25D fingerprint structure
        fingerprint_dict = {}

        # Frequency dimensions (7D)
        for field in ['sub_bass_pct', 'bass_pct', 'low_mid_pct', 'mid_pct',
                      'upper_mid_pct', 'presence_pct', 'air_pct']:
            if hasattr(fp_record, field):
                fingerprint_dict[field] = getattr(fp_record, field)

        # Dynamics dimensions (3D)
        for field in ['lufs', 'crest_db', 'bass_mid_ratio']:
            if hasattr(fp_record, field):
                fingerprint_dict[field] = getattr(fp_record, field)

        # Temporal dimensions (4D)
        for field in ['tempo', 'rhythm_stability', 'transient_density', 'silence_ratio']:
            if hasattr(fp_record, field):
                fingerprint_dict[field] = getattr(fp_record, field)

        # Spectral dimensions (3D)
        for field in ['spectral_centroid', 'spectral_rolloff', 'spectral_flatness']:
            if hasattr(fp_record, field):
                fingerprint_dict[field] = getattr(fp_record, field)

        # Harmonic dimensions (3D)
        for field in ['harmonic_ratio', 'pitch_stability', 'chroma_energy']:
            if hasattr(fp_record, field):
                fingerprint_dict[field] = getattr(fp_record, field)

        # Variation dimensions (3D)
        for field in ['dynamic_range_variation', 'loudness_variation', 'peak_consistency']:
            if hasattr(fp_record, field):
                fingerprint_dict[field] = getattr(fp_record, field)

        # Stereo dimensions (2D)
        for field in ['stereo_width', 'phase_correlation']:
            if hasattr(fp_record, field):
                fingerprint_dict[field] = getattr(fp_record, field)

        return fingerprint_dict

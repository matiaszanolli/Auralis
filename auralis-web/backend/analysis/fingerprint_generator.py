"""
Fingerprint Generator - On-Demand Fingerprint Generation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Manages fingerprint generation via PyO3 Rust bindings when fingerprints are not cached.
Handles async generation, database storage, and graceful fallback on failure.

**Threading model**: fingerprinting runs on a ThreadPoolExecutor, off the asyncio
event loop. The PyO3 Rust computation releases the GIL, so worker threads get true
parallelism without ProcessPoolExecutor's pickling / process-spawn / module re-import
overhead (which can exceed the timeout in AppImage environments). This is NOT crash
isolation: a pathological file that hangs the Rust DSP is not reclaimed on timeout —
the future is cancelled but the worker thread runs to completion, since threads
cannot be force-killed (#4377).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import atexit
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from collections.abc import Callable

from sqlalchemy.orm import Session

from core.env_config import get_int_env

from auralis.analysis.fingerprint.schema import DIMENSION_NAMES

logger = logging.getLogger(__name__)

# Try to import Rust fingerprinting via PyO3
try:
    from auralis_dsp import compute_fingerprint
    RUST_AVAILABLE = True
    logger.info("✅ Rust fingerprinting (PyO3) module available")
except ImportError:
    RUST_AVAILABLE = False
    compute_fingerprint = None
    logger.warning("⚠️  Rust fingerprinting module not available, fingerprint generation will fail")


# =============================================================================
# THREAD POOL EXECUTOR FOR FINGERPRINTING
# =============================================================================
# Uses a thread pool to run fingerprinting off the asyncio event loop.
# PyO3 Rust code releases the GIL, so threads get true parallelism
# without the overhead of ProcessPoolExecutor (pickling, process spawn,
# module re-import — which can exceed 10s timeout in AppImage environments).


from .fingerprint_executor import (  # noqa: E402  (split #6271; body-used)
    _compute_windowed_fingerprint_in_thread,
    _get_fingerprint_executor,
    shutdown_fingerprint_executor,
)


class FingerprintGenerator:
    """
    Manages fingerprint generation via PyO3 Rust bindings.

    Provides async fingerprint generation with:
    - Database caching (reuse existing fingerprints)
    - PyO3 Rust function calls (direct, no server process needed)
    - Timeout handling (10 seconds max per fingerprint)
    - Graceful fallback (proceed without fingerprint if generation fails)
    - Database storage (cache for future use)
    - **Off-loop execution** (a ThreadPoolExecutor keeps fingerprinting off the event loop)

    **Threading model**: CPU-intensive fingerprint computation runs on a
    ThreadPoolExecutor worker; the PyO3 Rust call releases the GIL, so playback
    threads and the event loop are not blocked. This is not crash isolation — a
    hung Rust DSP thread cannot be force-killed, so on timeout the future is
    cancelled but the worker thread keeps running to completion (#4377).
    """

    # Generation timeout (seconds) — includes audio loading + Rust computation.
    # Long tracks or hi-res files can take 15-20s to load and process.
    TIMEOUT = 30

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

            # Offload the sync DB read so it doesn't stall the event loop on
            # stream startup / background queue drain (#3854).
            fp_record = await asyncio.to_thread(fingerprint_repo.get_by_track_id, track_id)
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

            # Offload the sync DB write (#3854).
            await asyncio.to_thread(fingerprint_repo.add, track_id, fingerprint_data)
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

        **Threading model**: runs on a ThreadPoolExecutor worker (not a separate
        process); the GIL-releasing Rust call keeps the event loop and playback
        threads responsive. On timeout the future is cancelled but the worker
        thread is not reclaimed (#4377).

        Args:
            filepath: Path to audio file
            track_id: Track ID (for logging)

        Returns:
            Dict with 25 fingerprint dimensions, or None if generation fails
        """

        try:
            # Run the shared windowed pipeline in a thread pool worker:
            # bounded decoding + Rust analysis (GIL-releasing) keep the event
            # loop and playback threads responsive (#3854, #5531).
            executor = _get_fingerprint_executor()
            loop = asyncio.get_running_loop()

            logger.debug(f"🔄 Submitting windowed fingerprint computation to ThreadPoolExecutor for track {track_id}")

            fingerprint = await asyncio.wait_for(
                loop.run_in_executor(
                    executor,
                    _compute_windowed_fingerprint_in_thread,
                    filepath,
                ),
                timeout=self.TIMEOUT
            )

            if fingerprint is None:
                logger.error(f"Fingerprint computation returned None for track {track_id}")
                return None

            logger.info(f"✅ Generated windowed fingerprint for track {track_id}")
            return fingerprint

        except FileNotFoundError:
            logger.error(f"Audio file not found: {Path(filepath).name}")
            return None
        except TimeoutError:
            logger.error(f"Fingerprint generation timeout (>{self.TIMEOUT}s) for track {track_id}")
            return None
        except RuntimeError as e:
            logger.error(f"Rust fingerprinting error for track {track_id}: {e}")
            return None
        except Exception as e:
            logger.error(
                f"Unexpected error during fingerprint generation for track {track_id}: {e}",
                exc_info=True,
            )
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
        # The schema's name list is the one spelling of the 25 dimensions (#5786); the
        # model columns share it, so a hand-typed copy here drifted ('tempo' vs tempo_bpm).
        fingerprint_dict = {name: getattr(fp_record, name) for name in DIMENSION_NAMES}

        return fingerprint_dict

"""
Fingerprint and Similarity Initialization
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The batch fingerprint extraction queue, the on-demand fingerprint queue and
the similarity system. Each step catches its own failure, so none of them
triggers the Auralis-init rollback.

Split out of the former single-file config/startup.py (#5236).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def _init_fingerprint_extraction_queue(globals_dict: dict[str, Any]) -> None:
    """Start the CPU-based fingerprint extraction queue (36x speedup).

    Note: GPU batch processing was causing memory exhaustion crashes.
    CPU parallelization provides better stability and consistent
    performance. Own try/except: a failure here must not abort the rest
    of Auralis component initialization (matches original inline
    behavior).
    """
    try:
        from auralis.services.fingerprint_extractor import (
            FingerprintExtractor,
        )
        from auralis.services.fingerprint_queue import (
            FingerprintExtractionQueue,
        )

        # Create fingerprint extractor with library manager's fingerprint repository
        fingerprint_extractor = FingerprintExtractor(
            fingerprint_repository=globals_dict['library_database'].fingerprints,
            track_repository=globals_dict['library_database'].tracks,
        )
        logger.info("✅ Fingerprint Extractor initialized")

        # Create CPU-based fingerprint queue (24+ workers, 36x speedup)
        fingerprint_queue = FingerprintExtractionQueue(
            fingerprint_extractor=fingerprint_extractor,
            get_repository_factory=lambda: globals_dict.get('repository_factory'),
            num_workers=None,  # Auto-detect CPU cores
            max_workers=None  # Auto-size based on system
        )

        # Start background workers
        await fingerprint_queue.start()
        logger.info(f"✅ Fingerprint extraction queue started ({fingerprint_queue.num_workers} workers, 36x CPU speedup)")

        # Store for later reference
        globals_dict['fingerprint_queue'] = fingerprint_queue
        globals_dict['gpu_processor'] = None  # GPU disabled

    except Exception as fp_e:
        logger.warning(f"⚠️  Failed to initialize fingerprinting system: {fp_e}")


async def _init_ondemand_fingerprint_queue(globals_dict: dict[str, Any]) -> None:
    """Initialize on-demand fingerprint queue (Phase 7.4).

    Handles 404s during similarity lookup - queues tracks for
    background processing.
    """
    try:
        from analysis.fingerprint_generator import FingerprintGenerator
        from analysis.fingerprint_queue import (
            FingerprintQueue,
            set_fingerprint_queue,
        )

        # Create FingerprintGenerator for the queue
        fp_generator = FingerprintGenerator(
            session_factory=globals_dict['library_database'].SessionLocal,
            get_repository_factory=lambda: globals_dict.get('repository_factory')
        )

        # Helper to get track filepath
        def get_track_filepath(track_id: int) -> str | None:
            try:
                factory = globals_dict.get('repository_factory')
                if factory:
                    track = factory.tracks.get_by_id(track_id)
                    if track and track.filepath:
                        return str(track.filepath)
            except Exception:
                # Best-effort lookup (#4368 — was a bare pass,
                # hiding genuine repository failures from debugging).
                logger.debug(f"Track filepath lookup failed for {track_id}", exc_info=True)
            return None

        # Create and start on-demand fingerprint queue
        ondemand_queue = FingerprintQueue(
            fingerprint_generator=fp_generator,
            get_track_filepath=get_track_filepath
        )
        await ondemand_queue.start()
        set_fingerprint_queue(ondemand_queue)
        globals_dict['ondemand_fingerprint_queue'] = ondemand_queue
        logger.info("✅ On-demand fingerprint queue started (background processing for 404s)")

    except Exception as odq_e:
        logger.warning(f"⚠️  Failed to initialize on-demand fingerprint queue: {odq_e}")


async def _init_similarity_system(HAS_SIMILARITY: bool, globals_dict: dict[str, Any]) -> None:
    """Initialize the fingerprint similarity system and K-NN graph builder."""
    if not HAS_SIMILARITY:
        return
    try:
        from auralis.analysis.fingerprint import (
            FingerprintSimilarity,
            KNNGraphBuilder,
        )
        from services.similarity_autofit_worker import SimilarityAutoFitWorker

        globals_dict['similarity_system'] = FingerprintSimilarity(
            globals_dict['library_database'].fingerprints
        )
        logger.info("✅ Fingerprint Similarity System initialized")

        # #4139: auto-fit in the background so an existing
        # library gets working recommendations without a manual
        # /api/similarity/fit call. fit() is a no-op (returns
        # False) below min_samples (fresh install / library
        # reset), leaving the system unfitted — the similarity
        # router then surfaces a clear 503 rather than silently
        # empty results. Runs off the startup path because
        # normalizer.fit() streams every fingerprint in batches.
        #
        # #4682: this used to be a bare threading.Thread(daemon=True) with no
        # stop signal, never stored anywhere shutdown or library-reset could
        # find it. SimilarityAutoFitWorker gives it the same start()/stop()
        # shape every other BACKGROUND_WORKER_KEYS entry has, registered
        # below under 'similarity_autofit' so lifespan shutdown and
        # POST /api/library/reset both stop it through the shared helper
        # (config/background_workers.py) instead of being able to diverge.
        globals_dict['graph_builder'] = None
        autofit_worker = SimilarityAutoFitWorker(
            sim_system=globals_dict['similarity_system'],
            lib_mgr=globals_dict['library_database'],
            globals_dict=globals_dict,
            builder_cls=KNNGraphBuilder,
        )
        await autofit_worker.start()
        globals_dict['similarity_autofit'] = autofit_worker
    except Exception as sim_e:
        logger.warning(f"⚠️  Failed to initialize Similarity System: {sim_e}")
        globals_dict['similarity_system'] = None
        globals_dict['graph_builder'] = None

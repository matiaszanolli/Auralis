"""
Mastering Target Service
~~~~~~~~~~~~~~~~~~~~~~~~~

Centralized fingerprint loading and mastering target generation.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
import threading
from collections.abc import Callable
from typing import Any

from core.file_signature import FileSignatureService

from . import fingerprint_loading
from .fingerprint_single_flight import extract_once
from auralis.core.processing.mastering_targets import generate_targets_from_fingerprint
from auralis.core.processing.reference_cloud import ReferenceCloud

logger = logging.getLogger(__name__)


class MasteringTargetService:
    """
    Centralized fingerprint loading and mastering target generation.

    Provides 3-tier fingerprint loading hierarchy:
    1. Database (fastest - cached in SQLite)
    2. .25d file (fast - pre-computed)
    3. Extract from audio (slow - requires full analysis)

    Targets pull toward the reference cloud's k-NN band centers (#6356). A plan is
    cached per track and file signature and outlives a cloud refresh, so a processor
    rebuilt mid-track keeps the plan already heard; only a cache clear starts a new one.
    """

    def __init__(
        self,
        cache: dict[str, Any] | None = None,
        get_fingerprints_repository: Callable[[], Any] | None = None
    ):
        """
        Initialize mastering target service.

        Args:
            cache: Optional shared cache dictionary
            get_fingerprints_repository: Callable that returns fingerprints repository
                                        (for database lookups via repository pattern)
        """
        # FIFO-bounded: 256 entries x ~3 KB so the singleton cannot grow without limit (#3532).
        from collections import OrderedDict
        self.cache: OrderedDict[str, Any] = OrderedDict(cache) if cache is not None else OrderedDict()
        self._max_cache_entries = 256
        self._get_fingerprints_repository = get_fingerprints_repository
        # The same cloud ContinuousMode reads, so streams and jobs share one plan.
        self._reference_cloud = ReferenceCloud(lambda: get_fingerprints_repository and get_fingerprints_repository())
        self._lock = threading.RLock()
        logger.debug("MasteringTargetService initialized")

    def cached(self, key: str) -> tuple[Any, dict[str, Any] | None] | None:
        """The cached (fingerprint, targets) for ``key`` (refreshing its LRU position), or None."""
        with self._lock:
            value = self.cache.get(key)
            if not (isinstance(value, tuple) and len(value) == 2):
                return None
            self.cache.move_to_end(key)
            return value

    def store(self, key: str, value: Any) -> None:
        """Cache ``value`` under ``key`` (LRU-bounded, #3532)."""
        with self._lock:
            self._store_in_cache(key, value)

    def _store_in_cache(self, key: str, value: Any) -> None:
        """Insert into the LRU cache and evict the oldest entry if over cap."""
        self.cache[key] = value
        self.cache.move_to_end(key)
        while len(self.cache) > self._max_cache_entries:
            self.cache.popitem(last=False)

    def _get_cache_key(
        self, track_id: int, filepath: str, file_signature: str | None = None
    ) -> str:
        """Generate cache key for fingerprint.

        Keyed on the file's content signature, like every sibling cache
        (chunk_cache_manager.py, streamlined_processor_cache.py): a key built from
        the path alone kept serving pre-edit targets after the file was
        replaced in place (#5489).
        """
        if file_signature is None:
            file_signature = FileSignatureService.generate(filepath)
        return f"fingerprint_{track_id}_{file_signature}"

    def load_fingerprint_from_database(self, track_id: int) -> Any | None:
        """Tier 1 (database); see :func:`fingerprint_loading.load_from_database`."""
        return fingerprint_loading.load_from_database(
            self._get_fingerprints_repository, track_id
        )

    def load_fingerprint_from_file(
        self, filepath: str
    ) -> tuple[Any, dict[str, Any] | None] | None:
        """Tier 2 (.25d sidecar); see :func:`fingerprint_loading.load_from_file`."""
        return fingerprint_loading.load_from_file(
            filepath, self.generate_targets_from_fingerprint
        )

    def extract_fingerprint_from_audio(
        self, filepath: str, save_to_file: bool = True,
        should_stop: Callable[[], bool] | None = None,
    ) -> tuple[Any, dict[str, Any] | None] | None:
        """Tier 3 (decode + analyse); see :func:`fingerprint_loading.extract_from_audio`."""
        return fingerprint_loading.extract_from_audio(
            filepath, self.generate_targets_from_fingerprint, save_to_file, should_stop
        )

    def load_fingerprint(
        self,
        track_id: int,
        filepath: str,
        extract_if_missing: bool = True,
        save_extracted: bool = True,
        file_signature: str | None = None,
        should_stop: Callable[[], bool] | None = None,
    ) -> tuple[Any, dict[str, Any] | None] | None:
        """
        Load fingerprint using 3-tier hierarchy.

        1. Database (fastest)
        2. .25d file
        3. Extract from audio (if extract_if_missing=True)

        Args:
            track_id: Track ID for database lookup
            filepath: Path to audio file
            extract_if_missing: If True, extract from audio if not cached
            save_extracted: If True, save extracted fingerprint to .25d file
            file_signature: The file's FileSignatureService signature, when
                the caller already computed it; generated here otherwise.
            should_stop: Abandons a tier-3 wait on the analysis gate (#6336).

        Returns:
            Tuple of (fingerprint, mastering_targets) or None if not found
        """
        cache_key = self._get_cache_key(track_id, filepath, file_signature)
        cached = self.cached(cache_key)
        if cached is not None:
            logger.debug(f"Using cached fingerprint for track {track_id}")
            return cached

        # Tier 1: Try database
        fingerprint = self.load_fingerprint_from_database(track_id)
        if fingerprint is not None:
            # Generate targets from database fingerprint
            targets = self.generate_targets_from_fingerprint(fingerprint)
            result = (fingerprint, targets)
            self.store(cache_key, result)
            return result

        # Tier 2: Try .25d file
        file_result = self.load_fingerprint_from_file(filepath)
        if file_result is not None:
            self.store(cache_key, file_result)
            return file_result

        # Tier 3: extract from audio, once per (track, signature) however many callers ask (#6504)
        if extract_if_missing:
            extract_result = extract_once(self, cache_key, filepath, save_extracted, should_stop)
            if extract_result is not None:
                return extract_result

        logger.debug(f"No fingerprint found for track {track_id}")
        return None

    def generate_targets_from_fingerprint(self, fingerprint: dict[str, float]) -> dict[str, Any]:
        """Mastering targets for a fingerprint, toward the reference cloud's k-NN centers.

        See :func:`auralis.core.processing.mastering_targets.generate_targets_from_fingerprint`.
        """
        targets: dict[str, Any] = generate_targets_from_fingerprint(fingerprint, self._reference_cloud.band_centers(fingerprint))
        return targets

    def clear_track(self, track_id: int) -> None:
        """Drop one track's cached fingerprint/targets (every file signature)."""
        with self._lock:
            for key in [k for k in self.cache if k.startswith(f"fingerprint_{track_id}_")]:
                del self.cache[key]

    def clear_cache(self) -> None:
        """Clear all cached fingerprints."""
        with self._lock:
            count = len(self.cache)
            self.cache.clear()
            logger.info(f"Cleared {count} cached fingerprint(s)")


# Global mastering target service instance (singleton pattern)
_global_mastering_target_service: MasteringTargetService | None = None
_service_lock = threading.Lock()


def get_mastering_target_service() -> MasteringTargetService:
    """
    Get global mastering target service instance (singleton).
    """
    global _global_mastering_target_service

    if _global_mastering_target_service is None:
        with _service_lock:
            # Double-check locking pattern
            if _global_mastering_target_service is None:
                # Wire Tier-1 DB lookup via the global repository factory so the
                # singleton isn't a latent Tier-1-dead trap (#3836 / BE-PE-3).
                # Lazy import avoids a circular import at module load time.
                from core.chunk_fingerprint_registry import _default_get_fingerprints_repository
                _global_mastering_target_service = MasteringTargetService(
                    get_fingerprints_repository=_default_get_fingerprints_repository,
                )
                logger.info("Global MasteringTargetService instance created")

    return _global_mastering_target_service


def clear_global_mastering_target_cache() -> bool:
    """Clear the singleton's per-track fingerprint/target cache, if it exists.

    ``clear_all_caches()`` calls it so a clear or library reset leaves no stale
    fingerprints or targets behind (#5085). It does not create the singleton.

    Returns:
        True if a live service was cleared, False if none had been created.
    """
    service = _global_mastering_target_service
    if service is None:
        return False
    service.clear_cache()
    return True


def clear_global_mastering_target_entry(track_id: int) -> None:
    """Drop one track from the singleton's cache (never creates it)."""
    service = _global_mastering_target_service
    if service is not None:
        service.clear_track(track_id)

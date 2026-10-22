"""
Mastering Target Service
~~~~~~~~~~~~~~~~~~~~~~~~~

Centralized fingerprint loading and mastering target generation.

Consolidates duplicate logic from:
- chunked_processor._load_fingerprint_from_database()
- chunked_processor._generate_targets_from_fingerprint()
- chunked_processor fingerprint extraction in process_chunk()

This service eliminates ~200 lines of duplicate fingerprint/target management.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
import threading
from collections.abc import Callable
from typing import Any

from core.file_signature import FileSignatureService

from . import fingerprint_loading
from .mastering_target_generation import generate_targets_from_fingerprint

logger = logging.getLogger(__name__)


class MasteringTargetService:
    """
    Centralized fingerprint loading and mastering target generation.

    Provides 3-tier fingerprint loading hierarchy:
    1. Database (fastest - cached in SQLite)
    2. .25d file (fast - pre-computed)
    3. Extract from audio (slow - requires full analysis)

    Features:
    - Thread-safe caching with RLock
    - Automatic target generation from fingerprints
    - One-stop method for getting fingerprint + targets
    - Supports saving extracted fingerprints
    - Repository pattern via dependency injection
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
        # Bound the cache with simple FIFO eviction to prevent unbounded
        # growth when the service is held as a singleton (#3532 / BE-NEW-74).
        # 256 entries × ~3 KB each ≈ 1 MB ceiling — plenty for a typical
        # listening session, won't bloat long-running backend processes.
        from collections import OrderedDict
        self.cache: OrderedDict[str, Any] = OrderedDict(cache) if cache is not None else OrderedDict()
        self._max_cache_entries = 256
        self._get_fingerprints_repository = get_fingerprints_repository
        self._lock = threading.RLock()
        logger.debug("MasteringTargetService initialized")

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
        self, filepath: str, save_to_file: bool = True
    ) -> tuple[Any, dict[str, Any] | None] | None:
        """Tier 3 (decode + analyse); see :func:`fingerprint_loading.extract_from_audio`."""
        return fingerprint_loading.extract_from_audio(
            filepath, self.generate_targets_from_fingerprint, save_to_file
        )

    def load_fingerprint(
        self,
        track_id: int,
        filepath: str,
        extract_if_missing: bool = True,
        save_extracted: bool = True,
        file_signature: str | None = None,
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

        Returns:
            Tuple of (fingerprint, mastering_targets) or None if not found
        """
        # Check cache first
        cache_key = self._get_cache_key(track_id, filepath, file_signature)
        with self._lock:
            if cache_key in self.cache:
                cached = self.cache[cache_key]
                if isinstance(cached, tuple) and len(cached) == 2:
                    self.cache.move_to_end(cache_key)
                    logger.debug(f"Using cached fingerprint for track {track_id}")
                    return cached

        # Tier 1: Try database
        fingerprint = self.load_fingerprint_from_database(track_id)
        if fingerprint is not None:
            # Generate targets from database fingerprint
            targets = self.generate_targets_from_fingerprint(fingerprint)
            result = (fingerprint, targets)

            # Cache result (LRU-bounded, #3532)
            with self._lock:
                self._store_in_cache(cache_key, result)

            return result

        # Tier 2: Try .25d file
        file_result = self.load_fingerprint_from_file(filepath)
        if file_result is not None:
            # Cache result (LRU-bounded, #3532)
            with self._lock:
                self._store_in_cache(cache_key, file_result)

            return file_result

        # Tier 3: Extract from audio (if requested)
        if extract_if_missing:
            extract_result = self.extract_fingerprint_from_audio(
                filepath,
                save_to_file=save_extracted
            )

            if extract_result is not None:
                # Cache result (LRU-bounded, #3532)
                with self._lock:
                    self._store_in_cache(cache_key, extract_result)

                return extract_result

        logger.debug(f"No fingerprint found for track {track_id}")
        return None

    def generate_targets_from_fingerprint(self, fingerprint: Any) -> dict[str, Any]:
        """Derive mastering targets from a 25D fingerprint.

        See :func:`mastering_target_generation.generate_targets_from_fingerprint`.
        """
        return generate_targets_from_fingerprint(fingerprint)

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

    Returns:
        Global MasteringTargetService instance
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

    This is the backend's track-analysis cache tier: ``clear_all_caches()``
    calls it so a cache clear or library reset cannot leave stale fingerprints
    and targets behind (#5085). It does not create the singleton.

    Returns:
        True if a live service was cleared, False if none had been created.
    """
    service = _global_mastering_target_service
    if service is None:
        return False
    service.clear_cache()
    return True

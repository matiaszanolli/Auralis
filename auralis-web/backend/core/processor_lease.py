"""
Exclusive per-stream processor leases (split out of ProcessorFactory, #6091).

``get_or_create`` hands the identical cached HybridProcessor to every caller
that asks for the same (track, preset, config, targets) key, and the
processor's ``_process_lock`` serialises calls without ordering them. Two live
streams of one track (a reconnect while the old WebSocket is still half-open, a
second window) therefore fed chunks into one instance in interleaved order, so
its EQ envelope and limiter gain-reduction carried across unrelated seams, and
both streams then wrote those seams into the durable chunk cache.

A lease is the ``ProcessorPool`` pattern for a stream: ``acquire`` POPS the
instance out of the cache so nobody else can hold it, ``release_lease`` puts it
back at the most-recently-used end, and ``discard_lease`` drops one whose state
can no longer be trusted. A second concurrent stream builds its own instance; a
single stream keeps one instance, and its state, for its whole life.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
import threading
from copy import deepcopy
from collections import OrderedDict
from collections.abc import Callable
from typing import Any

from .processor_cache_key import ProcessorCacheKey, build_cache_key, hash_config
from .targets_hash import get_targets_hash

logger = logging.getLogger(__name__)


class ProcessorLeaseMixin:
    """Lease API and construction for ``ProcessorFactory``; the cache and its lock live on the factory."""

    _lock: threading.RLock
    _processor_cache: OrderedDict[ProcessorCacheKey, Any]
    _active_processors: dict[int, Any]
    # Provided by ProcessorFactory.
    _cache_cap: Callable[[], int]

    def _build_processor(
        self,
        track_id: int,
        preset: str,
        intensity: float,
        config: Any | None,
        mastering_targets: dict[str, Any] | None,
    ) -> Any:
        """Construct one HybridProcessor; shared by ``get_or_create`` and ``acquire``.

        Construction takes 200-500 ms and does not touch cache state. Callers run
        it outside the global factory lock so unrelated cold keys can construct
        concurrently (#4689). The processor receives its own config snapshot;
        factory preset changes must never mutate caller-owned state (#4827).
        """
        from auralis.core.config import UnifiedConfig
        from auralis.core.hybrid_processor import HybridProcessor

        logger.info(
            "Creating new processor: track_id=%s, preset=%s, intensity=%s",
            track_id,
            preset,
            intensity,
        )
        try:
            owned_config = deepcopy(config) if config is not None else UnifiedConfig()
            owned_config.mastering_profile = preset.lower()
            processor = HybridProcessor(owned_config)

            if mastering_targets is not None:
                processor.set_fixed_mastering_targets(deepcopy(mastering_targets))
                logger.debug("Applied fixed mastering targets to processor")
        except Exception as error:
            logger.error("Failed to create processor for track %s: %s", track_id, error)
            raise
        return processor

    @staticmethod
    def _lease_key(
        track_id: int, preset: str, config: Any | None, mastering_targets: dict[str, Any] | None
    ) -> ProcessorCacheKey:
        return build_cache_key(
            track_id, preset, hash_config(config), get_targets_hash(mastering_targets)
        )

    def acquire(
        self,
        track_id: int,
        preset: str,
        intensity: float = 1.0,
        config: Any | None = None,
        mastering_targets: dict[str, Any] | None = None,
    ) -> Any:
        """Lease a processor exclusively: a released warm one, else a fresh build.

        The caller MUST hand it back with ``release_lease`` (or ``discard_lease``).
        Construction runs outside the cache lock (#4689).
        """
        key = self._lease_key(track_id, preset, config, mastering_targets)
        with self._lock:
            processor = self._processor_cache.pop(key, None)
        if processor is None:
            processor = self._build_processor(track_id, preset, intensity, config, mastering_targets)
        with self._lock:
            if track_id > 0:
                self._active_processors[track_id] = processor
        return processor

    def release_lease(
        self,
        processor: Any,
        *,
        track_id: int,
        preset: str,
        config: Any | None = None,
        mastering_targets: dict[str, Any] | None = None,
    ) -> None:
        """Return a leased processor to the cache as the most recently used entry.

        A different instance already cached under the key (another stream built
        its own meanwhile) is replaced and closed, as ``ProcessorPool`` does.
        """
        key = self._lease_key(track_id, preset, config, mastering_targets)
        to_close: list[Any] = []
        with self._lock:
            if track_id > 0 and self._active_processors.get(track_id) is processor:
                self._active_processors.pop(track_id, None)
            replaced = self._processor_cache.pop(key, None)  # pop: re-append at the MRU end
            if replaced is not None and replaced is not processor:
                to_close.append(replaced)
            self._processor_cache[key] = processor
            while len(self._processor_cache) > self._cache_cap():
                evicted_key, evicted = self._processor_cache.popitem(last=False)
                to_close.append(evicted)
                if (
                    evicted_key.track_id > 0
                    and self._active_processors.get(evicted_key.track_id) is evicted
                ):
                    self._active_processors.pop(evicted_key.track_id, None)
        for stale in to_close:
            stale.close()

    def discard_lease(self, processor: Any, *, track_id: int) -> None:
        """Drop a leased processor whose state is unknown instead of returning it.

        Used after a post-DSP failure (#5274) and after a chunk DSP timeout
        (#5335), where an abandoned executor thread may still be advancing it.
        """
        with self._lock:
            if track_id > 0 and self._active_processors.get(track_id) is processor:
                self._active_processors.pop(track_id, None)
        processor.close()
        logger.warning("Discarded leased processor: track_id=%s", track_id)

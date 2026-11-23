"""
Reference Cloud
~~~~~~~~~~~~~~~

The cached reference cloud (``is_reference`` fingerprints) and the per-track
band centers the soft k-NN derives from it. Shared by the two places that turn
a fingerprint into mastering targets -- ``ContinuousMode`` (whole-file jobs and
the per-chunk fallback) and the backend's ``MasteringTargetService`` (streaming
fixed targets) -- so both read the same cloud with the same refresh rules.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import threading
import time
from collections.abc import Callable
from typing import Any

from ...utils.logging import debug
from .target_derivation import DistanceStats, derive_target

# How long a loaded, non-empty reference cloud is trusted before it is re-read.
REFERENCE_CLOUD_TTL_S = 60.0


class ReferenceCloud:
    """Lazy, TTL-refreshed view of the reference cloud.

    A non-empty cloud is trusted for ``REFERENCE_CLOUD_TTL_S`` seconds and then
    re-read, so a long-lived owner picks up a refreshed cloud instead of keeping
    the one it first saw. An empty cloud or a failed read is never cached: the
    next call asks again, so an owner created before the first refresh starts
    using the cloud as soon as one exists (#5722). A failed re-read keeps the
    previous cloud.
    """

    def __init__(self, get_repository: Callable[[], Any | None]) -> None:
        self._get_repository = get_repository
        self._cloud: list[Any] | None = None
        self._loaded_at = 0.0
        self._stats: DistanceStats | None = None
        self._lock = threading.Lock()

    def context(self) -> tuple[list[Any], DistanceStats] | None:
        """The cloud and its z-score stats, or None when there is no usable cloud."""
        with self._lock:
            now = time.monotonic()
            if self._cloud is None or now - self._loaded_at >= REFERENCE_CLOUD_TTL_S:
                self._reload(now)
            if not self._cloud:
                return None
            if self._stats is None:
                self._stats = DistanceStats.from_references(self._cloud)
            return self._cloud, self._stats

    def target_spectrum(self, fingerprint: Any) -> dict[str, float] | None:
        """The soft k-NN target band shares for ``fingerprint``; None without a cloud."""
        context = self.context()
        if context is None:
            return None
        references, stats = context
        result = derive_target(fingerprint, references, stats)
        if result is None:
            return None
        debug(
            f"[Mastering] Target derived from {result.n_matched} references "
            f"(top: {result.top_ref_ids[:3]})"
        )
        return result.target

    def _reload(self, now: float) -> None:
        """Re-read the cloud; keep the previous one if the read fails."""
        repository = self._get_repository()
        if repository is None:
            return
        try:
            cloud = repository.get_reference_cloud()
        except Exception as e:
            debug(f"[Mastering] Failed to load reference cloud: {e}")
            return
        # `or None` so an empty cloud is re-read on the next call, never cached.
        self._cloud = cloud or None
        self._loaded_at = now
        self._stats = None  # stats belong to the cloud they were fitted on


__all__ = ["REFERENCE_CLOUD_TTL_S", "ReferenceCloud"]

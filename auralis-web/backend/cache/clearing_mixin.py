"""
Streamlined Cache Clearing
~~~~~~~~~~~~~~~~~~~~~~~~~~

Clearing one track or the whole cache, including the on-disk WAV chunk files
behind the entries (#5249/#5340). Split out of cache/manager.py (#5238).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import logging
from collections import OrderedDict
from pathlib import Path
from typing import Any

from core.encoding.wav_encoder import delete_chunk_files

from .models import CachedChunk, TrackCacheStatus

logger = logging.getLogger(__name__)


class CacheClearingMixin:
    """Per-track and full cache clearing.

    State is initialized by StreamlinedCacheManager.__init__, not here —
    declared here only so type checkers know this mixin depends on it.
    """

    chunk_dir: Path
    tier1_cache: dict[str, CachedChunk]
    tier2_cache: dict[str, CachedChunk]
    track_status: dict[int, TrackCacheStatus]
    mastering_recommendations: OrderedDict[tuple[int, float], tuple[float, dict[str, Any]]]
    _lock: asyncio.Lock

    async def clear_track(self, track_id: int) -> int:
        """Clear all cached data for a single track.

        Also deletes the underlying on-disk WAV chunk files (#5249) —
        clearing only the tier1/tier2 in-memory bookkeeping left
        ChunkPathCache's independent on-disk existence check
        (core/chunk_path_cache.py) still finding and serving the exact same
        bytes on the very next request, making the user's "clear and retry"
        troubleshooting lever a no-op for anything already on disk.

        Returns the number of cache entries removed.
        """
        async with self._lock:
            # Remove Tier 1 entries for this track
            t1_removed = [
                (k, v) for k, v in self.tier1_cache.items()
                if v.track_id == track_id
            ]
            for key, _ in t1_removed:
                del self.tier1_cache[key]

            # Remove Tier 2 entries for this track
            t2_removed = [
                (k, v) for k, v in self.tier2_cache.items()
                if v.track_id == track_id
            ]
            for key, _ in t2_removed:
                del self.tier2_cache[key]

            # Remove track status
            self.track_status.pop(track_id, None)

            removed = len(t1_removed) + len(t2_removed)
            chunk_paths = [chunk.chunk_path for _, chunk in (*t1_removed, *t2_removed)]

        # Disk I/O outside the lock — a slow or failing deletion must not
        # hold up other cache operations, and the in-memory bookkeeping
        # above is already committed regardless of the disk outcome.
        await asyncio.to_thread(self._unlink_chunk_files, chunk_paths)
        # #5340: the tiers only record what the streamlined worker cached.
        # Live playback and pre-warm write the same directory directly and
        # ChunkPathCache finds their files by name, so sweep every file for
        # this track too — otherwise the next play serves the same bytes.
        swept = await asyncio.to_thread(delete_chunk_files, self.chunk_dir, track_id)

        logger.info(
            f"Cleared cache for track {track_id} "
            f"({removed} entries, {swept} on-disk chunk file(s) swept)"
        )
        return removed

    async def clear_all(self) -> None:
        """Clear all caches, including the underlying on-disk WAV chunk
        files (#5249) — see clear_track()'s docstring for why this matters."""
        async with self._lock:
            chunk_paths = [c.chunk_path for c in self.tier1_cache.values()]
            chunk_paths.extend(c.chunk_path for c in self.tier2_cache.values())
            self.tier1_cache.clear()
            self.tier2_cache.clear()
            self.track_status.clear()
            self.mastering_recommendations.clear()

        await asyncio.to_thread(self._unlink_chunk_files, chunk_paths)
        logger.info(f"All caches cleared ({len(chunk_paths)} on-disk chunk file(s) removed)")

    @staticmethod
    def _unlink_chunk_files(chunk_paths: list[Path]) -> None:
        """Best-effort delete of the on-disk WAV files backing cache entries
        that were just dropped from the in-memory dicts. A file that's
        already gone (race with another cleanup pass, or was never
        actually written) is not an error — matches this cache's
        established graceful-degradation style (see
        CachedChunk.__post_init__)."""
        for path in chunk_paths:
            try:
                path.unlink()
            except FileNotFoundError:
                pass
            except OSError as e:
                logger.warning(f"Could not delete cached chunk file {path}: {e}")

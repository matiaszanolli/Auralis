"""
Throttled maintenance of the on-disk thumbnail cache (#6439).

Reaping dead writers' ``.tmp-*`` files and enforcing the size cap each walk the
whole thumbnail directory (a glob, then ``iterdir`` + ``stat`` + a sort). Running
both on every cache miss made a first scroll through a large library cost
O(albums x cached files). The sweep now runs once per N renders - reusing the
chunk cache's counter + non-blocking scan lock (:class:`ChunkDiskPruneMixin`) -
and once at startup, so orphans are still reaped and the cap is still enforced.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import threading
from pathlib import Path

from core.chunk_disk_prune import ChunkDiskPruneMixin
from core.thumbnail_cache import (
    THUMBNAIL_CACHE_MAX_BYTES,
    prune_thumbnail_cache,
    reap_orphan_temp_files,
)

# Thumbnails are tens of KiB against a 128 MiB cap, so the cache can overshoot by at most
# this many renders between sweeps - a few MiB, reclaimed by the next one.
THUMBNAIL_SWEEP_EVERY_N_RENDERS = 32


def sweep_thumbnail_cache(
    thumb_dir: Path, max_bytes: int = THUMBNAIL_CACHE_MAX_BYTES
) -> tuple[int, int]:
    """Reap orphaned temp files, then enforce the cap. Returns ``(files_deleted, bytes_reclaimed)``."""
    reap_orphan_temp_files(thumb_dir)
    return prune_thumbnail_cache(thumb_dir, max_bytes)


class ThumbnailSweeper(ChunkDiskPruneMixin):
    """Counts renders and sweeps the thumbnail directory every ``every``-th one.

    The throttle state is class-level, as in the chunk cache, so every instance
    coordinates; the locks here are this class's own, so thumbnail renders never
    count against (or skip) a chunk-cache prune.
    """

    _prune_lock = threading.Lock()
    _write_counter = 0
    _prune_scan_lock = threading.Lock()

    def __init__(
        self,
        every: int = THUMBNAIL_SWEEP_EVERY_N_RENDERS,
        max_bytes: int = THUMBNAIL_CACHE_MAX_BYTES,
    ) -> None:
        self._prune_every = every
        self._max_disk_bytes = max_bytes

    def note_render(self, thumb_dir: Path) -> None:
        """Record one rendered thumbnail; sweep when this is the N-th."""
        self._maybe_prune(thumb_dir)

    def _sweep(self, directory: Path) -> None:
        sweep_thumbnail_cache(directory, self._max_disk_bytes)


thumbnail_sweeper = ThumbnailSweeper()

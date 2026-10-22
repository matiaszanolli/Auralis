"""
On-disk chunk-cache reaper (split from chunk_cache_manager.py, #5833).

All ChunkedAudioProcessor instances write WAVs to the same directory, so the
size cap is enforced by one throttled, process-wide reaper. The throttle state
is class-level on purpose: ``ChunkCacheManager`` inherits it, and
``type(self)`` addressing keeps every instance coordinated.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

# On-disk chunk cache (/tmp/auralis_chunks) bound (#3834). Mirrors the 512 MB
# in-memory cap of SimpleChunkCache. All ChunkedAudioProcessor instances share
# the same directory, so the reaper is global and runs on a throttle.
MAX_CHUNK_DISK_BYTES = 512 * 1024 * 1024  # 512 MB
PRUNE_EVERY_N_WRITES = 32  # amortise the directory scan across writes


class ChunkDiskPruneMixin:
    """Throttled oldest-first pruning of the shared on-disk chunk directory."""

    _max_disk_bytes: int
    _prune_every: int

    # Shared across all instances so the on-disk reaper throttle and the prune
    # itself are coordinated for the single /tmp/auralis_chunks directory (#3834).
    # Two separate locks (#4838): _prune_lock guards ONLY the counter
    # test-and-reset (a few instructions) so every concurrent writer's throttle
    # check is fast regardless of what the reaper is doing. _prune_scan_lock
    # guards the scan+delete itself, acquired non-blockingly — a writer that
    # crosses the throttle while a scan is already running skips this trigger
    # rather than queuing behind the full directory walk (previously ALL
    # concurrent writers serialised behind whichever one ran the scan, since
    # a single lock covered both the counter and the scan).
    _prune_lock: "threading.Lock" = threading.Lock()
    _write_counter: int = 0
    _prune_scan_lock: "threading.Lock" = threading.Lock()

    def _maybe_prune(self, chunk_dir: Path) -> None:
        """Run the on-disk reaper once every `prune_every` cached paths.

        A class-level counter + lock coordinates the throttle across every
        ChunkCacheManager instance, since they all share one chunk directory.

        #4838: the counter test-and-reset and the scan itself are two
        separate locks. Holding one lock across both used to serialise every
        concurrent chunk-cache writer in the process behind whichever one
        triggered the 32nd write — the directory scan (iterdir + stat per
        file) and the unlink loop are typically sub-millisecond on warm
        local SSD, but on cold cache or network storage they multiply the
        shared-executor exhaustion #4727 describes by holding every other
        writer's thread hostage too, not just the scanning one.
        """
        cls = type(self)
        with cls._prune_lock:
            cls._write_counter += 1
            if cls._write_counter < self._prune_every:
                return
            cls._write_counter = 0

        # Outside _prune_lock now: another writer's counter check above is
        # never blocked by the scan below, no matter how long it takes.
        if not cls._prune_scan_lock.acquire(blocking=False):
            # A scan is already in flight (a different writer crossed the
            # threshold first, or a slow prior scan is still running).
            # Skip rather than queue behind it — self-correcting on the next
            # PRUNE_EVERY_N_WRITES trigger, and non-silent so a persistently
            # skipped prune (a scan that never finishes) is visible.
            logger.debug(
                f"Chunk-cache prune already in progress for {chunk_dir}; "
                f"skipping this trigger"
            )
            return
        try:
            self.prune_chunk_directory(chunk_dir, self._max_disk_bytes)
        finally:
            cls._prune_scan_lock.release()

    @staticmethod
    def prune_chunk_directory(chunk_dir: Path, max_bytes: int) -> tuple[int, int]:
        """Delete the oldest files in *chunk_dir* (by mtime) until the directory's
        total size is within *max_bytes* (#3834).

        mtime-ordering means just-written chunks survive and the coldest tracks'
        WAVs are reclaimed first. Deleting a file another stream still references
        is safe: that stream's get_cached_chunk_path re-checks existence and
        treats a missing file as a cache miss (reprocess). Best-effort — per-file
        errors are logged, never raised.

        Returns (files_deleted, bytes_reclaimed).
        """
        try:
            entries: list[tuple[float, int, Path]] = []
            total = 0
            for p in chunk_dir.iterdir():
                if not p.is_file():
                    continue
                try:
                    st = p.stat()
                except OSError:
                    continue
                entries.append((st.st_mtime, st.st_size, p))
                total += st.st_size
        except OSError as e:
            logger.debug(f"Chunk-dir prune skipped ({chunk_dir}): {e}")
            return (0, 0)

        if total <= max_bytes:
            return (0, 0)

        entries.sort(key=lambda e: e[0])  # oldest mtime first
        deleted = 0
        reclaimed = 0
        for _mtime, size, p in entries:
            if total <= max_bytes:
                break
            try:
                p.unlink()
                deleted += 1
                reclaimed += size
                total -= size
            except OSError as e:
                logger.warning(f"Could not prune cached chunk {p}: {e}")

        if deleted:
            logger.info(
                f"Pruned {deleted} cached chunk file(s) from {chunk_dir}, "
                f"reclaimed {reclaimed / 1024 / 1024:.1f} MB (cap {max_bytes / 1024 / 1024:.0f} MB)"
            )
        return (deleted, reclaimed)

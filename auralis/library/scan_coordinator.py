"""
Scan concurrency accounting (split from database.py, #5837).

One object per :class:`~auralis.library.database.LibraryDatabase`, shared by every
caller because every caller constructs a fresh ``LibraryScanner`` per
invocation -- an instance attribute on the scanner would never be seen by a
second, overlapping scan. It owns three pieces of state, each behind its own
lock:

* the scan-slot counter and the destructive-operation flag (#2438, #4816),
  guarded by the SAME lock so "is a scan running?" and "may a scan start?" have
  one answer, not two that can disagree under a race;
* the set of directories currently being scanned (#3455 / #4509).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import threading
from collections.abc import Callable
from typing import Any


class ScanCoordinator:
    """Slot, path-reservation and exclusive-access accounting for library scans."""

    def __init__(self, get_settings: Callable[[], Any]) -> None:
        """
        Args:
            get_settings: Returns the current settings row (or None). Read on
                every :meth:`try_acquire_scan_slot` so a changed
                ``max_concurrent_scans`` applies to the next scan.
        """
        self._get_settings = get_settings
        # Scan concurrency tracking (#2438)
        self._scan_slots_lock = threading.Lock()
        self._active_scans: int = 0
        # Destructive-operation exclusion (#4816): POST /api/library/reset holds
        # this while it deletes every content row.
        self._exclusive_access: bool = False
        # Per-directory scan dedup (#3455 / #4509).
        self._active_scan_paths_lock = threading.Lock()
        self._active_scan_paths: set[str] = set()

    def try_acquire_scan_slot(self) -> tuple[bool, int]:
        """
        Atomically reserve a concurrent scan slot (#2438).

        Reads max_concurrent_scans from settings on every call so that user
        changes take effect for the next scan without a restart.

        Returns:
            (acquired, max_allowed)
            acquired=False means the caller must not start a scan.
        """
        try:
            settings = self._get_settings()
            max_scans: int = max(1, (settings.max_concurrent_scans or 1) if settings else 1)
        except Exception:
            max_scans = 1  # conservative fallback if settings are unavailable

        with self._scan_slots_lock:
            # A destructive reset owns the library; starting a scan now would
            # re-insert rows the reset is deleting (#4816).
            if self._exclusive_access:
                return False, max_scans
            if self._active_scans >= max_scans:
                return False, max_scans
            self._active_scans += 1
            return True, max_scans

    def release_scan_slot(self) -> None:
        """Release a slot previously acquired by try_acquire_scan_slot()."""
        with self._scan_slots_lock:
            self._active_scans = max(0, self._active_scans - 1)

    def try_reserve_scan_paths(self, paths: list[str]) -> list[str]:
        """
        Atomically reserve directory paths for an exclusive scan (#3455 / #4509).

        Args:
            paths: Normalized (os.path.normpath(os.path.abspath(...))) directory
                paths the caller is about to scan.

        Returns:
            The subset of `paths` already reserved by another in-flight scan.
            Empty means none clashed and all of `paths` are now reserved for
            the caller — who must call `release_scan_paths(paths)` when done,
            success or failure alike.
        """
        with self._active_scan_paths_lock:
            clashing = [p for p in paths if p in self._active_scan_paths]
            if clashing:
                return clashing
            self._active_scan_paths.update(paths)
            return []

    def release_scan_paths(self, paths: list[str]) -> None:
        """Release paths previously reserved by try_reserve_scan_paths()."""
        with self._active_scan_paths_lock:
            self._active_scan_paths.difference_update(paths)

    def try_begin_exclusive_access(self) -> bool:
        """Atomically reserve the library for a destructive operation (#4816).

        Granted only when no scan holds a slot, and while held it makes
        ``try_acquire_scan_slot()`` refuse every new scan — so the manual-scan
        route (``POST /api/library/scan``), the auto-scanner, and the reset
        route all arbitrate through this one counter instead of each keeping
        its own idea of whether a scan is in flight.

        A transient manual scan is not a registered background worker, so
        ``stop_background_workers()`` cannot pause it; without this guard a
        confirmed reset could delete everything and then be silently undone by
        the scan thread's next insert.

        Returns:
            True if exclusive access was granted — the caller MUST then call
            ``end_exclusive_access()`` in a ``finally``. False means a scan is
            active and the caller must not proceed.
        """
        with self._scan_slots_lock:
            if self._exclusive_access or self._active_scans > 0:
                return False
            self._exclusive_access = True
            return True

    def end_exclusive_access(self) -> None:
        """Release exclusive access taken by ``try_begin_exclusive_access()``."""
        with self._scan_slots_lock:
            self._exclusive_access = False

    def is_scanning(self) -> bool:
        """True if at least one scan currently holds a slot.

        Live read of the same counter try_acquire_scan_slot()/
        release_scan_slot() maintain — used by GET /api/library/scan/status
        so a client that reconnects mid-scan (or after one finished while it
        was offline) can resync `isScanning` instead of relying solely on a
        WebSocket broadcast it may have missed (#4821).
        """
        with self._scan_slots_lock:
            return self._active_scans > 0

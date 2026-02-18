"""
cleanup_missing_files Cursor-Pagination Regression Test
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Regression guard for issue #2242:
  cleanup_missing_files() used offset-based pagination while deleting rows
  inside the same loop. Each delete shifted the table, causing the next page
  to skip over rows that slid into the already-visited offset range. With 100
  tracks and a batch_size of 10, up to half the missing tracks could survive
  uncleaned.

Fix: use ID-based cursor pagination (filter(Track.id > last_id)) so that
deletes inside a batch never affect the position of subsequent batches.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import sys
from pathlib import Path

import pytest

# Ensure project root is importable.
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestCleanupMissingFilesPagination:
    """
    Verify that cleanup_missing_files removes ALL tracks whose files are
    missing, even when deletions span multiple batches (issue #2242).
    """

    def _add_track(self, track_repository, filepath: str, title: str) -> object:
        """Insert a single track and return the ORM object."""
        return track_repository.add({
            "title": title,
            "filepath": filepath,
            "duration": 30.0,
            "sample_rate": 44100,
            "channels": 2,
            "format": "WAV",
        })

    def _count(self, track_repository) -> int:
        """Return the total number of tracks in the repository."""
        _, total = track_repository.get_all(limit=1, offset=0)
        return total

    def test_all_missing_tracks_removed_across_batches(
        self, track_repository, tmp_path
    ):
        """
        Create 100 tracks: 50 backed by real files, 50 pointing at nonexistent
        paths. Run cleanup with batch_size=10 (forcing 10 batches) and assert
        that ALL 50 ghost tracks are removed.

        With offset-based pagination the bug manifests as only ~25 of the 50
        missing tracks being removed; cursor pagination removes all 50.
        """
        TOTAL = 100
        MISSING = 50  # every other track points at a nonexistent file

        real_files = []
        for i in range(TOTAL):
            if i % 2 == 0:
                # Real file: create an empty placeholder on disk.
                p = tmp_path / f"track_{i:03d}.wav"
                p.touch()
                filepath = str(p)
                real_files.append(filepath)
            else:
                # Ghost path: never created.
                filepath = str(tmp_path / f"missing_{i:03d}.wav")

            self._add_track(track_repository, filepath, f"Track {i:03d}")

        # Sanity check: all 100 inserted.
        assert self._count(track_repository) == TOTAL

        # Run cleanup with a small batch_size to exercise multi-batch paths.
        removed = track_repository.cleanup_missing_files(batch_size=10)

        assert removed == MISSING, (
            f"Expected {MISSING} tracks removed, got {removed}. "
            "Offset-based pagination skips rows when deletes shift the table "
            "(issue #2242). Use ID-cursor: filter(Track.id > last_id)."
        )

        remaining = self._count(track_repository)
        assert remaining == TOTAL - MISSING, (
            f"Expected {TOTAL - MISSING} tracks remaining, found {remaining}."
        )

    def test_no_tracks_removed_when_all_files_exist(
        self, track_repository, tmp_path
    ):
        """
        When every track has a real file, cleanup_missing_files must return 0
        and leave the library intact.
        """
        for i in range(20):
            p = tmp_path / f"real_{i:03d}.wav"
            p.touch()
            self._add_track(track_repository, str(p), f"Real Track {i:03d}")

        removed = track_repository.cleanup_missing_files(batch_size=5)

        assert removed == 0
        assert self._count(track_repository) == 20

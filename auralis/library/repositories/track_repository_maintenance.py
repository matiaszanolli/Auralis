"""
Track Repository — Maintenance Mixin
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Playback-stat and housekeeping concerns for :class:`TrackRepository`, split
out of ``track_repository.py`` (#4511): recording plays, toggling favorite
status, backfilling the ``filepath_key`` column, and cleaning up rows whose
audio file has gone missing.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Any, cast

from sqlalchemy import CursorResult, delete, func, select, update
from sqlalchemy.orm import Session

from ...utils.logging import debug, error, info
from ..models import Track
from ..path_key import make_filepath_key
from .base import BaseRepository


class TrackRepositoryMaintenanceMixin(BaseRepository):
    """Play-count/favorite tracking and background housekeeping operations."""

    def record_play(self, track_id: int) -> None:
        """Record a track play.

        Atomic at the SQL level (#5157): a prior SELECT-then-Python-increment
        (`track.play_count = (track.play_count or 0) + 1`) raced under
        concurrent plays -- two sessions could read the same starting count
        and each write back count+1, losing one increment. UPDATE ... SET
        play_count = play_count + 1 is a single statement the database
        applies atomically per row, so concurrent calls always sum correctly
        regardless of interleaving. coalesce() covers the (already-defensive)
        case of a NULL play_count from a pre-migration row.

        A missing ``track_id`` is a no-op (rowcount 0), matching the previous
        behaviour; nothing is returned so callers keep their current contract.
        """
        session = self.get_session()
        try:
            # cast(): session.execute() is typed Result, which has no
            # rowcount; the UPDATE path really returns a CursorResult.
            result = cast(CursorResult[Any], session.execute(
                update(Track)
                .where(Track.id == track_id)
                .values(
                    play_count=func.coalesce(Track.play_count, 0) + 1,
                    last_played=func.now(),
                )
            ))
            session.commit()
            if result.rowcount:
                debug(f"Recorded play for track id={track_id}")
        except Exception as e:
            session.rollback()
            error(f"Failed to record play: {e}")
        finally:
            session.close()

    def set_favorite(self, track_id: int, favorite: bool = True) -> bool:
        """Set track favorite status

        Returns:
            True if the track was found and updated, False if no track
            matched track_id.

        Raises:
            Exception: If the commit fails (#4763 — callers must be able to
                distinguish "not found" from "write failed" instead of both
                looking like silent success).
        """
        session = self.get_session()
        try:
            track = session.execute(select(Track).where(Track.id == track_id)).scalars().first()
            if not track:
                return False
            track.favorite = favorite
            session.commit()
            debug(f"Set favorite={favorite} for track: {track.title}")
            return True
        except Exception as e:
            session.rollback()
            error(f"Failed to set favorite: {e}")
            raise
        finally:
            session.close()

    def backfill_filepath_keys(self, batch_size: int = 500) -> int:
        """Populate ``filepath_key`` for rows the v017->v018 migration left NULL.

        The migration adds the column but cannot fill it: the key is case-folded
        only on case-insensitive platforms, and SQLite's ASCII-only ``lower()``
        disagrees with ``str.casefold()`` on non-ASCII paths. Doing it here keeps
        ``make_filepath_key`` the single authority (#4842).

        Idempotent and cheap once done — the WHERE clause matches nothing on
        every subsequent start, so this costs one indexed count.

        Returns:
            How many rows were backfilled.
        """
        updated = 0
        with self._session_scope() as session:
            while True:
                rows = session.execute(
                    select(Track.id, Track.filepath)
                    .where(Track.filepath_key.is_(None))
                    .limit(batch_size)
                ).all()
                if not rows:
                    break
                for track_id, filepath in rows:
                    session.execute(
                        update(Track)
                        .where(Track.id == track_id)
                        .values(filepath_key=make_filepath_key(filepath))
                    )
                    updated += 1
                session.commit()

        if updated:
            info(f"Backfilled filepath_key for {updated} track(s) (#4842)")
        return updated

    def cleanup_missing_files(self, batch_size: int = 1000) -> int:
        """
        Remove tracks with missing audio files from the database.

        Processes in batches to keep memory bounded regardless of library size.

        Args:
            batch_size: Number of tracks to load per batch

        Returns:
            Number of tracks removed

        Raises:
            Exception: If cleanup fails
        """
        from pathlib import Path

        session = self.get_session()
        try:
            removed_count = 0
            last_id = 0  # cursor: fetch rows with id > last_id (issue #2242)

            while True:
                rows = session.execute(
                    select(Track.id, Track.filepath)
                    .where(Track.id > last_id)
                    .order_by(Track.id)
                    .limit(batch_size)
                ).all()
                if not rows:
                    break

                missing_ids = []
                for row in rows:
                    filepath_path = Path(str(row.filepath))
                    # If the parent directory itself is absent the volume is
                    # likely unmounted (NFS/SMB). Skip this file rather than
                    # permanently deleting it from the library (fixes #2525).
                    if not filepath_path.parent.exists():
                        debug(f"Parent directory inaccessible, skipping: {filepath_path.parent}")
                        continue
                    if not filepath_path.exists():
                        missing_ids.append(row.id)

                if missing_ids:
                    # Re-verify paths immediately before deletion to narrow the
                    # TOCTOU window (a file could reappear between the initial
                    # exists() check and this point). Fixes #3310.
                    # Batch-fetch filepaths in a single IN query rather than one
                    # session.get() per id, keeping re-verification O(batches)
                    # instead of O(missing tracks) (fixes #4223).
                    recheck_rows = session.execute(
                        select(Track.id, Track.filepath)
                        .where(Track.id.in_(missing_ids))
                    ).all()
                    still_missing = [
                        row.id
                        for row in recheck_rows
                        if not Path(str(row.filepath)).exists()
                    ]
                    if still_missing:
                        session.execute(
                            delete(Track).where(Track.id.in_(still_missing))
                        )
                        session.commit()
                        removed_count += len(still_missing)

                last_id = rows[-1].id  # advance cursor past this batch

            debug(f"Removed {removed_count} tracks with missing files")
            return removed_count
        except Exception as e:
            session.rollback()
            error(f"Failed to cleanup missing files: {e}")
            raise
        finally:
            session.close()

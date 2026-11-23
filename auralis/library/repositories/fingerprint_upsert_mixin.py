"""
Fingerprint Upsert Mixin
~~~~~~~~~~~~~~~~~~~~~~~~

Raw-SQL ``INSERT ... ON CONFLICT DO UPDATE`` write paths for
``FingerprintRepository`` — ``upsert()``, used by the extraction pipeline for
single-round-trip writes. Extracted from
fingerprint_repository.py (#4511); split out from the sibling
``FingerprintCrudMixin`` (ORM add/update/delete) to keep both modules under
the project's per-file line budget.

Mixed into ``FingerprintRepository`` alongside ``FingerprintCrudMixin``,
``FingerprintQueryMixin`` and ``FingerprintSimilarityMixin`` — same
mixin-composes-BaseRepository layout as ``TrackRepository``'s
``track_repository_*.py`` split (#4511): each mixin inherits
``BaseRepository`` directly for ``get_session``/``_session_scope`` rather
than declaring a bare type annotation for them, so multiple sibling mixins
sharing the same base don't trip mypy's "incompatible definition in base
class" check when composed together on the facade.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from typing import Any, cast

from sqlalchemy import select, text
from sqlalchemy.orm import Session
from sqlalchemy.engine import CursorResult

from ...utils.logging import info, warning
from ...__version__ import FINGERPRINT_ALGORITHM_VERSION
from ..models import TrackFingerprint
from .base import BaseRepository
from .fingerprint_shared import PLACEHOLDER_LUFS_SENTINEL, _validate_fingerprint_columns


def _persisted_row(session: Session, track_id: int) -> TrackFingerprint | None:
    """The row as stored, detached: the id, timestamps, fingerprint_blob and fingerprint_version
    the raw INSERT/ON CONFLICT wrote, not a transient object that has none of them (#5539)."""
    row = session.scalars(select(TrackFingerprint).filter_by(track_id=track_id)).one_or_none()
    if row is not None:
        session.expunge(row)
    return row


class FingerprintUpsertMixin(BaseRepository):
    """Single-round-trip upsert operations for fingerprint rows."""

    def upsert(
        self,
        track_id: int,
        fingerprint_data: dict[str, float],
        expected_filepath: str | None = None,
    ) -> TrackFingerprint | None:
        """
        Insert or update a fingerprint (upsert operation)

        Optimized to do single database round-trip with immediate session cleanup

        Args:
            track_id: ID of the track
            fingerprint_data: Dictionary with all 25 fingerprint dimensions
            expected_filepath: The filepath the fingerprint was computed from.
                When given, the write happens only if ``track_id`` still has
                that filepath (checked in the same statement). A slow
                extraction can outlive a library reset, after which the id may
                belong to a different, rescanned file; storing there would
                attach this file's 25D fingerprint to the wrong track (#6095).

        Returns:
            TrackFingerprint object if successful, None if failed or if the
            track's filepath no longer matches ``expected_filepath``
        """
        # Validate column names before acquiring a session so ValueError
        # propagates to the caller instead of being swallowed (#2286).
        cols = list(fingerprint_data.keys())
        _validate_fingerprint_columns(cols)
        # That lufs marks a claim row ("extraction in progress"), which every reader hides and
        # each startup deletes; a fingerprint carrying it would vanish the same way (#6524).
        if fingerprint_data.get('lufs') == PLACEHOLDER_LUFS_SENTINEL:
            raise ValueError("lufs equals the fingerprint-claim sentinel; refusing to store it as a fingerprint")
        cols_str = ', '.join(cols)
        named_placeholders = ', '.join([f':{col}' for col in cols])

        # Use INSERT ... ON CONFLICT DO UPDATE rather than INSERT OR REPLACE.
        # REPLACE deletes the existing row and inserts a new one, which:
        #   - resets the `id` PK to a fresh auto-increment value
        #   - wipes `created_at` and any column not listed (e.g. the
        #     reference flags, or the legacy quantized `fingerprint_blob`)
        #   - causes a race window between the implicit DELETE and INSERT
        # ON CONFLICT updates only the listed columns in-place and is also
        # atomic, which closes the concurrent-insert race (#3467, #3459).
        #
        # On INSERT we must supply `fingerprint_version`, `is_reference` and
        # `reference_weight` because they are NOT NULL and their defaults are
        # Python-side ORM defaults (not SQL defaults on every install), so a
        # raw INSERT does not see them (#5530). On UPDATE we refresh the 25
        # dimension columns AND `fingerprint_version` — #5572: reads treat a
        # row as usable only when its version >= FINGERPRINT_ALGORITHM_VERSION,
        # so a rewrite that left the old version kept the row permanently
        # invisible to the cache (the "self-healing" outdated-row rewrite
        # never healed). `fingerprint_blob` and the reference flag/weight
        # stay as whatever set them (a dimension refresh must never clobber
        # reference-cloud membership).
        update_clause = ', '.join(
            f"{col} = excluded.{col}" for col in cols
        ) + ', fingerprint_version = excluded.fingerprint_version, updated_at = CURRENT_TIMESTAMP'

        with self._guarded(f"Failed to upsert fingerprint for track {track_id}") as session:
            params: dict[str, Any] = {
                'track_id': track_id,
                'fp_version': FINGERPRINT_ALGORITHM_VERSION,
                'is_reference': 0,
                'reference_weight': 0.0,
                **fingerprint_data,
            }

            values = (
                ":track_id, :fp_version, :is_reference, :reference_weight, "
                f"CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, {named_placeholders}"
            )
            if expected_filepath is None:
                source = f"VALUES ({values})"
            else:
                # INSERT ... SELECT ... WHERE (the WHERE also keeps SQLite from
                # reading ON CONFLICT as part of the SELECT).
                source = f"SELECT {values} FROM tracks WHERE id = :track_id AND filepath = :expected_filepath"
                params['expected_filepath'] = expected_filepath

            # cast(): session.execute() is typed Result, which has no rowcount.
            result = cast(CursorResult[Any], session.execute(
                text(
                    f"INSERT INTO track_fingerprints "
                    f"(track_id, fingerprint_version, is_reference, reference_weight, "
                    f"created_at, updated_at, {cols_str}) "
                    f"{source} "
                    f"ON CONFLICT (track_id) DO UPDATE SET {update_clause}"
                ),
                params,
            ))
            session.commit()
            if expected_filepath is not None and result.rowcount == 0:
                warning(
                    f"Fingerprint for track {track_id} not stored: the track is gone "
                    f"or no longer at {expected_filepath}"
                )
                return None

            fingerprint = _persisted_row(session, track_id)
            info(f"Upserted fingerprint for track {track_id}")
            return fingerprint
        return None


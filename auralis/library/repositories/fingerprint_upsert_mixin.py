"""
Fingerprint Upsert Mixin
~~~~~~~~~~~~~~~~~~~~~~~~

Raw-SQL ``INSERT ... ON CONFLICT DO UPDATE`` write paths for
``FingerprintRepository`` — ``upsert()`` and ``store_fingerprint()``, used by
the extraction pipeline for single-round-trip writes. Extracted from
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
from ..fingerprint_quantizer import FingerprintQuantizer
from ..models import TrackFingerprint
from .base import BaseRepository
from .fingerprint_shared import _validate_fingerprint_columns


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
        cols_str = ', '.join(cols)
        named_placeholders = ', '.join([f':{col}' for col in cols])

        # Use INSERT ... ON CONFLICT DO UPDATE rather than INSERT OR REPLACE.
        # REPLACE deletes the existing row and inserts a new one, which:
        #   - resets the `id` PK to a fresh auto-increment value
        #   - wipes `created_at` and any column not listed (e.g. the
        #     quantized `fingerprint_blob` set by store_fingerprint)
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

    def store_fingerprint(
        self,
        track_id: int,
        sub_bass_pct: float, bass_pct: float, low_mid_pct: float, mid_pct: float,
        upper_mid_pct: float, presence_pct: float, air_pct: float,
        lufs: float, crest_db: float, bass_mid_ratio: float,
        tempo_bpm: float, rhythm_stability: float, transient_density: float, silence_ratio: float,
        spectral_centroid: float, spectral_rolloff: float, spectral_flatness: float,
        harmonic_ratio: float, pitch_stability: float, chroma_energy: float,
        dynamic_range_variation: float, loudness_variation_std: float, peak_consistency: float,
        stereo_width: float, phase_correlation: float,
    ) -> TrackFingerprint | None:
        """
        Store fingerprint with automatic quantization (Phase 3A).

        Stores both the quantized blob (25 bytes) and the float values for backward compatibility.

        Args:
            track_id: Track ID
            (25 float parameters for each fingerprint dimension)

        Returns:
            TrackFingerprint object if successful, None if failed
        """
        # Build fingerprint dict from explicit named parameters (keys are always
        # known here, but validate anyway for defense-in-depth — #2286).
        fingerprint_dict = {
            'sub_bass_pct': sub_bass_pct, 'bass_pct': bass_pct, 'low_mid_pct': low_mid_pct,
            'mid_pct': mid_pct, 'upper_mid_pct': upper_mid_pct, 'presence_pct': presence_pct,
            'air_pct': air_pct, 'lufs': lufs, 'crest_db': crest_db, 'bass_mid_ratio': bass_mid_ratio,
            'tempo_bpm': tempo_bpm, 'rhythm_stability': rhythm_stability, 'transient_density': transient_density,
            'silence_ratio': silence_ratio, 'spectral_centroid': spectral_centroid,
            'spectral_rolloff': spectral_rolloff, 'spectral_flatness': spectral_flatness,
            'harmonic_ratio': harmonic_ratio, 'pitch_stability': pitch_stability, 'chroma_energy': chroma_energy,
            'dynamic_range_variation': dynamic_range_variation, 'loudness_variation_std': loudness_variation_std,
            'peak_consistency': peak_consistency, 'stereo_width': stereo_width, 'phase_correlation': phase_correlation,
        }

        # Validate before acquiring a session so ValueError reaches the caller (#2286).
        cols = list(fingerprint_dict.keys())
        _validate_fingerprint_columns(cols)
        cols_str = ', '.join(cols)
        named_placeholders = ', '.join([f':{col}' for col in cols])

        # ON CONFLICT DO UPDATE keeps the `id` PK stable and the existing
        # `created_at` intact (cf. #3467 sibling); only the listed columns
        # are written. fingerprint_blob and fingerprint_version are listed
        # here, so they're always refreshed on update. is_reference /
        # reference_weight are INSERT-only (#5530): a store must not clobber
        # reference-cloud membership set by the seeder.
        all_cols = cols + ['fingerprint_blob', 'fingerprint_version']
        update_clause = ', '.join(f"{col} = excluded.{col}" for col in all_cols) + ', updated_at = CURRENT_TIMESTAMP'

        with self._guarded(f"Failed to store fingerprint for track {track_id}") as session:
            # Quantize fingerprint
            quantized_blob = FingerprintQuantizer.quantize(fingerprint_dict)

            params: dict[str, Any] = {
                'track_id': track_id,
                'fingerprint_blob': quantized_blob,
                'fp_version': FINGERPRINT_ALGORITHM_VERSION,
                'is_reference': 0,
                'reference_weight': 0.0,
                **fingerprint_dict,
            }

            session.execute(
                text(f"""
                    INSERT INTO track_fingerprints
                    (track_id, {cols_str}, fingerprint_blob, fingerprint_version, is_reference, reference_weight,
                     created_at, updated_at)
                    VALUES (:track_id, {named_placeholders}, :fingerprint_blob, :fp_version, :is_reference, :reference_weight,
                            CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    ON CONFLICT (track_id) DO UPDATE SET {update_clause}
                """),
                params,
            )
            session.commit()

            fingerprint = _persisted_row(session, track_id)
            info(f"Stored fingerprint for track {track_id} (quantized blob: 25 bytes)")
            return fingerprint
        return None

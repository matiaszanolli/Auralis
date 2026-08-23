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
:license: GPLv3, see LICENSE for more details.
"""

from typing import Any

from sqlalchemy import text

from ...utils.logging import error, info
from ...__version__ import FINGERPRINT_ALGORITHM_VERSION
from ..fingerprint_quantizer import FingerprintQuantizer
from ..models import TrackFingerprint
from .base import BaseRepository
from .fingerprint_shared import _validate_fingerprint_columns


class FingerprintUpsertMixin(BaseRepository):
    """Single-round-trip upsert operations for fingerprint rows."""

    def upsert(self, track_id: int, fingerprint_data: dict[str, float]) -> TrackFingerprint | None:
        """
        Insert or update a fingerprint (upsert operation)

        Optimized to do single database round-trip with immediate session cleanup

        Args:
            track_id: ID of the track
            fingerprint_data: Dictionary with all 25 fingerprint dimensions

        Returns:
            TrackFingerprint object if successful, None if failed
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
        # On INSERT we must supply `fingerprint_version` because it is
        # NOT NULL and its default is a Python-side ORM default (not a
        # SQL default), so raw INSERT does not see it. On UPDATE we only
        # refresh the 25 dimension columns — `fingerprint_blob` and
        # `fingerprint_version` stay as whatever store_fingerprint set.
        update_clause = ', '.join(f"{col} = excluded.{col}" for col in cols)

        with self._session_scope() as session:
            try:
                params: dict[str, Any] = {
                    'track_id': track_id,
                    'fp_version': FINGERPRINT_ALGORITHM_VERSION,
                    **fingerprint_data,
                }

                session.execute(
                    text(
                        f"INSERT INTO track_fingerprints (track_id, fingerprint_version, {cols_str}) "
                        f"VALUES (:track_id, :fp_version, {named_placeholders}) "
                        f"ON CONFLICT (track_id) DO UPDATE SET {update_clause}"
                    ),
                    params,
                )
                session.commit()

                fingerprint = TrackFingerprint(track_id=track_id, **fingerprint_data)
                info(f"Upserted fingerprint for track {track_id}")
                return fingerprint

            except Exception as e:
                session.rollback()
                error(f"Failed to upsert fingerprint for track {track_id}: {e}")
                return None
            finally:
                session.expunge_all()

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
        # here, so they're always refreshed on update.
        all_cols = cols + ['fingerprint_blob', 'fingerprint_version']
        update_clause = ', '.join(f"{col} = excluded.{col}" for col in all_cols)

        with self._session_scope() as session:
            try:
                # Quantize fingerprint
                quantized_blob = FingerprintQuantizer.quantize(fingerprint_dict)

                params: dict[str, Any] = {
                    'track_id': track_id,
                    'fingerprint_blob': quantized_blob,
                    'fp_version': FINGERPRINT_ALGORITHM_VERSION,
                    **fingerprint_dict,
                }

                session.execute(
                    text(f"""
                        INSERT INTO track_fingerprints
                        (track_id, {cols_str}, fingerprint_blob, fingerprint_version)
                        VALUES (:track_id, {named_placeholders}, :fingerprint_blob, :fp_version)
                        ON CONFLICT (track_id) DO UPDATE SET {update_clause}
                    """),
                    params,
                )
                session.commit()

                info(f"Stored fingerprint for track {track_id} (quantized blob: 25 bytes)")
                return None

            except Exception as e:
                session.rollback()
                error(f"Failed to store fingerprint for track {track_id}: {e}")
                return None
            finally:
                session.expunge_all()

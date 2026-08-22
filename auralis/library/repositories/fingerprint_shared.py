"""
Fingerprint Repository — Shared Constants & Guards
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Module-scope constants and pure helper functions shared by every
fingerprint-repository concern module — the CRUD, query, and
similarity/reference-cloud mixins, plus the ``FingerprintRepository`` facade
itself (#4511 split).

Kept in its own module (rather than in the facade) so no mixin needs to
import ``fingerprint_repository`` directly, which would create a circular
import: the facade imports the mixins, so the mixins cannot import back from
the facade.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Any

from sqlalchemy import and_

from ...__version__ import FINGERPRINT_ALGORITHM_VERSION
from ..models import TrackFingerprint

# Whitelist of columns callers may supply to upsert() / store_fingerprint().
# Derived from the SQLAlchemy model so it stays in sync automatically (#2286).
# Excludes auto-managed columns (PK, timestamps) that callers must never set.
_FINGERPRINT_WRITABLE_COLS: frozenset[str] = (
    frozenset(TrackFingerprint.__table__.columns.keys())
    - {'id', 'created_at', 'updated_at'}
)


# Sentinel `lufs` value written by
# FingerprintSchedulerRepository.claim_next_unfingerprinted_track() for its
# placeholder row (all dimensions zeroed) the instant a track is claimed for
# processing — never a real measurement (real LUFS values are always > -100).
PLACEHOLDER_LUFS_SENTINEL = -100.0


def _current_fingerprint_clause() -> Any:
    """SQLAlchemy WHERE-clause condition matching only complete, current-
    algorithm-version fingerprint rows.

    Excludes the in-progress claim placeholder (``lufs`` sentinel) and rows
    left behind by an older fingerprinting algorithm version — the same two
    conditions ``is_current_fingerprint()`` checks on an already-fetched row.
    Without this, every unguarded read (exists/get_by_track_id/get_all/
    get_by_track_ids/get_by_multi_dimension_range) would hand mid-fingerprint
    or stale-version rows to callers (similarity search, the K-NN graph
    builder, the normalizer's percentile fit, fingerprint-display endpoints)
    as if they were valid (#4822).
    """
    return and_(
        TrackFingerprint.lufs != PLACEHOLDER_LUFS_SENTINEL,
        TrackFingerprint.fingerprint_version >= FINGERPRINT_ALGORITHM_VERSION,
    )


def is_current_fingerprint(fp: TrackFingerprint | None) -> bool:
    """Python-level mirror of ``_current_fingerprint_clause()`` for callers
    that already hold a fetched row rather than building a query — e.g.
    ``FingerprintService._load_from_database()``'s single-row mastering-path
    cache lookup (#4822). Keep both in sync: same two conditions, same
    constants.
    """
    if fp is None:
        return False
    if getattr(fp, 'lufs', PLACEHOLDER_LUFS_SENTINEL) == PLACEHOLDER_LUFS_SENTINEL:
        return False
    row_version = int(getattr(fp, 'fingerprint_version', 1) or 1)
    return row_version >= FINGERPRINT_ALGORITHM_VERSION


def _validate_fingerprint_columns(cols: list[str]) -> None:
    """Raise ValueError if any column name is not in the allowed whitelist.

    Prevents SQL injection via f-string column interpolation (#2286).

    Args:
        cols: Column names to validate before interpolation into SQL

    Raises:
        ValueError: If any column is not in _FINGERPRINT_WRITABLE_COLS
    """
    bad = set(cols) - _FINGERPRINT_WRITABLE_COLS
    if bad:
        raise ValueError(
            f"Invalid fingerprint column name(s): {sorted(bad)}. "
            f"Allowed: {sorted(_FINGERPRINT_WRITABLE_COLS)}"
        )

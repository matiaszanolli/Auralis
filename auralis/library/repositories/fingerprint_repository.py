"""
Fingerprint Repository
~~~~~~~~~~~~~~~~~~~~~

Data access layer for track fingerprint operations.

Public facade (#4511) composing four per-concern mixins:

- ``FingerprintCrudMixin`` — add/update/delete (ORM)
- ``FingerprintUpsertMixin`` — upsert/store_fingerprint (raw-SQL, single
  round-trip writes used by the extraction pipeline)
- ``FingerprintQueryMixin`` — single/bulk lookups, listing, counting, exists
- ``FingerprintSimilarityMixin`` — reference-cloud flags/weights and
  dimension-range pre-filtering for similarity search

Status/stats/crash-recovery queries were already split out to
``FingerprintStatsRepository`` (#4108); scheduler-claim queries live in the
separate, pre-existing ``FingerprintSchedulerRepository``. This class keeps
only thin delegators to the stats repo so existing callers that hold a
``FingerprintRepository`` (the fingerprint extractor, similarity/fingerprint
routers) keep working unchanged.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Any
from collections.abc import Callable

from sqlalchemy.orm import Session

from .fingerprint_crud_mixin import FingerprintCrudMixin
from .fingerprint_query_mixin import FingerprintQueryMixin
from .fingerprint_shared import (
    PLACEHOLDER_LUFS_SENTINEL,
    _FINGERPRINT_WRITABLE_COLS,
    _validate_fingerprint_columns,
    is_current_fingerprint,
)
from .fingerprint_similarity_mixin import FingerprintSimilarityMixin
from .fingerprint_stats_repository import FingerprintStatsRepository
from .fingerprint_upsert_mixin import FingerprintUpsertMixin

# Re-exported for backward compatibility — tests and other modules import
# these directly from this module path (e.g.
# ``from auralis.library.repositories.fingerprint_repository import
# is_current_fingerprint``). The real definitions live in fingerprint_shared
# so the mixin modules above can use them without importing this facade
# module and creating a circular import.
# The underscore-prefixed pair is re-exported too: tests/auralis/library/
# test_fingerprint_repository_db_path.py imports both from this module path.
# Listing them here is what makes that contract explicit — and what stops a
# mechanical `ruff --fix F401` sweep from deleting them as unused (#5209).
# _current_fingerprint_clause was in the import list but is NOT re-exported:
# its only users (fingerprint_query_mixin, fingerprint_similarity_mixin) take
# it straight from fingerprint_shared, so it was genuinely unused here.
__all__ = [
    "FingerprintRepository",
    "PLACEHOLDER_LUFS_SENTINEL",
    "is_current_fingerprint",
    "_FINGERPRINT_WRITABLE_COLS",
    "_validate_fingerprint_columns",
]


class FingerprintRepository(
    FingerprintCrudMixin,
    FingerprintUpsertMixin,
    FingerprintQueryMixin,
    FingerprintSimilarityMixin,
):
    """Repository for fingerprint database operations"""

    def __init__(
        self,
        session_factory: Callable[[], Session],
    ) -> None:
        """
        Initialize fingerprint repository

        Args:
            session_factory: SQLAlchemy session factory used for all DB access.
        """
        super().__init__(session_factory)
        # Status/stats methods were split into FingerprintStatsRepository; the
        # facade composes one and delegates (see bottom of class) so callers that
        # hold this repo (FingerprintExtractor, fingerprint/similarity routers)
        # keep working (#4108).
        self._stats = FingerprintStatsRepository(session_factory)

    # ------------------------------------------------------------------
    # Status / stats — delegated to FingerprintStatsRepository (#4108).
    # These were moved out of this class but callers still hold the facade,
    # so thin delegators keep the contract (and routes/extractor) intact.
    # ------------------------------------------------------------------

    def update_status(self, track_id: int, status: str, completed_at: str | None = None) -> bool:
        """Update fingerprint processing status (delegates to stats repo)."""
        return self._stats.update_status(track_id, status, completed_at)

    def get_fingerprint_status(self, track_id: int) -> dict[str, Any] | None:
        """Get fingerprint status for a track (delegates to stats repo)."""
        return self._stats.get_fingerprint_status(track_id)

    def get_fingerprint_stats(self) -> dict[str, int]:
        """Get overall fingerprint statistics (delegates to stats repo)."""
        return self._stats.get_fingerprint_stats()

    def cleanup_incomplete_fingerprints(self) -> int:
        """Reset stuck/incomplete fingerprint rows (delegates to stats repo)."""
        return self._stats.cleanup_incomplete_fingerprints()

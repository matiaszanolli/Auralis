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
``FingerprintStatsRepository``, and scheduler-claim queries to
``FingerprintSchedulerRepository`` (#4108). The "so callers keep working"
delegators that used to bridge the split are gone (#6264): callers hold
``repository_factory.fingerprint_stats`` for those operations directly.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from collections.abc import Callable

from sqlalchemy.orm import Session

from .fingerprint_crud_mixin import FingerprintCrudMixin
from .fingerprint_query_mixin import FingerprintQueryMixin
from .fingerprint_similarity_mixin import FingerprintSimilarityMixin
from .fingerprint_upsert_mixin import FingerprintUpsertMixin

__all__ = ["FingerprintRepository"]


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


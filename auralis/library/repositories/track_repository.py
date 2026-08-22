"""
Track Repository
~~~~~~~~~~~~~~~

Data access layer for track operations.

``TrackRepository`` is a thin facade over five per-concern mixins, split out
of a single 1082-line module (#4511) the same way ``AudioPlayer`` composes
its ``player_*_mixin.py`` modules:

- ``track_repository_lifecycle.py``   — create/delete + artist/genre/album resolution
- ``track_repository_mutation.py``    — field/metadata updates on an existing track
- ``track_repository_maintenance.py`` — play/favorite tracking, backfill, cleanup
- ``track_repository_lookup.py``      — fetch by id/filepath, singly or batched
- ``track_repository_search.py``      — free-text search, browsing, similarity

The shared eager-load helper, order-by whitelist, batching helper, and
metadata-field allowlist below stay in this module (rather than moving to
the mixins) because every mixin needs at least one of them and this module
is the natural common ancestor they all already import from — moving them
anywhere else would just relocate the shared-dependency problem, not remove
it. Keep the mixin imports below these definitions: the mixins import these
names back out of this module at their own import time, so this module must
finish defining them first.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from collections.abc import Callable, Iterator
from typing import Any

from sqlalchemy.orm import Session, joinedload, selectinload

from ...utils.logging import error
from ..models import Track
from .base import BaseRepository


def _track_eager_options(*, collections_via_selectin: bool = False) -> tuple:
    """Standard eager-loads for every Track read path (#4500).

    ``artists`` and ``album`` load inline (joined) by default, or via a separate
    IN query (selectin) for paginated / DISTINCT queries where a join would
    multiply rows. ``genres`` ALWAYS loads via selectin — a join on this
    many-to-many explodes rows — and MUST be eager-loaded on EVERY path: read
    paths ``expunge()`` the Track, so a lazy ``genres`` access inside
    ``to_dict()`` raises ``DetachedInstanceError`` (swallowed, yielding
    ``genres: []``). Centralised here so no read path can silently drop it again
    (extends the get_by_artist fix in #2523).
    """
    loader = selectinload if collections_via_selectin else joinedload
    return (loader(Track.artists), loader(Track.album), selectinload(Track.genres))


# Track columns a *metadata* code path is allowed to write (#4555).
#
# The metadata routes forward tag dictionaries that originate in a request body
# straight into a ``setattr`` loop.  Gating that loop on ``hasattr(track, key)``
# alone let any Track attribute through — including the primary key ``id``,
# ``filepath``, ``album_id``, ``play_count``, ``favorite`` and ``duration`` — so
# a single POST /api/metadata/batch could rewrite a track's identity or falsify
# playback statistics.  Only editable tag columns belong here; ``album``,
# ``artists`` and ``genres`` are relationships that are maintained through their
# own code paths and must never be assigned a raw tag string.
_METADATA_WRITABLE_COLUMNS: frozenset[str] = frozenset({
    'title',
    'year',
    'track_number',
    'disc_number',
    'comments',
    'lyrics',
})

# Whitelist to prevent arbitrary attribute access via order_by (shared by
# get_all() and search() so both pagination paths order consistently).
_VALID_TRACK_ORDER_COLUMNS: frozenset[str] = frozenset({
    'title', 'created_at', 'play_count', 'duration', 'year', 'last_played'
})

# Keep IN clauses comfortably below SQLite's variable limit. Eager relationship
# loaders may issue their own IN queries for every batch, so leave headroom for
# future predicates rather than relying on a build-specific maximum (#4690).
_SQLITE_IN_BATCH_SIZE = 500


def _iter_in_batches(values: list[Any]) -> Iterator[list[Any]]:
    """Yield bounded slices for repository ``WHERE ... IN (...)`` queries."""
    for start in range(0, len(values), _SQLITE_IN_BATCH_SIZE):
        yield values[start:start + _SQLITE_IN_BATCH_SIZE]


def _filter_metadata_fields(track_id: int, fields: dict[str, Any]) -> dict[str, Any]:
    """Drop any field that is not a metadata-writable Track column (#4555).

    Rejected keys are logged rather than raising: the batch route is
    best-effort per track, and a caller that sends an unknown tag should not
    abort the whole transaction.  The router-level model rejects them with a
    422 first — this is the second line of defence, for the other callers of
    ``update_metadata`` / ``update_metadata_batch``.
    """
    allowed = {k: v for k, v in fields.items() if k in _METADATA_WRITABLE_COLUMNS}
    rejected = set(fields) - set(allowed)
    if rejected:
        error(
            f"Refusing to write non-metadata field(s) {sorted(rejected)} to track "
            f"{track_id} through a metadata path (#4555)"
        )
    return allowed


# Mixin imports come after the shared helpers/constants above: each mixin
# imports one or more of those names back out of this module, so this module
# must have already defined them by the time a mixin module is loaded.
from .track_repository_lifecycle import TrackRepositoryLifecycleMixin  # noqa: E402
from .track_repository_lookup import TrackRepositoryLookupMixin  # noqa: E402
from .track_repository_maintenance import TrackRepositoryMaintenanceMixin  # noqa: E402
from .track_repository_mutation import TrackRepositoryMutationMixin  # noqa: E402
from .track_repository_search import TrackRepositorySearchMixin  # noqa: E402


class TrackRepository(
    TrackRepositoryLifecycleMixin,
    TrackRepositoryMutationMixin,
    TrackRepositoryMaintenanceMixin,
    TrackRepositoryLookupMixin,
    TrackRepositorySearchMixin,
):
    """Repository for track database operations.

    Public facade only — every method body lives in one of the five mixins
    listed in the module docstring, selected by the concern it serves.
    """

    def __init__(self, session_factory: Callable[[], Session], album_repository: Any | None = None) -> None:
        """
        Initialize track repository

        Args:
            session_factory: SQLAlchemy session factory
            album_repository: AlbumRepository instance for artwork extraction
        """
        super().__init__(session_factory)
        self.album_repository = album_repository

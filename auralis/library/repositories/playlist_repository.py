"""
Playlist Repository
~~~~~~~~~~~~~~~~~~

Data access layer for playlist operations

Facade that composes four focused mixins (#4511 god-file split; was a
single 728-line module):
- PlaylistCrudMixin: single-playlist create/get/update/delete
- PlaylistQueryMixin: paginated listing and search
- PlaylistMembershipMixin: adding tracks (add_track / add_tracks)
- PlaylistOrderingMixin: removing/clearing/reordering tracks

Public API (class name, method names/signatures) is unchanged by the
split — every method below lives in exactly one mixin and is inherited
here unmodified, so existing callers and tests are unaffected.

Note: the split plan in #4511 also names "smart-playlist criteria
evaluation" as a concern for this file. No such logic exists here (or
anywhere in the codebase) today — ``Playlist.smart_criteria`` is a stored
JSON column with no evaluator, so there was nothing to extract.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from .base import BaseRepository
from .playlist_crud_mixin import PlaylistCrudMixin
from .playlist_membership_mixin import PlaylistMembershipMixin
from .playlist_ordering_mixin import PlaylistOrderingMixin
from .playlist_query_mixin import PlaylistQueryMixin


class PlaylistRepository(
    PlaylistCrudMixin,
    PlaylistQueryMixin,
    PlaylistMembershipMixin,
    PlaylistOrderingMixin,
    BaseRepository,
):
    """Repository for playlist database operations"""

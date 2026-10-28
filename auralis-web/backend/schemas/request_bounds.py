"""
Request-Body Bounds

Shared bounded types for request bodies (#4681). Split out of schemas.py
(#5479).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from typing import Annotated, Literal

from pydantic import Field

# ---------------------------------------------------------------------------
# Request-body constraints (#4681)
# ---------------------------------------------------------------------------

# The query-parameter surface has always been constrained — `Query(50, ge=1,
# le=200)` and `routers.pagination.PaginationParams` — while the player/queue
# *body* models accepted any int. A negative index or a `track_id` of -1 therefore reached
# QueueService and the engine queue, where the failure mode is a 500 or a
# silently wrong queue position rather than a 422 naming the offending field.
#
# These aliases exist so a new body model inherits the bounds by picking the
# right type, rather than by remembering to hand-roll a validator — the same
# reason EnhancementIntensity (schemas/enhancement.py) is shared rather than
# repeated.

#: Upper bound on any track-id or index list carried in a request body. Sized
#: to swallow a whole playlist or album in one "play all" (the frontend posts
#: every id at once) while still refusing a pathological payload outright.
MAX_TRACK_ID_LIST = 50_000

#: Largest integer SQLite can bind. A bigger Python int makes the binding raise
#: OverflowError, which would surface as a 500 with a logged traceback (#6162).
MAX_SQLITE_INT = 2**63 - 1

#: A track's database id. 1-based, so 0 and negatives are contract violations.
TrackId = Annotated[int, Field(ge=1, le=MAX_SQLITE_INT)]

#: A zero-based position within the queue or a playlist.
QueueIndex = Annotated[int, Field(ge=0, le=MAX_SQLITE_INT)]

#: A list of track ids, bounded per element and in length.
TrackIdList = Annotated[list[TrackId], Field(max_length=MAX_TRACK_ID_LIST)]

#: A list of queue positions, bounded per element and in length.
QueueIndexList = Annotated[list[QueueIndex], Field(max_length=MAX_TRACK_ID_LIST)]

# Output bit depths the save step maps to a subtype (core/processing_engine.py).
# One definition for both the processing job settings and the persisted user
# setting, so they cannot accept different sets (#5984).
BitDepth = Literal[16, 24, 32]

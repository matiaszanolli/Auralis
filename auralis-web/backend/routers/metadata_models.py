"""
Metadata router request/response bodies (split from metadata.py, #5831).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from pydantic import BaseModel, Field
from schemas import TrackId
from typing import Any


# Text caps follow the scanner's MAX_TAG_TEXT_CHARS for short tags; free-text tags get more room.
_SHORT_TAG = 1000
_COMMENT_TAG = 10_000
_LYRICS_TAG = 100_000


class MetadataUpdateRequest(BaseModel):
    """Request model for metadata updates; every value is bounded (#5266)."""
    title: str | None = Field(default=None, max_length=_SHORT_TAG)
    artist: str | None = Field(default=None, max_length=_SHORT_TAG)
    album: str | None = Field(default=None, max_length=_SHORT_TAG)
    albumartist: str | None = Field(default=None, max_length=_SHORT_TAG)
    year: int | None = Field(default=None, ge=0, le=9999)
    genre: str | None = Field(default=None, max_length=_SHORT_TAG)
    track: int | None = Field(default=None, ge=0, le=99_999)
    disc: int | None = Field(default=None, ge=0, le=99_999)
    comment: str | None = Field(default=None, max_length=_COMMENT_TAG)
    bpm: int | None = Field(default=None, ge=0, le=1000)
    composer: str | None = Field(default=None, max_length=_SHORT_TAG)
    publisher: str | None = Field(default=None, max_length=_SHORT_TAG)
    lyrics: str | None = Field(default=None, max_length=_LYRICS_TAG)
    copyright: str | None = Field(default=None, max_length=_SHORT_TAG)

    # One name per field: the app's only payload builder (the metadata editor)
    # sends the mutagen tag names ``track``/``disc``, and the alias spelling
    # (``track_number``) was accepted by no producer (#6260).
    model_config = {"extra": "forbid"}


class BatchMetadataUpdateRequest(BaseModel):
    """Request model for batch metadata updates

    ``metadata`` is typed as :class:`MetadataUpdateRequest` rather than a
    free-form ``dict[str, Any]`` (#4555).  The loose dict flowed unfiltered into
    a ``setattr`` loop over the Track ORM object, so any column name that
    happened to appear in the payload — ``id``, ``filepath``, ``album_id``,
    ``play_count``, ``favorite`` — was written and committed without error.
    Reusing the single-track model (which declares an explicit tag-field list
    and ``extra="forbid"``) makes the two routes accept exactly the same shape
    and rejects unknown keys with a 422.
    """
    track_id: TrackId = Field(..., description="Track ID")
    metadata: MetadataUpdateRequest = Field(..., description="Metadata fields to update")


#: Upper bound on one batch. The route writes tags to every file in the list
#: inside a single request, so an unbounded payload is an unbounded amount of
#: synchronous disk I/O (#4681).
MAX_BATCH_UPDATES = 1000


class BatchMetadataRequest(BaseModel):
    """Request model for batch update endpoint"""
    # Upper bound only. The empty case is NOT a 422: the route answers it with
    # an explicit 400 "No updates provided", pinned by
    # test_metadata_batch_atomicity.py::test_empty_updates_returns_400 and
    # test_metadata_api.py::test_batch_update_empty_list. A min_length here
    # would preempt that with a 422 and change a contract this issue never
    # asked to change.
    updates: list[BatchMetadataUpdateRequest] = Field(
        ...,
        max_length=MAX_BATCH_UPDATES,
        description="List of updates",
    )


class EditableFieldsResponse(BaseModel):
    """Editable tag fields for a track, plus the file's current tag values."""
    track_id: int = Field(description="Track database ID")
    format: str | None = Field(default=None, description="Container/codec format")
    editable_fields: list[str] = Field(
        default_factory=list,
        description="Tag names writable for this format (per TAG_MAPPINGS)",
    )
    current_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Tags currently present in the file; keys vary by format",
    )


class TrackMetadataResponse(BaseModel):
    """Current on-disk tag values for a track."""
    track_id: int = Field(description="Track database ID")
    format: str | None = Field(default=None, description="Container/codec format")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Tags read from the file; keys vary by format",
    )


class MetadataUpdateResponse(BaseModel):
    """Result of writing tags to one track's file.

    `updated_fields` lists what was written to the FILE (tag names). Fields
    with no Track DB column — artist, album, albumartist, genre, bpm,
    composer, publisher, copyright — are intentionally file-only (#4731).
    """
    track_id: int = Field(description="Track database ID")
    success: bool = Field(description="True when the file write succeeded")
    updated_fields: list[str] = Field(
        default_factory=list,
        description="Tag names written to the file",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Tags re-read from the file after the write",
    )


class BatchMetadataResultItem(BaseModel):
    """Per-track outcome within a batch metadata update."""
    track_id: int = Field(description="Track database ID")
    success: bool = Field(description="True when this track's write succeeded")
    updates: dict[str, Any] | None = Field(
        default=None,
        description="Tags written for this track (successful entries only)",
    )
    error: str | None = Field(default=None, description="Failure reason, when unsuccessful")
    rolled_back: bool | None = Field(
        default=None,
        description="True on entries reverted because a sibling write failed",
    )


class BatchMetadataResponse(BaseModel):
    """Aggregate result of a batch metadata update."""
    success: bool = Field(
        description="True when no track failed and at least one update was attempted "
                    "(an all-skipped request is not a success)"
    )
    total: int = Field(description="Number of updates attempted")
    successful: int = Field(description="Number that succeeded")
    failed: int = Field(description="Number that failed")
    skipped: int = Field(
        default=0,
        description="Requested updates never attempted: unknown track, no fields to "
                    "write, or a file path that failed validation",
    )
    results: list[BatchMetadataResultItem] = Field(
        default_factory=list,
        description="Per-track outcomes",
    )
    rolled_back: bool = Field(description="True when the whole batch was reverted")

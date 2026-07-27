"""
Metadata Mass-Assignment Regression Tests (#4555)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

POST /api/metadata/batch used to accept a free-form ``dict[str, Any]`` that
flowed unfiltered into a ``setattr`` loop over the Track ORM object, so any
column name in the payload — including the primary key ``id``, ``filepath``,
``album_id``, ``play_count`` and ``favorite`` — was written and committed
without error.

Two layers must now hold:

1. The request model rejects non-tag keys outright (``extra="forbid"``).
2. The repository refuses to write non-metadata columns regardless of what
   any caller hands it, since ``update_metadata`` / ``update_metadata_batch``
   are reachable from more than one place.
"""

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from auralis.library.models import Base, Track
from auralis.library.repositories.track_repository import TrackRepository


# Columns an attacker would target: identity, file location, and stats.
STRUCTURAL_FIELDS = {
    "id": 999,
    "filepath": "/etc/passwd",
    "album_id": 42,
    "play_count": 9999,
    "favorite": True,
    "duration": 0.1,
}


def _make_repo() -> TrackRepository:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return TrackRepository(sessionmaker(bind=engine))


def _insert_track(repo: TrackRepository) -> int:
    session = repo.get_session()
    try:
        track = Track(title="Original", filepath="/music/original.mp3", duration=180.0)
        session.add(track)
        session.flush()
        track_id = track.id
        session.commit()
        return track_id
    finally:
        session.close()


def _load(repo: TrackRepository, track_id: int) -> Track:
    session = repo.get_session()
    try:
        track = session.execute(
            select(Track).where(Track.id == track_id)
        ).scalars().first()
        assert track is not None
        session.expunge(track)
        return track
    finally:
        session.close()


@pytest.mark.security
class TestRepositoryColumnAllowlist:
    """Layer 2: the repository never writes structural columns (#4555)."""

    def test_update_metadata_ignores_structural_columns(self):
        repo = _make_repo()
        track_id = _insert_track(repo)

        repo.update_metadata(track_id, title="New Title", **STRUCTURAL_FIELDS)

        track = _load(repo, track_id)
        assert track.id == track_id, "primary key must never be rewritten"
        assert track.filepath == "/music/original.mp3"
        assert track.album_id is None
        assert track.play_count == 0
        assert track.favorite is False
        assert track.duration == 180.0
        # The legitimate tag field still lands.
        assert track.title == "New Title"

    def test_update_metadata_batch_ignores_structural_columns(self):
        repo = _make_repo()
        track_id = _insert_track(repo)

        repo.update_metadata_batch([(track_id, {"title": "Batched", **STRUCTURAL_FIELDS})])

        track = _load(repo, track_id)
        assert track.id == track_id
        assert track.filepath == "/music/original.mp3"
        assert track.play_count == 0
        assert track.favorite is False
        assert track.title == "Batched"

    def test_legitimate_tag_columns_still_writable(self):
        """The allowlist must not lock out the fields the editor actually edits."""
        repo = _make_repo()
        track_id = _insert_track(repo)

        repo.update_metadata_batch([(track_id, {
            "title": "T",
            "year": 1999,
            "track_number": 7,
            "disc_number": 2,
            "comments": "hello",
            "lyrics": "la la",
        })])

        track = _load(repo, track_id)
        assert track.title == "T"
        assert track.year == 1999
        assert track.track_number == 7
        assert track.disc_number == 2
        assert track.comments == "hello"
        assert track.lyrics == "la la"


@pytest.mark.security
class TestBatchRequestModelRejectsExtras:
    """Layer 1: the request model forbids non-tag keys (#4555)."""

    def test_structural_keys_rejected(self):
        from routers.metadata import BatchMetadataUpdateRequest

        for key, value in STRUCTURAL_FIELDS.items():
            with pytest.raises(ValidationError):
                BatchMetadataUpdateRequest(track_id=1, metadata={key: value})

    def test_tag_keys_accepted(self):
        from routers.metadata import BatchMetadataUpdateRequest

        req = BatchMetadataUpdateRequest(
            track_id=1, metadata={"title": "OK", "year": 2024}
        )
        assert req.metadata.title == "OK"
        assert req.metadata.year == 2024

    def test_batch_and_single_track_routes_accept_the_same_shape(self):
        """The two routes must not drift apart again (#4555)."""
        from routers.metadata import BatchMetadataUpdateRequest, MetadataUpdateRequest

        batch_field = BatchMetadataUpdateRequest.model_fields["metadata"]
        assert batch_field.annotation is MetadataUpdateRequest

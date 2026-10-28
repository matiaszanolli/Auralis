"""A track's recommended-reference file path never reaches a client (#5498).

Track.recommended_reference is a filesystem path (the engine reads it through the ORM attribute).
to_dict() and TrackResponse exposed it, so populating the column would have leaked a raw path to
every client, against the "filepath is never sent" contract (#3205).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "auralis-web" / "backend"))

from routers.serializers_library import serialize_tracks  # noqa: E402
from schemas import TrackResponse  # noqa: E402

from auralis.library.models import Track  # noqa: E402

SECRET = "/home/someone/private/reference.flac"


def _track() -> Track:
    return Track(id=1, title="T", filepath="/music/t.flac", duration=10.0, recommended_reference=SECRET)


def test_to_dict_does_not_carry_the_reference_path():
    payload = _track().to_dict()

    assert "recommended_reference" not in payload
    assert SECRET not in str(payload)


def test_the_response_model_has_no_such_field_and_the_serialized_track_has_no_path():
    assert "recommended_reference" not in TrackResponse.model_fields

    [serialized] = serialize_tracks([_track()])

    assert "recommended_reference" not in serialized
    assert SECRET not in str(serialized)


def test_the_engine_still_reads_the_attribute():
    assert _track().recommended_reference == SECRET

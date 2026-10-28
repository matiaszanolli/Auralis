"""MetadataUpdateRequest values are bounded (#5266).

Every tag value was unbounded, so one request could carry a multi-megabyte string (written to the
file and the DB) or an integer SQLite cannot store.
"""

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "auralis-web" / "backend"))

from routers.metadata_models import BatchMetadataUpdateRequest, MetadataUpdateRequest  # noqa: E402


def test_ordinary_tags_pass():
    request = MetadataUpdateRequest(
        title="Oktubre", artist="Patricio Rey", year=1986, track=3, disc=1, bpm=120, lyrics="la " * 1000
    )

    assert request.year == 1986 and request.track == 3


@pytest.mark.parametrize("field,value", [
    ("title", "x" * 1001),
    ("artist", "x" * 1001),
    ("comment", "x" * 10_001),
    ("lyrics", "x" * 100_001),
    ("year", 10_000),
    ("year", -1),
    ("track", 100_000),
    ("disc", 2**63),
    ("bpm", 1001),
])
def test_out_of_range_values_are_rejected(field, value):
    with pytest.raises(ValidationError):
        MetadataUpdateRequest(**{field: value})


@pytest.mark.parametrize("field,value", [
    ("title", "x" * 1000),
    ("comment", "x" * 10_000),
    ("lyrics", "x" * 100_000),
    ("year", 9999),
    ("track", 99_999),
    ("bpm", 1000),
])
def test_the_limits_themselves_are_accepted(field, value):
    assert getattr(MetadataUpdateRequest(**{field: value}), field) == value


def test_the_batch_request_inherits_the_bounds():
    with pytest.raises(ValidationError):
        BatchMetadataUpdateRequest(updates=[{"track_id": 1, "metadata": {"title": "x" * 1001}}])

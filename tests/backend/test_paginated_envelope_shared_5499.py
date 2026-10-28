"""The three list responses share one paging envelope (#5499).

TrackListResponse and AlbumListResponse repeated the same four fields (with the noun swapped in
the descriptions) and ArtistsListResponse a third, undocumented copy. They now inherit
PaginatedResponse; the wire shape (required fields, names) is unchanged.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "auralis-web" / "backend"))

from routers.artists_models import ArtistsListResponse  # noqa: E402
from schemas import AlbumListResponse, PaginatedResponse, TrackListResponse  # noqa: E402

ENVELOPE = {"total", "limit", "offset", "has_more"}


@pytest.mark.parametrize("model,items", [
    (TrackListResponse, "tracks"),
    (AlbumListResponse, "albums"),
    (ArtistsListResponse, "artists"),
])
def test_each_list_response_is_the_envelope_plus_its_items(model, items):
    assert issubclass(model, PaginatedResponse)
    assert set(model.model_fields) == ENVELOPE | {items}


@pytest.mark.parametrize("model", [TrackListResponse, AlbumListResponse, ArtistsListResponse])
def test_the_envelope_fields_are_required_in_the_schema(model):
    assert ENVELOPE <= set(model.model_json_schema()["required"])


def test_the_envelope_itself_declares_only_the_paging_fields():
    assert set(PaginatedResponse.model_fields) == ENVELOPE

"""Album-track wire keys match what the frontend transformer reads (#4568).

`GET /api/albums/{id}/tracks` serialises tracks with `serialize_tracks()`, which
prefers `Track.to_dict()` — strictly snake_case, with `artists`/`genres` as
arrays and no `artist`/`genre`/`filepath` key at all. `useAlbumDetails.ts` mapped
that payload with camelCase reads (`t.artworkUrl`, `t.trackNumber`,
`t.discNumber`, `t.albumId`), every one of which was `undefined` and silently
`??`-defaulted, so the album detail page rendered blank artists and no track
numbers.

The frontend now routes the payload through `transformTracks`. This test pins
the backend half of that contract: the keys the transformer reads must actually
be emitted, so future drift on either side fails loudly rather than silently
rendering blanks.
"""

import re
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "auralis-web" / "backend"))

from routers.serializers import DEFAULT_TRACK_FIELDS, serialize_track

_TRANSFORMER = (
    _REPO_ROOT / "auralis-web" / "frontend" / "src" / "api" / "transformers" / "trackTransformer.ts"
)

# Keys the album-detail view actually depends on, per #4568.
_REQUIRED_WIRE_KEYS = {
    "id", "title", "duration", "album",
    "artwork_url", "album_id", "track_number", "disc_number", "favorite",
}


class _FakeTrack:
    """A track without to_dict(), exercising the getattr fallback path."""

    def __init__(self):
        self.id = 1
        self.title = "Angel of Death"
        self.artist = "Slayer"
        self.album = "Reign in Blood"
        self.duration = 286.0
        self.format = "flac"
        self.artwork_url = "/api/albums/1/artwork"
        self.album_id = 1
        self.track_number = 3
        self.disc_number = 2
        self.favorite = True


def _transformer_source() -> str:
    if not _TRANSFORMER.exists():  # pragma: no cover - frontend not checked out
        pytest.skip("frontend transformer not present")
    return _TRANSFORMER.read_text()


class TestEmittedKeys:
    def test_fallback_serializer_emits_every_required_key(self):
        data = serialize_track(_FakeTrack())

        missing = _REQUIRED_WIRE_KEYS - set(data)
        assert not missing, f"album-detail keys missing from the payload: {sorted(missing)}"

    def test_default_fields_are_all_snake_case(self):
        """No camelCase key may creep into this endpoint's payload."""
        camel = [k for k in DEFAULT_TRACK_FIELDS if re.search(r"[a-z][A-Z]", k)]
        assert not camel, f"camelCase keys in DEFAULT_TRACK_FIELDS: {camel}"

    def test_filepath_is_not_emitted(self):
        """#3205/#4586: the server-side path stays server-side."""
        assert "filepath" not in DEFAULT_TRACK_FIELDS
        assert "filepath" not in serialize_track(_FakeTrack())


class TestTransformerReadsWhatBackendEmits:
    """Set-difference guard so drift on either side fails loudly."""

    def test_transformer_reads_the_navigation_keys(self):
        src = _transformer_source()

        for key in ("album_id", "track_number", "disc_number", "favorite", "artwork_url"):
            assert f"apiTrack.{key}" in src, (
                f"transformTrack() does not read `{key}`, which the album-tracks "
                f"endpoint emits — the field will be undefined on every track (#4568)"
            )

    def test_transformer_does_not_read_keys_the_backend_never_sends(self):
        """`artist`/`genre` singular are tolerated fallbacks, but the array forms
        are what Track.to_dict() actually emits and must be read first."""
        src = _transformer_source()

        assert "apiTrack.artists?.[0]" in src
        assert "apiTrack.genres?.[0]" in src

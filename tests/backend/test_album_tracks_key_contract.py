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

from auralis.library.models import Track
from routers.serializers_library import serialize_tracks

_TRANSFORMER = (
    _REPO_ROOT / "auralis-web" / "frontend" / "src" / "api" / "transformers" / "trackTransformer.ts"
)

# Keys the album-detail view actually depends on, per #4568.
_REQUIRED_WIRE_KEYS = {
    "id", "title", "duration", "album",
    "artwork_url", "album_id", "track_number", "disc_number", "favorite",
}


def _real_track() -> Track:
    """A transient ORM row; serialize_tracks goes through its to_dict()."""
    return Track(
        id=1, title="Angel of Death", duration=286.0, format="flac",
        album_id=1, track_number=3, disc_number=2, favorite=True,
    )


def _transformer_source() -> str:
    # The frontend lives in this monorepo; a missing file is a rename the
    # contract must fail on, not skip over (#6241).
    assert _TRANSFORMER.exists(), (
        "frontend transformer moved or renamed — update this contract test's path"
    )
    return _TRANSFORMER.read_text()


class TestEmittedKeys:
    def test_serializer_emits_every_required_key(self):
        data = serialize_tracks([_real_track()])[0]

        missing = _REQUIRED_WIRE_KEYS - set(data)
        assert not missing, f"album-detail keys missing from the payload: {sorted(missing)}"

    def test_emitted_keys_are_all_snake_case(self):
        """No camelCase key may creep into this endpoint's payload."""
        camel = [k for k in serialize_tracks([_real_track()])[0] if re.search(r"[a-z][A-Z]", k)]
        assert not camel, f"camelCase keys in the track payload: {camel}"

    def test_filepath_is_not_emitted(self):
        """#3205/#4586: the server-side path stays server-side."""
        assert "filepath" not in serialize_tracks([_real_track()])[0]


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
        """Track.to_dict() emits the array forms only (#5823); the transformer
        must read those and none of the singular/aliased twins."""
        src = _transformer_source()

        assert "apiTrack.artists?.[0]" in src
        assert "apiTrack.genres?.[0]" in src
        for twin in ("apiTrack.artist ", "apiTrack.genre ", "apiTrack.date_added",
                     "apiTrack.date_modified", "apiTrack.loudness"):
            assert twin not in src, f"transformTrack() still reads the twin `{twin.strip()}`"

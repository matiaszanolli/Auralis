"""Artist-detail album wire keys match the frontend type exactly (#4752).

`GET /api/artists/{artist_id}` serialises each album via the `AlbumInArtist`
model, which only carries 5 fields (`id`, `title`, `year`, `track_count`,
`total_duration`). The frontend's `ArtistDetailApiResponse.albums` used to be
typed as `AlbumApiResponse[]` — the unrelated 8-field library-album shape,
which also promises `artist`/`artist_id`/`artwork_url`. FastAPI's
`response_model` strips those before they ever reach the wire, so the
frontend type was lying about what a caller could actually read off an
artist-detail album row.

This test pins the backend half of that contract: `albums[0]`'s emitted key
set must be exactly the 5-field `AlbumInArtist` shape, so future drift on
either side (backend adding a field, frontend re-widening the type) fails
loudly instead of silently promising fields that are always `undefined`.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "auralis-web" / "backend"))

_FRONTEND_TYPES = (
    _REPO_ROOT / "auralis-web" / "frontend" / "src" / "api" / "transformers" / "types.ts"
)

_EXPECTED_ALBUM_KEYS = {"id", "title", "year", "track_count", "total_duration"}


@pytest.fixture
def mock_artist_with_album():
    artist = Mock(spec=['id', 'name', 'albums', 'tracks', 'artwork_url', 'artwork_source'])
    artist.id = 1
    artist.name = "Test Artist"
    artist.artwork_url = None
    artist.artwork_source = None

    album = Mock(spec=['id', 'title', 'year', 'tracks'])
    album.id = 1
    album.title = "Test Album"
    album.year = 2024
    album.tracks = [Mock(spec=['duration'], duration=180.0)]

    artist.albums = [album]
    artist.tracks = []
    return artist


class TestArtistDetailAlbumKeys:
    def test_album_row_emits_exactly_the_five_field_contract(self, client, mock_artist_with_album):
        mock_repo_factory = Mock()
        mock_repo_factory.artists.get_by_id.return_value = mock_artist_with_album

        with patch.dict('main.globals_dict', {'repository_factory': mock_repo_factory}):
            response = client.get("/api/artists/1")

        assert response.status_code == 200
        data = response.json()

        assert len(data["albums"]) == 1
        assert set(data["albums"][0].keys()) == _EXPECTED_ALBUM_KEYS, (
            "GET /api/artists/{id} album row keys drifted from the AlbumInArtist "
            "contract — update AlbumInArtistApiResponse in "
            "api/transformers/types.ts to match (#4752)"
        )


class TestFrontendTypeMatchesContract:
    """Static guard: the frontend type must not re-widen back to the
    unrelated 8-field AlbumApiResponse shape."""

    def test_artist_detail_albums_use_the_dedicated_type(self):
        if not _FRONTEND_TYPES.exists():  # pragma: no cover - frontend not checked out
            pytest.skip("frontend types.ts not present")
        src = _FRONTEND_TYPES.read_text()

        assert "albums: AlbumInArtistApiResponse[];" in src, (
            "ArtistDetailApiResponse.albums must use the dedicated "
            "AlbumInArtistApiResponse type, not the unrelated 8-field "
            "AlbumApiResponse (#4752)"
        )

    def test_album_in_artist_type_has_no_fields_the_backend_never_sends(self):
        if not _FRONTEND_TYPES.exists():  # pragma: no cover - frontend not checked out
            pytest.skip("frontend types.ts not present")
        src = _FRONTEND_TYPES.read_text()

        start = src.index("interface AlbumInArtistApiResponse")
        end = src.index("}", start)
        body = src[start:end]

        for forbidden in ("artist:", "artist_id:", "artwork_url:"):
            assert forbidden not in body, (
                f"AlbumInArtistApiResponse declares `{forbidden}` — the backend's "
                f"AlbumInArtist model can never send it (#4752)"
            )

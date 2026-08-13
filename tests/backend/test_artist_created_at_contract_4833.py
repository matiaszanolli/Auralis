"""`GET /api/artists` actually emits the fields ArtistResponse declares (#4833).

`ArtistResponse` gained `normalized_name`, `total_plays`,
`avg_mastering_quality`, `created_at` and `updated_at` in #3838, but the list
handler kept building the model field-by-field from only the original seven —
so those five were `None` on every response no matter what the row held.

`created_at` is the one with a consumer: the frontend's `transformArtist()`
maps it to `Artist.dateAdded`. It read `date_added` (the *track* spelling)
against a hand-authored mock, so both halves of the contract were wrong at once
and the unit test still passed. This pins the backend half; the frontend half
is pinned by the static guard below and by
`api/transformers/__tests__/artistTransformer.test.ts`.
"""

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "auralis-web" / "backend"))

_FRONTEND_TRANSFORMER = (
    _REPO_ROOT / "auralis-web" / "frontend" / "src" / "api" / "transformers" / "artistTransformer.ts"
)


class _FakeArtist:
    """Stand-in for an ORM `Artist` row.

    Deliberately not a `Mock`: `serialize_object()` skips `to_dict()` for Mock
    types, and `to_dict()` is exactly the path the timestamps travel.
    """

    def __init__(self) -> None:
        self.id = 1
        self.name = "Test Artist"
        self.artwork_url = None
        self.artwork_source = None
        self.normalized_name = "test artist"
        self.total_plays = 12
        self.avg_mastering_quality = 0.75
        self.created_at = datetime(2026, 1, 15, 10, 30, 0)
        self.updated_at = datetime(2026, 2, 20, 8, 0, 0)
        self.albums = []
        self.tracks = []

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'normalized_name': self.normalized_name,
            'total_plays': self.total_plays,
            'avg_mastering_quality': self.avg_mastering_quality,
            'album_count': len(self.albums),
            'track_count': len(self.tracks),
            'artwork_url': self.artwork_url,
            'artwork_source': self.artwork_source,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }


@pytest.fixture
def mock_repo_factory():
    factory = Mock()
    factory.artists.get_all.return_value = ([_FakeArtist()], 1)
    return factory


class TestArtistListTimestamps:
    def test_created_at_reaches_the_wire(self, client, mock_repo_factory):
        with patch.dict('main.globals_dict', {'repository_factory': mock_repo_factory}):
            response = client.get("/api/artists")

        assert response.status_code == 200
        artist = response.json()["artists"][0]

        assert artist["created_at"] == "2026-01-15T10:30:00", (
            "GET /api/artists dropped created_at — the frontend transforms it "
            "into Artist.dateAdded (#4833)"
        )
        assert artist["updated_at"] == "2026-02-20T08:00:00"

    def test_remaining_declared_fields_are_populated(self, client, mock_repo_factory):
        with patch.dict('main.globals_dict', {'repository_factory': mock_repo_factory}):
            response = client.get("/api/artists")

        artist = response.json()["artists"][0]
        assert artist["normalized_name"] == "test artist"
        assert artist["total_plays"] == 12
        assert artist["avg_mastering_quality"] == 0.75


class TestFrontendTransformerMatchesContract:
    """Static guard: the transformer must read the key the backend sends."""

    def test_transformer_reads_created_at_not_date_added(self):
        if not _FRONTEND_TRANSFORMER.exists():  # pragma: no cover - frontend not checked out
            pytest.skip("frontend artistTransformer.ts not present")
        src = _FRONTEND_TRANSFORMER.read_text()

        assert "dateAdded: apiArtist.created_at" in src, (
            "transformArtist() must map dateAdded from `created_at`; "
            "`date_added` is the track spelling and no artist response "
            "carries it (#4833)"
        )

"""Album genre is derived and reaches the wire (#5170).

`AlbumMetadata` renders a `Genre:` line and `Album` declares `genre?: string`,
but nothing ever populated it: `GET /api/albums/{id}/tracks` sent no `genre`
key and `useAlbumDetails` mapped none. The block was unreachable, which a
vacuous `toBeGreaterThanOrEqual(0)` assertion had been hiding (#5136).

`Album` has no genre column — genre lives on `Track` via the `track_genre`
association — so an album genre must be *derived*. #4709 removed the
always-null `genre` key from `serialize_album_detail` for that reason and
called the derivation a feature rather than a bug fix; this pins that feature.

Two halves are covered here:
  * `_derive_album_genre` picks the modal genre, deterministically.
  * `_ALBUM_DETAIL_OPTIONS` eager-loads `Track.genres`, without which every
    track on this path reported `genres: []` (expunged + lazy = degraded to
    `[]` by `_safe_collection()`), so the derived genre was always None.
"""

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "auralis-web" / "backend"))

from routers.albums import AlbumTracksResponse, _derive_album_genre


class TestDeriveAlbumGenre:
    """Unit-level behaviour of the derivation itself."""

    def test_no_tracks_yields_none(self):
        assert _derive_album_genre([]) is None

    def test_untagged_tracks_yield_none(self):
        """None, not '' — the UI's `{genre && ...}` guard must hide the row."""
        assert _derive_album_genre([{'genres': []}, {}, {'genres': None}]) is None

    def test_picks_the_most_common_genre(self):
        tracks = [{'genres': ['Rock']}, {'genres': ['Rock']}, {'genres': ['Jazz']}]
        assert _derive_album_genre(tracks) == 'Rock'

    def test_multi_genre_track_votes_once_per_genre(self):
        """A track tagged [Rock, Blues] contributes one vote to each."""
        tracks = [
            {'genres': ['Rock', 'Blues']},
            {'genres': ['Blues']},
            {'genres': ['Rock']},
            {'genres': ['Blues']},
        ]
        assert _derive_album_genre(tracks) == 'Blues'

    def test_ties_break_on_first_appearance_deterministically(self):
        tracks = [{'genres': ['Ambient']}, {'genres': ['Drone']}]
        assert _derive_album_genre(tracks) == 'Ambient'
        # Same input, same answer — no set/dict iteration nondeterminism.
        assert _derive_album_genre(tracks) == 'Ambient'

    def test_ignores_empty_genre_strings(self):
        assert _derive_album_genre([{'genres': ['', 'Rock']}]) == 'Rock'


class TestResponseSchema:
    """SCHEMA: the Pydantic model must actually carry the field."""

    def test_model_declares_genre(self):
        assert 'genre' in AlbumTracksResponse.model_fields

    def test_genre_defaults_to_none(self):
        response = AlbumTracksResponse(album_id=1, total_tracks=0)
        assert response.genre is None

    def test_genre_survives_serialization(self):
        response = AlbumTracksResponse(album_id=1, total_tracks=0, genre='Rock')
        assert response.model_dump()['genre'] == 'Rock'


class TestAlbumDetailEagerLoadsTrackGenres:
    """The repository half — without this the derivation always sees []."""

    @pytest.fixture
    def seeded(self, session_factory, tmp_path):
        from auralis.library.repositories import AlbumRepository, TrackRepository

        track_repo = TrackRepository(session_factory)
        album_repo = AlbumRepository(session_factory)
        for index, genre in enumerate(['Rock', 'Rock', 'Jazz']):
            track_repo.add({
                'filepath': str(tmp_path / f'track_{index}.flac'),
                'title': f'Track {index}',
                'artists': ['Artist'],
                'album': 'Test Album',
                'genres': [genre],
                'format': 'FLAC',
                'sample_rate': 44100,
                'channels': 2,
            })
        albums, _ = album_repo.get_all(limit=10)
        return album_repo, albums[0].id

    def test_track_genres_survive_expunge(self, seeded):
        """Regression: these were [] for every track before #5170."""
        album_repo, album_id = seeded
        album = album_repo.get_by_id(album_id)

        genres = [track.to_dict().get('genres') for track in album.tracks]
        assert all(genres), f"genres lost on the detail path: {genres}"

    def test_derivation_over_a_real_album_row(self, seeded):
        """End to end: ORM rows -> serialized tracks -> derived genre."""
        from routers.serializers import serialize_tracks

        album_repo, album_id = seeded
        album = album_repo.get_by_id(album_id)

        assert _derive_album_genre(serialize_tracks(album.tracks)) == 'Rock'

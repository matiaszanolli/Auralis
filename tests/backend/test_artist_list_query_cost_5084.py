"""`/api/artists` list reads don't scale with tracks-per-artist (#5084).

`ArtistRepository.get_all()`/`search()` used to eager-load
`Artist.tracks -> Track.genres` plus `Artist.albums`, hydrating every full
`Track` row belonging to every artist on the page — including the unbounded
`lyrics` and `fingerprint_vector` Text columns — purely to build a genre-name
set and two `len()` counts. #4553 had already trimmed the eager loads to "what
the serializer reads"; the residue was that even that scoped load was a
full-Track hydration for a count-and-name-only consumer.

The counts now come from correlated COUNT subqueries (`track_count_expr` /
`album_count_expr`, the treatment Album got in #4777) and the genre names from
one grouped query over the association tables.

These tests assert both halves: the values are right, and the row/query cost no
longer follows the track count.
"""

import sys
from pathlib import Path

import pytest
from sqlalchemy import event

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from routers.serializers import serialize_artist  # noqa: E402


def _seed_artist(track_repository, artist_name: str, tracks: int, genres: list[str]) -> None:
    """Add `tracks` tracks for `artist_name`, cycling through `genres`."""
    for i in range(tracks):
        track_repository.add({
            'title': f'{artist_name} Track {i}',
            'filepath': f'/tmp/{artist_name.replace(" ", "_")}_{i}.wav',
            'duration': 100.0 + i,
            'sample_rate': 44100,
            'channels': 2,
            'format': 'WAV',
            'artists': [artist_name],
            'album': f'{artist_name} Album {i % 2}',
            'genres': [genres[i % len(genres)]] if genres else [],
        })


class _QueryCounter:
    """Count SQL statements issued through a session factory's engine."""

    def __init__(self, engine):
        self._engine = engine
        self.statements: list[str] = []

    def __enter__(self):
        event.listen(self._engine, "before_cursor_execute", self._record)
        return self

    def __exit__(self, *exc):
        event.remove(self._engine, "before_cursor_execute", self._record)
        return False

    def _record(self, conn, cursor, statement, params, context, executemany):
        self.statements.append(statement)

    def __len__(self) -> int:
        return len(self.statements)


def _engine_of(repository) -> object:
    session = repository.get_session()
    try:
        return session.get_bind()
    finally:
        session.close()


class TestArtistListValues:
    def test_counts_and_genres_are_correct(self, artist_repository, track_repository):
        _seed_artist(track_repository, 'Count Artist', tracks=5, genres=['Rock', 'Jazz'])

        artists, total = artist_repository.get_all(limit=10)

        assert total == 1
        artist = artists[0]
        assert artist.track_count_expr == 5
        assert artist.album_count_expr == 2  # 'Album 0' / 'Album 1'
        assert artist.genre_names == ['Jazz', 'Rock']  # sorted, distinct

    def test_serializer_reports_the_sql_counts(self, artist_repository, track_repository):
        _seed_artist(track_repository, 'Serialized Artist', tracks=3, genres=['Pop'])

        artists, _ = artist_repository.get_all(limit=10)
        data = serialize_artist(artists[0])

        assert data['track_count'] == 3
        assert data['album_count'] == 2
        assert data['genres'] == ['Pop']

    def test_artist_with_no_tracks_reports_zeroes_not_none(
        self, artist_repository, session_factory
    ):
        from auralis.library.models import Artist

        session = session_factory()
        try:
            session.add(Artist(name='Empty Artist'))
            session.commit()
        finally:
            session.close()

        artists, _ = artist_repository.get_all(limit=10)
        empty = next(a for a in artists if a.name == 'Empty Artist')

        # COUNT over zero rows is 0, not NULL — no COALESCE needed.
        assert empty.track_count_expr == 0
        assert empty.album_count_expr == 0
        # [] means "queried, none found" — distinct from the None default.
        assert empty.genre_names == []

    def test_search_carries_the_same_values(self, artist_repository, track_repository):
        _seed_artist(track_repository, 'Searchable Artist', tracks=4, genres=['Metal'])

        artists, total = artist_repository.search('Searchable')

        assert total == 1
        assert artists[0].track_count_expr == 4
        assert artists[0].genre_names == ['Metal']

    def test_genres_do_not_leak_between_artists(self, artist_repository, track_repository):
        _seed_artist(track_repository, 'Artist One', tracks=2, genres=['Rock'])
        _seed_artist(track_repository, 'Artist Two', tracks=2, genres=['Ambient'])

        artists, _ = artist_repository.get_all(limit=10)
        by_name = {a.name: a for a in artists}

        assert by_name['Artist One'].genre_names == ['Rock']
        assert by_name['Artist Two'].genre_names == ['Ambient']


class TestArtistListQueryCost:
    """The regression guard: cost must follow page size, not track count."""

    def test_query_count_does_not_scale_with_tracks_per_artist(
        self, artist_repository, track_repository
    ):
        _seed_artist(track_repository, 'Small Artist', tracks=2, genres=['Rock'])
        engine = _engine_of(artist_repository)

        with _QueryCounter(engine) as few:
            artist_repository.get_all(limit=10)
        baseline = len(few)

        _seed_artist(track_repository, 'Big Artist', tracks=25, genres=['Rock', 'Jazz', 'Pop'])

        with _QueryCounter(engine) as many:
            artists, _ = artist_repository.get_all(limit=10)

        assert len(many) == baseline, (
            f"query count grew from {baseline} to {len(many)} when tracks-per-artist "
            f"grew: {many.statements}"
        )
        # And the values are still right at the larger size.
        big = next(a for a in artists if a.name == 'Big Artist')
        assert big.track_count_expr == 25
        assert sorted(big.genre_names) == ['Jazz', 'Pop', 'Rock']

    def test_no_track_row_is_selected(self, artist_repository, track_repository):
        """The genre query must read only the association tables and genres —
        never the tracks table, whose unbounded lyrics/fingerprint_vector Text
        columns are what made the old hydration expensive."""
        _seed_artist(track_repository, 'No Hydration Artist', tracks=3, genres=['Rock'])
        engine = _engine_of(artist_repository)

        with _QueryCounter(engine) as counter:
            artist_repository.get_all(limit=10)

        selected_track_columns = [
            s for s in counter.statements
            if 'tracks.lyrics' in s or 'tracks.fingerprint_vector' in s
        ]
        assert not selected_track_columns, (
            f"a list read is still hydrating Track rows: {selected_track_columns}"
        )

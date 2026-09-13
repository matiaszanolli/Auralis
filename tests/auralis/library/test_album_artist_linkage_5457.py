"""Albums created on rescan keep their artist (#5457).

TrackRepository.update_by_filepath() — the production rescan path — and
update() looked an album up by title alone and created a missing one with no
artist_id. A retag into a new album title followed by a rescan therefore left
an album no artist page lists (serialized as `artist: null` against the
frontend's non-nullable type), and could attach the track to another artist's
album that merely shared the title. Both paths now resolve albums the way the
first scan does, a v018->v019 migration repairs existing orphans, and
Album.to_dict() reports a genuinely unknown artist as 'Unknown Artist'.
"""

from pathlib import Path

import auralis.library
from auralis.__version__ import __db_schema_version__
from auralis.library.migration_steps import validate_migration_sql
from auralis.library.models import Album, Track

MIGRATION = Path(auralis.library.__file__).parent / "migrations" / "migration_v018_to_v019.sql"


def _add(track_repository, name: str, artists: list[str], album: str | None = None) -> int:
    info = {
        'title': name, 'filepath': f'/music/{name}.mp3',
        'sample_rate': 44100, 'channels': 2, 'format': 'MP3', 'artists': artists,
    }
    if album:
        info['album'] = album
    return int(track_repository.add(info).id)


def _album_of(session_factory, track_id: int) -> tuple[int, str, str | None]:
    with session_factory() as session:
        album = session.get(Track, track_id).album
        return album.id, album.title, album.artist.name if album.artist else None


class TestRescanAlbumCreation:
    def test_update_by_filepath_links_a_new_album_to_the_tracks_artist(
        self, track_repository, session_factory
    ):
        track_id = _add(track_repository, 'song', ['Band'], album='First')

        track_repository.update_by_filepath('/music/song.mp3', {'album': 'Retagged', 'artists': ['Band']})

        _id, title, artist = _album_of(session_factory, track_id)
        assert (title, artist) == ('Retagged', 'Band')

    def test_update_links_a_new_album_to_the_tracks_artist(self, track_repository, session_factory):
        track_id = _add(track_repository, 'song', ['Band'], album='First')

        track_repository.update(track_id, {'album': 'Retagged'})

        _id, title, artist = _album_of(session_factory, track_id)
        assert (title, artist) == ('Retagged', 'Band')

    def test_a_retag_that_also_changes_the_artist_uses_the_new_artist(
        self, track_repository, session_factory
    ):
        track_id = _add(track_repository, 'song', ['Old Band'], album='First')

        track_repository.update_by_filepath(
            '/music/song.mp3', {'artists': ['New Band'], 'album': 'Retagged'}
        )

        assert _album_of(session_factory, track_id)[2] == 'New Band'

    def test_a_retag_does_not_join_another_artists_same_titled_album(
        self, track_repository, session_factory
    ):
        alpha = _add(track_repository, 'alpha', ['Alpha'], album='Greatest Hits')
        beta = _add(track_repository, 'beta', ['Beta'], album='Other')

        track_repository.update_by_filepath('/music/beta.mp3', {'album': 'Greatest Hits'})

        alpha_album_id, _t, _a = _album_of(session_factory, alpha)
        beta_album_id, title, artist = _album_of(session_factory, beta)
        assert (title, artist) == ('Greatest Hits', 'Beta')
        assert beta_album_id != alpha_album_id

    def test_a_track_without_an_artist_still_gets_its_album(self, track_repository, session_factory):
        track_id = _add(track_repository, 'loose', [])

        track_repository.update(track_id, {'album': 'Loose Album'})

        _id, title, artist = _album_of(session_factory, track_id)
        assert (title, artist) == ('Loose Album', None)


class TestUnknownArtistRepresentation:
    def test_album_without_an_artist_serializes_as_unknown_artist(self):
        assert Album(title='No Owner').to_dict()['artist'] == 'Unknown Artist'


class TestOrphanBackfillMigration:
    def test_schema_version_reaches_the_backfill(self):
        assert __db_schema_version__ == 19
        assert MIGRATION.exists()
        assert validate_migration_sql(MIGRATION.read_text(), MIGRATION.name)

    def test_orphans_take_their_tracks_most_credited_artist(self, track_repository, session_factory):
        majority = [_add(track_repository, f'm{i}', ['Majority']) for i in range(2)]
        minority = _add(track_repository, 'x', ['Minority'])
        artistless = _add(track_repository, 'y', [])

        with session_factory() as session:
            orphan = Album(title='Orphan')
            no_artists = Album(title='Nobody')
            session.add_all([orphan, no_artists])
            session.flush()
            for track_id in (*majority, minority):
                session.get(Track, track_id).album_id = orphan.id
            session.get(Track, artistless).album_id = no_artists.id
            session.commit()
            orphan_id, no_artists_id = orphan.id, no_artists.id

        engine = session_factory().get_bind()
        raw = engine.raw_connection()
        try:
            raw.executescript(MIGRATION.read_text())
            raw.commit()
        finally:
            raw.close()

        with session_factory() as session:
            assert session.get(Album, orphan_id).artist.name == 'Majority'
            assert session.get(Album, no_artists_id).artist_id is None

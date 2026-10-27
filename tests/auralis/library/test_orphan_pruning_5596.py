"""
Regression: deleting tracks prunes the albums, artists and genres they leave empty (#5596)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Track deletes removed only ``tracks`` and the association rows, so the
Albums/Artists/Genres views kept zero-track entries and the library statistics
overstated their totals. ``delete_tracks_by_ids`` now prunes in the delete's own
transaction, which covers ``delete``, ``cleanup_missing_files`` and
``remove_tracks_under_folder``.
"""

from pathlib import Path

from sqlalchemy import select

from auralis.library.models import Album, Artist, Genre


def _info(n: int, artists=None, genres=None, album=None, **over):
    info = {
        'filepath': f'/tmp/5596_{n}.flac', 'title': f'T{n}', 'duration': 10.0,
        'sample_rate': 44100, 'channels': 2, 'format': 'FLAC',
        'artists': artists or [], 'genres': genres or [],
    }
    if album:
        info['album'] = album
    info.update(over)
    return info


def _names(db) -> dict[str, set[str]]:
    with db.SessionLocal() as s:
        return {
            'albums': set(s.execute(select(Album.title)).scalars()),
            'artists': set(s.execute(select(Artist.name)).scalars()),
            'genres': set(s.execute(select(Genre.name)).scalars()),
        }


def test_deleting_the_last_track_removes_its_album_artist_and_genre(library_database):
    repo = library_database.tracks
    shared_a = repo.add(_info(1, ['Shared'], ['Rock'], 'Shared Album'))
    repo.add(_info(2, ['Shared'], ['Rock'], 'Shared Album'))
    solo = repo.add(_info(3, ['Solo'], ['Jazz'], 'Solo Album'))

    assert repo.delete(solo.id)

    assert _names(library_database) == {
        'albums': {'Shared Album'}, 'artists': {'Shared'}, 'genres': {'Rock'},
    }
    assert repo.delete(shared_a.id)  # one track of the shared rows left: nothing more to prune
    assert _names(library_database)['artists'] == {'Shared'}


def test_library_stats_match_the_surviving_tracks(library_database):
    repo = library_database.tracks
    repo.add(_info(1, ['A'], ['G'], 'Alb'))
    only = repo.add(_info(2, ['B'], ['H'], 'Alb 2'))

    repo.delete(only.id)

    stats = library_database.stats.get_library_stats()
    assert (stats['total_tracks'], stats['total_albums'], stats['total_artists']) == (1, 1, 1)
    assert library_database.albums.get_all()[1] == 1
    assert library_database.artists.get_all()[1] == 1


def test_an_artist_owning_an_album_with_other_artists_tracks_is_kept(library_database):
    """The album's artist_id is its owner: it stays while the album has a track."""
    repo = library_database.tracks
    owner = repo.add(_info(1, ['Owner'], album='Compilation'))
    repo.add(_info(2, ['Owner'], album='Compilation'))
    with library_database.SessionLocal() as s:
        guest = repo._get_or_create_artists(s, ['Guest'])[0]
        track = s.get(type(owner), owner.id)
        track.artists = [guest]  # the only track listing Owner now lists Guest
        s.commit()

    repo.delete(owner.id)

    names = _names(library_database)
    assert 'Compilation' in names['albums']  # track 2 still has it
    assert 'Owner' in names['artists']  # owns the surviving album


def test_untouched_rows_survive_a_delete_of_an_unrelated_track(library_database):
    repo = library_database.tracks
    repo.add(_info(1, ['Keep'], ['Keep G'], 'Keep Album'))
    other = repo.add(_info(2))

    repo.delete(other.id)

    assert _names(library_database) == {
        'albums': {'Keep Album'}, 'artists': {'Keep'}, 'genres': {'Keep G'},
    }


def test_cleanup_missing_files_prunes_too(library_database, tmp_path):
    repo = library_database.tracks
    present = tmp_path / 'present.flac'
    present.write_bytes(b'x')
    repo.add(_info(1, ['Here'], ['H'], 'Here Album', filepath=str(present)))
    repo.add(_info(2, ['Gone'], ['G'], 'Gone Album', filepath=str(tmp_path / 'gone.flac')))

    assert repo.cleanup_missing_files() == 1

    assert _names(library_database) == {
        'albums': {'Here Album'}, 'artists': {'Here'}, 'genres': {'H'},
    }


def test_removing_a_scan_folder_prunes_too(library_database, tmp_path):
    repo = library_database.tracks
    inside = tmp_path / 'removed'
    inside.mkdir()
    repo.add(_info(1, ['Inside'], ['I'], 'Inside Album', filepath=str(inside / 'a.flac')))
    repo.add(_info(2, ['Outside'], ['O'], 'Outside Album', filepath=str(tmp_path / 'b.flac')))

    assert repo.remove_tracks_under_folder(str(inside)) == 1

    assert _names(library_database) == {
        'albums': {'Outside Album'}, 'artists': {'Outside'}, 'genres': {'O'},
    }


class TestAlbumArtworkFile:
    def _album_with_artwork(self, library_database, tmp_path: Path):
        repo = library_database.tracks
        track = repo.add(_info(1, ['A'], album='Covered'))
        artwork = tmp_path / 'cover.jpg'
        artwork.write_bytes(b'jpeg')
        with library_database.SessionLocal() as s:
            s.get(Album, track.album.id).artwork_path = str(artwork)
            s.commit()
        return track, artwork

    def test_the_pruned_albums_artwork_file_is_removed_after_the_commit(self, library_database, tmp_path):
        track, artwork = self._album_with_artwork(library_database, tmp_path)

        library_database.tracks.delete(track.id)

        assert not artwork.exists()

    def test_a_rolled_back_delete_keeps_the_file(self, library_database, tmp_path):
        from auralis.library.repositories.track_deletion import delete_tracks_by_ids

        track, artwork = self._album_with_artwork(library_database, tmp_path)

        with library_database.SessionLocal() as session:
            assert delete_tracks_by_ids(session, [track.id]) == 1
            session.rollback()

        assert artwork.exists()
        assert 'Covered' in _names(library_database)['albums']

    def test_an_album_that_keeps_a_track_keeps_its_file(self, library_database, tmp_path):
        track, artwork = self._album_with_artwork(library_database, tmp_path)
        library_database.tracks.add(_info(2, ['A'], album='Covered'))

        library_database.tracks.delete(track.id)

        assert artwork.exists()

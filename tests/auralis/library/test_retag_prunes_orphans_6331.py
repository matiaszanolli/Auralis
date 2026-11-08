"""Retagging a track prunes the albums, artists and genres it leaves empty (#6331)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

#5596 swept orphans only when tracks are deleted. Editing a file's artist, album
or genre tag and rescanning goes through ``update_by_filepath`` (or ``update``),
which re-pointed the track and left the old album/artist/genre behind with zero
tracks, so the Albums/Artists/Genres views listed them and ``total_*`` in the
library stats overstated the library. Both update paths now prune in their own
transaction.
"""

from unittest.mock import patch

from sqlalchemy import select

from auralis.library.models import Album, Artist, Genre


def _info(n: int, artists=None, genres=None, album=None, **over):
    info = {
        'filepath': f'/tmp/6331_{n}.flac', 'title': f'T{n}', 'duration': 10.0,
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


def test_retagging_the_only_track_of_an_album_removes_the_old_album_artist_and_genre(library_database):
    repo = library_database.tracks
    repo.add(_info(1, ['Old Artist'], ['Old Genre'], 'Old Album'))

    repo.update_by_filepath('/tmp/6331_1.flac', {
        'artists': ['New Artist'], 'genres': ['New Genre'], 'album': 'New Album',
    })

    assert _names(library_database) == {
        'albums': {'New Album'}, 'artists': {'New Artist'}, 'genres': {'New Genre'},
    }


def test_the_library_stats_do_not_count_what_a_retag_emptied(library_database):
    repo = library_database.tracks
    repo.add(_info(1, ['A'], ['G'], 'Alb'))
    repo.update_by_filepath('/tmp/6331_1.flac', {'artists': ['B'], 'genres': ['H'], 'album': 'Alb 2'})

    stats = library_database.stats.get_library_stats()
    assert (stats['total_tracks'], stats['total_albums'], stats['total_artists']) == (1, 1, 1)
    assert library_database.albums.get_all()[1] == 1
    assert library_database.artists.get_all()[1] == 1


def test_rows_another_track_still_uses_survive_a_retag(library_database):
    repo = library_database.tracks
    repo.add(_info(1, ['Shared'], ['Rock'], 'Shared Album'))
    repo.add(_info(2, ['Shared'], ['Rock'], 'Shared Album'))

    repo.update_by_filepath('/tmp/6331_2.flac', {
        'artists': ['Other'], 'genres': ['Jazz'], 'album': 'Other Album',
    })

    assert _names(library_database) == {
        'albums': {'Shared Album', 'Other Album'},
        'artists': {'Shared', 'Other'},
        'genres': {'Rock', 'Jazz'},
    }


def test_the_update_by_id_path_prunes_too(library_database):
    repo = library_database.tracks
    track = repo.add(_info(1, ['Old Artist'], ['Old Genre'], 'Old Album'))

    repo.update(track.id, {'artists': ['New Artist'], 'genres': ['New Genre'], 'album': 'New Album'})

    assert _names(library_database) == {
        'albums': {'New Album'}, 'artists': {'New Artist'}, 'genres': {'New Genre'},
    }


def test_a_scalar_only_update_does_not_run_the_sweep(library_database):
    """A plain title/duration rescan of a huge library must not pay three DELETEs per file."""
    repo = library_database.tracks
    repo.add(_info(1, ['A'], ['G'], 'Alb'))

    with patch('auralis.library.repositories.track_repository_mutation.prune_orphans') as prune:
        repo.update_by_filepath('/tmp/6331_1.flac', {'title': 'Retitled', 'duration': 11.0})
        repo.update(repo.get_id_by_filepath('/tmp/6331_1.flac'), {'title': 'Again'})

    prune.assert_not_called()

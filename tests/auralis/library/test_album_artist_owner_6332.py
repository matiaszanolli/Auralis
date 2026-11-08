"""An album is owned by the file's ALBUMARTIST tag, not by one track's artist (#6332)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The scanner read ``albumartist`` and dropped it, and ``add()`` / both update paths
owned the album by the track's first artist. Since v30 ``(title, artist_id)`` is the
unique identity, so every compilation, soundtrack and guest-first album became one
same-titled album per track artist. The tag now reaches the repository; a file
without one keeps the old rule.
"""

from datetime import datetime

from sqlalchemy import select

from auralis.library.models import Album, Artist
from auralis.library.scan_models import AudioFileInfo
from auralis.library.scanner.metadata_extractor import MetadataExtractor


def _info(n: int, artist: str, album: str = 'Hits', album_artist: str | None = None, **over):
    info = {
        'filepath': f'/tmp/6332_{n}.flac', 'title': f'T{n}', 'duration': 10.0,
        'sample_rate': 44100, 'channels': 2, 'format': 'FLAC',
        'artists': [artist], 'genres': [], 'album': album,
    }
    if album_artist is not None:
        info['album_artist'] = album_artist
    info.update(over)
    return info


def _albums(db) -> list[tuple[str, str | None]]:
    """(album title, owner name) for every album, sorted."""
    with db.SessionLocal() as s:
        rows = s.execute(
            select(Album.title, Artist.name).outerjoin(Artist, Album.artist_id == Artist.id)
        ).all()
    return sorted((title, owner) for title, owner in rows)


class TestScannerCarriesTheTag:
    def _track_info(self, metadata: dict) -> dict:
        audio_info = AudioFileInfo(
            filepath='/tmp/x.flac', filename='x.flac', filesize=1,
            modified_time=datetime(2026, 1, 1), metadata=metadata,
        )
        return MetadataExtractor().audio_info_to_track_info(audio_info)

    def test_albumartist_becomes_album_artist(self):
        info = self._track_info({'artist': 'C feat. A', 'album': 'Hits', 'albumartist': 'Various Artists'})
        assert info['album_artist'] == 'Various Artists'
        assert info['artists'] == ['C', 'A']  # the track's own credits are untouched

    def test_an_ampersand_name_stays_whole(self):
        info = self._track_info({'album': 'Hits', 'albumartist': 'Iron & Wine'})
        assert info['album_artist'] == 'Iron & Wine'

    def test_a_file_without_the_tag_has_no_album_artist(self):
        assert 'album_artist' not in self._track_info({'artist': 'A', 'album': 'Hits'})

    def test_every_tag_spelling_is_read(self):
        """The mapping covers ID3 (TPE2), Vorbis (ALBUMARTIST) and MP4 (aART)."""
        for key in ('TPE2', 'ALBUMARTIST', 'aART'):
            metadata = MetadataExtractor().extract_metadata({key: ['Various Artists']})
            assert metadata['albumartist'] == 'Various Artists', key


class TestFirstScan:
    def test_a_compilation_is_one_album_owned_by_the_album_artist(self, library_database):
        repo = library_database.tracks
        repo.add(_info(1, 'A', album_artist='Various Artists'))
        repo.add(_info(2, 'B', album_artist='Various Artists'))
        repo.add(_info(3, 'C', album_artist='Various Artists', artists=['C', 'A']))

        assert _albums(library_database) == [('Hits', 'Various Artists')]

    def test_the_tracks_keep_their_own_artists(self, library_database):
        repo = library_database.tracks
        track = repo.add(_info(1, 'A', album_artist='Various Artists'))

        assert [a.name for a in track.artists] == ['A']
        assert _albums(library_database) == [('Hits', 'Various Artists')]

    def test_a_guest_listed_first_does_not_split_the_album(self, library_database):
        repo = library_database.tracks
        repo.add(_info(1, 'A', album='Solo Album', album_artist='A'))
        repo.add(_info(2, 'B', album='Solo Album', album_artist='A', artists=['B', 'A']))
        repo.add(_info(3, 'A', album='Solo Album', album_artist='A', artists=['A', 'B']))

        assert _albums(library_database) == [('Solo Album', 'A')]

    def test_the_album_artist_is_matched_like_any_artist_name(self, library_database):
        repo = library_database.tracks
        repo.add(_info(1, 'A', album_artist='Various Artists'))
        repo.add(_info(2, 'B', album_artist='various artists'))

        assert len(_albums(library_database)) == 1

    def test_same_titled_albums_by_different_album_artists_stay_apart(self, library_database):
        repo = library_database.tracks
        repo.add(_info(1, 'A', album='Greatest Hits', album_artist='A'))
        repo.add(_info(2, 'B', album='Greatest Hits', album_artist='B'))

        assert _albums(library_database) == [('Greatest Hits', 'A'), ('Greatest Hits', 'B')]

    def test_a_file_without_the_tag_keeps_the_track_artist_rule(self, library_database):
        repo = library_database.tracks
        repo.add(_info(1, 'A'))
        repo.add(_info(2, 'B'))

        assert _albums(library_database) == [('Hits', 'A'), ('Hits', 'B')]


class TestRescan:
    def _fragmented_library(self, db):
        """Three tracks of one compilation stored the way v30 stored them: one album each."""
        for n, artist in enumerate(['A', 'B', 'C'], start=1):
            db.tracks.add(_info(n, artist))
        assert len(_albums(db)) == 3

    def test_rescanning_with_the_tag_merges_the_fragments(self, library_database):
        self._fragmented_library(library_database)

        for n in (1, 2, 3):
            library_database.tracks.update_by_filepath(
                f'/tmp/6332_{n}.flac', {'album': 'Hits', 'album_artist': 'Various Artists'}
            )

        assert _albums(library_database) == [('Hits', 'Various Artists')]
        stats = library_database.stats.get_library_stats()
        assert (stats['total_tracks'], stats['total_albums']) == (3, 1)

    def test_the_update_by_id_path_resolves_the_same_owner(self, library_database):
        self._fragmented_library(library_database)

        for n in (1, 2, 3):
            track_id = library_database.tracks.get_id_by_filepath(f'/tmp/6332_{n}.flac')
            library_database.tracks.update(track_id, {'album': 'Hits', 'album_artist': 'Various Artists'})

        assert _albums(library_database) == [('Hits', 'Various Artists')]

    def test_removing_the_tag_returns_a_track_to_its_artists_album(self, library_database):
        repo = library_database.tracks
        repo.add(_info(1, 'A', album_artist='Various Artists'))

        repo.update_by_filepath('/tmp/6332_1.flac', {'album': 'Hits'})

        assert _albums(library_database) == [('Hits', 'A')]

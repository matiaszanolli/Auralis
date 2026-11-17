"""A tag removed from a file is cleared in the library on rescan (#6333).

audio_info_to_track_info omits keys for missing tags and the update path only wrote present keys, so
deleting the album/artist/genre/year/track-number tag and rescanning updated the other fields and kept
the removed values. The scanner now asks for ``replace_tags``; a partial update (no flag) still leaves
absent keys alone.
"""

from sqlalchemy import select

from auralis.library.models import Album, Track

PATH = "/tmp/6333_1.flac"


def _full_info(**over):
    info = {
        "filepath": PATH, "title": "Song", "duration": 10.0, "sample_rate": 44100, "channels": 2,
        "format": "FLAC", "artists": ["Band"], "genres": ["Rock"], "album": "Rec",
        "year": 1999, "track_number": 3, "disc_number": 1,
    }
    info.update(over)
    return info


def _row(db):
    with db.SessionLocal() as s:
        track = s.execute(select(Track)).scalars().first()
        return {
            "artists": [a.name for a in track.artists], "genres": [g.name for g in track.genres],
            "album": track.album.title if track.album else None,
            "year": track.year, "track": track.track_number, "disc": track.disc_number,
            "albums": [a.title for a in s.execute(select(Album)).scalars()],
        }


def test_a_rescan_without_the_tags_clears_them(library_database):
    repo = library_database.tracks
    repo.add(_full_info())
    bare = {k: v for k, v in _full_info().items() if k not in {"artists", "genres", "album", "year", "track_number", "disc_number"}}

    repo.update_by_filepath(PATH, bare, replace_tags=True)

    assert _row(library_database) == {
        "artists": [], "genres": [], "album": None, "year": None, "track": None, "disc": None, "albums": [],
    }


def test_a_partial_update_without_the_flag_leaves_absent_tags_alone(library_database):
    repo = library_database.tracks
    repo.add(_full_info())

    repo.update_by_filepath(PATH, {"title": "Retitled"})

    row = _row(library_database)
    assert row["artists"] == ["Band"] and row["album"] == "Rec" and row["year"] == 1999

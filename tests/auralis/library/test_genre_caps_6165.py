"""Genre tags are capped in length and count before they are stored (#6165).

Title, album and artists were truncated by ``add()``; ``genres`` went straight to
``Genre(name=...)``, so a crafted TCON frame was stored once and returned in every
track and genre payload.
"""

from auralis.library.repositories.track_repository_lifecycle import (
    MAX_GENRE_NAME_LENGTH,
    MAX_GENRES_PER_TRACK,
)


def _add(track_repository, genres):
    track = track_repository.add({
        "filepath": "/tmp/genre_caps_6165.flac",
        "title": "T",
        "duration": 10.0,
        "sample_rate": 44100,
        "channels": 2,
        "format": "FLAC",
        "genres": genres,
    })
    assert track is not None
    return track_repository.get_by_id(track.id)


def test_oversized_genre_name_is_truncated(track_repository):
    track = _add(track_repository, ["x" * 50_000])

    assert [len(g.name) for g in track.genres] == [MAX_GENRE_NAME_LENGTH]


def test_genre_count_is_capped_and_non_strings_dropped(track_repository):
    names = [f"genre{i}" for i in range(MAX_GENRES_PER_TRACK + 30)]
    track = _add(track_repository, [None, 7, *names])

    assert sorted(g.name for g in track.genres) == sorted(names[:MAX_GENRES_PER_TRACK])


def test_ordinary_genres_are_unchanged(track_repository):
    track = _add(track_repository, ["Rock", "Jazz"])

    assert sorted(g.name for g in track.genres) == ["Jazz", "Rock"]

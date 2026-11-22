"""A multi-valued ID3 text frame yields one clean value, not a NUL-joined string (#6133).

``str(TPE1(text=['X', 'Y']))`` is ``'X\\x00Y'``; the scanner stored that as one
Artist row with an embedded NUL.
"""


from mutagen.id3 import TCON, TIT2, TPE1, TRCK  # noqa: E402

from auralis.library.scanner.metadata_extractor import MetadataExtractor  # noqa: E402


def test_multi_valued_frames_keep_every_artist_and_genre_but_one_title():
    """#6133: never a NUL-joined string. #5732: artist and genre keep all their values; a title has one."""
    audio = {
        "TPE1": TPE1(encoding=3, text=["X", "Y"]),
        "TIT2": TIT2(encoding=3, text=["A", "B"]),
        "TCON": TCON(encoding=3, text=["Rock", "Pop"]),
    }

    metadata = MetadataExtractor().extract_metadata(audio)

    assert metadata["artist"] == ["X", "Y"]
    assert metadata["title"] == "A"
    assert metadata["genre"] == ["Rock", "Pop"]
    assert not any("\x00" in str(v) for v in metadata.values())


def test_single_valued_frames_and_track_numbers_are_unchanged():
    audio = {"TIT2": TIT2(encoding=3, text=["Solo"]), "TRCK": TRCK(encoding=3, text=["3/12"])}

    metadata = MetadataExtractor().extract_metadata(audio)

    assert metadata["title"] == "Solo"
    assert metadata["track"] == 3


def test_an_absurd_track_or_disc_number_is_dropped_not_stored_5732():
    """#5732: int(tag) was unbounded; a value past SQLite's int64 blocked the track's ingest."""
    audio = {
        "TRCK": TRCK(encoding=3, text=["99999999999999999999999/12"]),
        "TPOS": TRCK(encoding=3, text=["7"]),
        "TIT2": TIT2(encoding=3, text=["Song"]),
    }

    metadata = MetadataExtractor().extract_metadata(audio)

    assert "track" not in metadata
    assert metadata["title"] == "Song"
    assert metadata["disc"] == 7


def test_repeated_vorbis_values_and_mp4_lists_keep_every_value_without_repeats_5732():
    extractor = MetadataExtractor()

    vorbis = extractor.extract_metadata({"ARTIST": ["Artist One", "Artist Two", "Artist One"], "GENRE": ["Rock", "Pop"]})
    mp4 = extractor.extract_metadata({"\xa9ART": ["A", "B"], "\xa9gen": ["Jazz"]})

    assert vorbis["artist"] == ["Artist One", "Artist Two"]
    assert vorbis["genre"] == ["Rock", "Pop"]
    assert mp4["artist"] == ["A", "B"]
    assert mp4["genre"] == "Jazz"  # a single value stays a string, as before


def test_every_value_reaches_the_track_model_as_a_list_5732():
    extractor = MetadataExtractor()
    info = MetadataExtractor.audio_info_to_track_info(
        extractor,
        type("Info", (), {
            "filepath": "/m/x.flac", "duration": 1.0, "sample_rate": 44100, "channels": 2, "format": "flac",
            "filesize": 10, "metadata": {"artist": ["Artist One", "Artist Two"], "genre": ["Rock", "Pop"]},
        })(),
    )

    assert info["artists"] == ["Artist One", "Artist Two"]
    assert info["genres"] == ["Rock", "Pop"]


def test_a_real_flac_with_repeated_tags_is_stored_with_every_artist_and_genre_5732(library_database, tmp_path):
    """File -> mutagen -> extractor -> repository: the track ends up linked to all of them."""
    import numpy as np
    import soundfile as sf
    from mutagen.flac import FLAC

    path = tmp_path / "multi.flac"
    sf.write(str(path), np.zeros((4410, 2), dtype=np.float32), 44100, format="FLAC")
    tags = FLAC(str(path))
    tags["ARTIST"] = ["Artist One", "Artist Two"]
    tags["GENRE"] = ["Rock", "Pop"]
    tags["TITLE"] = "Duet"
    tags.save()

    extractor = MetadataExtractor()
    info = extractor.audio_info_to_track_info(
        type("Info", (), {
            "filepath": str(path), "duration": 0.1, "sample_rate": 44100, "channels": 2, "format": "FLAC",
            "filesize": path.stat().st_size, "metadata": extractor.extract_metadata_from_file(str(path)),
        })()
    )
    track = library_database.tracks.add(info)

    assert track is not None
    # In tag order: track_artist.position keeps it (#6714; this read
    # ["Artist Two", "Artist One"] before the column existed).
    assert [a.name for a in track.artists] == ["Artist One", "Artist Two"]
    assert sorted(g.name for g in track.genres) == ["Pop", "Rock"]

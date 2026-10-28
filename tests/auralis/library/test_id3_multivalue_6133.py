"""A multi-valued ID3 text frame yields one clean value, not a NUL-joined string (#6133).

``str(TPE1(text=['X', 'Y']))`` is ``'X\\x00Y'``; the scanner stored that as one
Artist row with an embedded NUL.
"""

import pytest

pytest.importorskip("mutagen")
from mutagen.id3 import TCON, TIT2, TPE1, TRCK  # noqa: E402

from auralis.library.scanner.metadata_extractor import MetadataExtractor  # noqa: E402


def test_multi_valued_frames_use_their_first_value():
    audio = {
        "TPE1": TPE1(encoding=3, text=["X", "Y"]),
        "TIT2": TIT2(encoding=3, text=["A", "B"]),
        "TCON": TCON(encoding=3, text=["Rock", "Pop"]),
    }

    metadata = MetadataExtractor().extract_metadata(audio)

    assert metadata["artist"] == "X"
    assert metadata["title"] == "A"
    assert metadata["genre"] == "Rock"
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

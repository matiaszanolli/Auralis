"""Artwork extraction prefers the front cover and finds folder art in any case (#5929).

_extract_from_id3 / _extract_from_flac returned the first picture, so a file listing its back
cover first showed that as the album art; the folder lookup tried a fixed list of spellings and
missed Cover.JPG and cover.webp on a case-sensitive filesystem.
"""

import base64
import io

import pytest
from mutagen.flac import Picture
from mutagen.id3 import APIC, ID3
from PIL import Image

from auralis.library.artwork import ArtworkExtractor
from auralis.library.picture_choice import front_cover_first
from auralis.library.folder_artwork import candidate_cover_files


def _image(fmt, color):
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), color).save(buf, format=fmt)
    return buf.getvalue()


BACK, FRONT = _image("JPEG", "red"), _image("JPEG", "blue")


@pytest.fixture
def extractor(tmp_path):
    return ArtworkExtractor(artwork_directory=str(tmp_path / "art"))


def _apic(kind, data, desc):
    return APIC(encoding=3, mime="image/jpeg", type=kind, desc=desc, data=data)


def test_id3_front_cover_wins_over_an_earlier_back_cover(extractor):
    tags = ID3()
    tags.add(_apic(4, BACK, "back"))
    tags.add(_apic(3, FRONT, "front"))

    assert extractor._extract_from_id3(tags)[0] == FRONT


def test_id3_without_a_front_cover_keeps_the_first_picture(extractor):
    tags = ID3()
    tags.add(_apic(4, BACK, "back"))

    assert extractor._extract_from_id3(tags)[0] == BACK


def test_flac_front_cover_wins(extractor):
    def pic(kind, data):
        p = Picture()
        p.type, p.mime, p.data = kind, "image/jpeg", data
        return p

    class _Flac:
        pictures = [pic(4, BACK), pic(3, FRONT)]

    assert extractor._extract_from_flac(_Flac())[0] == FRONT


def test_vorbis_picture_blocks_prefer_the_front_cover(extractor):
    def block(kind, data):
        p = Picture()
        p.type, p.mime, p.data = kind, "image/jpeg", data
        return base64.b64encode(p.write()).decode()

    class _Ogg:
        tags = {"METADATA_BLOCK_PICTURE": [block(4, BACK), block(3, FRONT)]}

    assert extractor._extract_from_generic(_Ogg())[0] == FRONT


def test_front_cover_first_returns_the_only_picture():
    only = Picture()

    assert front_cover_first([only]) is only


def test_folder_cover_names_match_in_any_case_and_webp(tmp_path):
    (tmp_path / "Cover.JPG").write_bytes(FRONT)
    (tmp_path / "notes.txt").write_text("x")
    (tmp_path / "FOLDER.webp").write_bytes(b"x")

    names = [p.name for p in candidate_cover_files(tmp_path)]

    assert names == ["FOLDER.webp", "Cover.JPG"]  # folder outranks cover


def test_folder_art_with_uppercase_name_is_extracted(extractor, tmp_path):
    album = tmp_path / "album"
    album.mkdir()
    (album / "Cover.JPG").write_bytes(FRONT)

    saved = extractor._find_folder_artwork(str(album / "01.flac"), album_id=1)

    assert saved is not None
    assert open(saved, "rb").read() == FRONT


def test_a_missing_folder_has_no_candidates(tmp_path):
    assert candidate_cover_files(tmp_path / "nope") == []

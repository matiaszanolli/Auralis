"""Folder cover files are read only when they are real image files (#6160).

An album folder is untrusted: ``cover.jpg`` could be a symlink to a secret (the
target would be copied into the served artwork directory), a FIFO (blocks the
scan forever) or ``/dev/zero`` (unbounded read).
"""

import os

import pytest
from PIL import Image

from auralis.library.artwork import ArtworkExtractor
from auralis.library.folder_artwork import read_folder_artwork


@pytest.fixture
def album(tmp_path):
    folder = tmp_path / "album"
    folder.mkdir()
    return folder


def _jpeg(path):
    Image.new("RGB", (32, 32), (9, 9, 9)).save(path, format="JPEG")
    return path


def test_regular_image_file_is_read(album):
    cover = _jpeg(album / "cover.jpg")

    assert read_folder_artwork(cover) == cover.read_bytes()


def test_symlink_to_a_secret_is_refused(album, tmp_path):
    secret = tmp_path / "id_ed25519"
    secret.write_text("-----BEGIN OPENSSH PRIVATE KEY-----")
    (album / "cover.jpg").symlink_to(secret)

    assert read_folder_artwork(album / "cover.jpg") is None


def test_symlink_to_a_real_image_is_refused_too(album, tmp_path):
    real = _jpeg(tmp_path / "elsewhere.jpg")
    (album / "cover.jpg").symlink_to(real)

    assert read_folder_artwork(album / "cover.jpg") is None


def test_fifo_does_not_block(album):
    os.mkfifo(album / "cover.jpg")

    assert read_folder_artwork(album / "cover.jpg") is None


def test_non_image_content_is_refused(album):
    (album / "cover.jpg").write_text("not an image at all")

    assert read_folder_artwork(album / "cover.jpg") is None


def test_missing_file_is_none(album):
    assert read_folder_artwork(album / "cover.jpg") is None


def test_extractor_skips_a_symlinked_cover_and_uses_the_next_name(album, tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text("top secret")
    (album / "cover.jpg").symlink_to(secret)
    _jpeg(album / "folder.jpg")
    (album / "track.mp3").write_bytes(b"x")
    extractor = ArtworkExtractor(str(tmp_path / "artwork"))

    saved = extractor._find_folder_artwork(str(album / "track.mp3"), album_id=3)

    assert saved is not None
    assert open(saved, "rb").read(3) == b"\xff\xd8\xff"
    assert b"top secret" not in open(saved, "rb").read()

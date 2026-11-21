"""Rewriting a live artwork file never shows a reader a truncated image (#6575).

Both artwork writers opened the content-hash-named destination ``'wb'`` - truncating the file in
place - and then wrote the bytes. Re-extracting or re-downloading the same cover produces the same
name, so a concurrent artwork GET or thumbnail render could read a zero-length or partial image.
They now publish through ``write_bytes_atomic`` (a staged sibling file + ``os.replace``).
"""
import asyncio
import io
import os
import sys
import threading
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "auralis-web" / "backend"))

from services.artwork_downloader import ArtworkDownloader  # noqa: E402

from auralis.library.artwork import ArtworkExtractor  # noqa: E402
from auralis.utils.atomic_write import write_bytes_atomic  # noqa: E402


def _png(size: int = 64) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (size, size), (200, 40, 90)).save(buffer, format="PNG")
    return buffer.getvalue()


def _assert_replaced_not_truncated(path: Path, rewrite) -> None:
    """A reader holding the old file keeps every byte; the path gets a new, complete file."""
    original = path.read_bytes()
    with path.open("rb") as reader:
        before = os.fstat(reader.fileno()).st_ino
        rewrite()
        assert reader.read() == original, "the file being read was truncated under the reader"
    assert path.stat().st_ino != before, "the destination was rewritten in place, not replaced"
    assert path.read_bytes() == original


def test_write_bytes_atomic_replaces_instead_of_truncating(tmp_path):
    target = tmp_path / "album_1_deadbeef.png"
    data = _png()
    write_bytes_atomic(target, data)

    _assert_replaced_not_truncated(target, lambda: write_bytes_atomic(target, data))
    assert sorted(p.name for p in tmp_path.iterdir()) == [target.name]  # no staged leftovers
    assert target.stat().st_mode & 0o044, "served artwork must stay group/world readable"


def test_extractor_rewrite_of_the_same_cover_is_atomic(tmp_path):
    extractor = ArtworkExtractor(str(tmp_path))
    data = _png()
    path = Path(extractor._save_artwork(data, album_id=7, mime_type="image/png"))

    _assert_replaced_not_truncated(path, lambda: extractor._save_artwork(data, album_id=7, mime_type="image/png"))


def test_downloader_rewrite_of_the_same_cover_is_atomic(tmp_path):
    downloader = ArtworkDownloader(cache_dir=str(tmp_path))
    data = _png()
    path = Path(asyncio.run(downloader._save_artwork(data, album_id=7, ext="png")))

    _assert_replaced_not_truncated(path, lambda: asyncio.run(downloader._save_artwork(data, album_id=7, ext="png")))


def test_a_reader_never_sees_a_partial_image_while_the_same_bytes_are_rewritten(tmp_path):
    target = tmp_path / "album_1_cafebabe.png"
    data = _png(256)
    write_bytes_atomic(target, data)
    stop = threading.Event()
    short_reads: list[int] = []

    def reader():
        while not stop.is_set():
            got = len(target.read_bytes())
            if got != len(data):
                short_reads.append(got)

    thread = threading.Thread(target=reader)
    thread.start()
    try:
        for _ in range(200):
            write_bytes_atomic(target, data)
    finally:
        stop.set()
        thread.join()

    assert short_reads == []

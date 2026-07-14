"""Regression tests for downloaded-artwork serving directory (#4408).

ArtworkDownloader used to default to ``~/.auralis/artwork_cache`` while the GET
endpoint (routers/artwork.py) only serves ``~/.auralis/artwork`` and 403s
anything outside it. So every online download saved to a directory the server
would never serve — online artwork was 100% broken end-to-end. The downloader
now defaults to the single served directory.
"""

import sys
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[2] / "auralis-web" / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from services.artwork_downloader import ArtworkDownloader  # noqa: E402

# The directory the GET endpoint hard-codes as allowed (routers/artwork.py:163).
SERVED_DIR = (Path.home() / ".auralis" / "artwork").resolve()

_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


def test_default_cache_dir_is_the_served_directory():
    # The independently-derived download target and serve target must agree,
    # or the router's is_relative_to guard rejects every downloaded image.
    downloader = ArtworkDownloader()
    assert downloader.cache_dir.resolve() == SERVED_DIR


@pytest.mark.asyncio
async def test_saved_artwork_passes_the_serving_guard(tmp_path, monkeypatch):
    # Redirect HOME (what both `~` expansion and Path.home() read on POSIX) so
    # the default target lands under a temp served dir, then replay the exact
    # guard the GET endpoint applies to album.artwork_path.
    monkeypatch.setenv("HOME", str(tmp_path))
    served = (Path("~/.auralis/artwork").expanduser()).resolve()

    downloader = ArtworkDownloader()  # default cache_dir -> served dir
    saved = await downloader._save_artwork(_PNG, album_id=42, ext="jpg")

    requested_path = Path(saved).resolve(strict=False)
    assert requested_path.is_relative_to(served)  # would be False for artwork_cache
    assert requested_path.exists()

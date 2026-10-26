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

from auralis.library import data_dir  # noqa: E402
from core.thumbnail_cache import artwork_cache_root  # noqa: E402
from services.artwork_downloader import ArtworkDownloader  # noqa: E402

_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


@pytest.fixture
def scratch_profile(tmp_path, monkeypatch):
    """A throwaway profile: HOME in tmp, no open library redirecting the data dir."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(data_dir, "_database_data_dir", None)
    return tmp_path


def test_default_cache_dir_is_the_served_directory(scratch_profile):
    # The independently-derived download target and serve target must agree,
    # or the router's is_relative_to guard rejects every downloaded image.
    downloader = ArtworkDownloader()
    assert downloader.cache_dir.resolve() == artwork_cache_root().resolve()


@pytest.mark.asyncio
async def test_saved_artwork_passes_the_serving_guard(scratch_profile):
    # The default target lands under the (temp) served dir; replay the exact
    # guard the GET endpoint applies to album.artwork_path.
    served = artwork_cache_root().resolve()

    downloader = ArtworkDownloader()  # default cache_dir -> served dir
    saved = await downloader._save_artwork(_PNG, album_id=42, ext="jpg")

    requested_path = Path(saved).resolve(strict=False)
    assert requested_path.is_relative_to(served)  # would be False for artwork_cache
    assert requested_path.exists()

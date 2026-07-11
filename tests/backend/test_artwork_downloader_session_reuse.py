"""
ArtworkDownloader Session Reuse & Async File Write Tests (#3915)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Regression coverage for a re-introduction of the pattern #3558 fixed:
`_try_musicbrainz`/`_try_itunes` each opened a fresh `aiohttp.ClientSession`
per call (no connection-pool reuse across a bulk artwork backfill), and
`_save_artwork` wrote to disk synchronously on the event loop.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from services.artwork_downloader import ArtworkDownloader, close_artwork_downloader
import services.artwork_downloader as artwork_downloader_module


class _FailFastResponse:
    """Fake aiohttp response context manager: non-200, so callers bail out
    before touching .json()/.content — proves session reuse without any
    real network I/O."""
    status = 599

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


class TestSharedSession:
    @pytest.mark.asyncio
    async def test_get_session_reuses_existing_session(self, tmp_path):
        downloader = ArtworkDownloader(cache_dir=str(tmp_path))
        try:
            session1 = downloader._get_session()
            session2 = downloader._get_session()
            assert session1 is session2
        finally:
            await downloader.close()

    @pytest.mark.asyncio
    async def test_get_session_creates_new_session_after_close(self, tmp_path):
        downloader = ArtworkDownloader(cache_dir=str(tmp_path))
        session1 = downloader._get_session()
        await downloader.close()

        assert session1.closed
        session2 = downloader._get_session()
        try:
            assert session2 is not session1
            assert not session2.closed
        finally:
            await downloader.close()

    @pytest.mark.asyncio
    async def test_close_is_safe_when_never_used(self, tmp_path):
        downloader = ArtworkDownloader(cache_dir=str(tmp_path))
        await downloader.close()  # must not raise
        assert downloader._session is None

    @pytest.mark.asyncio
    async def test_close_is_idempotent(self, tmp_path):
        downloader = ArtworkDownloader(cache_dir=str(tmp_path))
        downloader._get_session()
        await downloader.close()
        await downloader.close()  # must not raise
        assert downloader._session is None

    @pytest.mark.asyncio
    async def test_musicbrainz_and_itunes_share_the_same_session_across_calls(self, tmp_path):
        """Two consecutive artwork lookups must reuse one aiohttp.ClientSession
        instance instead of opening a fresh one per call — the core regression
        this issue tracks."""
        downloader = ArtworkDownloader(cache_dir=str(tmp_path))
        sessions_seen = []

        real_get_session = downloader._get_session

        def _spy_get_session():
            session = real_get_session()
            sessions_seen.append(session)
            return session

        downloader._get_session = _spy_get_session  # type: ignore[method-assign]

        try:
            with patch.object(aiohttp.ClientSession, "get", return_value=_FailFastResponse()):
                await downloader._try_musicbrainz("Artist", "Album", 1)
                await downloader._try_itunes("Artist", "Album", 1)

            assert len(sessions_seen) == 2
            assert sessions_seen[0] is sessions_seen[1], (
                "Expected _try_musicbrainz and _try_itunes to share one "
                "session — got two distinct ClientSession instances"
            )
        finally:
            await downloader.close()

    @pytest.mark.asyncio
    async def test_close_artwork_downloader_is_safe_when_singleton_never_created(self):
        with patch.object(artwork_downloader_module, "_artwork_downloader", None):
            await close_artwork_downloader()  # must not raise

    @pytest.mark.asyncio
    async def test_close_artwork_downloader_closes_the_singleton_session(self, tmp_path):
        downloader = ArtworkDownloader(cache_dir=str(tmp_path))
        session = downloader._get_session()

        with patch.object(artwork_downloader_module, "_artwork_downloader", downloader):
            await close_artwork_downloader()

        assert session.closed


class TestSaveArtworkOffloadsWrite:
    @pytest.mark.asyncio
    async def test_save_artwork_writes_correct_bytes(self, tmp_path):
        downloader = ArtworkDownloader(cache_dir=str(tmp_path))
        data = b"fake-image-bytes"

        path = await downloader._save_artwork(data, album_id=42, ext="jpg")

        written = Path(path)
        assert written.exists()
        assert written.read_bytes() == data
        assert written.name.startswith("album_42_")
        await downloader.close()

    @pytest.mark.asyncio
    async def test_save_artwork_offloads_write_via_to_thread(self, tmp_path):
        """The blocking file write must go through asyncio.to_thread rather
        than run directly on the event loop (#3915)."""
        downloader = ArtworkDownloader(cache_dir=str(tmp_path))

        with patch(
            "services.artwork_downloader.asyncio.to_thread", new_callable=AsyncMock
        ) as mock_to_thread:
            await downloader._save_artwork(b"data", album_id=1, ext="jpg")

        mock_to_thread.assert_awaited_once()
        write_fn, written_data = mock_to_thread.call_args.args
        assert write_fn.__name__ == "write_bytes"
        assert written_data == b"data"
        await downloader.close()

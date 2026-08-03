"""Regression tests for post-redirect artwork URL validation (#4940)."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from services.artwork_downloader import ArtworkDownloader


class _Response:
    def __init__(
        self,
        *,
        url: str,
        json_data=None,
        content: bytes = b"image-bytes",
    ) -> None:
        self.status = 200
        self.url = url
        self.content_length = len(content)
        self._json_data = json_data
        self.content = Mock()
        self.content.read = AsyncMock(return_value=content)

    async def json(self):
        return self._json_data

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


class TestITunesRedirectValidation:
    @staticmethod
    def _search_response() -> _Response:
        return _Response(
            url="https://itunes.apple.com/search",
            json_data={
                "results": [
                    {
                        "artworkUrl100": (
                            "https://is1-ssl.mzstatic.com/image/100x100.jpg"
                        )
                    }
                ]
            },
        )

    @pytest.mark.asyncio
    async def test_rejects_untrusted_final_redirect_before_reading(self, tmp_path):
        downloader = ArtworkDownloader(cache_dir=str(tmp_path))
        search_response = self._search_response()
        download_response = _Response(url="http://127.0.0.1:8765/api/library")
        session = Mock()
        session.get.side_effect = [search_response, download_response]
        downloader._save_artwork = AsyncMock()  # type: ignore[method-assign]

        with patch.object(downloader, "_get_session", return_value=session):
            result = await downloader._try_itunes("Artist", "Album", 1)

        assert result is None
        download_response.content.read.assert_not_awaited()
        downloader._save_artwork.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_accepts_allowlisted_final_redirect(self, tmp_path):
        downloader = ArtworkDownloader(cache_dir=str(tmp_path))
        search_response = self._search_response()
        download_response = _Response(
            url="https://is2-ssl.mzstatic.com/image/600x600.jpg"
        )
        session = Mock()
        session.get.side_effect = [search_response, download_response]
        downloader._save_artwork = AsyncMock(  # type: ignore[method-assign]
            return_value=str(tmp_path / "album.jpg")
        )

        with patch.object(downloader, "_get_session", return_value=session):
            result = await downloader._try_itunes("Artist", "Album", 1)

        assert result == str(tmp_path / "album.jpg")
        download_response.content.read.assert_awaited_once()
        downloader._save_artwork.assert_awaited_once_with(b"image-bytes", 1, "jpg")

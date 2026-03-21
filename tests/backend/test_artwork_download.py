"""
Artwork Download Endpoint Tests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests for POST /api/albums/{album_id}/artwork/download (#2743).

Covers:
- Happy path: successful download from online sources
- 404: album not found
- 404: no artwork found online
- 503: repository factory unavailable
- 500: download failure (unexpected exception)

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))


class TestArtworkDownloadEndpoint:
    """Tests for POST /api/albums/{album_id}/artwork/download"""

    def _make_mock_album(self, album_id: int = 1, title: str = "Test Album",
                         artist_name: str = "Test Artist") -> Mock:
        """Create a mock album with artist relationship."""
        album = Mock()
        album.id = album_id
        album.title = title
        album.artist = Mock()
        album.artist.name = artist_name
        return album

    def _make_mock_repos(self, album: Mock | None = None) -> Mock:
        """Create mock repos that return the given album on get_by_id."""
        repos = Mock()
        repos.albums.get_by_id.return_value = album
        repos.albums.update_artwork_path.return_value = album
        return repos

    # ------------------------------------------------------------------
    # Happy path
    # ------------------------------------------------------------------

    def test_download_artwork_success(self, client):
        """Happy path: download artwork and broadcast update."""
        album = self._make_mock_album()
        repos = self._make_mock_repos(album)

        mock_downloader = AsyncMock()
        mock_downloader.download_artwork.return_value = "/home/user/.auralis/artwork/1.jpg"

        with (
            patch('routers.artwork.require_repository_factory', return_value=repos),
            patch('services.artwork_downloader.get_artwork_downloader',
                  return_value=mock_downloader),
        ):
            response = client.post("/api/albums/1/artwork/download")

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Artwork downloaded successfully"
        assert data["artwork_url"] == "/api/albums/1/artwork"
        assert data["album_id"] == 1
        assert data["artist"] == "Test Artist"
        assert data["album"] == "Test Album"

        mock_downloader.download_artwork.assert_awaited_once_with(
            artist="Test Artist", album="Test Album", album_id=1
        )
        repos.albums.update_artwork_path.assert_called_once_with(
            1, "/home/user/.auralis/artwork/1.jpg"
        )

    def test_download_artwork_unknown_artist_fallback(self, client):
        """Album without artist uses 'Unknown Artist' fallback."""
        album = self._make_mock_album()
        album.artist = None  # No artist relationship
        repos = self._make_mock_repos(album)

        mock_downloader = AsyncMock()
        mock_downloader.download_artwork.return_value = "/home/user/.auralis/artwork/1.jpg"

        with (
            patch('routers.artwork.require_repository_factory', return_value=repos),
            patch('services.artwork_downloader.get_artwork_downloader',
                  return_value=mock_downloader),
        ):
            response = client.post("/api/albums/1/artwork/download")

        assert response.status_code == 200
        mock_downloader.download_artwork.assert_awaited_once_with(
            artist="Unknown Artist", album="Test Album", album_id=1
        )

    # ------------------------------------------------------------------
    # 404 cases
    # ------------------------------------------------------------------

    def test_download_artwork_album_not_found(self, client):
        """Return 404 when album does not exist."""
        repos = self._make_mock_repos(album=None)

        with patch('routers.artwork.require_repository_factory', return_value=repos):
            response = client.post("/api/albums/999/artwork/download")

        assert response.status_code == 404
        assert "Album not found" in response.json()["detail"]

    def test_download_artwork_no_artwork_found_online(self, client):
        """Return 404 when no artwork is found from any online source."""
        album = self._make_mock_album()
        repos = self._make_mock_repos(album)

        mock_downloader = AsyncMock()
        mock_downloader.download_artwork.return_value = None  # No artwork found

        with (
            patch('routers.artwork.require_repository_factory', return_value=repos),
            patch('services.artwork_downloader.get_artwork_downloader',
                  return_value=mock_downloader),
        ):
            response = client.post("/api/albums/1/artwork/download")

        assert response.status_code == 404
        assert "No artwork found online" in response.json()["detail"]
        assert "Test Album" in response.json()["detail"]
        assert "Test Artist" in response.json()["detail"]

    def test_download_artwork_update_path_fails(self, client):
        """Return 404 when DB update of artwork path fails (album disappeared)."""
        album = self._make_mock_album()
        repos = self._make_mock_repos(album)
        repos.albums.update_artwork_path.return_value = None  # Update returns None

        mock_downloader = AsyncMock()
        mock_downloader.download_artwork.return_value = "/home/user/.auralis/artwork/1.jpg"

        with (
            patch('routers.artwork.require_repository_factory', return_value=repos),
            patch('services.artwork_downloader.get_artwork_downloader',
                  return_value=mock_downloader),
        ):
            response = client.post("/api/albums/1/artwork/download")

        assert response.status_code == 404
        assert "Album not found" in response.json()["detail"]

    # ------------------------------------------------------------------
    # 503 — service unavailable
    # ------------------------------------------------------------------

    def test_download_artwork_repository_unavailable(self, client):
        """Return 503 when repository factory is not initialised."""
        with patch('routers.artwork.require_repository_factory',
                   side_effect=__import__('fastapi').HTTPException(
                       status_code=503, detail="Repository factory not available")):
            response = client.post("/api/albums/1/artwork/download")

        assert response.status_code == 503
        assert "Repository factory not available" in response.json()["detail"]

    # ------------------------------------------------------------------
    # 500 — unexpected failure
    # ------------------------------------------------------------------

    def test_download_artwork_unexpected_exception(self, client):
        """Return 500 when downloader raises an unexpected exception."""
        album = self._make_mock_album()
        repos = self._make_mock_repos(album)

        mock_downloader = AsyncMock()
        mock_downloader.download_artwork.side_effect = RuntimeError("Connection refused")

        with (
            patch('routers.artwork.require_repository_factory', return_value=repos),
            patch('services.artwork_downloader.get_artwork_downloader',
                  return_value=mock_downloader),
        ):
            response = client.post("/api/albums/1/artwork/download")

        assert response.status_code == 500
        assert "Failed to download artwork" in response.json()["detail"]

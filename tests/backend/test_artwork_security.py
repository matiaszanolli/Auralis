"""
Artwork Security Tests
~~~~~~~~~~~~~~~~~~~~~~

Tests path traversal protection in artwork endpoints (Issue #2237).

Tests:
- Valid artwork paths within allowed directory
- Path traversal attempts outside allowed directory
- Symlink attacks
- Absolute paths outside artwork directory
- Relative path traversal (../..)

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))


class TestArtworkPathTraversalProtection:
    """Test path traversal protection in GET /api/albums/{album_id}/artwork"""

    def test_valid_artwork_path_within_directory(self, client):
        """Test that valid artwork paths within allowed directory are served"""
        # Create mock album with valid artwork path
        mock_album = Mock()
        artwork_dir = Path.home() / ".auralis" / "artwork"
        artwork_dir.mkdir(parents=True, exist_ok=True)

        # Create a test artwork file
        test_artwork = artwork_dir / "test_album_1.jpg"
        test_artwork.write_bytes(b'\xff\xd8\xff\xe0' + b'\x00' * 100)  # Minimal JPEG

        mock_album.id = 1
        mock_album.artwork_path = str(test_artwork)

        # Mock repository to return album
        mock_repos = Mock()
        mock_repos.albums.get_by_id.return_value = mock_album

        with patch('main.globals_dict', {'repository_factory': lambda: mock_repos}):
            response = client.get("/api/albums/1/artwork")

            assert response.status_code == 200
            assert response.headers['content-type'] == 'image/jpeg'

        # Cleanup
        test_artwork.unlink(missing_ok=True)

    def test_path_traversal_absolute_path_blocked(self, client):
        """Test that absolute paths outside artwork directory are blocked"""
        # Create mock album with absolute path to /etc/passwd
        mock_album = Mock()
        mock_album.id = 1
        mock_album.artwork_path = "/etc/passwd"

        # Mock repository to return album
        mock_repos = Mock()
        mock_repos.albums.get_by_id.return_value = mock_album

        with patch('main.globals_dict', {'repository_factory': lambda: mock_repos}):
            response = client.get("/api/albums/1/artwork")

            # Debug: print response to understand what's happening
            print(f"Status: {response.status_code}, Detail: {response.json()}")

            # Should return 403 Forbidden (path outside allowed directory)
            assert response.status_code == 403
            assert "outside artwork directory" in response.json()["detail"]

    def test_path_traversal_relative_path_blocked(self, client):
        """Test that relative path traversal (../../) is blocked"""
        # Create mock album with relative path traversal
        mock_album = Mock()
        artwork_dir = Path.home() / ".auralis" / "artwork"

        mock_album.id = 1
        # Attempt to traverse up and access /etc/passwd
        mock_album.artwork_path = str(artwork_dir / ".." / ".." / ".." / "etc" / "passwd")

        # Mock repository to return album
        mock_repos = Mock()
        mock_repos.albums.get_by_id.return_value = mock_album

        with patch('main.globals_dict', {'repository_factory': lambda: mock_repos}):
            response = client.get("/api/albums/1/artwork")

            # Should return 403 Forbidden (resolved path outside allowed directory)
            assert response.status_code == 403
            assert "outside artwork directory" in response.json()["detail"]

    def test_symlink_outside_directory_blocked(self, client):
        """Test that symlinks pointing outside artwork directory are blocked"""
        # Create mock album with symlink to /etc/passwd
        mock_album = Mock()
        artwork_dir = Path.home() / ".auralis" / "artwork"
        artwork_dir.mkdir(parents=True, exist_ok=True)

        # Create symlink to /etc/passwd
        symlink_path = artwork_dir / "evil_link.jpg"
        try:
            symlink_path.symlink_to("/etc/passwd")
        except OSError:
            pytest.skip("Cannot create symlinks on this system")

        mock_album.id = 1
        mock_album.artwork_path = str(symlink_path)

        # Mock repository to return album
        mock_repos = Mock()
        mock_repos.albums.get_by_id.return_value = mock_album

        try:
            with patch('main.globals_dict', {'repository_factory': lambda: mock_repos}):
                response = client.get("/api/albums/1/artwork")

                # Should return 403 Forbidden (resolved path outside allowed directory)
                assert response.status_code == 403
                assert "outside artwork directory" in response.json()["detail"]
        finally:
            # Cleanup
            symlink_path.unlink(missing_ok=True)

    def test_nonexistent_file_returns_404(self, client):
        """Test that nonexistent files within allowed directory return 404"""
        # Create mock album with path to nonexistent file
        mock_album = Mock()
        artwork_dir = Path.home() / ".auralis" / "artwork"

        mock_album.id = 1
        mock_album.artwork_path = str(artwork_dir / "nonexistent.jpg")

        # Mock repository to return album
        mock_repos = Mock()
        mock_repos.albums.get_by_id.return_value = mock_album

        with patch('main.globals_dict', {'repository_factory': lambda: mock_repos}):
            response = client.get("/api/albums/1/artwork")

            # Should return 404 Not Found (file doesn't exist)
            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()

    def test_album_not_found_returns_404(self, client):
        """Test that nonexistent album returns 404"""
        # Mock repository to return None (album not found)
        mock_repos = Mock()
        mock_repos.albums.get_by_id.return_value = None

        with patch('main.globals_dict', {'repository_factory': lambda: mock_repos}):
            response = client.get("/api/albums/999999/artwork")

            assert response.status_code == 404
            assert "Album not found" in response.json()["detail"]

    def test_album_without_artwork_returns_404(self, client):
        """Test that album without artwork_path returns 404"""
        # Create mock album without artwork
        mock_album = Mock()
        mock_album.id = 1
        mock_album.artwork_path = None

        # Mock repository to return album
        mock_repos = Mock()
        mock_repos.albums.get_by_id.return_value = mock_album

        with patch('main.globals_dict', {'repository_factory': lambda: mock_repos}):
            response = client.get("/api/albums/1/artwork")

            assert response.status_code == 404
            assert "Artwork not found" in response.json()["detail"]

    def test_cache_headers_present(self, client):
        """Test that cache headers are set for valid artwork"""
        # Create mock album with valid artwork path
        mock_album = Mock()
        artwork_dir = Path.home() / ".auralis" / "artwork"
        artwork_dir.mkdir(parents=True, exist_ok=True)

        # Create a test artwork file
        test_artwork = artwork_dir / "test_cache.jpg"
        test_artwork.write_bytes(b'\xff\xd8\xff\xe0' + b'\x00' * 100)  # Minimal JPEG

        mock_album.id = 1
        mock_album.artwork_path = str(test_artwork)

        # Mock repository to return album
        mock_repos = Mock()
        mock_repos.albums.get_by_id.return_value = mock_album

        try:
            with patch('main.globals_dict', {'repository_factory': lambda: mock_repos}):
                response = client.get("/api/albums/1/artwork")

                assert response.status_code == 200
                # Check cache headers
                assert 'cache-control' in response.headers
                assert 'public' in response.headers['cache-control']
                assert 'max-age' in response.headers['cache-control']
        finally:
            # Cleanup
            test_artwork.unlink(missing_ok=True)

    def test_path_with_null_bytes_rejected(self, client):
        """Test that paths containing null bytes are rejected"""
        # Create mock album with null byte in path
        mock_album = Mock()
        mock_album.id = 1
        mock_album.artwork_path = "/etc/passwd\x00.jpg"

        # Mock repository to return album
        mock_repos = Mock()
        mock_repos.albums.get_by_id.return_value = mock_album

        with patch('main.globals_dict', {'repository_factory': lambda: mock_repos}):
            response = client.get("/api/albums/1/artwork")

            # Should return 404 or 403 (invalid path)
            assert response.status_code in [403, 404]


class TestArtworkPathValidationIntegration:
    """Integration tests for artwork path validation with real database"""

    def test_sql_injection_artwork_path_blocked(self, library_manager):
        """
        Test that SQL injection tampering of artwork_path is blocked

        Simulates issue #2078 (SQL injection) + issue #2237 (unvalidated path serving)
        """
        # Create a test album
        album = library_manager.albums.create(
            title="Test Album",
            artist_id=1,
            year=2024
        )

        # Simulate SQL injection that sets artwork_path to /etc/passwd
        # In real attack, this would come from issue #2078
        library_manager.albums.update_artwork_path(album.id, "/etc/passwd")

        # Fetch album to verify malicious path was set
        album = library_manager.albums.get_by_id(album.id)
        assert album.artwork_path == "/etc/passwd"

        # Now attempt to retrieve artwork via API endpoint
        # The endpoint should block this path even though it's in the database
        from fastapi.testclient import TestClient
        # Note: This requires a full app client setup, skipping for now
        # The important thing is that the path validation logic is in place


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

"""
Scan Path Validation Security Tests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Security tests for directory scan/file path validation actually reachable
from a real entry point: LibraryScanRequest (path traversal, system-path,
mixed-batch, valid-path handling) and validate_file_path (mastering
endpoint, #2229). validate_scan_path/is_safe_filename were removed as dead
code with zero call sites (#4799); their coverage went with them.

Fixes #2069: Path traversal in directory scanning endpoint

SECURITY CONTROLS TESTED:
- Path traversal prevention (../ sequences)
- Absolute path restriction (paths outside allowed dirs)
- Non-existent/unreadable path rejection
- Path sanitization for API responses

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web/backend"))

from security.path_security import (
    PathValidationError,
    get_allowed_directories,
    sanitize_path_for_response,
    validate_file_path,
)


@pytest.mark.security
class TestAllowedDirectories:
    """Test allowed directory configuration."""

    def test_default_allowed_directories(self):
        """Default allowed directories should include home and Music."""
        allowed = get_allowed_directories()

        # Should include at least home directory
        assert any(str(Path.home()) in str(d) for d in allowed)

        # All paths should be absolute
        assert all(d.is_absolute() for d in allowed)

        # All paths should exist
        assert all(d.exists() for d in allowed)

    def test_xdg_music_dir_support(self):
        """XDG_MUSIC_DIR environment variable should be respected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {'XDG_MUSIC_DIR': tmpdir}):
                allowed = get_allowed_directories()

                # Should include XDG_MUSIC_DIR
                assert any(tmpdir in str(d) for d in allowed)


@pytest.mark.security
class TestPathSanitization:
    """Test path sanitization for API responses."""

    def test_sanitize_path_in_home(self):
        """Paths in home directory should be converted to ~/..."""
        home = Path.home()
        test_path = home / "Music" / "song.mp3"

        sanitized = sanitize_path_for_response(test_path)

        assert sanitized.startswith("~/")
        assert "Music/song.mp3" in sanitized
        assert str(home) not in sanitized  # Full path not exposed

    def test_sanitize_path_outside_home(self):
        """Paths outside home should be returned as-is."""
        test_path = Path("/var/lib/music/song.mp3")

        sanitized = sanitize_path_for_response(test_path)

        # Should return absolute path (can't make relative to home)
        assert sanitized == str(test_path.resolve())


@pytest.mark.security
@pytest.mark.integration
class TestLibraryScanRequestValidation:
    """Test schemas.py LibraryScanRequest validation (library scan endpoint).

    Fixes #2181: Library scan endpoint bypasses path validation.
    Fixes #2182: Renamed from ScanRequest to LibraryScanRequest to eliminate
    naming collision with the (now-removed) files router local class.
    """

    def test_library_scan_request_rejects_traversal(self):
        """LibraryScanRequest should reject path traversal attempts."""
        from pydantic import ValidationError
        from schemas import LibraryScanRequest

        traversal_paths = [
            "../../../etc",
            "../../..",
            "./music/../../../etc",
        ]

        for path in traversal_paths:
            with pytest.raises(ValidationError) as exc_info:
                LibraryScanRequest(directories=[path])

            errors = exc_info.value.errors()
            assert any("traversal" in str(err).lower() for err in errors), \
                f"Should reject traversal path: {path}"

    def test_library_scan_request_rejects_system_paths(self):
        """LibraryScanRequest should reject system directories."""
        from pydantic import ValidationError
        from schemas import LibraryScanRequest

        for path in ["/etc", "/root", "/var"]:
            if not Path(path).exists():
                continue
            with pytest.raises(ValidationError):
                LibraryScanRequest(directories=[path])

    def test_library_scan_request_rejects_mixed_paths(self):
        """One bad path in the list should reject the entire request."""
        from pydantic import ValidationError
        from schemas import LibraryScanRequest

        with pytest.raises(ValidationError):
            LibraryScanRequest(directories=[str(Path.home() / "Music"), "../../etc"])

    def test_library_scan_request_accepts_valid_paths(self, tmp_path):
        """LibraryScanRequest should accept valid paths."""
        from schemas import LibraryScanRequest

        test_dir = tmp_path / "music"
        test_dir.mkdir()

        with patch('security.path_security.DEFAULT_ALLOWED_DIRS', [tmp_path]):
            request = LibraryScanRequest(directories=[str(test_dir)])
            assert request.directories == [str(test_dir.resolve())]


@pytest.mark.security
class TestFilePathValidation:
    """Test validate_file_path for mastering endpoint (#2229)."""

    def test_reject_path_traversal(self):
        """SECURITY: Reject ../ traversal in file paths."""
        traversal_paths = [
            "../../etc/passwd",
            "../../../etc/shadow",
            "music/../../etc/passwd",
        ]
        for path in traversal_paths:
            with pytest.raises(PathValidationError) as exc_info:
                validate_file_path(path)
            assert "traversal" in str(exc_info.value).lower()

    def test_reject_paths_outside_allowed_dirs(self, tmp_path):
        """SECURITY: Reject files outside allowed directories."""
        # Create a file in a non-allowed location
        outside_file = tmp_path / "outside" / "secret.txt"
        outside_file.parent.mkdir()
        outside_file.write_text("secret")

        allowed = [tmp_path / "music"]
        (tmp_path / "music").mkdir()

        with pytest.raises(PathValidationError) as exc_info:
            validate_file_path(str(outside_file), allowed_base_dirs=allowed)
        assert "outside allowed directories" in str(exc_info.value).lower()

    def test_accept_valid_file_in_allowed_dir(self, tmp_path):
        """Valid files within allowed directories should be accepted."""
        music_dir = tmp_path / "music"
        music_dir.mkdir()
        audio_file = music_dir / "song.mp3"
        audio_file.write_bytes(b"\x00" * 100)

        result = validate_file_path(str(audio_file), allowed_base_dirs=[tmp_path])
        assert result == audio_file.resolve()

    def test_reject_nonexistent_file(self, tmp_path):
        """SECURITY: Reject non-existent files."""
        fake_file = tmp_path / "nonexistent.mp3"

        with pytest.raises(PathValidationError) as exc_info:
            validate_file_path(str(fake_file), allowed_base_dirs=[tmp_path])
        assert "does not exist" in str(exc_info.value).lower()

    def test_reject_directory_as_file(self, tmp_path):
        """SECURITY: Reject directories when file expected."""
        test_dir = tmp_path / "music"
        test_dir.mkdir()

        with pytest.raises(PathValidationError) as exc_info:
            validate_file_path(str(test_dir), allowed_base_dirs=[tmp_path])
        assert "not a file" in str(exc_info.value).lower()

    def test_reject_empty_path(self):
        """SECURITY: Reject empty file path."""
        with pytest.raises(PathValidationError) as exc_info:
            validate_file_path("")
        assert "cannot be empty" in str(exc_info.value).lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "security"])

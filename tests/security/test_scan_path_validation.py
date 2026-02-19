"""
Scan Path Validation Security Tests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Security tests for directory scan path validation.

Fixes #2069: Path traversal in directory scanning endpoint

SECURITY CONTROLS TESTED:
- Path traversal prevention (../ sequences)
- Absolute path restriction (paths outside allowed dirs)
- Symlink attack prevention (path resolution)
- Non-existent directory rejection
- Unreadable directory rejection
- Empty/null path rejection

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

from path_security import (
    PathValidationError,
    get_allowed_directories,
    is_safe_filename,
    sanitize_path_for_response,
    validate_file_path,
    validate_scan_path,
)


@pytest.mark.security
class TestPathTraversalPrevention:
    """Test path traversal prevention in scan endpoint."""

    def test_reject_parent_directory_traversal(self):
        """
        SECURITY: Reject ../ path traversal sequences.
        Attack vector: Access directories outside allowed paths.
        """
        traversal_paths = [
            "../../../etc",
            "../../..",
            "../sensitive",
            "music/../../etc",
            "./music/../../../etc",
        ]

        for path in traversal_paths:
            with pytest.raises(PathValidationError) as exc_info:
                validate_scan_path(path)

            assert "path traversal" in str(exc_info.value).lower(), \
                f"Should reject traversal path: {path}"

    def test_reject_absolute_paths_outside_allowed(self):
        """
        SECURITY: Reject absolute paths outside allowed directories.
        Attack vector: Direct access to system directories.
        """
        # These paths should be rejected (not in user's home directory)
        system_paths = [
            "/etc",
            "/var",
            "/tmp/system",
            "/root",
            "/proc",
            "/sys",
        ]

        allowed_dirs = [Path.home()]  # Only allow home directory

        for path in system_paths:
            # Skip if path doesn't exist (can't test on all systems)
            if not Path(path).exists():
                continue

            with pytest.raises(PathValidationError) as exc_info:
                validate_scan_path(path, allowed_base_dirs=allowed_dirs)

            assert "outside allowed directories" in str(exc_info.value).lower(), \
                f"Should reject system path: {path}"

    def test_accept_valid_paths_in_home(self, tmp_path):
        """Valid paths within home directory should be accepted."""
        # Create test directory in home
        test_dir = tmp_path / "music"
        test_dir.mkdir()

        # Mock Path.home() to return tmp_path
        with patch('path_security.Path.home', return_value=tmp_path):
            # Should accept path in home directory
            result = validate_scan_path(str(test_dir))
            assert result == test_dir.resolve()

    def test_reject_non_existent_directory(self):
        """
        SECURITY: Reject non-existent directories.
        Prevents enumeration attacks.
        """
        non_existent = str(Path.home() / "this_directory_does_not_exist_12345")

        with pytest.raises(PathValidationError) as exc_info:
            validate_scan_path(non_existent)

        assert "does not exist" in str(exc_info.value).lower()

    def test_reject_file_as_directory(self, tmp_path):
        """
        SECURITY: Reject files when directory expected.
        """
        # Create a file (not directory)
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")

        with patch('path_security.Path.home', return_value=tmp_path):
            with pytest.raises(PathValidationError) as exc_info:
                validate_scan_path(str(test_file))

            assert "not a directory" in str(exc_info.value).lower()

    def test_reject_unreadable_directory(self, tmp_path):
        """
        SECURITY: Reject unreadable directories.
        """
        # Create unreadable directory
        test_dir = tmp_path / "unreadable"
        test_dir.mkdir()

        # Remove read permission
        os.chmod(test_dir, 0o000)

        try:
            with patch('path_security.Path.home', return_value=tmp_path):
                with pytest.raises(PathValidationError) as exc_info:
                    validate_scan_path(str(test_dir))

                assert "not readable" in str(exc_info.value).lower()
        finally:
            # Restore permissions for cleanup
            os.chmod(test_dir, 0o755)

    def test_reject_empty_path(self):
        """
        SECURITY: Reject empty path strings.
        """
        with pytest.raises(PathValidationError) as exc_info:
            validate_scan_path("")

        assert "cannot be empty" in str(exc_info.value).lower()

    def test_reject_null_path(self):
        """
        SECURITY: Reject null/None paths.
        """
        with pytest.raises(PathValidationError):
            validate_scan_path(None)  # type: ignore

    def test_symlink_resolution(self, tmp_path):
        """
        SECURITY: Symlinks are resolved and validated against final target.
        Prevents symlink attacks to escape allowed directories.
        """
        # Create target directory outside allowed area
        system_dir = tmp_path / "system"
        system_dir.mkdir()

        # Create allowed directory
        allowed_dir = tmp_path / "music"
        allowed_dir.mkdir()

        # Create symlink from allowed to system
        symlink = allowed_dir / "link_to_system"
        symlink.symlink_to(system_dir)

        # Mock Path.home() to only allow music directory
        with patch('path_security.Path.home', return_value=tmp_path):
            # Symlink target (system_dir) is outside allowed (music only)
            # Should be rejected after resolution
            with pytest.raises(PathValidationError) as exc_info:
                validate_scan_path(
                    str(symlink),
                    allowed_base_dirs=[allowed_dir]
                )

            assert "outside allowed directories" in str(exc_info.value).lower()


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
class TestFilenameValidation:
    """Test filename safety validation."""

    def test_safe_filenames(self):
        """Safe filenames should be accepted."""
        safe_names = [
            "song.mp3",
            "track-01.flac",
            "my_music_file.wav",
            "Album Name - Song.m4a",
            "file.ogg",
        ]

        for name in safe_names:
            assert is_safe_filename(name), f"Should accept safe filename: {name}"

    def test_reject_path_traversal_in_filename(self):
        """
        SECURITY: Filenames with path traversal should be rejected.
        """
        unsafe_names = [
            "../../../etc/passwd",
            "../../file.mp3",
            "../music.mp3",
            "dir/../file.mp3",
        ]

        for name in unsafe_names:
            assert not is_safe_filename(name), \
                f"Should reject unsafe filename: {name}"

    def test_reject_absolute_paths_in_filename(self):
        """
        SECURITY: Absolute paths should be rejected as filenames.
        """
        absolute_paths = [
            "/etc/passwd",
            "/var/log/file.mp3",
            "C:\\Windows\\file.mp3",
        ]

        for name in absolute_paths:
            assert not is_safe_filename(name), \
                f"Should reject absolute path: {name}"

    def test_reject_null_bytes(self):
        """
        SECURITY: Null bytes in filenames should be rejected.
        """
        assert not is_safe_filename("file\0.mp3")
        assert not is_safe_filename("\0passwd")

    def test_reject_empty_filename(self):
        """Empty filenames should be rejected."""
        assert not is_safe_filename("")

    def test_reject_hidden_files_except_music(self):
        """Hidden files should be rejected unless they're music files."""
        # Non-music hidden files
        assert not is_safe_filename(".hidden")
        assert not is_safe_filename(".env")
        assert not is_safe_filename(".secret")

        # Music hidden files should be OK (unlikely but valid)
        assert is_safe_filename(".song.mp3")
        assert is_safe_filename(".track.flac")


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

        with patch('path_security.DEFAULT_ALLOWED_DIRS', [tmp_path]):
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

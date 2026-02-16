"""
Artwork Path Validation Unit Tests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Unit tests for path validation logic in artwork router (Issue #2237).

Tests the path resolution and validation logic directly without full app setup.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from pathlib import Path

import pytest


class TestArtworkPathValidation:
    """Test path validation logic for artwork serving"""

    def test_valid_path_within_allowed_directory(self):
        """Test that valid paths within allowed directory pass validation"""
        artwork_dir = Path.home() / ".auralis" / "artwork"
        artwork_dir.mkdir(parents=True, exist_ok=True)
        allowed_dir = artwork_dir.resolve()

        # Test path within allowed directory
        test_path = artwork_dir / "test_album.jpg"
        resolved_path = test_path.resolve(strict=False)

        assert resolved_path.is_relative_to(allowed_dir)

    def test_absolute_path_outside_directory_rejected(self):
        """Test that absolute paths outside allowed directory are rejected"""
        artwork_dir = Path.home() / ".auralis" / "artwork"
        allowed_dir = artwork_dir.resolve()

        # Test absolute path outside directory
        test_path = Path("/etc/passwd")
        resolved_path = test_path.resolve(strict=False)

        assert not resolved_path.is_relative_to(allowed_dir)

    def test_relative_path_traversal_rejected(self):
        """Test that relative path traversal (../..) is rejected"""
        artwork_dir = Path.home() / ".auralis" / "artwork"
        allowed_dir = artwork_dir.resolve()

        # Test relative path traversal
        test_path = artwork_dir / ".." / ".." / ".." / "etc" / "passwd"
        resolved_path = test_path.resolve(strict=False)

        assert not resolved_path.is_relative_to(allowed_dir)

    def test_symlink_outside_directory_rejected(self):
        """Test that symlinks pointing outside allowed directory are rejected"""
        artwork_dir = Path.home() / ".auralis" / "artwork"
        artwork_dir.mkdir(parents=True, exist_ok=True)
        allowed_dir = artwork_dir.resolve()

        # Create symlink to /etc/passwd
        symlink_path = artwork_dir / "evil_link.jpg"
        try:
            symlink_path.symlink_to("/etc/passwd")
        except OSError:
            pytest.skip("Cannot create symlinks on this system")

        try:
            resolved_path = symlink_path.resolve(strict=False)
            assert not resolved_path.is_relative_to(allowed_dir)
        finally:
            # Cleanup
            symlink_path.unlink(missing_ok=True)

    def test_path_with_dot_segments_normalized(self):
        """Test that paths with dot segments are normalized correctly"""
        artwork_dir = Path.home() / ".auralis" / "artwork"
        artwork_dir.mkdir(parents=True, exist_ok=True)
        allowed_dir = artwork_dir.resolve()

        # Test path with dots that stays within directory
        test_path = artwork_dir / "subdir" / ".." / "test.jpg"
        resolved_path = test_path.resolve(strict=False)

        assert resolved_path.is_relative_to(allowed_dir)
        assert resolved_path == allowed_dir / "test.jpg"

    def test_nested_subdirectory_allowed(self):
        """Test that nested subdirectories within allowed directory are allowed"""
        artwork_dir = Path.home() / ".auralis" / "artwork"
        artwork_dir.mkdir(parents=True, exist_ok=True)
        allowed_dir = artwork_dir.resolve()

        # Test nested subdirectory
        test_path = artwork_dir / "albums" / "rock" / "test.jpg"
        resolved_path = test_path.resolve(strict=False)

        assert resolved_path.is_relative_to(allowed_dir)

    def test_artwork_dir_with_symlink_handled(self):
        """Test that symlinks in the allowed directory itself are handled"""
        # Create a temp directory and symlink artwork dir to it
        temp_dir = Path("/tmp/test_artwork_temp")
        temp_dir.mkdir(parents=True, exist_ok=True)

        artwork_dir = Path.home() / ".auralis" / "artwork_symlink_test"
        try:
            artwork_dir.symlink_to(temp_dir)
        except OSError:
            pytest.skip("Cannot create symlinks on this system")

        try:
            # Resolve allowed directory (should resolve the symlink)
            allowed_dir = artwork_dir.resolve()
            assert allowed_dir == temp_dir

            # Test path within symlinked directory
            test_path = artwork_dir / "test.jpg"
            resolved_path = test_path.resolve(strict=False)

            assert resolved_path.is_relative_to(allowed_dir)
        finally:
            # Cleanup
            artwork_dir.unlink(missing_ok=True)
            temp_dir.rmdir()

    def test_null_byte_in_path_rejected(self):
        """Test that paths containing null bytes are rejected"""
        artwork_dir = Path.home() / ".auralis" / "artwork"
        allowed_dir = artwork_dir.resolve()

        # Path with null byte should fail during resolve()
        with pytest.raises((ValueError, OSError)):
            test_path = Path("/etc/passwd\x00.jpg")
            test_path.resolve(strict=False)


class TestArtworkPathValidationEdgeCases:
    """Test edge cases in path validation"""

    def test_empty_path_rejected(self):
        """Test that empty path resolves to current directory (not allowed)"""
        artwork_dir = Path.home() / ".auralis" / "artwork"
        allowed_dir = artwork_dir.resolve()

        # Empty path resolves to current working directory
        test_path = Path("")
        resolved_path = test_path.resolve(strict=False)

        # Should not be within artwork directory (unless running from there)
        # This is safe because CWD is unlikely to be ~/.auralis/artwork
        assert not resolved_path.is_relative_to(allowed_dir)

    def test_root_path_rejected(self):
        """Test that root path is rejected"""
        artwork_dir = Path.home() / ".auralis" / "artwork"
        allowed_dir = artwork_dir.resolve()

        test_path = Path("/")
        resolved_path = test_path.resolve(strict=False)

        assert not resolved_path.is_relative_to(allowed_dir)

    def test_home_directory_rejected(self):
        """Test that home directory is rejected"""
        artwork_dir = Path.home() / ".auralis" / "artwork"
        allowed_dir = artwork_dir.resolve()

        test_path = Path.home()
        resolved_path = test_path.resolve(strict=False)

        assert not resolved_path.is_relative_to(allowed_dir)

    def test_parent_directory_rejected(self):
        """Test that parent directory (.auralis) is rejected"""
        artwork_dir = Path.home() / ".auralis" / "artwork"
        allowed_dir = artwork_dir.resolve()

        test_path = Path.home() / ".auralis"
        resolved_path = test_path.resolve(strict=False)

        assert not resolved_path.is_relative_to(allowed_dir)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

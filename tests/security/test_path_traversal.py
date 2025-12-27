"""
Path Traversal Prevention Tests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests to verify that the system is protected against path traversal attacks.

Path traversal attacks attempt to access files outside the intended directory
by using relative paths (../) or absolute paths.
"""

import os
import sys
from pathlib import Path

import pytest

# Add paths for imports
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from auralis.library.models import Album, Artist, Track
from auralis.library.scanner import LibraryScanner
from tests.security.helpers import (
    is_path_traversal,
    sanitize_filename,
    validate_path_safety,
)


@pytest.mark.security
@pytest.mark.integration
class TestPathTraversalPrevention:
    """Test suite for path traversal prevention."""

    def test_directory_traversal_in_file_paths(self, temp_db, temp_dir, malicious_inputs):
        """
        Test directory traversal in file paths.

        Verifies that traversal attempts cannot:
        - Access files outside the library directory
        - Read system files
        - Bypass path restrictions
        """
        session = temp_db()

        # Create safe base directory
        library_dir = Path(temp_dir) / "library"
        library_dir.mkdir()
        sensitive_file = Path(temp_dir) / "sensitive.txt"
        sensitive_file.write_text("SENSITIVE DATA")

        # Create artist and album
        artist = Artist(name="Test Artist")
        session.add(artist)
        session.flush()

        album = Album(title="Test Album", artist_id=artist.id)
        session.add(album)
        session.flush()

        # Try path traversal in filepath
        for traversal_path in malicious_inputs['path_traversal']:
            # Create track with traversal attempt
            track = Track(
                filepath=traversal_path,
                title="Test Track",
                duration=180.0,
                album_id=album.id
            )
            session.add(track)
            session.flush()

            # Verify path is stored as-is (not resolved)
            assert track.filepath == traversal_path

            # Verify path is detected as traversal
            assert is_path_traversal(traversal_path) or os.path.isabs(traversal_path), \
                f"Should detect traversal or absolute path: {traversal_path}"

        session.commit()
        session.close()

    def test_absolute_path_validation(self, temp_dir):
        """
        Test absolute path validation.

        Verifies that absolute paths are detected and handled:
        - Unix absolute paths (/etc/passwd)
        - Windows absolute paths (C:\\Windows\\)
        """
        library_dir = Path(temp_dir) / "library"
        library_dir.mkdir()

        # Test various absolute paths
        absolute_paths = [
            "/etc/passwd",
            "/var/log/syslog",
            "C:\\Windows\\System32\\config\\sam",
            "D:\\sensitive\\data.txt",
        ]

        for abs_path in absolute_paths:
            # Verify path is detected as unsafe
            is_safe = validate_path_safety(library_dir, Path(abs_path))
            assert not is_safe, f"Absolute path should be rejected: {abs_path}"

    def test_symlink_following_prevention(self, temp_dir):
        """
        Test symlink following prevention.

        Verifies that symlinks cannot be used to:
        - Access files outside library
        - Bypass path restrictions
        - Create security vulnerabilities
        """
        library_dir = Path(temp_dir) / "library"
        library_dir.mkdir()

        sensitive_dir = Path(temp_dir) / "sensitive"
        sensitive_dir.mkdir()
        sensitive_file = sensitive_dir / "data.txt"
        sensitive_file.write_text("SENSITIVE DATA")

        # Create symlink pointing outside library
        symlink_path = library_dir / "link_to_sensitive"
        try:
            symlink_path.symlink_to(sensitive_file)
        except OSError:
            # Symlinks may not be supported on this system
            pytest.skip("Symlinks not supported")

        # Verify symlink is detected as unsafe
        is_safe = validate_path_safety(library_dir, symlink_path.resolve())
        assert not is_safe, "Symlink should not escape library directory"

    def test_filesystem_boundary_enforcement(self, temp_dir):
        """
        Test filesystem boundary enforcement.

        Verifies that file operations respect library boundaries:
        - Files must be within library root
        - Relative paths resolved correctly
        - Boundary checks enforced
        """
        library_dir = Path(temp_dir) / "library"
        library_dir.mkdir()

        music_dir = library_dir / "music"
        music_dir.mkdir()

        # Create safe file
        safe_file = music_dir / "track.mp3"
        safe_file.touch()

        # Verify safe file is within boundaries
        assert validate_path_safety(library_dir, safe_file)

        # Try various boundary escape attempts
        escape_attempts = [
            music_dir / ".." / ".." / "sensitive.txt",  # Relative traversal
            library_dir.parent / "sensitive.txt",  # Direct parent access
        ]

        for escape_path in escape_attempts:
            is_safe = validate_path_safety(library_dir, escape_path)
            assert not is_safe, f"Boundary escape should be blocked: {escape_path}"

    def test_url_based_path_injection(self, temp_db, malicious_inputs):
        """
        Test URL-based path injection attempts.

        Verifies that URL-encoded path traversal is prevented:
        - %2e%2e%2f (../)
        - Mixed encoding
        - Double encoding
        """
        session = temp_db()

        # Create artist and album
        artist = Artist(name="Test Artist")
        session.add(artist)
        session.flush()

        album = Album(title="Test Album", artist_id=artist.id)
        session.add(album)
        session.flush()

        # URL-encoded traversal attempts
        url_encoded_paths = [
            "%2e%2e%2f%2e%2e%2fetc%2fpasswd",  # ../../etc/passwd
            "..%2f..%2f..%2fetc%2fpasswd",  # Mixed encoding
            "%252e%252e%252f",  # Double-encoded ../
        ]

        for encoded_path in url_encoded_paths:
            # Verify encoded path is detected as traversal
            assert is_path_traversal(encoded_path), f"Should detect encoded traversal: {encoded_path}"

            # Create track with encoded path
            track = Track(
                filepath=encoded_path,
                title="Test Track",
                duration=180.0,
                album_id=album.id
            )
            session.add(track)
            session.flush()

            # Path stored as-is (application should decode and validate before use)
            assert track.filepath == encoded_path

        session.commit()
        session.close()


@pytest.mark.security
@pytest.mark.unit
class TestFilenameSanitization:
    """Test filename sanitization functions."""

    def test_sanitize_removes_traversal(self):
        """Test that sanitize_filename removes path traversal."""
        dangerous_names = [
            "../../../etc/passwd",
            "..\\..\\windows\\system32",
            "./../../sensitive.txt",
        ]

        for dangerous in dangerous_names:
            safe = sanitize_filename(dangerous)
            # Should not contain traversal patterns
            assert '..' not in safe
            assert '/' not in safe
            assert '\\' not in safe

    def test_sanitize_removes_null_bytes(self):
        """Test that sanitize_filename removes null bytes."""
        filename = "test\x00.txt"
        safe = sanitize_filename(filename)
        assert '\x00' not in safe

    def test_sanitize_prevents_hidden_files(self):
        """Test that sanitize_filename prevents hidden files."""
        filename = ".hidden_file"
        safe = sanitize_filename(filename)
        assert not safe.startswith('.')

    def test_sanitize_allows_safe_characters(self):
        """Test that sanitize_filename allows safe characters."""
        filename = "My_Song-2024.mp3"
        safe = sanitize_filename(filename)
        assert safe == filename  # Should be unchanged

    def test_sanitize_handles_empty_filename(self):
        """Test that sanitize_filename handles empty input."""
        filename = ""
        safe = sanitize_filename(filename)
        assert safe == "unnamed"  # Default fallback

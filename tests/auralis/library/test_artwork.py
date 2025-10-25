"""
Tests for Artwork Extraction
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests the album artwork extraction and management system.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, mock_open
import sys

# Add auralis to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from auralis.library.artwork import (
    ArtworkExtractor,
    create_artwork_extractor
)


class TestArtworkExtractorInit:
    """Tests for ArtworkExtractor initialization"""

    def test_initialization(self):
        """Test basic initialization with temp directory"""
        with tempfile.TemporaryDirectory() as tmpdir:
            extractor = ArtworkExtractor(tmpdir)

            assert extractor.artwork_dir == Path(tmpdir)
            assert extractor.artwork_dir.exists()

    def test_initialization_creates_directory(self):
        """Test that initialization creates directory if it doesn't exist"""
        with tempfile.TemporaryDirectory() as tmpdir:
            artwork_dir = os.path.join(tmpdir, 'nested', 'artwork')

            extractor = ArtworkExtractor(artwork_dir)

            assert extractor.artwork_dir.exists()
            assert extractor.artwork_dir == Path(artwork_dir)


class TestExtractArtwork:
    """Tests for extract_artwork method"""

    def test_extract_artwork_no_file(self):
        """Test extracting from non-existent file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            extractor = ArtworkExtractor(tmpdir)

            with patch('auralis.library.artwork.MutagenFile', return_value=None):
                result = extractor.extract_artwork('/path/to/nonexistent.mp3', album_id=1)

                assert result is None

    def test_extract_artwork_exception_handling(self):
        """Test that exceptions are handled gracefully"""
        with tempfile.TemporaryDirectory() as tmpdir:
            extractor = ArtworkExtractor(tmpdir)

            with patch('auralis.library.artwork.MutagenFile', side_effect=Exception("Test error")):
                result = extractor.extract_artwork('/path/to/test.mp3', album_id=1)

                assert result is None


class TestExtractFromID3:
    """Tests for _extract_from_id3 method"""

    def test_extract_from_id3_no_apic(self):
        """Test extracting from ID3 without APIC frame"""
        with tempfile.TemporaryDirectory() as tmpdir:
            extractor = ArtworkExtractor(tmpdir)

            mock_tags = MagicMock()
            mock_tags.keys.return_value = ['TIT2', 'TPE1']

            data, mime = extractor._extract_from_id3(mock_tags)

            assert data is None
            assert mime is None

    def test_extract_from_id3_exception(self):
        """Test _extract_from_id3 handles exceptions"""
        with tempfile.TemporaryDirectory() as tmpdir:
            extractor = ArtworkExtractor(tmpdir)

            mock_tags = MagicMock()
            mock_tags.keys.side_effect = Exception("Test error")

            data, mime = extractor._extract_from_id3(mock_tags)

            assert data is None
            assert mime is None


class TestExtractFromMP4:
    """Tests for _extract_from_mp4 method"""

    def test_extract_from_mp4_jpeg(self):
        """Test extracting JPEG artwork from MP4"""
        with tempfile.TemporaryDirectory() as tmpdir:
            extractor = ArtworkExtractor(tmpdir)

            # Create mock cover that returns bytes when bytes() is called
            mock_cover = b'jpeg_data'

            # Mock the imageformat attribute
            mock_cover_obj = MagicMock()
            mock_cover_obj.imageformat = 13  # MP4Cover.FORMAT_JPEG
            # Make bytes(mock_cover_obj) work
            mock_cover_obj.__class__.__bytes__ = lambda self: mock_cover

            mock_audio = MagicMock()
            mock_audio.tags = {'covr': [mock_cover_obj]}

            with patch('auralis.library.artwork.MP4Cover.FORMAT_JPEG', 13):
                data, mime = extractor._extract_from_mp4(mock_audio)

                assert data == b'jpeg_data'
                assert mime == 'image/jpeg'

    def test_extract_from_mp4_png(self):
        """Test extracting PNG artwork from MP4"""
        with tempfile.TemporaryDirectory() as tmpdir:
            extractor = ArtworkExtractor(tmpdir)

            # Create mock cover that returns bytes when bytes() is called
            mock_cover = b'png_data'

            # Mock the imageformat attribute
            mock_cover_obj = MagicMock()
            mock_cover_obj.imageformat = 14  # MP4Cover.FORMAT_PNG
            # Make bytes(mock_cover_obj) work
            mock_cover_obj.__class__.__bytes__ = lambda self: mock_cover

            mock_audio = MagicMock()
            mock_audio.tags = {'covr': [mock_cover_obj]}

            with patch('auralis.library.artwork.MP4Cover.FORMAT_PNG', 14):
                data, mime = extractor._extract_from_mp4(mock_audio)

                assert data == b'png_data'
                assert mime == 'image/png'

    def test_extract_from_mp4_no_cover(self):
        """Test extracting from MP4 without cover art"""
        with tempfile.TemporaryDirectory() as tmpdir:
            extractor = ArtworkExtractor(tmpdir)

            mock_audio = MagicMock()
            mock_audio.tags = {}

            data, mime = extractor._extract_from_mp4(mock_audio)

            assert data is None
            assert mime is None


class TestExtractFromFLAC:
    """Tests for _extract_from_flac method"""

    def test_extract_from_flac_with_pictures(self):
        """Test extracting from FLAC with embedded pictures"""
        with tempfile.TemporaryDirectory() as tmpdir:
            extractor = ArtworkExtractor(tmpdir)

            mock_picture = MagicMock()
            mock_picture.data = b'flac_image_data'
            mock_picture.mime = 'image/jpeg'

            mock_audio = MagicMock()
            mock_audio.pictures = [mock_picture]

            data, mime = extractor._extract_from_flac(mock_audio)

            assert data == b'flac_image_data'
            assert mime == 'image/jpeg'

    def test_extract_from_flac_no_pictures(self):
        """Test extracting from FLAC without pictures"""
        with tempfile.TemporaryDirectory() as tmpdir:
            extractor = ArtworkExtractor(tmpdir)

            mock_audio = MagicMock()
            mock_audio.pictures = []

            data, mime = extractor._extract_from_flac(mock_audio)

            assert data is None
            assert mime is None


class TestSaveArtwork:
    """Tests for _save_artwork method"""

    def test_save_artwork_jpeg(self):
        """Test saving JPEG artwork"""
        with tempfile.TemporaryDirectory() as tmpdir:
            extractor = ArtworkExtractor(tmpdir)

            artwork_data = b'jpeg_image_data'
            album_id = 123

            result = extractor._save_artwork(artwork_data, album_id, 'image/jpeg')

            assert result is not None
            assert 'album_123_' in result
            assert result.endswith('.jpg')
            assert Path(result).exists()

    def test_save_artwork_png(self):
        """Test saving PNG artwork"""
        with tempfile.TemporaryDirectory() as tmpdir:
            extractor = ArtworkExtractor(tmpdir)

            artwork_data = b'png_image_data'
            album_id = 456

            result = extractor._save_artwork(artwork_data, album_id, 'image/png')

            assert result is not None
            assert 'album_456_' in result
            assert result.endswith('.png')

    def test_save_artwork_default_extension(self):
        """Test saving artwork with unknown MIME type defaults to JPG"""
        with tempfile.TemporaryDirectory() as tmpdir:
            extractor = ArtworkExtractor(tmpdir)

            artwork_data = b'unknown_image_data'
            album_id = 789

            result = extractor._save_artwork(artwork_data, album_id, 'image/unknown')

            assert result is not None
            assert result.endswith('.jpg')

    def test_save_artwork_same_content_same_hash(self):
        """Test that same content produces same hash in filename"""
        with tempfile.TemporaryDirectory() as tmpdir:
            extractor = ArtworkExtractor(tmpdir)

            artwork_data = b'identical_data'
            album_id = 100

            result1 = extractor._save_artwork(artwork_data, album_id, 'image/jpeg')
            result2 = extractor._save_artwork(artwork_data, album_id, 'image/jpeg')

            # Same album + same content = same filename
            assert Path(result1).name == Path(result2).name


class TestGetArtworkPath:
    """Tests for get_artwork_path method"""

    def test_get_artwork_path_exists(self):
        """Test getting path for existing artwork"""
        with tempfile.TemporaryDirectory() as tmpdir:
            extractor = ArtworkExtractor(tmpdir)

            # Create a test artwork file
            artwork_data = b'test_data'
            album_id = 42
            saved_path = extractor._save_artwork(artwork_data, album_id, 'image/jpeg')

            # Now retrieve it
            retrieved_path = extractor.get_artwork_path(album_id)

            assert retrieved_path is not None
            assert retrieved_path == saved_path

    def test_get_artwork_path_not_exists(self):
        """Test getting path for non-existent artwork"""
        with tempfile.TemporaryDirectory() as tmpdir:
            extractor = ArtworkExtractor(tmpdir)

            result = extractor.get_artwork_path(album_id=999)

            assert result is None


class TestDeleteArtwork:
    """Tests for delete_artwork method"""

    def test_delete_artwork_exists(self):
        """Test deleting existing artwork"""
        with tempfile.TemporaryDirectory() as tmpdir:
            extractor = ArtworkExtractor(tmpdir)

            # Create artwork file
            artwork_data = b'test_data'
            saved_path = extractor._save_artwork(artwork_data, 1, 'image/jpeg')

            # Delete it
            result = extractor.delete_artwork(saved_path)

            assert result is True
            assert not Path(saved_path).exists()

    def test_delete_artwork_not_exists(self):
        """Test deleting non-existent artwork"""
        with tempfile.TemporaryDirectory() as tmpdir:
            extractor = ArtworkExtractor(tmpdir)

            result = extractor.delete_artwork('/path/to/nonexistent.jpg')

            assert result is False

    def test_delete_artwork_exception(self):
        """Test delete handles exceptions"""
        with tempfile.TemporaryDirectory() as tmpdir:
            extractor = ArtworkExtractor(tmpdir)

            with patch('pathlib.Path.unlink', side_effect=PermissionError("Access denied")):
                # Create a file to attempt deletion
                test_file = Path(tmpdir) / 'test.jpg'
                test_file.write_bytes(b'data')

                result = extractor.delete_artwork(str(test_file))

                assert result is False


class TestFactoryFunction:
    """Tests for create_artwork_extractor factory"""

    def test_create_artwork_extractor(self):
        """Test factory function creates ArtworkExtractor instance"""
        with tempfile.TemporaryDirectory() as tmpdir:
            extractor = create_artwork_extractor(tmpdir)

            assert isinstance(extractor, ArtworkExtractor)
            assert extractor.artwork_dir == Path(tmpdir)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

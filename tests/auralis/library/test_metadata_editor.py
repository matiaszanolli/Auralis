"""
Tests for Metadata Editor
~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests the audio file metadata editing system.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import pytest
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, call
import sys

# Add auralis to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from auralis.library.metadata_editor import (
    MetadataEditor,
    MetadataUpdate,
    create_metadata_editor,
    MUTAGEN_AVAILABLE
)


class TestMetadataUpdate:
    """Tests for MetadataUpdate dataclass"""

    def test_metadata_update_creation(self):
        """Test creating MetadataUpdate with required fields"""
        update = MetadataUpdate(
            track_id=1,
            filepath="/path/to/track.mp3",
            updates={'title': 'New Title'}
        )

        assert update.track_id == 1
        assert update.filepath == "/path/to/track.mp3"
        assert update.updates == {'title': 'New Title'}
        assert update.backup is True  # Default value

    def test_metadata_update_without_backup(self):
        """Test creating MetadataUpdate without backup"""
        update = MetadataUpdate(
            track_id=1,
            filepath="/path/to/track.mp3",
            updates={'title': 'New Title'},
            backup=False
        )

        assert update.backup is False


class TestMetadataEditorInit:
    """Tests for MetadataEditor initialization"""

    @pytest.mark.skipif(not MUTAGEN_AVAILABLE, reason="mutagen not installed")
    def test_initialization_with_mutagen(self):
        """Test initialization when mutagen is available"""
        editor = MetadataEditor()
        assert editor is not None

    @pytest.mark.skipif(MUTAGEN_AVAILABLE, reason="mutagen is installed")
    def test_initialization_without_mutagen(self):
        """Test initialization fails when mutagen is not available"""
        with pytest.raises(ImportError, match="mutagen library is required"):
            MetadataEditor()


@pytest.mark.skipif(not MUTAGEN_AVAILABLE, reason="mutagen not installed")
class TestMetadataEditorConstants:
    """Tests for MetadataEditor constants"""

    def test_standard_fields(self):
        """Test STANDARD_FIELDS constant"""
        editor = MetadataEditor()

        assert 'title' in editor.STANDARD_FIELDS
        assert 'artist' in editor.STANDARD_FIELDS
        assert 'album' in editor.STANDARD_FIELDS
        assert 'year' in editor.STANDARD_FIELDS
        assert 'genre' in editor.STANDARD_FIELDS
        assert len(editor.STANDARD_FIELDS) == 14

    def test_tag_mappings_formats(self):
        """Test TAG_MAPPINGS has all required formats"""
        editor = MetadataEditor()

        assert 'mp3' in editor.TAG_MAPPINGS
        assert 'flac' in editor.TAG_MAPPINGS
        assert 'm4a' in editor.TAG_MAPPINGS
        assert 'ogg' in editor.TAG_MAPPINGS

    def test_tag_mappings_fields(self):
        """Test TAG_MAPPINGS has standard fields for each format"""
        editor = MetadataEditor()

        for format_name, tag_map in editor.TAG_MAPPINGS.items():
            assert 'title' in tag_map
            assert 'artist' in tag_map
            assert 'album' in tag_map


@pytest.mark.skipif(not MUTAGEN_AVAILABLE, reason="mutagen not installed")
class TestSupportedFormats:
    """Tests for supported format queries"""

    def test_get_supported_formats(self):
        """Test getting list of supported formats"""
        editor = MetadataEditor()
        formats = editor.get_supported_formats()

        assert isinstance(formats, list)
        assert 'mp3' in formats
        assert 'flac' in formats
        assert 'm4a' in formats
        assert 'aac' in formats
        assert 'ogg' in formats
        assert 'wav' in formats

    def test_get_editable_fields_mp3(self):
        """Test getting editable fields for MP3"""
        editor = MetadataEditor()
        fields = editor.get_editable_fields('/path/to/file.mp3')

        assert isinstance(fields, list)
        assert 'title' in fields
        assert 'artist' in fields
        assert 'album' in fields
        assert len(fields) > 0

    def test_get_editable_fields_flac(self):
        """Test getting editable fields for FLAC"""
        editor = MetadataEditor()
        fields = editor.get_editable_fields('/path/to/file.flac')

        assert isinstance(fields, list)
        assert 'title' in fields
        assert 'artist' in fields

    def test_get_editable_fields_m4a(self):
        """Test getting editable fields for M4A"""
        editor = MetadataEditor()
        fields = editor.get_editable_fields('/path/to/file.m4a')

        assert 'title' in fields
        assert 'artist' in fields

    def test_get_editable_fields_unknown_format(self):
        """Test getting editable fields for unknown format (defaults to FLAC)"""
        editor = MetadataEditor()
        fields = editor.get_editable_fields('/path/to/file.xyz')

        assert isinstance(fields, list)
        assert len(fields) > 0  # Should default to FLAC tags


@pytest.mark.skipif(not MUTAGEN_AVAILABLE, reason="mutagen not installed")
class TestReadMetadata:
    """Tests for reading metadata"""

    def test_read_metadata_file_not_found(self):
        """Test reading metadata from non-existent file"""
        editor = MetadataEditor()

        with pytest.raises(FileNotFoundError, match="File not found"):
            editor.read_metadata('/path/to/nonexistent.mp3')

    def test_read_metadata_with_mock(self):
        """Test reading metadata with mocked file"""
        editor = MetadataEditor()

        with patch('auralis.library.metadata_editor.MutagenFile') as mock_file, \
             patch('os.path.exists', return_value=True):

            # Mock FLAC file with metadata
            mock_audio = MagicMock()
            mock_audio.__class__.__name__ = 'FLAC'
            mock_audio.__contains__ = lambda self, key: key in {'TITLE': ['Test Song']}
            mock_audio.__getitem__ = lambda self, key: ['Test Song']
            mock_file.return_value = mock_audio

            metadata = editor.read_metadata('/path/to/test.flac')

            assert isinstance(metadata, dict)
            mock_file.assert_called_once_with('/path/to/test.flac')


@pytest.mark.skipif(not MUTAGEN_AVAILABLE, reason="mutagen not installed")
class TestWriteMetadata:
    """Tests for writing metadata"""

    def test_write_metadata_file_not_found(self):
        """Test writing metadata to non-existent file"""
        editor = MetadataEditor()

        with pytest.raises(FileNotFoundError, match="File not found"):
            editor.write_metadata('/path/to/nonexistent.mp3', {'title': 'Test'})

    def test_write_metadata_creates_backup(self):
        """Test that write_metadata creates backup when requested"""
        editor = MetadataEditor()

        with patch('auralis.library.metadata_editor.MutagenFile') as mock_file, \
             patch('os.path.exists', return_value=True), \
             patch.object(editor, '_create_backup') as mock_backup:

            mock_audio = MagicMock()
            mock_audio.__class__.__name__ = 'FLAC'
            mock_file.return_value = mock_audio

            editor.write_metadata('/path/to/test.flac', {'title': 'New Title'}, backup=True)

            mock_backup.assert_called_once_with('/path/to/test.flac')

    def test_write_metadata_no_backup(self):
        """Test that write_metadata skips backup when not requested"""
        editor = MetadataEditor()

        with patch('auralis.library.metadata_editor.MutagenFile') as mock_file, \
             patch('os.path.exists', return_value=True), \
             patch.object(editor, '_create_backup') as mock_backup:

            mock_audio = MagicMock()
            mock_audio.__class__.__name__ = 'FLAC'
            mock_file.return_value = mock_audio

            editor.write_metadata('/path/to/test.flac', {'title': 'New Title'}, backup=False)

            mock_backup.assert_not_called()

    def test_write_metadata_saves_file(self):
        """Test that write_metadata saves the file"""
        editor = MetadataEditor()

        with patch('auralis.library.metadata_editor.MutagenFile') as mock_file, \
             patch('os.path.exists', return_value=True), \
             patch.object(editor, '_create_backup'):

            mock_audio = MagicMock()
            mock_audio.__class__.__name__ = 'FLAC'
            mock_file.return_value = mock_audio

            result = editor.write_metadata('/path/to/test.flac', {'title': 'New Title'})

            assert result is True
            mock_audio.save.assert_called_once()


@pytest.mark.skipif(not MUTAGEN_AVAILABLE, reason="mutagen not installed")
class TestBatchUpdate:
    """Tests for batch metadata updates"""

    def test_batch_update_all_success(self):
        """Test batch update with all successful updates"""
        editor = MetadataEditor()

        updates = [
            MetadataUpdate(1, '/path/to/track1.mp3', {'title': 'Title 1'}),
            MetadataUpdate(2, '/path/to/track2.mp3', {'title': 'Title 2'})
        ]

        with patch.object(editor, 'write_metadata', return_value=True):
            results = editor.batch_update(updates)

            assert results['success'] == 2
            assert results['failed'] == 0
            assert len(results['errors']) == 0

    def test_batch_update_with_failures(self):
        """Test batch update with some failures"""
        editor = MetadataEditor()

        updates = [
            MetadataUpdate(1, '/path/to/track1.mp3', {'title': 'Title 1'}),
            MetadataUpdate(2, '/path/to/track2.mp3', {'title': 'Title 2'})
        ]

        def mock_write(filepath, metadata, backup=True):
            if 'track2' in filepath:
                raise ValueError("Test error")
            return True

        with patch.object(editor, 'write_metadata', side_effect=mock_write):
            results = editor.batch_update(updates)

            assert results['success'] == 1
            assert results['failed'] == 1
            assert len(results['errors']) == 1
            assert results['errors'][0]['track_id'] == 2
            assert 'Test error' in results['errors'][0]['error']

    def test_batch_update_empty_list(self):
        """Test batch update with empty list"""
        editor = MetadataEditor()

        results = editor.batch_update([])

        assert results['success'] == 0
        assert results['failed'] == 0
        assert len(results['errors']) == 0


@pytest.mark.skipif(not MUTAGEN_AVAILABLE, reason="mutagen not installed")
class TestBackupRestore:
    """Tests for backup and restore functionality"""

    def test_create_backup(self):
        """Test creating backup file"""
        editor = MetadataEditor()

        with patch('shutil.copy2') as mock_copy:
            editor._create_backup('/path/to/test.mp3')

            mock_copy.assert_called_once_with('/path/to/test.mp3', '/path/to/test.mp3.bak')

    def test_create_backup_failure(self):
        """Test backup creation handles errors gracefully"""
        editor = MetadataEditor()

        with patch('shutil.copy2', side_effect=OSError("Permission denied")):
            # Should not raise, just log warning
            editor._create_backup('/path/to/test.mp3')

    def test_restore_backup(self):
        """Test restoring from backup"""
        editor = MetadataEditor()

        with patch('os.path.exists', return_value=True), \
             patch('shutil.move') as mock_move:

            editor._restore_backup('/path/to/test.mp3')

            mock_move.assert_called_once_with('/path/to/test.mp3.bak', '/path/to/test.mp3')

    def test_restore_backup_not_exists(self):
        """Test restore when backup doesn't exist"""
        editor = MetadataEditor()

        with patch('os.path.exists', return_value=False), \
             patch('shutil.move') as mock_move:

            editor._restore_backup('/path/to/test.mp3')

            mock_move.assert_not_called()


@pytest.mark.skipif(not MUTAGEN_AVAILABLE, reason="mutagen not installed")
class TestFactoryFunction:
    """Tests for create_metadata_editor factory"""

    def test_create_metadata_editor(self):
        """Test factory function creates MetadataEditor instance"""
        editor = create_metadata_editor()

        assert isinstance(editor, MetadataEditor)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

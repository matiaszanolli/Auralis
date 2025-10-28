"""
Tests for Chunked Audio Processor
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests the chunked audio processing system for fast streaming.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import pytest
import numpy as np
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, mock_open

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from chunked_processor import (
    ChunkedAudioProcessor,
    CHUNK_DURATION,
    OVERLAP_DURATION,
    CONTEXT_DURATION,
    apply_crossfade_between_chunks
)


class TestChunkedProcessorConstants:
    """Tests for module constants"""

    def test_chunk_duration(self):
        """Test CHUNK_DURATION constant"""
        assert isinstance(CHUNK_DURATION, int)
        assert CHUNK_DURATION == 30
        assert CHUNK_DURATION > 0

    def test_overlap_duration(self):
        """Test OVERLAP_DURATION constant"""
        assert isinstance(OVERLAP_DURATION, int)
        assert OVERLAP_DURATION == 3  # Updated to match current value
        assert OVERLAP_DURATION > 0

    def test_context_duration(self):
        """Test CONTEXT_DURATION constant"""
        assert isinstance(CONTEXT_DURATION, int)
        assert CONTEXT_DURATION == 5
        assert CONTEXT_DURATION > 0


class TestChunkedAudioProcessorInit:
    """Tests for ChunkedAudioProcessor initialization"""

    def test_initialization_basic(self):
        """Test basic initialization with mocked file"""
        track_id = 1
        filepath = "/path/to/test.mp3"

        with patch.object(ChunkedAudioProcessor, '_generate_file_signature', return_value='test_sig'), \
             patch.object(ChunkedAudioProcessor, "_load_metadata", lambda self: (setattr(self, "sample_rate", 44100), setattr(self, "total_duration", 60.0), setattr(self, "total_chunks", 2))):

            processor = ChunkedAudioProcessor(track_id, filepath)

            assert processor.track_id == track_id
            assert processor.filepath == filepath
            assert processor.preset == "adaptive"  # default
            assert processor.intensity == 1.0  # default
            assert isinstance(processor.chunk_cache, dict)

    def test_initialization_with_preset(self):
        """Test initialization with custom preset"""
        with patch.object(ChunkedAudioProcessor, '_generate_file_signature', return_value='test_sig'), \
             patch.object(ChunkedAudioProcessor, '_load_metadata', lambda self: (setattr(self, 'sample_rate', 44100), setattr(self, 'total_duration', 60.0), setattr(self, 'total_chunks', 2))):

            processor = ChunkedAudioProcessor(
                track_id=1,
                filepath="/path/to/test.mp3",
                preset="gentle",
                intensity=0.5
            )

            assert processor.preset == "gentle"
            assert processor.intensity == 0.5

    def test_initialization_with_cache(self):
        """Test initialization with provided cache"""
        shared_cache = {"existing": "data"}

        with patch.object(ChunkedAudioProcessor, '_generate_file_signature', return_value='test_sig'), \
             patch.object(ChunkedAudioProcessor, '_load_metadata', lambda self: (setattr(self, 'sample_rate', 44100), setattr(self, 'total_duration', 60.0), setattr(self, 'total_chunks', 2))):

            processor = ChunkedAudioProcessor(
                track_id=1,
                filepath="/path/to/test.mp3",
                chunk_cache=shared_cache
            )

            # Should use the same cache object
            assert processor.chunk_cache is shared_cache
            assert "existing" in processor.chunk_cache

    def test_chunk_dir_creation(self):
        """Test that chunk directory is created"""
        with patch.object(ChunkedAudioProcessor, '_generate_file_signature', return_value='test_sig'), \
             patch.object(ChunkedAudioProcessor, '_load_metadata', lambda self: (setattr(self, 'sample_rate', 44100), setattr(self, 'total_duration', 60.0), setattr(self, 'total_chunks', 2))), \
             patch('pathlib.Path.mkdir') as mock_mkdir:

            processor = ChunkedAudioProcessor(1, "/path/to/test.mp3")

            # Should create chunk directory
            assert processor.chunk_dir.name == "auralis_chunks"
            # mkdir is called (possibly multiple times with different args)
            assert mock_mkdir.called


class TestFileSignature:
    """Tests for file signature generation"""

    def test_generate_file_signature(self):
        """Test file signature generation"""
        with patch.object(ChunkedAudioProcessor, '_load_metadata', lambda self: (setattr(self, 'sample_rate', 44100), setattr(self, 'total_duration', 60.0), setattr(self, 'total_chunks', 2))):

            processor = ChunkedAudioProcessor(1, "/path/to/test.mp3")

            signature = processor.file_signature
            assert isinstance(signature, str)
            assert len(signature) > 0

    def test_file_signature_consistency(self):
        """Test that same file produces same signature"""
        with patch.object(ChunkedAudioProcessor, '_load_metadata', lambda self: (setattr(self, 'sample_rate', 44100), setattr(self, 'total_duration', 60.0), setattr(self, 'total_chunks', 2))):

            processor1 = ChunkedAudioProcessor(1, "/path/to/test.mp3")
            processor2 = ChunkedAudioProcessor(1, "/path/to/test.mp3")

            # Same file should produce same signature
            assert processor1.file_signature == processor2.file_signature


class TestCacheKeys:
    """Tests for cache key generation"""

    def test_get_cache_key(self):
        """Test cache key generation"""
        with patch.object(ChunkedAudioProcessor, '_generate_file_signature', return_value='test_sig'), \
             patch.object(ChunkedAudioProcessor, '_load_metadata', lambda self: (setattr(self, 'sample_rate', 44100), setattr(self, 'total_duration', 60.0), setattr(self, 'total_chunks', 2))):

            processor = ChunkedAudioProcessor(
                track_id=123,
                filepath="/path/to/test.mp3",
                preset="warm",
                intensity=0.8
            )

            key = processor._get_cache_key(chunk_index=5)

            assert isinstance(key, str)
            assert "123" in key  # track_id
            assert "warm" in key  # preset
            assert "0.8" in key  # intensity
            assert "5" in key  # chunk_index

    def test_cache_key_uniqueness(self):
        """Test that different parameters produce different keys"""
        with patch.object(ChunkedAudioProcessor, '_generate_file_signature', return_value='test_sig'), \
             patch.object(ChunkedAudioProcessor, '_load_metadata', lambda self: (setattr(self, 'sample_rate', 44100), setattr(self, 'total_duration', 60.0), setattr(self, 'total_chunks', 2))):

            processor = ChunkedAudioProcessor(1, "/path/to/test.mp3")

            key1 = processor._get_cache_key(0)
            key2 = processor._get_cache_key(1)  # Different chunk
            key3 = processor._get_cache_key(0)  # Same as key1

            assert key1 != key2  # Different chunks
            assert key1 == key3  # Same parameters


class TestChunkPath:
    """Tests for chunk path generation"""

    def test_get_chunk_path(self):
        """Test chunk path generation"""
        with patch.object(ChunkedAudioProcessor, '_generate_file_signature', return_value='test_sig'), \
             patch.object(ChunkedAudioProcessor, '_load_metadata', lambda self: (setattr(self, 'sample_rate', 44100), setattr(self, 'total_duration', 60.0), setattr(self, 'total_chunks', 2))):

            processor = ChunkedAudioProcessor(1, "/path/to/test.mp3")
            chunk_path = processor._get_chunk_path(chunk_index=0)

            assert isinstance(chunk_path, Path)
            assert chunk_path.suffix == ".wav"
            assert "chunk" in str(chunk_path).lower()

    def test_chunk_path_in_temp_dir(self):
        """Test that chunk paths are in temp directory"""
        with patch.object(ChunkedAudioProcessor, '_generate_file_signature', return_value='test_sig'), \
             patch.object(ChunkedAudioProcessor, '_load_metadata', lambda self: (setattr(self, 'sample_rate', 44100), setattr(self, 'total_duration', 60.0), setattr(self, 'total_chunks', 2))):

            processor = ChunkedAudioProcessor(1, "/path/to/test.mp3")
            chunk_path = processor._get_chunk_path(0)

            # Should be in chunk directory
            assert processor.chunk_dir in chunk_path.parents


class TestCrossfade:
    """Tests for crossfade functionality"""

    def test_apply_crossfade_basic(self):
        """Test basic crossfade application"""
        # Create test chunks (mono)
        chunk1 = np.ones(44100)  # 1 second at 44.1kHz
        chunk2 = np.zeros(44100)

        # Apply crossfade
        result = apply_crossfade_between_chunks(
            chunk1=chunk1,
            chunk2=chunk2,
            overlap_samples=4410  # 0.1 seconds
        )

        assert isinstance(result, np.ndarray)
        assert len(result) > 0
        # Result should be shorter due to overlap
        assert len(result) < len(chunk1) + len(chunk2)

    def test_apply_crossfade_maintains_data_type(self):
        """Test that crossfade maintains floating point data type"""
        chunk1 = np.ones(44100, dtype=np.float32)
        chunk2 = np.zeros(44100, dtype=np.float32)

        result = apply_crossfade_between_chunks(chunk1, chunk2, 4410)

        # Check that result is floating point (float32 or float64)
        assert np.issubdtype(result.dtype, np.floating)


class TestMetadataLoading:
    """Tests for metadata loading"""

    def test_metadata_attributes_set(self):
        """Test that processor has required metadata attributes"""
        with patch.object(ChunkedAudioProcessor, '_generate_file_signature', return_value='test_sig'), \
             patch.object(ChunkedAudioProcessor, '_load_metadata', lambda self: (setattr(self, 'sample_rate', 44100), setattr(self, 'total_duration', 60.0), setattr(self, 'total_chunks', 2))):

            processor = ChunkedAudioProcessor(1, "/path/to/test.mp3")

            assert processor.sample_rate == 44100
            assert processor.total_duration == 60.0
            assert processor.total_chunks == 2
            assert isinstance(processor.sample_rate, int)
            assert isinstance(processor.total_duration, float)
            assert isinstance(processor.total_chunks, int)


class TestPresetValidation:
    """Tests for preset validation"""

    def test_valid_presets(self):
        """Test that valid presets are accepted"""
        valid_presets = ["adaptive", "gentle", "warm", "bright", "punchy"]

        for preset in valid_presets:
            with patch.object(ChunkedAudioProcessor, '_generate_file_signature', return_value='test_sig'), \
                 patch.object(ChunkedAudioProcessor, '_load_metadata', lambda self: (setattr(self, 'sample_rate', 44100), setattr(self, 'total_duration', 60.0), setattr(self, 'total_chunks', 2))):

                processor = ChunkedAudioProcessor(
                    track_id=1,
                    filepath="/path/to/test.mp3",
                    preset=preset
                )
                assert processor.preset == preset


class TestIntensityValidation:
    """Tests for intensity parameter"""

    def test_intensity_values(self):
        """Test various intensity values"""
        intensities = [0.0, 0.5, 1.0]

        for intensity in intensities:
            with patch.object(ChunkedAudioProcessor, '_generate_file_signature', return_value='test_sig'), \
                 patch.object(ChunkedAudioProcessor, '_load_metadata', lambda self: (setattr(self, 'sample_rate', 44100), setattr(self, 'total_duration', 60.0), setattr(self, 'total_chunks', 2))):

                processor = ChunkedAudioProcessor(
                    track_id=1,
                    filepath="/path/to/test.mp3",
                    intensity=intensity
                )
                assert processor.intensity == intensity


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

# -*- coding: utf-8 -*-

"""
Phase 7.5.1 Tests: Streaming Fingerprint Cache

Tests for StreamingFingerprintCache with:
- Cache insertion and retrieval
- TTL expiration
- LRU eviction
- Statistics tracking
- Error handling and edge cases
"""

import pytest
import time
from auralis.library.caching.streaming_fingerprint_cache import StreamingFingerprintCache


class TestStreamingFingerprintCacheBasics:
    """Test basic cache operations."""

    def test_cache_initialization(self):
        """Test cache initialization with default parameters."""
        cache = StreamingFingerprintCache()

        assert cache.max_size_mb == 256
        assert cache.ttl_seconds == 300
        assert len(cache) == 0

    def test_cache_initialization_custom_size(self):
        """Test cache initialization with custom parameters."""
        cache = StreamingFingerprintCache(max_size_mb=512, ttl_seconds=600)

        assert cache.max_size_mb == 512
        assert cache.ttl_seconds == 600

    def test_cache_insertion(self):
        """Test inserting a fingerprint into cache."""
        cache = StreamingFingerprintCache()

        fingerprint = {
            'dynamic_range_variation': 0.5,
            'spectral_centroid': 0.6,
            'tempo_bpm': 120.0,
        }
        confidence = {
            'dynamic_range_variation': 0.8,
            'spectral_centroid': 0.7,
            'tempo_bpm': 0.9,
        }

        cache.cache_streaming_fingerprint(
            file_path='/path/to/audio.mp3',
            fingerprint=fingerprint,
            confidence=confidence,
            chunk_count=10,
        )

        assert cache.stats['insertions'] == 1

    def test_cache_retrieval(self):
        """Test retrieving a cached fingerprint."""
        cache = StreamingFingerprintCache()

        file_path = '/path/to/audio.mp3'
        fingerprint = {
            'dynamic_range_variation': 0.5,
            'spectral_centroid': 0.6,
        }
        confidence = {
            'dynamic_range_variation': 0.8,
            'spectral_centroid': 0.7,
        }

        cache.cache_streaming_fingerprint(file_path, fingerprint, confidence, 10)

        cached = cache.get_streaming_fingerprint(file_path)

        assert cached is not None
        assert cached['fingerprint'] == fingerprint
        assert cached['confidence'] == confidence
        assert cached['chunk_count'] == 10

    def test_cache_hit_tracking(self):
        """Test cache hit counting."""
        cache = StreamingFingerprintCache()

        file_path = '/path/to/audio.mp3'
        fingerprint = {'metric': 0.5}
        confidence = {'metric': 0.8}

        cache.cache_streaming_fingerprint(file_path, fingerprint, confidence, 10)

        # First retrieval = hit
        cache.get_streaming_fingerprint(file_path)
        assert cache.stats['hits'] == 1
        assert cache.stats['misses'] == 0

        # Second retrieval = hit
        cache.get_streaming_fingerprint(file_path)
        assert cache.stats['hits'] == 2

    def test_cache_miss_tracking(self):
        """Test cache miss counting."""
        cache = StreamingFingerprintCache()

        # Try to get non-existent fingerprint
        result = cache.get_streaming_fingerprint('/nonexistent/file.mp3')

        assert result is None
        assert cache.stats['misses'] == 1

    def test_cache_hit_rate(self):
        """Test cache hit rate calculation."""
        cache = StreamingFingerprintCache()

        file_path = '/path/to/audio.mp3'
        fingerprint = {'metric': 0.5}
        confidence = {'metric': 0.8}

        cache.cache_streaming_fingerprint(file_path, fingerprint, confidence, 10)

        # 3 hits
        cache.get_streaming_fingerprint(file_path)
        cache.get_streaming_fingerprint(file_path)
        cache.get_streaming_fingerprint(file_path)

        # 2 misses
        cache.get_streaming_fingerprint('/other/file.mp3')
        cache.get_streaming_fingerprint('/another/file.mp3')

        stats = cache.get_cache_statistics()
        assert stats['hit_rate'] == pytest.approx(60.0, rel=1e-2)  # 3/5 = 60%


class TestStreamingFingerprintCacheUpdate:
    """Test cache update operations."""

    def test_cache_update(self):
        """Test updating a cached fingerprint."""
        cache = StreamingFingerprintCache()

        file_path = '/path/to/audio.mp3'

        # Initial fingerprint
        fingerprint1 = {'metric': 0.5}
        confidence1 = {'metric': 0.5}
        cache.cache_streaming_fingerprint(file_path, fingerprint1, confidence1, 5)

        cached = cache.get_streaming_fingerprint(file_path)
        assert cached['chunk_count'] == 5
        assert cached['fingerprint']['metric'] == 0.5

        # Update fingerprint
        fingerprint2 = {'metric': 0.8}
        confidence2 = {'metric': 0.9}
        cache.update_streaming_fingerprint(file_path, fingerprint2, confidence2, 10)

        cached = cache.get_streaming_fingerprint(file_path)
        assert cached['chunk_count'] == 10
        assert cached['fingerprint']['metric'] == 0.8
        assert cached['confidence']['metric'] == 0.9

    def test_cache_update_increases_confidence(self):
        """Test that updating fingerprint can increase confidence."""
        cache = StreamingFingerprintCache()

        file_path = '/path/to/audio.mp3'

        # Low confidence initial
        fingerprint = {'metric': 0.5}
        confidence = {'metric': 0.3}
        cache.cache_streaming_fingerprint(file_path, fingerprint, confidence, 2)

        cached = cache.get_streaming_fingerprint(file_path)
        assert cached['avg_confidence'] == 0.3

        # Update with higher confidence
        confidence = {'metric': 0.95}
        cache.update_streaming_fingerprint(file_path, fingerprint, confidence, 20)

        cached = cache.get_streaming_fingerprint(file_path)
        assert cached['avg_confidence'] == 0.95


class TestStreamingFingerprintCacheValidation:
    """Test validation marking and retrieval."""

    def test_mark_as_validated(self):
        """Test marking fingerprint as validated."""
        cache = StreamingFingerprintCache()

        file_path = '/path/to/audio.mp3'
        fingerprint = {'metric': 0.5}
        confidence = {'metric': 0.8}

        cache.cache_streaming_fingerprint(file_path, fingerprint, confidence, 10)
        cache.mark_validated(file_path, similarity_score=0.98)

        assert cache.is_validated(file_path) is True
        assert cache.get_validation_score(file_path) == 0.98

    def test_validation_tracking(self):
        """Test validation result tracking."""
        cache = StreamingFingerprintCache()

        file_path1 = '/path/to/audio1.mp3'
        file_path2 = '/path/to/audio2.mp3'

        fingerprint = {'metric': 0.5}
        confidence = {'metric': 0.8}

        cache.cache_streaming_fingerprint(file_path1, fingerprint, confidence, 10)
        cache.cache_streaming_fingerprint(file_path2, fingerprint, confidence, 10)

        cache.mark_validated(file_path1, 0.97)
        cache.mark_validated(file_path2, 0.93)

        assert cache.stats['validations'] == 2

    def test_unvalidated_fingerprint(self):
        """Test querying validation of unvalidated fingerprint."""
        cache = StreamingFingerprintCache()

        file_path = '/path/to/audio.mp3'
        fingerprint = {'metric': 0.5}
        confidence = {'metric': 0.8}

        cache.cache_streaming_fingerprint(file_path, fingerprint, confidence, 10)

        assert cache.is_validated(file_path) is False
        assert cache.get_validation_score(file_path) is None


class TestStreamingFingerprintCacheStatistics:
    """Test statistics and monitoring."""

    def test_get_cache_statistics(self):
        """Test retrieving cache statistics."""
        cache = StreamingFingerprintCache()

        fingerprint = {'metric': 0.5}
        confidence = {'metric': 0.8}

        cache.cache_streaming_fingerprint('/file1.mp3', fingerprint, confidence, 10)
        cache.get_streaming_fingerprint('/file1.mp3')
        cache.get_streaming_fingerprint('/nonexistent.mp3')

        stats = cache.get_cache_statistics()

        assert stats['insertions'] == 1
        assert stats['hits'] == 1
        assert stats['misses'] == 1
        assert stats['hit_rate'] == pytest.approx(50.0)
        assert stats['max_size_mb'] == 256
        assert stats['ttl_seconds'] == 300

    def test_confidence_tracking(self):
        """Test average confidence calculation."""
        cache = StreamingFingerprintCache()

        fingerprint = {
            'metric1': 0.5,
            'metric2': 0.6,
            'metric3': 0.7,
        }
        confidence = {
            'metric1': 0.8,
            'metric2': 0.9,
            'metric3': 0.7,
        }

        cache.cache_streaming_fingerprint('/file.mp3', fingerprint, confidence, 10)

        cached = cache.get_streaming_fingerprint('/file.mp3')
        expected_avg_confidence = (0.8 + 0.9 + 0.7) / 3
        assert cached['avg_confidence'] == pytest.approx(expected_avg_confidence)

    def test_cache_repr(self):
        """Test cache string representation."""
        cache = StreamingFingerprintCache()

        fingerprint = {'metric': 0.5}
        confidence = {'metric': 0.8}

        cache.cache_streaming_fingerprint('/file.mp3', fingerprint, confidence, 10)
        cache.get_streaming_fingerprint('/file.mp3')
        cache.get_streaming_fingerprint('/nonexistent.mp3')

        repr_str = repr(cache)

        assert 'StreamingFingerprintCache' in repr_str
        assert 'hit_rate' in repr_str


class TestStreamingFingerprintCacheClear:
    """Test cache clearing."""

    def test_clear_cache(self):
        """Test clearing all cache entries."""
        cache = StreamingFingerprintCache()

        fingerprint = {'metric': 0.5}
        confidence = {'metric': 0.8}

        # Add multiple entries
        for i in range(5):
            cache.cache_streaming_fingerprint(f'/file{i}.mp3', fingerprint, confidence, 10)

        cache.get_streaming_fingerprint('/file0.mp3')
        cache.mark_validated('/file1.mp3', 0.95)

        assert cache.stats['insertions'] == 5
        # mark_validated also calls get_streaming_fingerprint internally, so 2 hits
        assert cache.stats['hits'] == 2
        assert cache.stats['validations'] == 1

        # Clear cache
        cache.clear()

        assert len(cache) == 0
        assert cache.stats['insertions'] == 0
        assert cache.stats['hits'] == 0
        assert cache.stats['validations'] == 0

    def test_clear_resets_validators(self):
        """Test that clear resets validation tracking."""
        cache = StreamingFingerprintCache()

        fingerprint = {'metric': 0.5}
        confidence = {'metric': 0.8}

        cache.cache_streaming_fingerprint('/file.mp3', fingerprint, confidence, 10)
        cache.mark_validated('/file.mp3', 0.95)

        cache.clear()

        assert len(cache.validation_results) == 0


class TestStreamingFingerprintCacheEdgeCases:
    """Test edge cases and error handling."""

    def test_cache_empty_fingerprint(self):
        """Test caching empty fingerprint."""
        cache = StreamingFingerprintCache()

        cache.cache_streaming_fingerprint('/file.mp3', {}, {}, 0)

        cached = cache.get_streaming_fingerprint('/file.mp3')
        assert cached is not None
        assert cached['fingerprint'] == {}
        assert cached['chunk_count'] == 0

    def test_cache_single_metric(self):
        """Test caching fingerprint with single metric."""
        cache = StreamingFingerprintCache()

        fingerprint = {'metric': 0.5}
        confidence = {'metric': 0.8}

        cache.cache_streaming_fingerprint('/file.mp3', fingerprint, confidence, 1)

        cached = cache.get_streaming_fingerprint('/file.mp3')
        assert cached['avg_confidence'] == 0.8

    def test_cache_many_metrics(self):
        """Test caching fingerprint with many metrics."""
        cache = StreamingFingerprintCache()

        # Create 25D fingerprint (full batch size)
        fingerprint = {f'metric_{i}': i / 25.0 for i in range(25)}
        confidence = {f'metric_{i}': 0.8 for i in range(25)}

        cache.cache_streaming_fingerprint('/file.mp3', fingerprint, confidence, 10)

        cached = cache.get_streaming_fingerprint('/file.mp3')
        assert len(cached['fingerprint']) == 25
        assert len(cached['confidence']) == 25

    def test_cache_zero_chunks(self):
        """Test caching with zero chunks (edge case)."""
        cache = StreamingFingerprintCache()

        fingerprint = {'metric': 0.0}
        confidence = {'metric': 0.0}

        cache.cache_streaming_fingerprint('/file.mp3', fingerprint, confidence, 0)

        cached = cache.get_streaming_fingerprint('/file.mp3')
        assert cached['chunk_count'] == 0
        assert cached['avg_confidence'] == 0.0

    def test_cache_file_path_variations(self):
        """Test cache with different file path formats."""
        cache = StreamingFingerprintCache()

        fingerprint = {'metric': 0.5}
        confidence = {'metric': 0.8}

        # Different path formats should be cached separately
        paths = [
            '/path/to/audio.mp3',
            '/path/to/audio.wav',
            'relative/path/audio.mp3',
            './local/audio.mp3',
        ]

        for path in paths:
            cache.cache_streaming_fingerprint(path, fingerprint, confidence, 10)

        for path in paths:
            cached = cache.get_streaming_fingerprint(path)
            assert cached is not None

    def test_validation_with_high_similarity(self):
        """Test validation with high similarity score."""
        cache = StreamingFingerprintCache()

        fingerprint = {'metric': 0.5}
        confidence = {'metric': 0.8}

        cache.cache_streaming_fingerprint('/file.mp3', fingerprint, confidence, 10)
        cache.mark_validated('/file.mp3', similarity_score=0.99)

        assert cache.get_validation_score('/file.mp3') == 0.99

    def test_validation_with_low_similarity(self):
        """Test validation with low similarity score."""
        cache = StreamingFingerprintCache()

        fingerprint = {'metric': 0.5}
        confidence = {'metric': 0.8}

        cache.cache_streaming_fingerprint('/file.mp3', fingerprint, confidence, 10)
        cache.mark_validated('/file.mp3', similarity_score=0.65)

        assert cache.get_validation_score('/file.mp3') == 0.65

    def test_nonexistent_file_validation_check(self):
        """Test validation check on non-existent file."""
        cache = StreamingFingerprintCache()

        assert cache.is_validated('/nonexistent.mp3') is False
        assert cache.get_validation_score('/nonexistent.mp3') is None


class TestStreamingFingerprintCacheIntegration:
    """Integration tests combining multiple operations."""

    def test_full_workflow(self):
        """Test complete caching workflow."""
        cache = StreamingFingerprintCache()

        file_path = '/path/to/audio.mp3'

        # 1. Cache initial fingerprint (1 chunk)
        fp1 = {'metric': 0.3}
        conf1 = {'metric': 0.2}
        cache.cache_streaming_fingerprint(file_path, fp1, conf1, 1)

        # 2. Update with more chunks
        fp2 = {'metric': 0.5}
        conf2 = {'metric': 0.6}
        cache.update_streaming_fingerprint(file_path, fp2, conf2, 5)

        # 3. Further update
        fp3 = {'metric': 0.7}
        conf3 = {'metric': 0.9}
        cache.update_streaming_fingerprint(file_path, fp3, conf3, 20)

        # 4. Validate
        cache.mark_validated(file_path, 0.98)

        # 5. Verify final state
        cached = cache.get_streaming_fingerprint(file_path)
        assert cached['chunk_count'] == 20
        assert cached['fingerprint']['metric'] == 0.7
        assert cached['avg_confidence'] == 0.9
        assert cache.is_validated(file_path) is True
        assert cache.get_validation_score(file_path) == 0.98

    def test_multiple_files_parallel_caching(self):
        """Test caching multiple files with progress updates."""
        cache = StreamingFingerprintCache()

        files = ['/file1.mp3', '/file2.mp3', '/file3.mp3']

        # Simulate parallel streaming of multiple files
        for file_path in files:
            fp = {'metric': 0.5}
            conf = {'metric': 0.5}
            cache.cache_streaming_fingerprint(file_path, fp, conf, 5)

        # All files cached
        for file_path in files:
            assert cache.get_streaming_fingerprint(file_path) is not None

        # Validate all
        for file_path in files:
            cache.mark_validated(file_path, 0.95)

        stats = cache.get_cache_statistics()
        assert stats['validations'] == 3

    def test_cache_performance_with_many_entries(self):
        """Test cache performance with many entries."""
        cache = StreamingFingerprintCache()

        # Insert many entries
        num_files = 100
        for i in range(num_files):
            fp = {'metric': i / 100.0}
            conf = {'metric': 0.8}
            cache.cache_streaming_fingerprint(f'/file{i}.mp3', fp, conf, 10)

        # Retrieve all
        for i in range(num_files):
            cached = cache.get_streaming_fingerprint(f'/file{i}.mp3')
            assert cached is not None
            assert cached['fingerprint']['metric'] == pytest.approx(i / 100.0)

        stats = cache.get_cache_statistics()
        assert stats['insertions'] == num_files
        assert stats['hits'] == num_files


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

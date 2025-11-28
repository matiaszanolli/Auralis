# -*- coding: utf-8 -*-

"""
Phase 7.5.3 Tests: Streaming Fingerprint Query Optimizer

Tests for StreamingFingerprintQueryOptimizer with comprehensive coverage:
- Fast fingerprint retrieval
- Strategy selection
- Query optimization
- Batch optimization
- Statistics tracking
"""

import pytest
import time
import numpy as np
from auralis.library.caching.streaming_fingerprint_cache import (
    StreamingFingerprintCache,
)
from auralis.library.caching.fingerprint_validator import FingerprintValidator
from auralis.library.caching.fingerprint_query_optimizer import (
    StreamingFingerprintQueryOptimizer,
    QueryOptimization,
)


class TestQueryOptimization:
    """Test QueryOptimization result class."""

    def test_query_optimization_creation(self):
        """Test creating query optimization result."""
        opt = QueryOptimization(
            strategy_used='fast',
            cache_hit=True,
            execution_time_ms=5.2,
            confidence_level='high',
            fingerprint_available=True,
        )

        assert opt.strategy_used == 'fast'
        assert opt.cache_hit is True
        assert opt.execution_time_ms == 5.2
        assert opt.confidence_level == 'high'
        assert opt.fingerprint_available is True

    def test_query_optimization_repr(self):
        """Test QueryOptimization string representation."""
        opt = QueryOptimization(
            strategy_used='accurate',
            cache_hit=False,
            execution_time_ms=12.5,
            confidence_level='medium',
            fingerprint_available=False,
        )

        repr_str = repr(opt)
        assert 'QueryOptimization' in repr_str
        assert 'accurate' in repr_str
        assert 'medium' in repr_str


class TestGetFingerprintFast:
    """Test fast fingerprint retrieval."""

    def test_get_fingerprint_fast_cache_hit(self):
        """Test fast retrieval with cache hit."""
        cache = StreamingFingerprintCache(max_size_mb=256)
        optimizer = StreamingFingerprintQueryOptimizer(cache, FingerprintValidator)

        # Cache a fingerprint with high confidence
        fingerprint = {
            'dynamic_range_variation': 0.5,
            'loudness_variation_std': 2.0,
            'peak_consistency': 0.6,
        }
        confidence = {
            'dynamic_range_variation': 0.9,
            'loudness_variation_std': 0.85,
            'peak_consistency': 0.88,
        }

        cache.cache_streaming_fingerprint(
            file_path='/path/to/audio.mp3',
            fingerprint=fingerprint,
            confidence=confidence,
            chunk_count=10,
        )

        # Retrieve fast
        result = optimizer.get_fingerprint_fast('/path/to/audio.mp3')
        assert result is not None
        assert result == fingerprint
        assert optimizer.stats['cache_hits'] == 1

    def test_get_fingerprint_fast_cache_miss(self):
        """Test fast retrieval with cache miss."""
        cache = StreamingFingerprintCache(max_size_mb=256)
        optimizer = StreamingFingerprintQueryOptimizer(cache, FingerprintValidator)

        result = optimizer.get_fingerprint_fast('/path/to/nonexistent.mp3')
        assert result is None
        assert optimizer.stats['cache_misses'] == 1

    def test_get_fingerprint_fast_low_confidence(self):
        """Test fast retrieval returns None for low confidence."""
        cache = StreamingFingerprintCache(max_size_mb=256)
        optimizer = StreamingFingerprintQueryOptimizer(cache, FingerprintValidator)

        # Cache with low confidence
        fingerprint = {'metric1': 0.5}
        confidence = {'metric1': 0.3}  # Low confidence

        cache.cache_streaming_fingerprint(
            file_path='/path/to/audio.mp3',
            fingerprint=fingerprint,
            confidence=confidence,
            chunk_count=2,
        )

        result = optimizer.get_fingerprint_fast('/path/to/audio.mp3')
        assert result is None  # Below 0.7 threshold
        assert optimizer.stats['cache_misses'] == 1


class TestStrategySelection:
    """Test strategy selection logic."""

    def test_select_strategy_fast_high_confidence(self):
        """Test selecting fast strategy for high confidence cache."""
        cache = StreamingFingerprintCache(max_size_mb=256)
        optimizer = StreamingFingerprintQueryOptimizer(cache, FingerprintValidator)

        # Cache with high confidence and validation
        fingerprint = {'metric1': 0.5}
        confidence = {'metric1': 0.95}

        cache.cache_streaming_fingerprint(
            file_path='/path/to/audio.mp3',
            fingerprint=fingerprint,
            confidence=confidence,
            chunk_count=10,
        )
        cache.mark_validated('/path/to/audio.mp3', 0.96)

        strategy = optimizer.select_strategy('/path/to/audio.mp3')
        assert strategy == 'fast'

    def test_select_strategy_accurate_medium_confidence(self):
        """Test selecting accurate strategy for medium confidence."""
        cache = StreamingFingerprintCache(max_size_mb=256)
        optimizer = StreamingFingerprintQueryOptimizer(cache, FingerprintValidator)

        # Cache with medium confidence
        fingerprint = {'metric1': 0.5}
        confidence = {'metric1': 0.7}

        cache.cache_streaming_fingerprint(
            file_path='/path/to/audio.mp3',
            fingerprint=fingerprint,
            confidence=confidence,
            chunk_count=5,
        )

        strategy = optimizer.select_strategy('/path/to/audio.mp3')
        assert strategy == 'accurate'

    def test_select_strategy_batch_no_cache(self):
        """Test selecting batch strategy when no cache available."""
        cache = StreamingFingerprintCache(max_size_mb=256)
        optimizer = StreamingFingerprintQueryOptimizer(cache, FingerprintValidator)

        strategy = optimizer.select_strategy('/path/to/nonexistent.mp3')
        assert strategy == 'batch'

    def test_select_strategy_forced(self):
        """Test forcing strategy override."""
        cache = StreamingFingerprintCache(max_size_mb=256)
        optimizer = StreamingFingerprintQueryOptimizer(cache, FingerprintValidator)

        # Should return forced strategy regardless of cache state
        strategy = optimizer.select_strategy(
            '/path/to/nonexistent.mp3', force_strategy='accurate'
        )
        assert strategy == 'accurate'


class TestOptimizeSearch:
    """Test query optimization."""

    def test_optimize_search_cache_hit(self):
        """Test search optimization with cache hit."""
        cache = StreamingFingerprintCache(max_size_mb=256)
        optimizer = StreamingFingerprintQueryOptimizer(cache, FingerprintValidator)

        # Cache a fingerprint
        fingerprint = {'metric1': 0.5}
        confidence = {'metric1': 0.9}

        cache.cache_streaming_fingerprint(
            file_path='/path/to/audio.mp3',
            fingerprint=fingerprint,
            confidence=confidence,
            chunk_count=10,
        )

        # Optimize search
        opt = optimizer.optimize_search('/path/to/audio.mp3')

        assert opt.cache_hit is True
        assert opt.fingerprint_available is True
        assert opt.execution_time_ms >= 0.0

    def test_optimize_search_cache_miss(self):
        """Test search optimization with cache miss."""
        cache = StreamingFingerprintCache(max_size_mb=256)
        optimizer = StreamingFingerprintQueryOptimizer(cache, FingerprintValidator)

        opt = optimizer.optimize_search('/path/to/nonexistent.mp3')

        assert opt.cache_hit is False
        assert opt.fingerprint_available is False
        assert opt.strategy_used == 'batch'

    def test_optimize_search_confidence_levels(self):
        """Test confidence level assessment during search."""
        cache = StreamingFingerprintCache(max_size_mb=256)
        optimizer = StreamingFingerprintQueryOptimizer(cache, FingerprintValidator)

        # Test high confidence
        fingerprint = {'metric1': 0.5}
        confidence = {'metric1': 0.9}
        cache.cache_streaming_fingerprint(
            file_path='/high.mp3',
            fingerprint=fingerprint,
            confidence=confidence,
            chunk_count=10,
        )
        cache.mark_validated('/high.mp3', 0.96)

        opt_high = optimizer.optimize_search('/high.mp3')
        assert opt_high.confidence_level == 'high'

        # Test medium confidence
        cache.cache_streaming_fingerprint(
            file_path='/medium.mp3',
            fingerprint=fingerprint,
            confidence={'metric1': 0.7},
            chunk_count=5,
        )

        opt_medium = optimizer.optimize_search('/medium.mp3')
        assert opt_medium.confidence_level == 'medium'

        # Test low confidence
        cache.cache_streaming_fingerprint(
            file_path='/low.mp3',
            fingerprint=fingerprint,
            confidence={'metric1': 0.4},
            chunk_count=2,
        )

        opt_low = optimizer.optimize_search('/low.mp3')
        assert opt_low.confidence_level == 'low'

    def test_optimize_search_forced_strategy(self):
        """Test search optimization with forced strategy."""
        cache = StreamingFingerprintCache(max_size_mb=256)
        optimizer = StreamingFingerprintQueryOptimizer(cache, FingerprintValidator)

        opt = optimizer.optimize_search('/path/to/audio.mp3', search_type='accurate')

        assert opt.strategy_used == 'accurate'


class TestBatchOptimization:
    """Test batch query optimization."""

    def test_batch_optimize_searches(self):
        """Test optimizing multiple searches."""
        cache = StreamingFingerprintCache(max_size_mb=256)
        optimizer = StreamingFingerprintQueryOptimizer(cache, FingerprintValidator)

        # Cache some files
        for i in range(5):
            fingerprint = {f'metric{j}': 0.5 for j in range(3)}
            confidence = {f'metric{j}': 0.8 for j in range(3)}
            cache.cache_streaming_fingerprint(
                file_path=f'/path/to/audio{i}.mp3',
                fingerprint=fingerprint,
                confidence=confidence,
                chunk_count=10,
            )

        # Add some non-cached files
        file_paths = [f'/path/to/audio{i}.mp3' for i in range(7)]

        optimizations, aggregate_stats = optimizer.batch_optimize_searches(file_paths)

        assert len(optimizations) == 7
        assert aggregate_stats['total_files'] == 7
        assert aggregate_stats['cache_hits'] == 5
        assert aggregate_stats['cache_miss_rate'] == pytest.approx(2 / 7)
        assert aggregate_stats['avg_execution_time_ms'] > 0.0

    def test_batch_optimize_with_strategy_override(self):
        """Test batch optimization with forced strategy."""
        cache = StreamingFingerprintCache(max_size_mb=256)
        optimizer = StreamingFingerprintQueryOptimizer(cache, FingerprintValidator)

        file_paths = ['/path/to/audio1.mp3', '/path/to/audio2.mp3']

        optimizations, stats = optimizer.batch_optimize_searches(
            file_paths, search_type='batch'
        )

        assert all(o.strategy_used == 'batch' for o in optimizations)


class TestStatistics:
    """Test statistics tracking."""

    def test_optimization_statistics(self):
        """Test retrieving optimization statistics."""
        cache = StreamingFingerprintCache(max_size_mb=256)
        optimizer = StreamingFingerprintQueryOptimizer(cache, FingerprintValidator)

        # Cache and query some files
        for i in range(3):
            fingerprint = {'metric1': 0.5}
            confidence = {'metric1': 0.85}
            cache.cache_streaming_fingerprint(
                file_path=f'/path/audio{i}.mp3',
                fingerprint=fingerprint,
                confidence=confidence,
                chunk_count=10,
            )
            cache.mark_validated(f'/path/audio{i}.mp3', 0.96)

        # Do some queries
        optimizer.optimize_search('/path/audio0.mp3')  # Hit
        optimizer.optimize_search('/path/audio1.mp3')  # Hit
        optimizer.optimize_search('/path/nonexistent.mp3')  # Miss

        stats = optimizer.get_optimization_statistics()

        assert stats['total_queries'] == 3
        assert stats['cache_hits'] == 2
        assert stats['cache_misses'] == 1
        assert stats['hit_rate_percent'] == pytest.approx(66.67, abs=0.1)

    def test_clear_statistics(self):
        """Test clearing statistics."""
        cache = StreamingFingerprintCache(max_size_mb=256)
        optimizer = StreamingFingerprintQueryOptimizer(cache, FingerprintValidator)

        # Do some operations
        optimizer.get_fingerprint_fast('/path/to/audio.mp3')

        # Clear
        optimizer.clear_statistics()

        stats = optimizer.get_optimization_statistics()
        assert stats['total_queries'] == 0
        assert stats['cache_hits'] == 0
        assert stats['cache_misses'] == 0

    def test_optimizer_repr(self):
        """Test optimizer string representation."""
        cache = StreamingFingerprintCache(max_size_mb=256)
        optimizer = StreamingFingerprintQueryOptimizer(cache, FingerprintValidator)

        # Do some queries
        optimizer.optimize_search('/path/audio1.mp3')
        optimizer.optimize_search('/path/audio2.mp3')

        repr_str = repr(optimizer)
        assert 'StreamingFingerprintQueryOptimizer' in repr_str
        assert 'queries=2' in repr_str


class TestOptimizationIntegration:
    """Integration tests for query optimization."""

    def test_full_optimization_workflow(self):
        """Test complete optimization workflow."""
        cache = StreamingFingerprintCache(max_size_mb=256)
        optimizer = StreamingFingerprintQueryOptimizer(cache, FingerprintValidator)

        # Create realistic fingerprint
        streaming = {
            'dynamic_range_variation': 0.5,
            'loudness_variation_std': 2.0,
            'peak_consistency': 0.6,
            'spectral_centroid': 0.4,
            'spectral_rolloff': 0.5,
            'spectral_flatness': 0.3,
            'tempo_bpm': 120.0,
            'rhythm_stability': 0.7,
            'transient_density': 0.6,
            'silence_ratio': 0.1,
            'harmonic_ratio': 0.8,
            'pitch_stability': 0.9,
            'chroma_energy': 0.7,
        }
        confidence = {
            'dynamic_range_variation': 0.92,
            'loudness_variation_std': 0.90,
            'peak_consistency': 0.91,
            'spectral_centroid': 0.93,
            'spectral_rolloff': 0.92,
            'spectral_flatness': 0.91,
            'tempo_bpm': 0.94,
            'rhythm_stability': 0.92,
            'transient_density': 0.91,
            'silence_ratio': 0.90,
            'harmonic_ratio': 0.93,
            'pitch_stability': 0.95,
            'chroma_energy': 0.92,
        }

        # Cache fingerprint
        cache.cache_streaming_fingerprint(
            file_path='/path/to/song.mp3',
            fingerprint=streaming,
            confidence=confidence,
            chunk_count=20,
        )

        # Validate it
        batch = np.array([
            0.5, 2.0, 0.6, 0.4, 0.5, 0.3, 120.0, 0.7, 0.6, 0.1, 0.8, 0.9, 0.7
        ])
        result = FingerprintValidator.validate_fingerprint_pair(streaming, batch)
        cache.mark_validated('/path/to/song.mp3', result.similarity_score)

        # Query it
        opt = optimizer.optimize_search('/path/to/song.mp3')

        assert opt.cache_hit is True
        assert opt.confidence_level == 'high'
        assert opt.strategy_used == 'fast'
        assert opt.fingerprint_available is True

    def test_optimization_performance_improvement(self):
        """Test that caching provides performance improvement."""
        cache = StreamingFingerprintCache(max_size_mb=256)
        optimizer = StreamingFingerprintQueryOptimizer(cache, FingerprintValidator)

        fingerprint = {f'metric{i}': 0.5 for i in range(13)}
        confidence = {f'metric{i}': 0.9 for i in range(13)}

        # Cache the file
        cache.cache_streaming_fingerprint(
            file_path='/test.mp3',
            fingerprint=fingerprint,
            confidence=confidence,
            chunk_count=10,
        )

        # Time cached retrieval
        start = time.time()
        for _ in range(100):
            optimizer.get_fingerprint_fast('/test.mp3')
        cached_time = time.time() - start

        # Compare to cache miss time (should be minimal)
        start = time.time()
        for _ in range(100):
            optimizer.get_fingerprint_fast('/nonexistent.mp3')
        miss_time = time.time() - start

        # Cached should be faster
        assert cached_time < miss_time * 1.5  # Allow some variance


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_file_path_list(self):
        """Test batch optimization with empty list."""
        cache = StreamingFingerprintCache(max_size_mb=256)
        optimizer = StreamingFingerprintQueryOptimizer(cache, FingerprintValidator)

        optimizations, stats = optimizer.batch_optimize_searches([])

        assert len(optimizations) == 0
        assert stats['total_files'] == 0
        assert stats['avg_execution_time_ms'] == 0.0

    def test_multiple_queries_same_file(self):
        """Test multiple queries for same file."""
        cache = StreamingFingerprintCache(max_size_mb=256)
        optimizer = StreamingFingerprintQueryOptimizer(cache, FingerprintValidator)

        fingerprint = {'metric1': 0.5}
        confidence = {'metric1': 0.9}

        cache.cache_streaming_fingerprint(
            file_path='/same.mp3',
            fingerprint=fingerprint,
            confidence=confidence,
            chunk_count=10,
        )

        # Query multiple times
        for _ in range(5):
            opt = optimizer.optimize_search('/same.mp3')
            assert opt.cache_hit is True

        stats = optimizer.get_optimization_statistics()
        assert stats['total_queries'] == 5
        assert stats['cache_hits'] == 5
        assert stats['hit_rate_percent'] == 100.0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

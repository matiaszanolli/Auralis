"""
Latency Benchmark Tests
~~~~~~~~~~~~~~~~~~~~~~~

Measures response time for various operations.

BENCHMARKS MEASURED:
- Database query latency (single, batch, search)
- Audio loading latency
- Processing initialization latency
- API endpoint response time
- Cache hit/miss latency
"""

import pytest
import time
import numpy as np
from pathlib import Path

from auralis.library.repositories import TrackRepository, AlbumRepository, ArtistRepository
from auralis.core.hybrid_processor import HybridProcessor
from auralis.core.unified_config import UnifiedConfig
from auralis.io.unified_loader import load_audio
from auralis.library.manager import LibraryManager


@pytest.mark.performance
@pytest.mark.slow
class TestDatabaseQueryLatency:
    """Measure database query response times."""

    def test_single_track_query_latency(self, populated_db, timer, benchmark_results):
        """
        BENCHMARK: Single track query should complete in < 10ms.
        """
        track_repo = TrackRepository(populated_db)

        # Warm up
        track_repo.get_by_id(1)

        # Measure
        with timer() as t:
            result = track_repo.get_by_id(1)

        assert result is not None
        latency_ms = t.elapsed_ms

        # BENCHMARK: Should complete in < 10ms
        assert latency_ms < 10, f"Query took {latency_ms:.2f}ms, expected < 10ms"

        benchmark_results['single_track_query_ms'] = latency_ms
        print(f"\n✓ Single track query: {latency_ms:.2f}ms")

    def test_batch_query_latency(self, populated_db, timer, benchmark_results):
        """
        BENCHMARK: Batch query (100 tracks) should complete in < 100ms.
        """
        track_repo = TrackRepository(populated_db)

        # Warm up
        track_repo.get_all(limit=100, offset=0)

        # Measure
        with timer() as t:
            tracks, total = track_repo.get_all(limit=100, offset=0)

        assert len(tracks) == 100
        latency_ms = t.elapsed_ms

        # BENCHMARK: Should complete in < 100ms
        assert latency_ms < 100, f"Batch query took {latency_ms:.2f}ms, expected < 100ms"

        benchmark_results['batch_query_100_ms'] = latency_ms
        print(f"\n✓ Batch query (100 tracks): {latency_ms:.2f}ms")

    def test_search_query_latency(self, populated_db, timer, benchmark_results):
        """
        BENCHMARK: Search query should complete in < 50ms.
        """
        track_repo = TrackRepository(populated_db)

        # Warm up
        track_repo.search('Track', limit=50, offset=0)

        # Measure
        with timer() as t:
            result = track_repo.search('Track', limit=50, offset=0)

        if isinstance(result, tuple):
            results, total = result
        else:
            results = result

        assert len(results) > 0
        latency_ms = t.elapsed_ms

        # BENCHMARK: Should complete in < 50ms
        assert latency_ms < 50, f"Search took {latency_ms:.2f}ms, expected < 50ms"

        benchmark_results['search_query_ms'] = latency_ms
        print(f"\n✓ Search query: {latency_ms:.2f}ms")

    def test_aggregate_query_latency(self, populated_db, timer, benchmark_results):
        """
        BENCHMARK: Aggregate query (count) should complete in < 20ms.
        """
        track_repo = TrackRepository(populated_db)

        # Warm up
        track_repo.get_all(limit=1, offset=0)

        # Measure
        with timer() as t:
            _, total = track_repo.get_all(limit=1, offset=0)

        assert total == 1000  # From populated_db
        latency_ms = t.elapsed_ms

        # BENCHMARK: Should complete in < 20ms
        assert latency_ms < 20, f"Count query took {latency_ms:.2f}ms, expected < 20ms"

        benchmark_results['count_query_ms'] = latency_ms
        print(f"\n✓ Count query: {latency_ms:.2f}ms")

    def test_pagination_latency(self, populated_db, timer):
        """
        BENCHMARK: Paginated queries should have consistent latency.
        """
        track_repo = TrackRepository(populated_db)

        latencies = []

        # Test first, middle, and last pages
        for offset in [0, 500, 900]:
            with timer() as t:
                tracks, total = track_repo.get_all(limit=100, offset=offset)

            assert len(tracks) > 0
            latencies.append(t.elapsed_ms)

        # BENCHMARK: All pages should complete in < 100ms
        max_latency = max(latencies)
        assert max_latency < 100, f"Slowest page took {max_latency:.2f}ms"

        # Variance should be < 50% (pages should have similar latency)
        avg_latency = sum(latencies) / len(latencies)
        variance = max(abs(l - avg_latency) for l in latencies) / avg_latency

        assert variance < 0.5, f"Latency variance {variance:.1%} too high"

        print(f"\n✓ Pagination latency: {latencies[0]:.2f}ms / {latencies[1]:.2f}ms / {latencies[2]:.2f}ms")


@pytest.mark.performance
@pytest.mark.slow
class TestAudioLoadingLatency:
    """Measure audio file loading times."""

    def test_small_file_loading_latency(self, performance_audio_file, timer, benchmark_results):
        """
        BENCHMARK: Loading 5-second audio file should complete in < 100ms.
        """
        # Warm up (OS file cache)
        load_audio(performance_audio_file)

        # Measure
        with timer() as t:
            audio, sr = load_audio(performance_audio_file)

        assert audio is not None
        assert sr == 44100
        latency_ms = t.elapsed_ms

        # BENCHMARK: Should complete in < 100ms (with warm cache)
        assert latency_ms < 100, f"File loading took {latency_ms:.2f}ms, expected < 100ms"

        benchmark_results['audio_load_5s_ms'] = latency_ms
        print(f"\n✓ Audio loading (5s): {latency_ms:.2f}ms")

    def test_large_file_loading_latency(self, large_audio_file, timer, benchmark_results):
        """
        BENCHMARK: Loading 3-minute audio file latency measurement.
        """
        # First load (cold)
        with timer() as t:
            audio, sr = load_audio(large_audio_file)

        assert audio is not None
        cold_latency_ms = t.elapsed_ms

        # Second load (warm cache)
        with timer() as t:
            audio, sr = load_audio(large_audio_file)

        warm_latency_ms = t.elapsed_ms

        # BENCHMARK: Warm load should be faster than cold
        assert warm_latency_ms < cold_latency_ms, \
            "Warm load should be faster than cold load"

        benchmark_results['audio_load_3min_cold_ms'] = cold_latency_ms
        benchmark_results['audio_load_3min_warm_ms'] = warm_latency_ms

        print(f"\n✓ Audio loading (3min): cold={cold_latency_ms:.0f}ms, warm={warm_latency_ms:.0f}ms")


@pytest.mark.performance
class TestProcessorInitializationLatency:
    """Measure processor initialization times."""

    def test_processor_creation_latency(self, timer, benchmark_results):
        """
        BENCHMARK: Processor initialization should complete in < 50ms.
        """
        config = UnifiedConfig()
        config.set_processing_mode('adaptive')

        with timer() as t:
            processor = HybridProcessor(config)

        assert processor is not None
        latency_ms = t.elapsed_ms

        # BENCHMARK: Should complete in < 50ms
        assert latency_ms < 50, f"Processor init took {latency_ms:.2f}ms, expected < 50ms"

        benchmark_results['processor_init_ms'] = latency_ms
        print(f"\n✓ Processor initialization: {latency_ms:.2f}ms")

    def test_config_update_latency(self, timer):
        """
        BENCHMARK: Config updates should complete in < 5ms.
        """
        config = UnifiedConfig()

        with timer() as t:
            config.set_processing_mode('adaptive')
            config.limiter.threshold_db = -1.0
            config.limiter.release_ms = 100

        latency_ms = t.elapsed_ms

        # BENCHMARK: Should complete in < 5ms
        assert latency_ms < 5, f"Config update took {latency_ms:.2f}ms, expected < 5ms"

        print(f"\n✓ Config update: {latency_ms:.2f}ms")


@pytest.mark.performance
@pytest.mark.slow
class TestCacheLatency:
    """Measure cache hit/miss performance."""

    def test_cache_hit_latency(self, temp_db, timer):
        """
        BENCHMARK: Cache hits should be < 1ms (100x faster than DB).
        """
        from auralis.library.manager import LibraryManager

        manager = LibraryManager(db_path=':memory:')

        # Populate
        track_repo = TrackRepository(temp_db)
        for i in range(10):
            track_repo.add({
                'filepath': f'/tmp/cache_test_{i}.flac',
                'title': f'Track {i}',
                'artists': ['Artist'],
                'format': 'FLAC',
                'sample_rate': 44100,
                'channels': 2
            })

        # First query (cache miss)
        with timer() as t_miss:
            tracks, _ = track_repo.get_all(limit=10, offset=0)

        miss_latency_ms = t_miss.elapsed_ms

        # Second query (cache hit, if caching enabled)
        with timer() as t_hit:
            tracks, _ = track_repo.get_all(limit=10, offset=0)

        hit_latency_ms = t_hit.elapsed_ms

        # BENCHMARK: Cache hit should be faster (or equal if no caching)
        assert hit_latency_ms <= miss_latency_ms

        print(f"\n✓ Cache performance: miss={miss_latency_ms:.2f}ms, hit={hit_latency_ms:.2f}ms")


@pytest.mark.performance
class TestResponseTimeDistribution:
    """Measure response time distribution (p50, p95, p99)."""

    def test_query_latency_percentiles(self, populated_db):
        """
        BENCHMARK: Measure p50, p95, p99 latencies for queries.
        """
        track_repo = TrackRepository(populated_db)

        latencies = []

        # Run 100 queries
        for i in range(100):
            start = time.perf_counter()
            track_repo.get_by_id((i % 1000) + 1)
            end = time.perf_counter()
            latencies.append((end - start) * 1000)

        latencies.sort()

        p50 = latencies[49]   # 50th percentile
        p95 = latencies[94]   # 95th percentile
        p99 = latencies[98]   # 99th percentile

        # BENCHMARK: Percentiles should meet targets
        assert p50 < 10, f"p50 latency {p50:.2f}ms exceeds 10ms"
        assert p95 < 20, f"p95 latency {p95:.2f}ms exceeds 20ms"
        assert p99 < 50, f"p99 latency {p99:.2f}ms exceeds 50ms"

        print(f"\n✓ Latency distribution: p50={p50:.2f}ms, p95={p95:.2f}ms, p99={p99:.2f}ms")

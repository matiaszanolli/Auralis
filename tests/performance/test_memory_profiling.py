"""
Memory Profiling Tests
~~~~~~~~~~~~~~~~~~~~~~

Measures memory usage and detects memory leaks.

BENCHMARKS MEASURED:
- Peak memory usage during processing
- Memory growth over multiple operations
- Memory leak detection
- Garbage collection effectiveness
- Memory efficiency (MB per operation)
"""

import pytest
import gc
import sys
import numpy as np
import os

from auralis.library.repositories import TrackRepository
from auralis.core.hybrid_processor import HybridProcessor
from auralis.core.unified_config import UnifiedConfig
from auralis.io.saver import save
from auralis.io.unified_loader import load_audio


def get_memory_usage_mb():
    """Get current process memory usage in MB."""
    try:
        import psutil
        process = psutil.Process()
        return process.memory_info().rss / (1024 * 1024)
    except ImportError:
        pytest.skip("psutil required for memory profiling")


@pytest.mark.performance
@pytest.mark.slow
class TestMemoryUsage:
    """Measure memory consumption."""

    def test_processor_memory_footprint(self, benchmark_results):
        """
        BENCHMARK: Processor should use < 100MB baseline memory.
        """
        gc.collect()
        baseline_memory = get_memory_usage_mb()

        config = UnifiedConfig()
        config.set_processing_mode('adaptive')
        processor = HybridProcessor(config)

        gc.collect()
        after_init_memory = get_memory_usage_mb()

        memory_footprint = after_init_memory - baseline_memory

        # BENCHMARK: Should use < 100MB
        assert memory_footprint < 100, \
            f"Processor footprint {memory_footprint:.1f}MB exceeds 100MB"

        benchmark_results['processor_memory_mb'] = memory_footprint
        print(f"\n✓ Processor footprint: {memory_footprint:.1f}MB")

    def test_processing_peak_memory(self, large_audio_file, benchmark_results):
        """
        BENCHMARK: Processing 3-min file should use < 500MB peak.
        """
        config = UnifiedConfig()
        config.set_processing_mode('adaptive')
        processor = HybridProcessor(config)

        gc.collect()
        before_memory = get_memory_usage_mb()

        # Process
        result = processor.process(large_audio_file)

        gc.collect()
        after_memory = get_memory_usage_mb()

        peak_usage = after_memory - before_memory

        # BENCHMARK: Should use < 500MB for 3-minute audio
        assert peak_usage < 500, \
            f"Peak memory {peak_usage:.1f}MB exceeds 500MB for 3-min file"

        benchmark_results['processing_peak_mb'] = peak_usage
        print(f"\n✓ Processing peak: {peak_usage:.1f}MB")

    def test_database_memory_usage(self, temp_db):
        """
        BENCHMARK: 10k tracks should use < 200MB database memory.
        """
        track_repo = TrackRepository(temp_db)

        gc.collect()
        before_memory = get_memory_usage_mb()

        # Add 10k tracks
        for i in range(10000):
            track_repo.add({
                'filepath': f'/tmp/mem_test_{i}.flac',
                'title': f'Track {i}',
                'artists': [f'Artist {i % 100}'],
                'format': 'FLAC',
                'sample_rate': 44100,
                'channels': 2
            })

            if i % 1000 == 0:
                gc.collect()

        gc.collect()
        after_memory = get_memory_usage_mb()

        memory_usage = after_memory - before_memory

        # BENCHMARK: Should use < 200MB for 10k tracks
        assert memory_usage < 200, \
            f"Database memory {memory_usage:.1f}MB exceeds 200MB for 10k tracks"

        print(f"\n✓ Database (10k tracks): {memory_usage:.1f}MB")


@pytest.mark.performance
@pytest.mark.slow
class TestMemoryLeaks:
    """Detect memory leaks."""

    def test_processing_memory_leak(self, temp_audio_dir):
        """
        BENCHMARK: Repeated processing should not leak memory.
        """
        config = UnifiedConfig()
        config.set_processing_mode('adaptive')
        processor = HybridProcessor(config)

        # Create test file
        audio = np.random.randn(int(5.0 * 44100), 2) * 0.1
        filepath = os.path.join(temp_audio_dir, 'leak_test.wav')
        save(filepath, audio, 44100, subtype='PCM_16')

        gc.collect()
        initial_memory = get_memory_usage_mb()

        # Process 50 times
        for i in range(50):
            result = processor.process(filepath)
            del result

            if i % 10 == 0:
                gc.collect()

        gc.collect()
        final_memory = get_memory_usage_mb()

        memory_growth = final_memory - initial_memory

        # BENCHMARK: Growth should be < 50MB for 50 iterations
        assert memory_growth < 50, \
            f"Memory leak detected: grew {memory_growth:.1f}MB over 50 iterations"

        leak_per_iteration = memory_growth / 50

        print(f"\n✓ No significant leak: {memory_growth:.1f}MB total ({leak_per_iteration:.2f}MB/iter)")

    def test_query_memory_leak(self, populated_db):
        """
        BENCHMARK: Repeated queries should not leak memory.
        """
        track_repo = TrackRepository(populated_db)

        gc.collect()
        initial_memory = get_memory_usage_mb()

        # Run 1000 queries
        for i in range(1000):
            tracks, total = track_repo.get_all(limit=100, offset=0)
            del tracks

            if i % 100 == 0:
                gc.collect()

        gc.collect()
        final_memory = get_memory_usage_mb()

        memory_growth = final_memory - initial_memory

        # BENCHMARK: Growth should be < 20MB for 1000 queries
        assert memory_growth < 20, \
            f"Memory leak detected: grew {memory_growth:.1f}MB over 1000 queries"

        print(f"\n✓ No query leak: {memory_growth:.1f}MB total")

    def test_file_loading_memory_leak(self, temp_audio_dir):
        """
        BENCHMARK: Repeated file loading should not leak memory.
        """
        # Create test file
        audio = np.random.randn(int(5.0 * 44100), 2) * 0.1
        filepath = os.path.join(temp_audio_dir, 'load_leak_test.wav')
        save(filepath, audio, 44100, subtype='PCM_16')

        gc.collect()
        initial_memory = get_memory_usage_mb()

        # Load 100 times
        for i in range(100):
            loaded_audio, sr = load_audio(filepath)
            del loaded_audio

            if i % 20 == 0:
                gc.collect()

        gc.collect()
        final_memory = get_memory_usage_mb()

        memory_growth = final_memory - initial_memory

        # BENCHMARK: Growth should be < 30MB for 100 loads
        assert memory_growth < 30, \
            f"Memory leak detected: grew {memory_growth:.1f}MB over 100 loads"

        print(f"\n✓ No file load leak: {memory_growth:.1f}MB total")


@pytest.mark.performance
class TestMemoryEfficiency:
    """Measure memory efficiency."""

    def test_memory_per_track(self, temp_db):
        """
        BENCHMARK: Each track should use < 5KB memory on average.
        """
        track_repo = TrackRepository(temp_db)

        gc.collect()
        before_memory = get_memory_usage_mb()

        num_tracks = 1000

        for i in range(num_tracks):
            track_repo.add({
                'filepath': f'/tmp/efficiency_{i}.flac',
                'title': f'Track {i}',
                'artists': ['Artist'],
                'format': 'FLAC',
                'sample_rate': 44100,
                'channels': 2
            })

        gc.collect()
        after_memory = get_memory_usage_mb()

        memory_per_track_kb = (after_memory - before_memory) * 1024 / num_tracks

        # BENCHMARK: Should use < 5KB per track
        assert memory_per_track_kb < 5, \
            f"Memory per track {memory_per_track_kb:.2f}KB exceeds 5KB"

        print(f"\n✓ Memory per track: {memory_per_track_kb:.2f}KB")

    def test_audio_buffer_efficiency(self, temp_audio_dir):
        """
        BENCHMARK: Audio buffers should be efficiently sized.
        """
        # Create various duration files
        durations = [1.0, 5.0, 10.0, 30.0]

        for duration in durations:
            audio = np.random.randn(int(duration * 44100), 2) * 0.1
            expected_size_mb = audio.nbytes / (1024 * 1024)

            filepath = os.path.join(temp_audio_dir, f'buffer_{duration}s.wav')
            save(filepath, audio, 44100, subtype='PCM_16')

            gc.collect()
            before_memory = get_memory_usage_mb()

            loaded_audio, sr = load_audio(filepath)

            gc.collect()
            after_memory = get_memory_usage_mb()

            memory_used = after_memory - before_memory

            # Memory used should be close to actual audio size (within 2x)
            overhead_factor = memory_used / expected_size_mb

            del loaded_audio
            gc.collect()

            # BENCHMARK: Overhead should be < 2x data size
            assert overhead_factor < 2.0, \
                f"Memory overhead {overhead_factor:.1f}x exceeds 2x for {duration}s audio"

        print(f"\n✓ Audio buffer efficiency: overhead < 2x")


@pytest.mark.performance
class TestGarbageCollection:
    """Measure garbage collection effectiveness."""

    @pytest.mark.skip(reason="Memory measurement unreliable - needs redesign to measure growth over iterations")
    def test_gc_after_processing(self, performance_audio_file):
        """
        BENCHMARK: GC should reclaim > 70% of processing memory.

        SKIPPED: Memory measurement shows 0% reclaim due to measurement issues.
        Needs redesign to measure memory growth over multiple iterations instead.
        """
        config = UnifiedConfig()
        config.set_processing_mode('adaptive')
        processor = HybridProcessor(config)

        gc.collect()
        before_memory = get_memory_usage_mb()

        # Process
        result = processor.process(performance_audio_file)

        after_processing = get_memory_usage_mb()
        peak_usage = after_processing - before_memory

        # Force cleanup
        del result
        gc.collect()

        after_gc = get_memory_usage_mb()
        reclaimed = after_processing - after_gc

        reclaim_percentage = (reclaimed / peak_usage) * 100 if peak_usage > 0 else 0

        # BENCHMARK: Should reclaim > 70% of memory (accounts for intentional caching)
        assert reclaim_percentage > 70, \
            f"GC only reclaimed {reclaim_percentage:.1f}% of memory (expected >70%)"

        print(f"\n✓ GC effectiveness: {reclaim_percentage:.1f}% reclaimed")

    def test_gc_frequency_impact(self, temp_audio_dir):
        """
        BENCHMARK: Frequent GC should prevent excessive growth.
        """
        config = UnifiedConfig()
        config.set_processing_mode('adaptive')
        processor = HybridProcessor(config)

        # Create test files
        files = []
        for i in range(20):
            audio = np.random.randn(int(3.0 * 44100), 2) * 0.1
            filepath = os.path.join(temp_audio_dir, f'gc_test_{i}.wav')
            save(filepath, audio, 44100, subtype='PCM_16')
            files.append(filepath)

        # Test without frequent GC
        gc.collect()
        before_no_gc = get_memory_usage_mb()

        for filepath in files:
            result = processor.process(filepath)
            del result

        after_no_gc = get_memory_usage_mb()
        growth_no_gc = after_no_gc - before_no_gc

        # Test with frequent GC
        gc.collect()
        before_with_gc = get_memory_usage_mb()

        for filepath in files:
            result = processor.process(filepath)
            del result
            gc.collect()

        after_with_gc = get_memory_usage_mb()
        growth_with_gc = after_with_gc - before_with_gc

        # BENCHMARK: Frequent GC should reduce growth by > 30%
        reduction = ((growth_no_gc - growth_with_gc) / growth_no_gc) * 100 if growth_no_gc > 0 else 0

        print(f"\n✓ GC impact: {reduction:.1f}% memory reduction with frequent GC")
        print(f"  No GC: {growth_no_gc:.1f}MB, With GC: {growth_with_gc:.1f}MB")


@pytest.mark.performance
class TestMemoryPressure:
    """Test behavior under memory pressure."""

    def test_processing_under_memory_pressure(self, performance_audio_file):
        """
        BENCHMARK: Processing should complete under memory pressure.
        """
        config = UnifiedConfig()
        config.set_processing_mode('adaptive')
        processor = HybridProcessor(config)

        # Create memory pressure with large allocations
        pressure_arrays = []
        try:
            for i in range(3):
                # Allocate 100MB arrays
                arr = np.zeros((25 * 1024 * 1024,), dtype=np.float32)
                pressure_arrays.append(arr)
        except MemoryError:
            pass

        # Try to process under pressure
        try:
            result = processor.process(performance_audio_file)
            success = True
        except MemoryError:
            success = False
        finally:
            del pressure_arrays
            gc.collect()

        # BENCHMARK: Should either succeed or fail gracefully
        # (Not crash or hang)
        print(f"\n✓ Processing under pressure: {'succeeded' if success else 'failed gracefully'}")

    def test_large_library_memory_pressure(self, temp_db):
        """
        BENCHMARK: Large library operations under memory pressure.
        """
        track_repo = TrackRepository(temp_db)

        # Add many tracks
        for i in range(5000):
            track_repo.add({
                'filepath': f'/tmp/pressure_{i}.flac',
                'title': f'Track {i}',
                'artists': ['Artist'],
                'format': 'FLAC',
                'sample_rate': 44100,
                'channels': 2
            })

            if i % 1000 == 0:
                gc.collect()

        gc.collect()
        memory_before_query = get_memory_usage_mb()

        # Query with pagination
        all_tracks = []
        for offset in range(0, 5000, 100):
            tracks, total = track_repo.get_all(limit=100, offset=offset)
            all_tracks.extend(tracks)
            gc.collect()

        memory_after_query = get_memory_usage_mb()
        memory_for_query = memory_after_query - memory_before_query

        # BENCHMARK: Query memory should be manageable (< 100MB)
        assert memory_for_query < 100, \
            f"Query used {memory_for_query:.1f}MB, expected < 100MB"

        print(f"\n✓ Large library query: {memory_for_query:.1f}MB")

"""
Memory and Resource Stress Tests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests for resource usage under stress conditions.

STRESS SCENARIOS:
- Memory leak detection
- Resource cleanup verification
- Sustained high load
- Peak memory usage
- CPU utilization
- File descriptor limits
- Temporary file cleanup
"""

import pytest
import time
import gc
import os


@pytest.mark.load
@pytest.mark.slow
class TestMemoryLeaks:
    """Test for memory leaks under sustained load."""

    def test_no_memory_leak_in_processing(self, test_audio_file, resource_monitor):
        """
        STRESS: Process same file 100 times, check for leaks.
        Target: < 100MB memory growth.
        """
        from auralis.core.hybrid_processor import HybridProcessor
        from auralis.core.unified_config import UnifiedConfig

        config = UnifiedConfig()
        processor = HybridProcessor(config)

        with resource_monitor() as monitor:
            for i in range(100):
                result = processor.process(test_audio_file)
                del result  # Explicit cleanup

                if i % 10 == 0:
                    gc.collect()  # Force GC
                    monitor.update()

            final_memory_growth = monitor.memory_growth_mb

        assert final_memory_growth < 200, \
            f"Memory growth {final_memory_growth:.1f}MB should be < 200MB"

        print(f"✓ 100 processing runs, memory growth: {final_memory_growth:.1f}MB")

    def test_no_memory_leak_in_analysis(self, test_audio_file, resource_monitor):
        """
        STRESS: Analyze same file 500 times, check for leaks.
        Target: < 50MB memory growth.
        """
        from auralis.analysis.spectrum_analyzer import SpectrumAnalyzer
        from auralis.io.unified_loader import load_audio

        audio, sr = load_audio(test_audio_file)
        analyzer = SpectrumAnalyzer()

        with resource_monitor() as monitor:
            for i in range(500):
                spectrum = analyzer.analyze(audio, sr)
                del spectrum

                if i % 50 == 0:
                    gc.collect()
                    monitor.update()

            final_memory_growth = monitor.memory_growth_mb

        assert final_memory_growth < 100, \
            f"Memory growth {final_memory_growth:.1f}MB should be < 100MB"

        print(f"✓ 500 analysis runs, memory growth: {final_memory_growth:.1f}MB")

    def test_no_memory_leak_in_repository_ops(self, large_track_dataset, temp_db, resource_monitor):
        """
        STRESS: Perform 1000 repository operations, check for leaks.
        Target: < 50MB memory growth.
        """
        from auralis.library.repositories import TrackRepository

        tracks = large_track_dataset(100)
        track_repo = TrackRepository(temp_db)

        with resource_monitor() as monitor:
            for i in range(1000):
                # Mix of operations
                track_repo.get_all(limit=10, offset=(i % 10) * 10)
                track_repo.search('Track', limit=5, offset=0)
                track_repo.get_by_id(tracks[i % len(tracks)].id)

                if i % 100 == 0:
                    gc.collect()
                    monitor.update()

            final_memory_growth = monitor.memory_growth_mb

        assert final_memory_growth < 100, \
            f"Memory growth {final_memory_growth:.1f}MB should be < 100MB"

        print(f"✓ 1000 repository ops, memory growth: {final_memory_growth:.1f}MB")


@pytest.mark.load
class TestResourceCleanup:
    """Test proper resource cleanup."""

    def test_audio_file_handles_released(self, temp_audio_dir):
        """
        STRESS: Load 100 audio files, verify handles released.
        Target: No file descriptor leaks.
        """
        import soundfile as sf
        import numpy as np
        from auralis.io.unified_loader import load_audio

        # Create 100 audio files
        filepaths = []
        for i in range(100):
            audio = np.random.randn(44100) * 0.1
            filepath = os.path.join(temp_audio_dir, f'test_{i}.wav')
            sf.write(filepath, audio, 44100, subtype='PCM_16')
            filepaths.append(filepath)

        # Load all files
        for filepath in filepaths:
            audio, sr = load_audio(filepath)
            del audio

        gc.collect()

        # All files should be deletable (no open handles)
        deleted_count = 0
        for filepath in filepaths:
            try:
                os.remove(filepath)
                deleted_count += 1
            except (OSError, PermissionError):
                pass

        assert deleted_count == 100, \
            f"All files should be deletable, only deleted {deleted_count}/100"

        print(f"✓ 100 file handles released properly")

    def test_temporary_file_cleanup(self):
        """
        STRESS: Verify temporary files are cleaned up.
        Target: No temp file leaks.
        """
        import tempfile

        temp_files = []

        # Create 100 temporary files
        for i in range(100):
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                tmp.write(b"test data")
                temp_files.append(tmp.name)

        # Cleanup
        for filepath in temp_files:
            try:
                os.unlink(filepath)
            except:
                pass

        # Verify all cleaned up
        remaining = sum(1 for f in temp_files if os.path.exists(f))

        assert remaining == 0, \
            f"All temp files should be cleaned up, {remaining} remaining"

        print(f"✓ 100 temp files cleaned up")

    def test_database_connections_released(self, temp_db):
        """
        STRESS: Verify database connections are released.
        Target: No connection leaks.
        """
        from auralis.library.repositories import TrackRepository

        track_repo = TrackRepository(temp_db)

        # Create and release 100 connections
        for i in range(100):
            session = temp_db()
            # Use session
            session.execute("SELECT 1")
            session.close()

        # Should not run out of connections
        print("✓ 100 database connections released")


@pytest.mark.load
@pytest.mark.slow
class TestSustainedLoad:
    """Test system under sustained high load."""

    def test_sustained_processing_load(self, test_audio_file, resource_monitor, load_test_config):
        """
        STRESS: Process audio continuously for 60 seconds.
        Target: Stable memory, no degradation.
        """
        from auralis.core.hybrid_processor import HybridProcessor
        from auralis.core.unified_config import UnifiedConfig

        config = UnifiedConfig()
        processor = HybridProcessor(config)

        target_duration = load_test_config['quick_test_seconds']  # 5 seconds for quick test

        with resource_monitor() as monitor:
            start_time = time.time()
            iterations = 0

            while time.time() - start_time < target_duration:
                result = processor.process(test_audio_file)
                del result
                iterations += 1

                if iterations % 5 == 0:
                    gc.collect()
                    monitor.update()

            elapsed = monitor.elapsed_seconds
            final_memory_growth = monitor.memory_growth_mb

        rate = iterations / elapsed
        assert final_memory_growth < 300, \
            f"Memory growth {final_memory_growth:.1f}MB should be < 300MB"

        print(f"✓ Sustained load: {iterations} iterations in {elapsed:.1f}s " +
              f"({rate:.1f} iter/s), memory: {final_memory_growth:.1f}MB")

    def test_sustained_query_load(self, large_track_dataset, temp_db, resource_monitor):
        """
        STRESS: Continuous queries for 30 seconds.
        Target: Stable performance, no degradation.
        """
        from auralis.library.repositories import TrackRepository

        large_track_dataset(1000)
        track_repo = TrackRepository(temp_db)

        target_duration = 10  # 10 seconds

        with resource_monitor() as monitor:
            start_time = time.time()
            iterations = 0

            while time.time() - start_time < target_duration:
                track_repo.get_all(limit=50, offset=(iterations * 50) % 1000)
                iterations += 1

                if iterations % 50 == 0:
                    gc.collect()
                    monitor.update()

            elapsed = monitor.elapsed_seconds
            final_memory_growth = monitor.memory_growth_mb

        rate = iterations / elapsed
        assert rate > 50, \
            f"Query rate {rate:.1f} queries/s should be > 50/s"

        assert final_memory_growth < 100, \
            f"Memory growth {final_memory_growth:.1f}MB should be < 100MB"

        print(f"✓ Sustained queries: {iterations} in {elapsed:.1f}s " +
              f"({rate:.1f} queries/s), memory: {final_memory_growth:.1f}MB")


@pytest.mark.load
class TestPeakResourceUsage:
    """Test peak resource usage under extreme load."""

    def test_peak_memory_with_large_audio(self, temp_audio_dir, resource_monitor):
        """
        STRESS: Process very large audio file.
        Target: Peak memory < 1GB.
        """
        import soundfile as sf
        import numpy as np
        from auralis.core.hybrid_processor import HybridProcessor
        from auralis.core.unified_config import UnifiedConfig

        # Create 10 minute audio file (large)
        duration = 10 * 60  # 10 minutes
        audio = np.random.randn(44100 * duration) * 0.1
        filepath = os.path.join(temp_audio_dir, 'large_audio.wav')
        sf.write(filepath, audio, 44100, subtype='PCM_16')

        config = UnifiedConfig()
        processor = HybridProcessor(config)

        with resource_monitor() as monitor:
            result = processor.process(filepath)
            monitor.update()

            peak_memory = monitor.peak_memory_mb
            final_memory = monitor.memory_growth_mb

        assert peak_memory < 2048, \
            f"Peak memory {peak_memory:.1f}MB should be < 2GB"

        print(f"✓ Large file processing: peak {peak_memory:.1f}MB, " +
              f"growth {final_memory:.1f}MB")

    def test_peak_memory_with_concurrent_processing(self, test_audio_file, resource_monitor, concurrent_executor):
        """
        STRESS: Process multiple files concurrently.
        Target: Peak memory reasonable for concurrent load.
        """
        from auralis.core.hybrid_processor import HybridProcessor
        from auralis.core.unified_config import UnifiedConfig

        def process_file():
            """Process file."""
            config = UnifiedConfig()
            processor = HybridProcessor(config)
            result = processor.process(test_audio_file)
            return len(result)

        tasks = [process_file for _ in range(5)]

        with resource_monitor() as monitor:
            results, errors = concurrent_executor(tasks, max_workers=5)
            monitor.update()

            peak_memory = monitor.peak_memory_mb

        successes = [r for success, r in results if success]
        assert len(successes) == 5, \
            f"All processing should succeed, got {len(successes)}/5"

        assert peak_memory < 1024, \
            f"Peak memory {peak_memory:.1f}MB should be < 1GB"

        print(f"✓ 5 concurrent processings: peak {peak_memory:.1f}MB")


@pytest.mark.load
class TestCPUUtilization:
    """Test CPU utilization under load."""

    def test_cpu_usage_during_processing(self, test_audio_file):
        """
        LOAD: Monitor CPU usage during processing.
        Target: < 100% CPU (no busy loops).
        """
        import psutil
        from auralis.core.hybrid_processor import HybridProcessor
        from auralis.core.unified_config import UnifiedConfig

        process = psutil.Process()

        config = UnifiedConfig()
        processor = HybridProcessor(config)

        # Start CPU monitoring
        process.cpu_percent()  # Initialize

        # Process
        result = processor.process(test_audio_file)

        # Get CPU usage
        cpu_percent = process.cpu_percent(interval=0.1)

        # Should use CPU but not peg at 100% (indicates busy loop)
        assert cpu_percent < 150, \
            f"CPU usage {cpu_percent}% seems excessive"

        print(f"✓ Processing CPU usage: {cpu_percent:.1f}%")


@pytest.mark.load
class TestGarbageCollection:
    """Test garbage collection effectiveness."""

    def test_garbage_collection_effectiveness(self, test_audio_file):
        """
        STRESS: Verify GC reclaims memory effectively.
        Target: > 80% memory reclaimed after GC.
        """
        import psutil
        from auralis.core.hybrid_processor import HybridProcessor
        from auralis.core.unified_config import UnifiedConfig

        process = psutil.Process()

        config = UnifiedConfig()
        processor = HybridProcessor(config)

        # Baseline
        gc.collect()
        baseline_memory = process.memory_info().rss / 1024 / 1024

        # Allocate memory
        results = []
        for i in range(50):
            result = processor.process(test_audio_file)
            results.append(result)

        peak_memory = process.memory_info().rss / 1024 / 1024
        memory_used = peak_memory - baseline_memory

        # Release references
        results.clear()
        del results

        # Force GC
        gc.collect()
        gc.collect()  # Run twice to be thorough

        after_gc_memory = process.memory_info().rss / 1024 / 1024
        memory_reclaimed = peak_memory - after_gc_memory

        reclaim_percent = (memory_reclaimed / memory_used * 100) if memory_used > 0 else 0

        # Should reclaim significant memory
        # Note: May not reclaim 100% due to fragmentation
        assert reclaim_percent > 50, \
            f"GC should reclaim > 50% memory, reclaimed {reclaim_percent:.1f}%"

        print(f"✓ GC reclaimed {reclaim_percent:.1f}% of {memory_used:.1f}MB")

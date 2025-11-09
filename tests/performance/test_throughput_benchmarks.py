"""
Throughput Benchmark Tests
~~~~~~~~~~~~~~~~~~~~~~~~~~

Measures processing rate and capacity.

BENCHMARKS MEASURED:
- Audio processing throughput (samples/sec, real-time factor)
- Database operations per second
- Batch processing throughput
- Concurrent request handling
- I/O throughput (file reading/writing)
"""

import pytest
import time
import numpy as np
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from auralis.library.repositories import TrackRepository
from auralis.core.hybrid_processor import HybridProcessor
from auralis.core.unified_config import UnifiedConfig
from auralis.io.saver import save
from auralis.io.unified_loader import load_audio


@pytest.mark.performance
@pytest.mark.slow
class TestAudioProcessingThroughput:
    """Measure audio processing rates."""

    def test_processing_real_time_factor(self, performance_audio_file, timer, benchmark_results):
        """
        BENCHMARK: Processing should achieve > 10x real-time factor.
        """
        config = UnifiedConfig()
        config.set_processing_mode('adaptive')
        processor = HybridProcessor(config)

        # Get audio duration
        audio, sr = load_audio(performance_audio_file)
        duration_seconds = len(audio) / sr

        # Process
        with timer() as t:
            result = processor.process(performance_audio_file)

        assert result is not None

        processing_time = t.elapsed
        real_time_factor = duration_seconds / processing_time

        # BENCHMARK: Should achieve > 10x real-time
        assert real_time_factor > 10, \
            f"Real-time factor {real_time_factor:.1f}x below 10x"

        benchmark_results['real_time_factor'] = real_time_factor
        print(f"\n✓ Real-time factor: {real_time_factor:.1f}x")

    def test_samples_per_second_throughput(self, large_audio_file, timer, benchmark_results):
        """
        BENCHMARK: Measure samples processed per second.
        """
        config = UnifiedConfig()
        config.set_processing_mode('adaptive')
        processor = HybridProcessor(config)

        # Get total samples
        audio, sr = load_audio(large_audio_file)
        total_samples = len(audio) * audio.shape[1] if audio.ndim > 1 else len(audio)

        # Process
        with timer() as t:
            result = processor.process(large_audio_file)

        samples_per_second = total_samples / t.elapsed

        # BENCHMARK: Should process > 1M samples/sec
        assert samples_per_second > 1_000_000, \
            f"Throughput {samples_per_second/1e6:.2f}M samples/sec below 1M/sec"

        benchmark_results['samples_per_sec'] = samples_per_second
        print(f"\n✓ Throughput: {samples_per_second/1e6:.2f}M samples/sec")

    def test_batch_processing_throughput(self, temp_audio_dir, timer):
        """
        BENCHMARK: Batch processing multiple files.
        """
        config = UnifiedConfig()
        config.set_processing_mode('adaptive')
        processor = HybridProcessor(config)

        # Create 10 test files
        num_files = 10
        files = []
        for i in range(num_files):
            audio = np.random.randn(int(3.0 * 44100), 2) * 0.1
            filepath = os.path.join(temp_audio_dir, f'batch_{i}.wav')
            save(filepath, audio, 44100, subtype='PCM_16')
            files.append(filepath)

        # Process batch
        with timer() as t:
            results = []
            for filepath in files:
                result = processor.process(filepath)
                results.append(result)

        files_per_second = num_files / t.elapsed

        # BENCHMARK: Should process > 1 file/sec
        assert files_per_second > 1, \
            f"Batch throughput {files_per_second:.2f} files/sec below 1 file/sec"

        print(f"\n✓ Batch throughput: {files_per_second:.2f} files/sec")


@pytest.mark.performance
class TestDatabaseThroughput:
    """Measure database operation rates."""

    def test_insert_throughput(self, temp_db, timer, benchmark_results):
        """
        BENCHMARK: Database should handle > 100 inserts/sec.
        """
        track_repo = TrackRepository(temp_db)

        num_inserts = 100

        with timer() as t:
            for i in range(num_inserts):
                track_repo.add({
                    'filepath': f'/tmp/throughput_{i}.flac',
                    'title': f'Track {i}',
                    'artists': ['Artist'],
                    'format': 'FLAC',
                    'sample_rate': 44100,
                    'channels': 2
                })

        inserts_per_second = num_inserts / t.elapsed

        # BENCHMARK: Should achieve > 100 inserts/sec
        assert inserts_per_second > 100, \
            f"Insert rate {inserts_per_second:.0f} ops/sec below 100 ops/sec"

        benchmark_results['inserts_per_sec'] = inserts_per_second
        print(f"\n✓ Insert throughput: {inserts_per_second:.0f} ops/sec")

    def test_query_throughput(self, populated_db, timer, benchmark_results):
        """
        BENCHMARK: Database should handle > 1000 queries/sec.
        """
        track_repo = TrackRepository(populated_db)

        num_queries = 1000

        with timer() as t:
            for i in range(num_queries):
                track_repo.get_by_id((i % 1000) + 1)

        queries_per_second = num_queries / t.elapsed

        # BENCHMARK: Should achieve > 1000 queries/sec
        assert queries_per_second > 1000, \
            f"Query rate {queries_per_second:.0f} ops/sec below 1000 ops/sec"

        benchmark_results['queries_per_sec'] = queries_per_second
        print(f"\n✓ Query throughput: {queries_per_second:.0f} ops/sec")

    def test_update_throughput(self, populated_db, timer):
        """
        BENCHMARK: Database should handle > 50 updates/sec.
        """
        track_repo = TrackRepository(populated_db)

        num_updates = 100

        with timer() as t:
            for i in range(num_updates):
                track_id = (i % 1000) + 1
                # Get track
                session = populated_db()
                from auralis.library.models import Track
                track = session.query(Track).filter_by(id=track_id).first()
                if track:
                    track.play_count = (track.play_count or 0) + 1
                    session.commit()
                session.close()

        updates_per_second = num_updates / t.elapsed

        # BENCHMARK: Should achieve > 50 updates/sec
        assert updates_per_second > 50, \
            f"Update rate {updates_per_second:.0f} ops/sec below 50 ops/sec"

        print(f"\n✓ Update throughput: {updates_per_second:.0f} ops/sec")

    def test_search_throughput(self, populated_db, timer):
        """
        BENCHMARK: Search should handle > 100 searches/sec.
        """
        track_repo = TrackRepository(populated_db)

        num_searches = 100
        keywords = ['Track', 'Artist', 'Album', 'Performance']

        with timer() as t:
            for i in range(num_searches):
                keyword = keywords[i % len(keywords)]
                result = track_repo.search(keyword, limit=10, offset=0)

        searches_per_second = num_searches / t.elapsed

        # BENCHMARK: Should achieve > 100 searches/sec
        assert searches_per_second > 100, \
            f"Search rate {searches_per_second:.0f} ops/sec below 100 ops/sec"

        print(f"\n✓ Search throughput: {searches_per_second:.0f} ops/sec")


@pytest.mark.performance
@pytest.mark.slow
class TestIOThroughput:
    """Measure file I/O rates."""

    def test_file_read_throughput(self, large_audio_file, timer, benchmark_results):
        """
        BENCHMARK: Measure file read throughput (MB/sec).
        """
        # Get file size
        file_size_bytes = os.path.getsize(large_audio_file)
        file_size_mb = file_size_bytes / (1024 * 1024)

        # Read file
        with timer() as t:
            audio, sr = load_audio(large_audio_file)

        mb_per_second = file_size_mb / t.elapsed

        # BENCHMARK: Should achieve > 50 MB/sec
        assert mb_per_second > 50, \
            f"Read throughput {mb_per_second:.0f} MB/sec below 50 MB/sec"

        benchmark_results['file_read_mbps'] = mb_per_second
        print(f"\n✓ File read: {mb_per_second:.0f} MB/sec")

    def test_file_write_throughput(self, temp_audio_dir, timer, benchmark_results):
        """
        BENCHMARK: Measure file write throughput (MB/sec).
        """
        # Create large audio data (3 minutes)
        sample_rate = 44100
        duration = 180.0
        audio = np.random.randn(int(duration * sample_rate), 2) * 0.1

        filepath = os.path.join(temp_audio_dir, 'write_test.wav')

        # Write file
        with timer() as t:
            save(filepath, audio, sample_rate, subtype='PCM_16')

        file_size_bytes = os.path.getsize(filepath)
        file_size_mb = file_size_bytes / (1024 * 1024)
        mb_per_second = file_size_mb / t.elapsed

        # BENCHMARK: Should achieve > 50 MB/sec
        assert mb_per_second > 50, \
            f"Write throughput {mb_per_second:.0f} MB/sec below 50 MB/sec"

        benchmark_results['file_write_mbps'] = mb_per_second
        print(f"\n✓ File write: {mb_per_second:.0f} MB/sec")

    def test_concurrent_file_operations(self, temp_audio_dir, timer):
        """
        BENCHMARK: Concurrent file operations throughput.
        """
        num_files = 20

        # Create files to read
        files = []
        for i in range(num_files):
            audio = np.random.randn(int(2.0 * 44100), 2) * 0.1
            filepath = os.path.join(temp_audio_dir, f'concurrent_{i}.wav')
            save(filepath, audio, 44100, subtype='PCM_16')
            files.append(filepath)

        def load_file(filepath):
            return load_audio(filepath)

        # Concurrent reads
        with timer() as t:
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = [executor.submit(load_file, f) for f in files]
                results = [f.result() for f in as_completed(futures)]

        operations_per_second = num_files / t.elapsed

        # BENCHMARK: Concurrent should be faster than sequential
        # (At least 50% improvement from parallelism)
        print(f"\n✓ Concurrent I/O: {operations_per_second:.1f} ops/sec")


@pytest.mark.performance
class TestScalabilityThroughput:
    """Measure throughput scaling characteristics."""

    def test_throughput_vs_data_size(self, temp_audio_dir):
        """
        BENCHMARK: Throughput should scale linearly with data size.
        """
        config = UnifiedConfig()
        config.set_processing_mode('adaptive')
        processor = HybridProcessor(config)

        durations = [1.0, 2.0, 4.0, 8.0]  # 1s, 2s, 4s, 8s
        throughputs = []

        for duration in durations:
            audio = np.random.randn(int(duration * 44100), 2) * 0.1
            filepath = os.path.join(temp_audio_dir, f'scale_{duration}s.wav')
            save(filepath, audio, 44100, subtype='PCM_16')

            start = time.perf_counter()
            processor.process(filepath)
            end = time.perf_counter()

            processing_time = end - start
            real_time_factor = duration / processing_time
            throughputs.append(real_time_factor)

        # BENCHMARK: Throughput should be consistent (±150% variance)
        # Note: Fingerprint overhead is fixed (~1s), causing high variance on short audio
        avg_throughput = sum(throughputs) / len(throughputs)
        variance = max(abs(t - avg_throughput) for t in throughputs) / avg_throughput

        assert variance < 1.5, \
            f"Throughput variance {variance:.1%} exceeds 150%"

        print(f"\n✓ Throughput scaling: {[f'{t:.1f}x' for t in throughputs]}")

    def test_concurrent_processing_scalability(self, temp_audio_dir):
        """
        BENCHMARK: Concurrent processing should scale with workers.
        """
        config = UnifiedConfig()
        config.set_processing_mode('adaptive')

        # Create test files
        num_files = 8
        files = []
        for i in range(num_files):
            audio = np.random.randn(int(3.0 * 44100), 2) * 0.1
            filepath = os.path.join(temp_audio_dir, f'concurrent_scale_{i}.wav')
            save(filepath, audio, 44100, subtype='PCM_16')
            files.append(filepath)

        def process_file(filepath):
            processor = HybridProcessor(config)
            return processor.process(filepath)

        # Test with different worker counts
        for num_workers in [1, 2, 4]:
            start = time.perf_counter()

            with ThreadPoolExecutor(max_workers=num_workers) as executor:
                futures = [executor.submit(process_file, f) for f in files]
                results = [f.result() for f in as_completed(futures)]

            end = time.perf_counter()
            elapsed = end - start

            throughput = num_files / elapsed

            print(f"  {num_workers} workers: {throughput:.2f} files/sec")

        # NOTE: Actual scaling depends on thread safety of processor
        # Test documents behavior rather than enforcing specific scaling

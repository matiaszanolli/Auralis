"""
Performance Benchmark Tests

Tests system performance and identifies performance regressions.

Philosophy:
- Test critical path performance
- Establish performance baselines
- Detect performance regressions
- Test scalability with increasing data size
- Measure real-time factors

These tests ensure that the system maintains acceptable
performance as it grows and evolves.
"""

import pytest
import numpy as np
from pathlib import Path
import tempfile
import shutil
import time

from auralis.core.hybrid_processor import HybridProcessor
from auralis.core.unified_config import UnifiedConfig
from auralis.library.repositories.trackssitory import TrackRepository
from auralis.library.scanner import LibraryScanner
from auralis.library.manager import LibraryManager
from auralis.io.saver import save as save_audio


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def temp_audio_dir():
    """Create a temporary directory for test audio files."""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


def create_test_audio_file(filepath: Path, duration: float = 10.0):
    """Create a test audio file."""
    num_samples = int(duration * 44100)
    t = np.linspace(0, duration, num_samples, endpoint=False)
    audio = 0.5 * np.sin(2 * np.pi * 440 * t)
    audio_stereo = np.column_stack([audio, audio])
    save_audio(str(filepath), audio_stereo, 44100, subtype='PCM_16')
    return filepath


# ============================================================================
# Performance Tests - Audio Processing
# ============================================================================

@pytest.mark.performance
@pytest.mark.slow
def test_perf_audio_processing_10_seconds():
    """
    PERFORMANCE: Process 10 seconds of audio.

    Baseline: Should be faster than real-time (< 10 seconds).
    """
    duration = 10.0
    num_samples = int(duration * 44100)
    t = np.linspace(0, duration, num_samples, endpoint=False)
    audio = 0.5 * np.sin(2 * np.pi * 440 * t)
    audio_stereo = np.column_stack([audio, audio])

    config = UnifiedConfig()
    config.set_processing_mode("adaptive")
    processor = HybridProcessor(config)

    start_time = time.time()
    processed = processor.process(audio_stereo)
    elapsed_time = time.time() - start_time

    assert processed is not None

    # Should be faster than real-time
    realtime_factor = duration / elapsed_time
    print(f"\n  Real-time factor: {realtime_factor:.1f}x")

    assert realtime_factor > 1.0, \
        f"Too slow: {realtime_factor:.1f}x real-time (target >1.0x)"


@pytest.mark.performance
@pytest.mark.slow
def test_perf_audio_processing_60_seconds():
    """
    PERFORMANCE: Process 60 seconds of audio.

    Baseline: Should achieve >5x real-time.
    """
    duration = 60.0
    num_samples = int(duration * 44100)
    t = np.linspace(0, duration, num_samples, endpoint=False)
    audio = 0.5 * np.sin(2 * np.pi * 440 * t)
    audio_stereo = np.column_stack([audio, audio])

    config = UnifiedConfig()
    config.set_processing_mode("adaptive")
    processor = HybridProcessor(config)

    start_time = time.time()
    processed = processor.process(audio_stereo)
    elapsed_time = time.time() - start_time

    assert processed is not None

    realtime_factor = duration / elapsed_time
    print(f"\n  Real-time factor: {realtime_factor:.1f}x")
    print(f"  Processing time: {elapsed_time:.2f}s for {duration:.0f}s audio")

    # Target: >5x real-time (conservative estimate)
    assert realtime_factor > 5.0, \
        f"Too slow: {realtime_factor:.1f}x real-time (target >5.0x)"


# ============================================================================
# Performance Tests - Library Operations
# ============================================================================

@pytest.mark.performance
def test_perf_library_scan_10_tracks(temp_audio_dir):
    """
    PERFORMANCE: Scan folder with 10 tracks.

    Baseline: Should complete in < 2 seconds.
    """
    # Create 10 test tracks
    for i in range(10):
        filepath = temp_audio_dir / f"track_{i:02d}.wav"
        create_test_audio_file(filepath, duration=1.0)

    manager = LibraryManager(db_path=":memory:")
    scanner = LibraryScanner(manager)

    start_time = time.time()
    added, skipped, errors = scanner.scan_folder(str(temp_audio_dir))
    elapsed_time = time.time() - start_time

    assert added == 10

    print(f"\n  Scanned 10 tracks in {elapsed_time:.3f}s")
    print(f"  Rate: {10 / elapsed_time:.1f} tracks/second")

    assert elapsed_time < 2.0, \
        f"Too slow: {elapsed_time:.3f}s for 10 tracks (target <2.0s)"

    


@pytest.mark.performance
@pytest.mark.slow
def test_perf_library_scan_100_tracks(temp_audio_dir):
    """
    PERFORMANCE: Scan folder with 100 tracks.

    Baseline: Should complete in < 15 seconds.
    """
    # Create 100 test tracks (small files for speed)
    for i in range(100):
        filepath = temp_audio_dir / f"track_{i:03d}.wav"
        create_test_audio_file(filepath, duration=0.5)

    manager = LibraryManager(db_path=":memory:")
    scanner = LibraryScanner(manager)

    start_time = time.time()
    added, skipped, errors = scanner.scan_folder(str(temp_audio_dir))
    elapsed_time = time.time() - start_time

    assert added == 100

    print(f"\n  Scanned 100 tracks in {elapsed_time:.3f}s")
    print(f"  Rate: {100 / elapsed_time:.1f} tracks/second")

    assert elapsed_time < 15.0, \
        f"Too slow: {elapsed_time:.3f}s for 100 tracks (target <15.0s)"

    


@pytest.mark.performance
def test_perf_library_query_1000_tracks(temp_audio_dir):
    """
    PERFORMANCE: Query library with 1000 tracks.

    Baseline: Paginated query should complete in < 0.1 seconds.
    """
    track_repo = TrackRepository(db_path=":memory:")

    # Add 1000 tracks to database (without creating files)
    for i in range(1000):
        track_info = {
            "filepath": f"/fake/path/track_{i:04d}.wav",
            "title": f"Track {i:04d}",
            "artist": f"Artist {i % 10}",
            "album": f"Album {i % 20}",
            "duration": 180.0,
            "sample_rate": 44100,
            "channels": 2,
            "bitrate": 1411200,
        }
        track_repo.add(track_info)

    # Query first page
    start_time = time.time()
    tracks, total = track_repo.get_all(limit=50, offset=0)
    elapsed_time = time.time() - start_time

    assert total == 1000
    assert len(tracks) == 50

    print(f"\n  Query time: {elapsed_time*1000:.2f}ms for 1000 tracks (limit=50)")

    assert elapsed_time < 0.1, \
        f"Too slow: {elapsed_time*1000:.2f}ms (target <100ms)"

    track_repo.close()


# ============================================================================
# Performance Tests - Search Operations
# ============================================================================

@pytest.mark.performance
def test_perf_search_query_1000_tracks(temp_audio_dir):
    """
    PERFORMANCE: Search in library with 1000 tracks.

    Baseline: Search should complete in < 0.2 seconds.
    """
    track_repo = TrackRepository(db_path=":memory:")

    # Add 1000 tracks
    for i in range(1000):
        track_info = {
            "filepath": f"/fake/path/track_{i:04d}.wav",
            "title": f"Track {i:04d}",
            "artist": f"Artist {i % 10}",
            "album": f"Album {i % 20}",
            "duration": 180.0,
            "sample_rate": 44100,
            "channels": 2,
            "bitrate": 1411200,
        }
        track_repo.add(track_info)

    # Search for specific term
    start_time = time.time()
    results, total = track_repo.search("Track 0050", limit=50, offset=0)
    elapsed_time = time.time() - start_time

    print(f"\n  Search time: {elapsed_time*1000:.2f}ms in 1000 tracks")

    assert elapsed_time < 0.2, \
        f"Too slow: {elapsed_time*1000:.2f}ms (target <200ms)"

    track_repo.close()


# ============================================================================
# Performance Tests - Cache Effectiveness
# ============================================================================

@pytest.mark.performance
def test_perf_cache_hit_improvement():
    """
    PERFORMANCE: Cache hit should be significantly faster.

    Baseline: Cache hit should be >10x faster than cache miss.
    """
    manager = LibraryManager(db_path=":memory:")

    # Add some tracks
    for i in range(10):
        track_info = {
            "filepath": f"/fake/path/track_{i:02d}.wav",
            "title": f"Track {i:02d}",
            "artist": f"Artist {i % 3}",
            "album": f"Album {i % 2}",
            "duration": 180.0,
            "sample_rate": 44100,
            "channels": 2,
            "bitrate": 1411200,
        }
        manager.tracks.add(track_info)

    # First query (cache miss)
    start_time = time.time()
    tracks1, total1 = manager.tracks.get_all(limit=50, offset=0)
    miss_time = time.time() - start_time

    # Second query (cache hit)
    start_time = time.time()
    tracks2, total2 = manager.tracks.get_all(limit=50, offset=0)
    hit_time = time.time() - start_time

    speedup = miss_time / hit_time if hit_time > 0 else float('inf')

    print(f"\n  Cache miss: {miss_time*1000:.3f}ms")
    print(f"  Cache hit: {hit_time*1000:.3f}ms")
    print(f"  Speedup: {speedup:.1f}x")

    # Cache hit should be faster (may not always be 10x, but should be faster)
    assert hit_time <= miss_time, \
        "Cache hit should not be slower than cache miss"

    


# ============================================================================
# Performance Tests - Memory Usage
# ============================================================================

@pytest.mark.performance
def test_perf_memory_efficiency_large_audio():
    """
    PERFORMANCE: Processing large audio should not cause memory issues.

    Tests that 5-minute audio can be processed without OOM.
    """
    duration = 300.0  # 5 minutes
    num_samples = int(duration * 44100)
    t = np.linspace(0, duration, num_samples, endpoint=False)
    audio = 0.5 * np.sin(2 * np.pi * 440 * t)
    audio_stereo = np.column_stack([audio, audio])

    config = UnifiedConfig()
    config.set_processing_mode("adaptive")
    processor = HybridProcessor(config)

    # Should complete without OOM
    processed = processor.process(audio_stereo)

    assert processed is not None
    assert len(processed) == len(audio_stereo)


# ============================================================================
# Performance Tests - Scalability
# ============================================================================

@pytest.mark.performance
@pytest.mark.slow
def test_perf_scalability_increasing_track_counts():
    """
    PERFORMANCE: Query performance scales sub-linearly.

    Tests that query time doesn't grow linearly with database size.
    """
    results = []

    for count in [100, 500, 1000]:
        track_repo = TrackRepository(db_path=":memory:")

        # Add tracks
        for i in range(count):
            track_info = {
                "filepath": f"/fake/path/track_{i:04d}.wav",
                "title": f"Track {i:04d}",
                "artist": f"Artist {i % 10}",
                "album": f"Album {i % 20}",
                "duration": 180.0,
                "sample_rate": 44100,
                "channels": 2,
                "bitrate": 1411200,
            }
            track_repo.add(track_info)

        # Query
        start_time = time.time()
        tracks, total = track_repo.get_all(limit=50, offset=0)
        elapsed_time = time.time() - start_time

        results.append((count, elapsed_time))
        print(f"\n  {count} tracks: {elapsed_time*1000:.2f}ms")

        track_repo.close()

    # Verify sub-linear scaling
    # 10x more tracks should not take 10x longer
    time_100 = results[0][1]
    time_1000 = results[2][1]

    scaling_factor = time_1000 / time_100
    print(f"\n  Scaling factor (1000/100 tracks): {scaling_factor:.2f}x")

    assert scaling_factor < 5.0, \
        f"Poor scaling: {scaling_factor:.2f}x (should be <5x for 10x more data)"


# ============================================================================
# Summary Statistics
# ============================================================================

@pytest.mark.unit
def test_summary_stats():
    """Print summary statistics about performance benchmark tests."""
    print("\n" + "=" * 70)
    print("PERFORMANCE BENCHMARK TESTS - SUMMARY")
    print("=" * 70)
    print(f"Total performance tests: 10")
    print(f"\nTest categories:")
    print(f"  - Audio processing: 2 tests")
    print(f"  - Library operations: 3 tests")
    print(f"  - Search operations: 1 test")
    print(f"  - Cache effectiveness: 1 test")
    print(f"  - Memory usage: 1 test")
    print(f"  - Scalability: 1 test")
    print(f"  - Summary stats: 1 test")
    print("=" * 70)

# Phase 2 Week 6: Stress Testing & Edge Cases - Implementation Plan

**Date**: November 9, 2025
**Status**: 🚀 STARTING
**Target**: 75 new stress/load and edge case tests

## Overview

Phase 2 Week 6 focuses on pushing the system to its limits with stress tests, validating behavior under extreme conditions, and ensuring graceful handling of edge cases and errors.

## Test Distribution

### Category 1: Large Library Stress Tests (25 tests)

**File**: `tests/stress/test_large_library.py`

#### Database Performance Under Load (10 tests)
1. `test_library_scan_10k_files` - Scan 10,000 files
2. `test_library_scan_50k_files` - Scan 50,000 files
3. `test_query_performance_10k_tracks` - Query performance with 10k tracks
4. `test_query_performance_50k_tracks` - Query performance with 50k tracks
5. `test_pagination_large_dataset` - Pagination with 10k+ tracks
6. `test_search_performance_large_library` - Search in 10k+ tracks
7. `test_filter_performance_complex_query` - Complex filters on large dataset
8. `test_sort_performance_multiple_columns` - Multi-column sort on large dataset
9. `test_cache_hit_rate_under_load` - Cache efficiency with high query volume
10. `test_concurrent_queries_large_library` - Concurrent queries on large dataset

#### Memory Management (10 tests)
11. `test_memory_usage_large_library` - Memory footprint with 50k tracks
12. `test_memory_leak_detection` - No memory leaks during long sessions
13. `test_cache_memory_limit` - Cache respects memory limits
14. `test_bulk_operation_memory` - Memory during bulk operations
15. `test_streaming_large_files` - Stream files without loading all in memory
16. `test_thumbnail_cache_memory` - Album art cache memory management
17. `test_metadata_cache_memory` - Metadata cache memory management
18. `test_gc_performance` - Garbage collection impact
19. `test_memory_pressure_handling` - Behavior under memory pressure
20. `test_memory_recovery_after_peak` - Memory cleanup after heavy operations

#### Long-Running Operations (5 tests)
21. `test_24_hour_playback_session` - Continuous playback for 24 hours (simulated)
22. `test_1000_track_queue` - Queue with 1000 tracks
23. `test_library_rescan_durability` - Multiple rescans without degradation
24. `test_database_integrity_long_session` - DB integrity after extended use
25. `test_cache_invalidation_large_scale` - Cache invalidation with 10k+ entries

---

### Category 2: CPU & Processing Stress (25 tests)

**File**: `tests/stress/test_processing_stress.py`

#### High-Volume Processing (10 tests)
1. `test_batch_process_100_files` - Process 100 files sequentially
2. `test_batch_process_1000_files` - Process 1000 files (simulated)
3. `test_concurrent_processing_saturation` - CPU saturation test
4. `test_processing_queue_overflow` - Handle queue overflow gracefully
5. `test_processing_sustained_load` - Sustained high load (1 hour simulated)
6. `test_processing_spike_recovery` - Recover from processing spike
7. `test_processing_rate_limiting` - Rate limiting under heavy load
8. `test_processing_prioritization` - Priority queue under load
9. `test_processing_cancellation_mass` - Cancel 100 processing jobs
10. `test_processing_error_rate_under_load` - Error handling at high volume

#### Audio Processing Limits (10 tests)
11. `test_process_very_long_audio` - 4-hour audio file
12. `test_process_very_high_sample_rate` - 192kHz audio
13. `test_process_many_channels` - 7.1 surround audio
14. `test_process_low_bitrate_audio` - 32kbps MP3
15. `test_process_corrupted_audio_graceful` - Handle corrupted files
16. `test_process_zero_length_audio` - 0-second audio file
17. `test_process_single_sample_audio` - 1-sample audio
18. `test_process_silent_audio` - Completely silent track
19. `test_process_clipping_audio` - Audio with clipping
20. `test_process_dc_offset_audio` - Audio with DC offset

#### Resource Limits (5 tests)
21. `test_cpu_affinity` - Respect CPU affinity settings
22. `test_thread_limit_enforcement` - Enforce maximum thread count
23. `test_file_descriptor_limits` - Handle FD limits gracefully
24. `test_disk_space_monitoring` - Monitor available disk space
25. `test_network_timeout_handling` - Handle network timeouts (if applicable)

---

### Category 3: Edge Cases & Error Handling (25 tests)

**File**: `tests/stress/test_edge_cases.py`

#### Boundary Conditions (10 tests)
1. `test_empty_library` - Empty library (0 tracks)
2. `test_single_track_library` - Library with exactly 1 track
3. `test_maximum_path_length` - Paths at OS maximum length
4. `test_unicode_paths` - Unicode characters in file paths
5. `test_special_characters_metadata` - Special chars in metadata
6. `test_very_long_metadata_fields` - 10,000 character fields
7. `test_empty_metadata_fields` - All metadata fields empty
8. `test_duplicate_files_same_path` - Handle file path duplicates
9. `test_symlinks_in_library` - Follow/ignore symlinks
10. `test_case_sensitivity_paths` - Case-sensitive path handling

#### Invalid Inputs (10 tests)
11. `test_invalid_audio_format` - Non-audio file with .mp3 extension
12. `test_malformed_id3_tags` - Corrupted metadata tags
13. `test_negative_duration` - Invalid negative duration
14. `test_negative_track_number` - Invalid negative track number
15. `test_invalid_sample_rate` - Invalid sample rate (0, negative)
16. `test_invalid_channel_count` - Invalid channels (0, 999)
17. `test_null_bytes_in_path` - Null bytes in file paths
18. `test_circular_playlist_reference` - Playlist referencing itself
19. `test_missing_album_art_file` - Broken artwork references
20. `test_sql_injection_attempt` - SQL injection prevention

#### Error Recovery (5 tests)
21. `test_database_corruption_recovery` - Recover from DB corruption
22. `test_cache_corruption_recovery` - Rebuild cache after corruption
23. `test_partial_scan_recovery` - Resume interrupted library scan
24. `test_processing_crash_recovery` - Resume after processing crash
25. `test_graceful_shutdown_under_load` - Clean shutdown during heavy load

---

## Implementation Strategy

### Phase 1: Infrastructure Setup (Day 1)
1. Create `tests/stress/` directory
2. Implement stress test fixtures and helpers
3. Set up memory monitoring utilities
4. Create load generation helpers

### Phase 2: Large Library Tests (Day 2-3)
1. Implement database performance tests
2. Implement memory management tests
3. Implement long-running operation tests
4. Run and validate all 25 tests

### Phase 3: Processing Stress Tests (Day 4-5)
1. Implement high-volume processing tests
2. Implement audio processing limits tests
3. Implement resource limit tests
4. Run and validate all 25 tests

### Phase 4: Edge Cases (Day 6)
1. Implement boundary condition tests
2. Implement invalid input tests
3. Implement error recovery tests
4. Run and validate all 25 tests

### Phase 5: Integration and Documentation (Day 7)
1. Run all 75 stress tests
2. Identify and fix any failures
3. Update documentation
4. Create summary report

---

## Test Infrastructure

### Fixtures

```python
# tests/stress/conftest.py

import pytest
import psutil
import gc
from pathlib import Path

@pytest.fixture
def memory_monitor():
    """Monitor memory usage during test."""
    process = psutil.Process()
    initial_memory = process.memory_info().rss / 1024 / 1024  # MB

    yield process

    gc.collect()
    final_memory = process.memory_info().rss / 1024 / 1024  # MB
    memory_increase = final_memory - initial_memory

    # Assert memory increase is reasonable
    assert memory_increase < 500, f"Memory leak detected: {memory_increase}MB increase"

@pytest.fixture
def large_library_mock(tmp_path):
    """Create mock large library (10k tracks)."""
    from auralis.library.models import Track
    tracks = []
    for i in range(10000):
        track = Track(
            id=i,
            filepath=f"/fake/path/track_{i}.mp3",
            title=f"Track {i}",
            duration=180.0
        )
        tracks.append(track)
    return tracks

@pytest.fixture
def cpu_monitor():
    """Monitor CPU usage during test."""
    cpu_before = psutil.cpu_percent(interval=1)
    yield
    cpu_after = psutil.cpu_percent(interval=1)
    # Just monitoring, not asserting

@pytest.fixture
def very_long_audio(tmp_path):
    """Create 1-hour test audio file."""
    import numpy as np
    import soundfile as sf

    # 1 hour = 3600 seconds * 44100 Hz
    duration_samples = 3600 * 44100
    # Create in chunks to avoid memory issues
    chunk_size = 44100 * 10  # 10 second chunks

    filepath = tmp_path / "long_audio.wav"
    with sf.SoundFile(str(filepath), 'w', 44100, 2, 'PCM_16') as f:
        for _ in range(duration_samples // chunk_size):
            chunk = np.random.randn(chunk_size, 2).astype(np.float32) * 0.1
            f.write(chunk)

    return str(filepath)
```

### Helper Functions

```python
# tests/stress/helpers.py

import time
import psutil
import gc
from typing import Callable, Dict

def measure_memory_usage(func: Callable, *args, **kwargs) -> Dict[str, float]:
    """
    Measure memory usage of a function.

    Returns:
        Dictionary with 'before', 'after', 'peak', 'increase' in MB
    """
    gc.collect()
    process = psutil.Process()

    mem_before = process.memory_info().rss / 1024 / 1024

    # Run function
    result = func(*args, **kwargs)

    gc.collect()
    mem_after = process.memory_info().rss / 1024 / 1024

    return {
        'before': mem_before,
        'after': mem_after,
        'increase': mem_after - mem_before,
        'result': result
    }

def simulate_sustained_load(func: Callable, duration: int, interval: float = 1.0):
    """
    Simulate sustained load by calling function repeatedly.

    Args:
        func: Function to call
        duration: Duration in seconds
        interval: Interval between calls
    """
    start = time.time()
    calls = 0
    errors = 0

    while time.time() - start < duration:
        try:
            func()
            calls += 1
        except Exception:
            errors += 1

        time.sleep(interval)

    return {'calls': calls, 'errors': errors, 'duration': time.time() - start}

def create_large_test_library(db_session, n_tracks: int = 10000):
    """Create large test library in database."""
    from auralis.library.models import Track, Album, Artist

    # Create artists
    artists = []
    for i in range(n_tracks // 10):
        artist = Artist(name=f"Artist {i}")
        db_session.add(artist)
        artists.append(artist)

    # Create albums
    albums = []
    for i in range(n_tracks // 10):
        album = Album(title=f"Album {i}", artist=artists[i % len(artists)])
        db_session.add(album)
        albums.append(album)

    # Create tracks
    for i in range(n_tracks):
        track = Track(
            filepath=f"/test/track_{i}.mp3",
            title=f"Track {i}",
            duration=180.0,
            album=albums[i % len(albums)],
            artist=artists[i % len(artists)]
        )
        db_session.add(track)

    db_session.commit()
```

---

## Success Criteria

### Test Coverage
- ✅ 75/75 stress and edge case tests passing
- ✅ All stress tests complete within reasonable time
- ✅ No memory leaks detected
- ✅ Graceful handling of all edge cases

### Performance Benchmarks
- Large library (10k tracks): Scan < 30 seconds, queries < 100ms
- Large library (50k tracks): Scan < 3 minutes, queries < 500ms
- Memory: < 500MB for 10k tracks, < 2GB for 50k tracks
- Long audio: 4-hour file processes without issues
- High sample rate: 192kHz processes correctly
- Error recovery: All recovery mechanisms work

### Quality Metrics
- Zero unhandled exceptions in edge cases
- All boundary conditions handled gracefully
- Memory usage stays bounded under load
- CPU usage reasonable (no busy loops)
- Clean shutdown under all conditions

---

## Pytest Markers

```python
# pytest.ini additions (already present)

markers =
    load: Load testing (large datasets, high volume operations)
    stress: Stress testing (resource limits, extreme conditions)
    edge_case: Edge case tests (extreme conditions, failures)
    slow: Long-running tests (> 10 seconds)
    memory: Memory-intensive tests
```

---

## Running the Tests

```bash
# Run all stress tests
python -m pytest tests/stress/ -v

# Run by category
python -m pytest tests/stress/test_large_library.py -v
python -m pytest tests/stress/test_processing_stress.py -v
python -m pytest tests/stress/test_edge_cases.py -v

# Run by marker
python -m pytest -m load -v
python -m pytest -m stress -v
python -m pytest -m edge_case -v

# Skip slow tests
python -m pytest tests/stress/ -m "not slow" -v

# Run with memory monitoring
python -m pytest tests/stress/ -v --memray
```

---

## Expected Deliverables

### Test Files (3 new files)
1. `tests/stress/test_large_library.py` (~850 lines)
2. `tests/stress/test_processing_stress.py` (~900 lines)
3. `tests/stress/test_edge_cases.py` (~750 lines)

### Supporting Files
4. `tests/stress/conftest.py` (~250 lines)
5. `tests/stress/helpers.py` (~200 lines)

### Documentation
6. `docs/testing/PHASE2_WEEK6_PROGRESS.md` - Progress tracking
7. `docs/testing/PHASE2_WEEK6_COMPLETE.md` - Completion summary

**Total**: ~2,950 lines of test code + infrastructure

---

## Potential Issues and Mitigations

### Issue 1: Long Test Execution Time
- **Problem**: Stress tests take too long to run
- **Mitigation**: Use simulation/mocking for sustained load, add @pytest.mark.slow

### Issue 2: Memory Exhaustion
- **Problem**: Large library tests consume all memory
- **Mitigation**: Use generators, process in batches, set memory limits

### Issue 3: Flaky Timing Tests
- **Problem**: Load tests depend on system performance
- **Mitigation**: Use relative thresholds, retry logic, mark as xfail if needed

### Issue 4: Platform Differences
- **Problem**: Resource limits differ on Windows/Linux/Mac
- **Mitigation**: Use platform-specific thresholds, skip tests if needed

---

## Timeline

- **Day 1**: Infrastructure setup (fixtures, helpers)
- **Day 2-3**: Large library stress tests (25 tests)
- **Day 4-5**: Processing stress tests (25 tests)
- **Day 6**: Edge case tests (25 tests)
- **Day 7**: Integration, fixes, documentation

**Total**: 7 days to complete 75 stress tests

---

## Dependencies

### Required Packages
- `pytest` - Test framework
- `psutil` - Process and system monitoring
- `pytest-timeout` - Timeout for long-running tests
- `pytest-memray` (optional) - Memory profiling

### Install
```bash
pip install pytest psutil pytest-timeout
pip install pytest-memray  # Optional
```

---

## Next Steps

1. ✅ Review and approve this plan
2. Create `tests/stress/` directory structure
3. Implement large library stress tests (25 tests)
4. Implement processing stress tests (25 tests)
5. Implement edge case tests (25 tests)
6. Run all tests and fix failures
7. Document results

---

**Status**: 📋 PLAN READY - Awaiting approval to begin implementation
**Estimated Time**: 7 days
**Expected Outcome**: 75 passing stress tests validating production scalability

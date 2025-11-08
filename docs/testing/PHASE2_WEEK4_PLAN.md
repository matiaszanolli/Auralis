# Phase 2 Week 4: Performance Tests - Implementation Plan

**Date**: November 8, 2025
**Target**: 100 performance tests
**Goal**: Establish performance baselines and ensure system meets performance requirements

---

## Overview

**Performance testing** validates that the system meets speed, memory, and throughput requirements. Unlike functional tests that verify correctness, performance tests establish baselines and detect regressions.

**Key Insight**: Performance tests catch slowdowns before they reach production and help optimize critical paths.

**Performance Requirements** (from existing benchmarks):
- **Real-time factor**: >20x (process 1 hour in <3 minutes)
- **API response**: <100ms for typical queries
- **Memory usage**: <500MB for typical workloads
- **Library scanning**: >500 files/second

---

## Test Organization

### Directory Structure
```
tests/performance/
├── __init__.py
├── conftest.py                                    # Performance fixtures
├── test_audio_processing_performance.py           (25 tests)
├── test_library_operations_performance.py         (25 tests)
├── test_api_endpoint_performance.py               (25 tests)
└── test_memory_usage_performance.py               (25 tests)
```

---

## Category 1: Audio Processing Performance (25 tests)

**File**: `tests/performance/test_audio_processing_performance.py`

### Real-time Factor Tests (10 tests)

**Real-time factor** = audio_duration / processing_time (higher is better)

```python
@pytest.mark.performance
@pytest.mark.audio
def test_adaptive_processing_real_time_factor_short():
    """Short audio (10s) meets real-time factor target."""
    audio_10s = generate_audio(duration=10.0, sr=44100)

    start_time = time.time()
    processed = processor.process(audio_10s)
    elapsed = time.time() - start_time

    real_time_factor = 10.0 / elapsed
    assert real_time_factor > 20, f"RTF {real_time_factor:.1f}x < 20x target"

def test_adaptive_processing_real_time_factor_medium():
    """Medium audio (1 minute) meets real-time factor target."""
    audio_60s = generate_audio(duration=60.0, sr=44100)

    start_time = time.time()
    processed = processor.process(audio_60s)
    elapsed = time.time() - start_time

    real_time_factor = 60.0 / elapsed
    assert real_time_factor > 20, f"RTF {real_time_factor:.1f}x < 20x target"

def test_adaptive_processing_real_time_factor_long():
    """Long audio (5 minutes) meets real-time factor target."""
    audio_300s = generate_audio(duration=300.0, sr=44100)

    start_time = time.time()
    processed = processor.process(audio_300s)
    elapsed = time.time() - start_time

    real_time_factor = 300.0 / elapsed
    assert real_time_factor > 20, f"RTF {real_time_factor:.1f}x < 20x target"
```

**Tests**:
1. Short audio (10s) real-time factor
2. Medium audio (1 minute) real-time factor
3. Long audio (5 minutes) real-time factor
4. Very long audio (30 minutes) real-time factor
5. Different sample rates (44.1kHz, 48kHz, 96kHz)
6. Stereo vs mono processing speed
7. Different presets performance comparison
8. Chunked processing overhead
9. Real-time processing latency
10. Batch processing throughput

### Component Performance Tests (10 tests)

**Component-level benchmarks** for DSP modules:

```python
@pytest.mark.performance
@pytest.mark.dsp
def test_psychoacoustic_eq_performance():
    """EQ processing meets performance target."""
    audio_60s = generate_audio(duration=60.0, sr=44100)
    eq = PsychoacousticEQ()

    start_time = time.time()
    processed = eq.process(audio_60s, sr=44100)
    elapsed = time.time() - start_time

    # Target: >70x real-time
    real_time_factor = 60.0 / elapsed
    assert real_time_factor > 70, f"EQ RTF {real_time_factor:.1f}x < 70x target"

def test_adaptive_compressor_performance():
    """Compressor processing meets performance target."""
    audio_60s = generate_audio(duration=60.0, sr=44100)
    compressor = AdaptiveCompressor()

    start_time = time.time()
    processed = compressor.process(audio_60s, sr=44100)
    elapsed = time.time() - start_time

    # Target: >150x real-time
    real_time_factor = 60.0 / elapsed
    assert real_time_factor > 150, f"Compressor RTF {real_time_factor:.1f}x < 150x"
```

**Tests**:
1. Psychoacoustic EQ performance
2. Adaptive compressor performance
3. Adaptive limiter performance
4. Spectrum analyzer performance
5. Loudness meter performance
6. Content analyzer performance
7. Fingerprint analyzer performance
8. FFT performance (various window sizes)
9. Resampling performance
10. Format conversion performance

### Memory Efficiency Tests (5 tests)

```python
@pytest.mark.performance
@pytest.mark.memory
def test_processing_memory_usage():
    """Audio processing stays within memory budget."""
    import psutil
    import os

    process = psutil.Process(os.getpid())
    baseline_memory = process.memory_info().rss / 1024 / 1024  # MB

    # Process 5 minutes of audio
    audio_300s = generate_audio(duration=300.0, sr=44100)
    processed = processor.process(audio_300s)

    peak_memory = process.memory_info().rss / 1024 / 1024  # MB
    memory_used = peak_memory - baseline_memory

    # Target: <500MB for 5 minutes of audio
    assert memory_used < 500, f"Memory usage {memory_used:.1f}MB exceeds 500MB"
```

**Tests**:
1. Processing memory usage (5 minutes audio)
2. Memory usage scales linearly with duration
3. Memory released after processing
4. Chunked processing memory efficiency
5. No memory leaks over multiple iterations

---

## Category 2: Library Operations Performance (25 tests)

**File**: `tests/performance/test_library_operations_performance.py`

### Scanning Performance (10 tests)

```python
@pytest.mark.performance
@pytest.mark.library
def test_folder_scanning_speed():
    """Folder scanning meets throughput target."""
    # Create test library with 1000 files
    test_dir = create_test_library(num_files=1000)

    start_time = time.time()
    result = library_manager.scan_folder(str(test_dir))
    elapsed = time.time() - start_time

    files_per_second = 1000 / elapsed
    # Target: >500 files/second
    assert files_per_second > 500, f"Scanning {files_per_second:.0f} files/s < 500 files/s target"

def test_large_library_scanning():
    """Large library (10k+ files) scans within timeout."""
    test_dir = create_test_library(num_files=10000)

    start_time = time.time()
    result = library_manager.scan_folder(str(test_dir))
    elapsed = time.time() - start_time

    # Target: Complete in <30 seconds
    assert elapsed < 30, f"Scanning 10k files took {elapsed:.1f}s > 30s timeout"
```

**Tests**:
1. Folder scanning speed (1k files)
2. Large library scanning (10k files)
3. Incremental scan performance
4. Duplicate detection speed
5. Metadata extraction speed
6. Album artwork extraction
7. Multiple format handling
8. Nested folder scanning
9. Network drive scanning (if applicable)
10. Concurrent scanning performance

### Query Performance (10 tests)

```python
@pytest.mark.performance
@pytest.mark.library
def test_track_query_performance():
    """Track queries complete within latency target."""
    # Populate library with 10k tracks
    populate_library(num_tracks=10000)

    start_time = time.time()
    result = library_manager.get_tracks(limit=50, offset=0)
    elapsed = time.time() - start_time

    # Target: <10ms for typical query
    elapsed_ms = elapsed * 1000
    assert elapsed_ms < 10, f"Query took {elapsed_ms:.1f}ms > 10ms target"

def test_search_query_performance():
    """Search queries complete within latency target."""
    populate_library(num_tracks=10000)

    start_time = time.time()
    result = library_manager.search_tracks("test")
    elapsed = time.time() - start_time

    # Target: <50ms for search
    elapsed_ms = elapsed * 1000
    assert elapsed_ms < 50, f"Search took {elapsed_ms:.1f}ms > 50ms target"
```

**Tests**:
1. Track query performance (10k library)
2. Search query performance
3. Album query performance
4. Artist query performance
5. Playlist query performance
6. Sorting performance (various fields)
7. Filtering performance (various criteria)
8. Pagination performance
9. Cache hit performance
10. Cache miss performance

### Database Performance (5 tests)

```python
@pytest.mark.performance
@pytest.mark.database
def test_bulk_insert_performance():
    """Bulk inserts meet throughput target."""
    tracks = [create_test_track_data() for _ in range(1000)]

    start_time = time.time()
    for track in tracks:
        library_manager.add_track(track)
    elapsed = time.time() - start_time

    tracks_per_second = 1000 / elapsed
    # Target: >200 tracks/second
    assert tracks_per_second > 200, f"Inserts {tracks_per_second:.0f} tracks/s < 200/s"
```

**Tests**:
1. Bulk insert performance (1k tracks)
2. Bulk update performance
3. Bulk delete performance
4. Index performance on large tables
5. Transaction performance

---

## Category 3: API Endpoint Performance (25 tests)

**File**: `tests/performance/test_api_endpoint_performance.py`

### Player API Performance (10 tests)

```python
@pytest.mark.performance
@pytest.mark.api
@pytest.mark.asyncio
async def test_play_track_latency(test_client):
    """Play track endpoint meets latency target."""
    # Add test track
    track = create_test_track()

    start_time = time.time()
    response = await test_client.post("/api/player/play", json={"track_id": track.id})
    elapsed = time.time() - start_time

    # Target: <100ms
    elapsed_ms = elapsed * 1000
    assert elapsed_ms < 100, f"Play latency {elapsed_ms:.1f}ms > 100ms target"
    assert response.status_code == 200

@pytest.mark.performance
@pytest.mark.api
@pytest.mark.asyncio
async def test_queue_operations_latency(test_client):
    """Queue operations meet latency target."""
    track = create_test_track()

    start_time = time.time()
    response = await test_client.post("/api/player/queue", json={"track_id": track.id})
    elapsed = time.time() - start_time

    elapsed_ms = elapsed * 1000
    assert elapsed_ms < 50, f"Queue operation {elapsed_ms:.1f}ms > 50ms target"
```

**Tests**:
1. Play track latency
2. Pause/resume latency
3. Seek latency
4. Queue operations latency
5. Volume change latency
6. Next/previous track latency
7. Shuffle/repeat toggle latency
8. Player state query latency
9. Current track query latency
10. Queue list query latency

### Library API Performance (10 tests)

```python
@pytest.mark.performance
@pytest.mark.api
@pytest.mark.asyncio
async def test_library_tracks_latency(test_client):
    """Library tracks endpoint meets latency target."""
    # Populate with 10k tracks
    populate_library(num_tracks=10000)

    start_time = time.time()
    response = await test_client.get("/api/library/tracks?limit=50&offset=0")
    elapsed = time.time() - start_time

    elapsed_ms = elapsed * 1000
    assert elapsed_ms < 100, f"Library query {elapsed_ms:.1f}ms > 100ms target"
    assert response.status_code == 200
```

**Tests**:
1. Library tracks query latency
2. Search query latency
3. Albums query latency
4. Artists query latency
5. Playlists query latency
6. Metadata update latency
7. Favorite toggle latency
8. Batch operations latency
9. Artwork retrieval latency
10. Cache statistics query latency

### Streaming API Performance (5 tests)

```python
@pytest.mark.performance
@pytest.mark.api
@pytest.mark.asyncio
async def test_chunk_streaming_latency(test_client):
    """Chunk streaming meets latency target."""
    track = create_test_track()

    start_time = time.time()
    response = await test_client.get(f"/api/streaming/chunk/{track.id}/0")
    elapsed = time.time() - start_time

    elapsed_ms = elapsed * 1000
    # Target: <200ms for first chunk
    assert elapsed_ms < 200, f"First chunk {elapsed_ms:.1f}ms > 200ms target"
```

**Tests**:
1. First chunk latency
2. Subsequent chunk latency
3. Chunk generation throughput
4. Preset switching latency
5. Concurrent streaming performance

---

## Category 4: Memory Usage Performance (25 tests)

**File**: `tests/performance/test_memory_usage_performance.py`

### Memory Baseline Tests (10 tests)

```python
@pytest.mark.performance
@pytest.mark.memory
def test_idle_memory_usage():
    """Idle memory usage is reasonable."""
    import psutil
    import os

    process = psutil.Process(os.getpid())
    idle_memory = process.memory_info().rss / 1024 / 1024  # MB

    # Target: <100MB idle
    assert idle_memory < 100, f"Idle memory {idle_memory:.1f}MB > 100MB"

def test_library_load_memory():
    """Loading large library stays within memory budget."""
    import psutil
    import os

    process = psutil.Process(os.getpid())
    baseline = process.memory_info().rss / 1024 / 1024

    # Load 10k track library
    populate_library(num_tracks=10000)

    loaded = process.memory_info().rss / 1024 / 1024
    memory_increase = loaded - baseline

    # Target: <50MB for 10k tracks
    assert memory_increase < 50, f"Library memory {memory_increase:.1f}MB > 50MB"
```

**Tests**:
1. Idle memory usage
2. Library load memory (10k tracks)
3. Player memory usage
4. Processing memory usage
5. Cache memory usage
6. Artwork cache memory
7. Metadata memory usage
8. Queue memory usage
9. Playlist memory usage
10. WebSocket connection memory

### Memory Leak Tests (10 tests)

```python
@pytest.mark.performance
@pytest.mark.memory
def test_no_memory_leak_processing():
    """Repeated processing doesn't leak memory."""
    import psutil
    import os
    import gc

    process = psutil.Process(os.getpid())

    # Baseline
    gc.collect()
    baseline = process.memory_info().rss / 1024 / 1024

    # Process 100 times
    audio = generate_audio(duration=10.0, sr=44100)
    for _ in range(100):
        processed = processor.process(audio)
        del processed

    # Check final memory
    gc.collect()
    final = process.memory_info().rss / 1024 / 1024
    memory_growth = final - baseline

    # Target: <10MB growth for 100 iterations
    assert memory_growth < 10, f"Memory leak detected: {memory_growth:.1f}MB growth"
```

**Tests**:
1. No leak in audio processing (100 iterations)
2. No leak in library queries (1000 queries)
3. No leak in player operations (1000 operations)
4. No leak in chunk streaming (100 chunks)
5. No leak in cache operations (1000 cache hits/misses)
6. No leak in metadata updates (1000 updates)
7. No leak in search operations (1000 searches)
8. No leak in WebSocket connections (100 connections)
9. No leak in artwork loading (100 images)
10. No leak in format conversions (100 conversions)

### Memory Peak Tests (5 tests)

```python
@pytest.mark.performance
@pytest.mark.memory
def test_concurrent_processing_memory_peak():
    """Concurrent processing peak memory is reasonable."""
    import psutil
    import os
    import threading

    process = psutil.Process(os.getpid())
    baseline = process.memory_info().rss / 1024 / 1024

    # Process 4 tracks concurrently
    def process_track():
        audio = generate_audio(duration=60.0, sr=44100)
        processed = processor.process(audio)

    threads = [threading.Thread(target=process_track) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    peak = process.memory_info().rss / 1024 / 1024
    peak_increase = peak - baseline

    # Target: <1GB for 4 concurrent 1-minute tracks
    assert peak_increase < 1024, f"Peak memory {peak_increase:.1f}MB > 1GB"
```

**Tests**:
1. Concurrent processing peak memory
2. Large file processing peak memory
3. Library scanning peak memory
4. Batch operations peak memory
5. Streaming peak memory

---

## Performance Test Utilities

### Fixtures (conftest.py)

```python
import pytest
import time
import psutil
import os
from typing import Callable

@pytest.fixture
def measure_time():
    """Measure execution time."""
    def _measure(func: Callable, *args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start
        return result, elapsed
    return _measure

@pytest.fixture
def measure_memory():
    """Measure memory usage."""
    process = psutil.Process(os.getpid())

    def _measure(func: Callable, *args, **kwargs):
        import gc
        gc.collect()
        baseline = process.memory_info().rss / 1024 / 1024  # MB

        result = func(*args, **kwargs)

        gc.collect()
        final = process.memory_info().rss / 1024 / 1024  # MB
        memory_used = final - baseline

        return result, memory_used
    return _measure

@pytest.fixture
def performance_logger(tmp_path):
    """Log performance metrics."""
    import json
    log_file = tmp_path / "performance.json"
    metrics = []

    def _log(test_name: str, metric: str, value: float, unit: str):
        metrics.append({
            "test": test_name,
            "metric": metric,
            "value": value,
            "unit": unit,
            "timestamp": time.time()
        })

    yield _log

    # Write metrics to file
    with open(log_file, "w") as f:
        json.dump(metrics, f, indent=2)

@pytest.fixture
def generate_audio():
    """Generate test audio."""
    import numpy as np
    def _generate(duration: float = 10.0, sr: int = 44100):
        samples = int(duration * sr)
        # Generate white noise
        audio = np.random.randn(samples) * 0.1
        return audio
    return _generate
```

---

## Success Criteria

- [ ] 100 performance tests created
- [ ] All tests passing
- [ ] Performance baselines established
- [ ] Test markers applied (`@pytest.mark.performance`, `@pytest.mark.memory`)
- [ ] Documentation complete

---

## Expected Impact

**Performance tests prevent**:
1. ✅ Slowdowns in audio processing (real-time factor regression)
2. ✅ API latency increases
3. ✅ Memory leaks
4. ✅ Library scanning slowdowns
5. ✅ Query performance degradation
6. ✅ Concurrent processing issues
7. ✅ Memory growth over time
8. ✅ Resource exhaustion

**Performance baselines enable**:
- Detecting regressions in CI/CD
- Optimizing critical paths
- Capacity planning
- Performance comparison across versions

---

## Implementation Order

### Day 1: Audio Processing Performance (25 tests)
- Real-time factor tests
- Component performance tests
- Memory efficiency tests

### Day 2: Library Operations Performance (25 tests)
- Scanning performance
- Query performance
- Database performance

### Day 3: API Endpoint Performance (25 tests)
- Player API
- Library API
- Streaming API

### Day 4: Memory Usage Performance (25 tests)
- Memory baselines
- Memory leak detection
- Peak memory tests

### Day 5: Documentation and Reporting
- Complete performance report
- Establish baselines
- Document findings

---

**Ready to start with Category 1: Audio Processing Performance?**

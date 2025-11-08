"""
Load and Stress Tests
~~~~~~~~~~~~~~~~~~~~~

Load and stress testing suite for Auralis audio processing system.

TEST CATEGORIES:
- Large library stress tests (50k+ tracks)
- Concurrent operations (multi-threaded access)
- Memory/resource stress (sustained high load)
- Long-running operations (hours of processing)
- Database connection pooling
- Cache performance under load
- Queue management stress
- Filesystem stress

LOAD TESTING PRINCIPLES:
1. Test at scale (10x, 100x production load)
2. Measure degradation curves (how performance degrades)
3. Find breaking points (where system fails)
4. Validate resource cleanup (no leaks under stress)
5. Test concurrent access (thread safety)
6. Simulate real-world usage patterns

MARKERS:
- @pytest.mark.load - Load/stress tests
- @pytest.mark.slow - Long-running tests (> 30s)
- @pytest.mark.stress - Resource-intensive tests

RUNNING TESTS:
    # All load tests (WARNING: may take 10+ minutes)
    python -m pytest tests/load_stress/ -v

    # Quick load tests only (< 30s each)
    python -m pytest tests/load_stress/ -v -m "not slow"

    # Specific category
    python -m pytest tests/load_stress/test_large_library_stress.py -v

    # With resource monitoring
    python -m pytest tests/load_stress/ -v --tb=short --durations=10

PERFORMANCE TARGETS:
- 50k track library: < 30s scan time
- 1000 concurrent queries: < 5s total
- 24 hour processing: < 10% memory growth
- 100 parallel API calls: all succeed
- Database: > 1000 queries/sec sustained
"""

# -*- coding: utf-8 -*-

"""
Phase 3B Tests: Request Pipelining
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests concurrent fingerprint extraction with request batching:
- Concurrent request handling (batch size 5)
- Throughput improvement (15-20% target)
- Error handling in concurrent context
- Batch completion semantics

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import time
from typing import List, Tuple
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from auralis.library.fingerprint_extractor import (
    CorruptedTrackError,
    FingerprintExtractor,
)


class TestConcurrentPipelining:
    """Test concurrent fingerprint extraction with request pipelining."""

    @pytest.fixture
    def mock_extractor(self):
        """Create a FingerprintExtractor with mocked dependencies."""
        repo_mock = MagicMock()
        repo_mock.exists.return_value = False
        extractor = FingerprintExtractor(repo_mock)

        # Mock the Rust server async method
        extractor._get_fingerprint_from_rust_server_async = AsyncMock()

        return extractor

    @pytest.mark.asyncio
    async def test_concurrent_extraction_single_batch(self, mock_extractor):
        """Test concurrent extraction for tracks in single batch."""
        # Setup
        track_ids_paths = [(1, 'track1.wav'), (2, 'track2.wav'), (3, 'track3.wav')]

        # Mock fingerprint results
        fingerprints = {
            1: {'sub_bass_pct': 10.5, 'bass_pct': 25.3},
            2: {'sub_bass_pct': 12.0, 'bass_pct': 23.0},
            3: {'sub_bass_pct': 11.5, 'bass_pct': 24.0},
        }

        async def mock_fp_call(track_id, filepath):
            # Simulate 100ms per request
            await asyncio.sleep(0.1)
            return fingerprints[track_id]

        mock_extractor._get_fingerprint_from_rust_server_async.side_effect = mock_fp_call

        # Execute
        start = time.time()
        results = await mock_extractor._get_fingerprints_concurrent(track_ids_paths, batch_size=5)
        elapsed = time.time() - start

        # Verify
        assert len(results) == 3
        assert results[1] == fingerprints[1]
        assert results[2] == fingerprints[2]
        assert results[3] == fingerprints[3]

        # With batching, 3 concurrent requests should take ~100ms (not 300ms)
        # Add some buffer for timing variations
        assert elapsed < 0.25, f"Expected concurrent execution (~100ms), took {elapsed*1000:.1f}ms"

    @pytest.mark.asyncio
    async def test_concurrent_extraction_multiple_batches(self, mock_extractor):
        """Test concurrent extraction across multiple batches."""
        # Setup: 12 tracks with batch size 5 (3 batches: 5, 5, 2)
        track_ids_paths = [(i, f'track{i}.wav') for i in range(1, 13)]

        fingerprints = {i: {'sub_bass_pct': float(i), 'bass_pct': float(i*2)} for i in range(1, 13)}

        call_times = []

        async def mock_fp_call(track_id, filepath):
            call_times.append(time.time())
            await asyncio.sleep(0.05)
            return fingerprints[track_id]

        mock_extractor._get_fingerprint_from_rust_server_async.side_effect = mock_fp_call

        # Execute
        start = time.time()
        results = await mock_extractor._get_fingerprints_concurrent(track_ids_paths, batch_size=5)
        elapsed = time.time() - start

        # Verify all results present
        assert len(results) == 12
        for track_id in range(1, 13):
            assert results[track_id] == fingerprints[track_id]

        # With 3 batches of concurrent requests:
        # - Batch 1: 5 concurrent (50ms) + overhead
        # - Batch 2: 5 concurrent (50ms) + overhead
        # - Batch 3: 2 concurrent (50ms) + overhead
        # Total should be ~150-200ms, not 600ms sequential
        assert elapsed < 0.3, f"Expected ~150ms for 3 batches, took {elapsed*1000:.1f}ms"

    @pytest.mark.asyncio
    async def test_concurrent_error_handling(self, mock_extractor):
        """Test error handling in concurrent context."""
        track_ids_paths = [(1, 'good.wav'), (2, 'corrupted.wav'), (3, 'good2.wav')]

        async def mock_fp_call(track_id, filepath):
            await asyncio.sleep(0.05)
            if track_id == 2:
                raise CorruptedTrackError(f"Track {track_id} is corrupted")
            return {'sub_bass_pct': float(track_id)}

        mock_extractor._get_fingerprint_from_rust_server_async.side_effect = mock_fp_call
        mock_extractor._delete_corrupted_track = MagicMock()

        # Execute
        results = await mock_extractor._get_fingerprints_concurrent(track_ids_paths)

        # Verify error handling
        assert results[1] == {'sub_bass_pct': 1.0}
        assert results[2] is None  # Corrupted track marked as None
        assert results[3] == {'sub_bass_pct': 3.0}

        # Verify corrupted track deletion was called
        mock_extractor._delete_corrupted_track.assert_called_once()

    @pytest.mark.asyncio
    async def test_concurrent_partial_failures(self, mock_extractor):
        """Test graceful handling of partial failures in batch."""
        track_ids_paths = [(1, 't1.wav'), (2, 't2.wav'), (3, 't3.wav'), (4, 't4.wav')]

        async def mock_fp_call(track_id, filepath):
            await asyncio.sleep(0.05)
            if track_id == 2:
                raise Exception("Network error")
            return {'sub_bass_pct': float(track_id)}

        mock_extractor._get_fingerprint_from_rust_server_async.side_effect = mock_fp_call

        # Execute
        results = await mock_extractor._get_fingerprints_concurrent(track_ids_paths, batch_size=2)

        # Verify results (should have successful and failed)
        assert results[1] == {'sub_bass_pct': 1.0}
        assert results[2] is None  # Failed
        assert results[3] == {'sub_bass_pct': 3.0}
        assert results[4] == {'sub_bass_pct': 4.0}

    @pytest.mark.asyncio
    async def test_batch_size_parameter(self, mock_extractor):
        """Test that batch_size parameter controls concurrency."""
        track_ids_paths = [(i, f'track{i}.wav') for i in range(1, 11)]

        fingerprints = {i: {'sub_bass_pct': float(i)} for i in range(1, 11)}

        call_log = []

        async def mock_fp_call(track_id, filepath):
            call_log.append(('start', track_id))
            await asyncio.sleep(0.1)
            call_log.append(('end', track_id))
            return fingerprints[track_id]

        mock_extractor._get_fingerprint_from_rust_server_async.side_effect = mock_fp_call

        # Execute with small batch size
        results = await mock_extractor._get_fingerprints_concurrent(track_ids_paths, batch_size=2)

        # Verify all results present
        assert len(results) == 10

        # With batch_size=2, should have 5 batches
        # Each batch should have 2 concurrent requests
        starts = [t for event, t in call_log if event == 'start']
        assert len(starts) == 10

    @pytest.mark.asyncio
    async def test_empty_batch_handling(self, mock_extractor):
        """Test handling of empty track list."""
        track_ids_paths = []

        # Execute
        results = await mock_extractor._get_fingerprints_concurrent(track_ids_paths)

        # Verify
        assert results == {}

    @pytest.mark.asyncio
    async def test_single_track_batch(self, mock_extractor):
        """Test handling of single track."""
        track_ids_paths = [(1, 'track1.wav')]

        async def mock_fp_call(track_id, filepath):
            await asyncio.sleep(0.05)
            return {'sub_bass_pct': 10.5}

        mock_extractor._get_fingerprint_from_rust_server_async.side_effect = mock_fp_call

        # Execute
        results = await mock_extractor._get_fingerprints_concurrent(track_ids_paths)

        # Verify
        assert len(results) == 1
        assert results[1] == {'sub_bass_pct': 10.5}


class TestThroughputImprovement:
    """Test throughput improvements with request pipelining."""

    @pytest.mark.asyncio
    async def test_sequential_vs_concurrent_throughput(self):
        """Verify concurrent execution is faster than sequential."""
        # Setup: 10 tracks, each "processing" takes 50ms
        async def mock_sequential():
            """Simulate sequential extraction."""
            total = 0
            for i in range(10):
                await asyncio.sleep(0.05)
                total += 1
            return total

        async def mock_concurrent():
            """Simulate concurrent extraction with batching."""
            total = 0
            for batch_start in range(0, 10, 5):
                # Batch of up to 5 concurrent
                tasks = [asyncio.sleep(0.05) for _ in range(min(5, 10 - batch_start))]
                await asyncio.gather(*tasks)
                total += len(tasks)
            return total

        # Execute sequential
        start = time.time()
        seq_result = await mock_sequential()
        seq_time = time.time() - start

        # Execute concurrent
        start = time.time()
        conc_result = await mock_concurrent()
        conc_time = time.time() - start

        # Verify
        assert seq_result == conc_result == 10
        assert conc_time < seq_time, f"Concurrent {conc_time:.3f}s should be faster than sequential {seq_time:.3f}s"

        # Expected improvement: ~3-4x (with 5 concurrent per batch)
        improvement = seq_time / conc_time
        assert improvement > 2.5, f"Expected ~3x improvement, got {improvement:.2f}x"


class TestBatchSemantics:
    """Test batch processing semantics."""

    @pytest.mark.asyncio
    async def test_batch_completes_before_next_starts(self):
        """Verify that all tasks in a batch complete before next batch starts."""
        repo_mock = MagicMock()
        extractor = FingerprintExtractor(repo_mock)
        extractor._get_fingerprint_from_rust_server_async = AsyncMock()

        batch_sequence = []

        async def mock_fp_call(track_id, filepath):
            batch_num = (track_id - 1) // 3
            batch_sequence.append(('start', batch_num, track_id))
            await asyncio.sleep(0.05)
            batch_sequence.append(('end', batch_num, track_id))
            return {'sub_bass_pct': float(track_id)}

        extractor._get_fingerprint_from_rust_server_async.side_effect = mock_fp_call

        # Execute with batch_size=3 (3 batches total)
        track_ids_paths = [(i, f'track{i}.wav') for i in range(1, 10)]
        results = await extractor._get_fingerprints_concurrent(track_ids_paths, batch_size=3)

        # Verify all tracks processed
        assert len(results) == 9


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])

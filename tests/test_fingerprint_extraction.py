# -*- coding: utf-8 -*-

"""
Tests for Fingerprint Extraction System

Tests the 25D fingerprint extraction pipeline, including:
- FingerprintExtractor: Synchronous extraction with sidecar caching
- FingerprintExtractionQueue: Async queue with worker threads
- Database integration and status tracking
- Batch processing during library scan

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import asyncio
import json
import tempfile
from pathlib import Path
from typing import Dict

import numpy as np
import pytest

# Fixtures for fingerprint testing

@pytest.fixture
def sample_audio():
    """Generate sample audio for fingerprint testing (3 seconds, 44.1kHz)"""
    duration = 3.0
    sample_rate = 44100
    samples = int(duration * sample_rate)

    # Complex audio with multiple frequency components
    t = np.linspace(0, duration, samples, False)

    # Mix of bass, mid, and treble frequencies
    bass = np.sin(2 * np.pi * 60 * t) * 0.3          # 60 Hz bass
    mid = np.sin(2 * np.pi * 440 * t) * 0.4          # 440 Hz middle
    treble = np.sin(2 * np.pi * 4000 * t) * 0.2      # 4kHz treble

    audio = (bass + mid + treble) * 0.5
    audio = audio.astype(np.float32)

    return audio, sample_rate


@pytest.fixture
def fingerprint_repository_mock():
    """Mock fingerprint repository for testing"""
    class MockFingerprintRepository:
        def __init__(self):
            self.fingerprints = {}

        def upsert(self, track_id: int, fingerprint: Dict) -> bool:
            """Store fingerprint"""
            self.fingerprints[track_id] = fingerprint
            return True

        def exists(self, track_id: int) -> bool:
            """Check if fingerprint exists"""
            return track_id in self.fingerprints

        def get_by_track_id(self, track_id: int):
            """Get fingerprint by track ID"""
            if track_id in self.fingerprints:
                class MockFingerprint:
                    def __init__(self, data):
                        self.data = data
                    def to_dict(self):
                        return self.data
                return MockFingerprint(self.fingerprints[track_id])
            return None

        def get_missing_fingerprints(self, limit=None):
            """Get tracks missing fingerprints"""
            return []  # Mock implementation

    return MockFingerprintRepository()


@pytest.fixture
def library_manager_mock():
    """Mock library manager for testing"""
    class MockLibraryManager:
        def __init__(self):
            self.tracks = {}

        def get_track_by_filepath(self, filepath: str):
            """Get track by filepath"""
            if filepath in self.tracks:
                return self.tracks[filepath]
            return None

        def add_track(self, track_info):
            """Add track to library"""
            class MockTrack:
                def __init__(self, filepath, track_id=1):
                    self.id = track_id
                    self.filepath = filepath
                    self.fingerprint_status = 'pending'

            track = MockTrack(track_info.get('filepath', ''))
            self.tracks[track_info.get('filepath', '')] = track
            return track

    return MockLibraryManager()


@pytest.fixture
def fingerprint_extractor_mock():
    """Mock fingerprint extractor"""
    class MockFingerprintExtractor:
        def extract_and_store(self, track_id: int, filepath: str) -> bool:
            """Simulate fingerprint extraction"""
            return True

        def extract_batch(self, track_ids_paths, max_failures=10):
            """Simulate batch extraction"""
            return {
                'success': len(track_ids_paths),
                'failed': 0,
                'skipped': 0,
                'cached': 0
            }

    return MockFingerprintExtractor()


# Tests for fingerprint data structure

class TestFingerprintJob:
    """Tests for FingerprintJob dataclass"""

    def test_fingerprint_job_creation(self):
        """Test basic job creation"""
        from auralis.services.fingerprint_queue import FingerprintJob

        job = FingerprintJob(
            track_id=123,
            filepath='/path/to/audio.mp3',
            priority=1
        )

        assert job.track_id == 123
        assert job.filepath == '/path/to/audio.mp3'
        assert job.priority == 1
        assert job.retry_count == 0
        assert job.max_retries == 3

    def test_fingerprint_job_priority_ordering(self):
        """Test job priority queue ordering"""
        from auralis.services.fingerprint_queue import FingerprintJob

        job1 = FingerprintJob(track_id=1, filepath='file1.mp3', priority=0)
        job2 = FingerprintJob(track_id=2, filepath='file2.mp3', priority=2)
        job3 = FingerprintJob(track_id=3, filepath='file3.mp3', priority=1)

        # Test __lt__ ordering
        assert job2 < job3  # priority 2 > priority 1
        assert job3 < job1  # priority 1 > priority 0
        assert not (job1 < job2)


# Tests for FingerprintExtractionQueue

class TestFingerprintExtractionQueue:
    """Tests for async fingerprint extraction queue"""

    @pytest.mark.asyncio
    async def test_queue_initialization(self, fingerprint_extractor_mock, library_manager_mock):
        """Test queue initialization"""
        from auralis.services.fingerprint_queue import FingerprintExtractionQueue

        queue = FingerprintExtractionQueue(
            fingerprint_extractor=fingerprint_extractor_mock,
            library_manager=library_manager_mock,
            num_workers=4,
            max_queue_size=100
        )

        assert queue.num_workers == 4
        assert queue.max_queue_size == 100
        assert queue.get_queue_size() == 0
        assert queue.should_stop == False  # Initially not stopped

    @pytest.mark.asyncio
    async def test_enqueue_single_job(self, fingerprint_extractor_mock, library_manager_mock):
        """Test enqueueing a single job"""
        from auralis.services.fingerprint_queue import FingerprintExtractionQueue

        queue = FingerprintExtractionQueue(
            fingerprint_extractor=fingerprint_extractor_mock,
            library_manager=library_manager_mock,
            num_workers=1
        )

        success = await queue.enqueue(
            track_id=123,
            filepath='/path/to/audio.mp3',
            priority=0
        )

        assert success is True
        assert queue.get_queue_size() == 1
        assert queue.get_stats()['queued'] == 1

    @pytest.mark.asyncio
    async def test_enqueue_batch(self, fingerprint_extractor_mock, library_manager_mock):
        """Test batch enqueuing"""
        from auralis.services.fingerprint_queue import FingerprintExtractionQueue

        queue = FingerprintExtractionQueue(
            fingerprint_extractor=fingerprint_extractor_mock,
            library_manager=library_manager_mock,
            num_workers=2
        )

        tracks = [
            (1, '/path/audio1.mp3'),
            (2, '/path/audio2.mp3'),
            (3, '/path/audio3.mp3'),
        ]

        enqueued = await queue.enqueue_batch(tracks, priority=0)

        assert enqueued == 3
        assert queue.get_queue_size() == 3
        assert queue.get_stats()['queued'] == 3

    @pytest.mark.asyncio
    async def test_queue_statistics(self, fingerprint_extractor_mock, library_manager_mock):
        """Test queue statistics tracking"""
        from auralis.services.fingerprint_queue import FingerprintExtractionQueue

        queue = FingerprintExtractionQueue(
            fingerprint_extractor=fingerprint_extractor_mock,
            library_manager=library_manager_mock
        )

        # Enqueue some jobs
        await queue.enqueue(1, '/path/file1.mp3')
        await queue.enqueue(2, '/path/file2.mp3')

        stats = queue.get_stats()

        assert stats['queued'] == 2
        assert stats['processing'] == 0
        assert stats['completed'] == 0
        assert stats['failed'] == 0


# Tests for FingerprintQueueManager

class TestFingerprintQueueManager:
    """Tests for fingerprint queue manager lifecycle"""

    @pytest.mark.asyncio
    async def test_manager_initialization(self, fingerprint_extractor_mock, library_manager_mock):
        """Test queue manager initialization"""
        from auralis.services.fingerprint_queue import FingerprintQueueManager

        manager = FingerprintQueueManager(
            fingerprint_extractor=fingerprint_extractor_mock,
            library_manager=library_manager_mock,
            num_workers=4
        )

        assert not manager.is_running
        assert manager.queue is not None

    @pytest.mark.asyncio
    async def test_manager_startup_shutdown(self, fingerprint_extractor_mock, library_manager_mock):
        """Test manager startup and shutdown"""
        from auralis.services.fingerprint_queue import FingerprintQueueManager

        manager = FingerprintQueueManager(
            fingerprint_extractor=fingerprint_extractor_mock,
            library_manager=library_manager_mock,
            num_workers=2
        )

        # Test startup
        await manager.initialize()
        assert manager.is_running

        # Test shutdown
        success = await manager.shutdown(timeout=5.0)
        assert success
        assert not manager.is_running


# Tests for integration with library scanner

class TestScannerFingerprinterIntegration:
    """Tests for scanner-fingerprinter integration"""

    def test_scanner_accepts_fingerprint_queue(self, library_manager_mock):
        """Test that scanner accepts optional fingerprint queue"""
        from auralis.services.fingerprint_extractor import FingerprintExtractor
        from auralis.services.fingerprint_queue import FingerprintExtractionQueue
        from auralis.library.scanner import LibraryScanner

        # Create minimal queue
        extractor = type('MockExtractor', (), {'extract_and_store': lambda *a, **k: True})()
        queue = FingerprintExtractionQueue(
            fingerprint_extractor=extractor,
            library_manager=library_manager_mock
        )

        # Scanner should accept queue
        scanner = LibraryScanner(
            library_manager=library_manager_mock,
            fingerprint_queue=queue
        )

        assert scanner.fingerprint_queue is queue

    def test_scanner_works_without_fingerprint_queue(self, library_manager_mock):
        """Test that scanner works without fingerprint queue"""
        from auralis.library.scanner import LibraryScanner

        scanner = LibraryScanner(library_manager=library_manager_mock)

        assert scanner.fingerprint_queue is None


# Tests for database integration

class TestFingerprintDatabaseIntegration:
    """Tests for fingerprint database schema"""

    def test_track_model_has_fingerprint_columns(self):
        """Test that Track model has fingerprint columns"""
        from auralis.library.models.core import Track

        # Check column existence by inspecting table columns
        columns = [col.name for col in Track.__table__.columns]

        assert 'fingerprint_status' in columns
        assert 'fingerprint_computed_at' in columns
        assert 'fingerprint_error_message' in columns
        assert 'fingerprint_vector' in columns

    def test_track_fingerprint_status_default(self):
        """Test fingerprint status default value"""
        from auralis.library.models.core import Track

        # Check default value
        fingerprint_status_col = Track.__table__.columns['fingerprint_status']
        assert fingerprint_status_col.default.arg == 'pending'


# Tests for fingerprint data format

class TestFingerprintDataFormat:
    """Tests for 25D fingerprint data format"""

    def test_fingerprint_json_serialization(self):
        """Test fingerprint JSON serialization"""
        # Create a sample 25D fingerprint
        fingerprint = {
            # Frequency Distribution (7D)
            'sub_bass_pct': 0.15,
            'bass_pct': 0.25,
            'low_mid_pct': 0.18,
            'mid_pct': 0.22,
            'upper_mid_pct': 0.12,
            'presence_pct': 0.05,
            'air_pct': 0.03,
            # Dynamics (3D)
            'lufs': -12.5,
            'crest_db': 8.3,
            'bass_mid_ratio': 1.1,
            # Temporal (4D)
            'tempo_bpm': 120.0,
            'rhythm_stability': 0.92,
            'transient_density': 3.5,
            'silence_ratio': 0.02,
            # Spectral (3D)
            'spectral_centroid': 2800.0,
            'spectral_rolloff': 8000.0,
            'spectral_flatness': 0.45,
            # Harmonic (3D)
            'harmonic_ratio': 0.78,
            'pitch_stability': 0.85,
            'chroma_energy': 0.65,
            # Variation (3D)
            'dynamic_range_variation': 2.1,
            'loudness_variation_std': 1.3,
            'peak_consistency': 0.88,
            # Stereo (2D)
            'stereo_width': 0.7,
            'phase_correlation': 0.92,
        }

        # Serialize to JSON
        json_str = json.dumps(fingerprint)

        # Deserialize
        loaded = json.loads(json_str)

        # Check all dimensions present
        assert len(loaded) == 25
        assert loaded['sub_bass_pct'] == 0.15
        assert loaded['stereo_width'] == 0.7


# Performance and stress tests

class TestFingerprintQueuePerformance:
    """Performance tests for fingerprint queue"""

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_enqueue_throughput(self, fingerprint_extractor_mock, library_manager_mock):
        """Test enqueue throughput (should be fast)"""
        import time

        from auralis.services.fingerprint_queue import FingerprintExtractionQueue

        queue = FingerprintExtractionQueue(
            fingerprint_extractor=fingerprint_extractor_mock,
            library_manager=library_manager_mock,
            max_queue_size=1000
        )

        start = time.time()

        # Enqueue 100 jobs
        for i in range(100):
            await queue.enqueue(i, f'/path/file{i}.mp3')

        elapsed = time.time() - start

        # Should enqueue 100 jobs very quickly (< 1 second)
        assert elapsed < 1.0
        assert queue.get_queue_size() == 100

    @pytest.mark.asyncio
    @pytest.mark.boundary
    async def test_queue_max_size_limit(self, fingerprint_extractor_mock, library_manager_mock):
        """Test queue respects max size limit"""
        from auralis.services.fingerprint_queue import FingerprintExtractionQueue

        queue = FingerprintExtractionQueue(
            fingerprint_extractor=fingerprint_extractor_mock,
            library_manager=library_manager_mock,
            max_queue_size=5  # Small limit for testing
        )

        # Enqueue up to limit
        for i in range(5):
            success = await queue.enqueue(i, f'/path/file{i}.mp3')
            assert success

        # Try to enqueue beyond limit (should fail)
        success = await queue.enqueue(5, '/path/file5.mp3')
        assert not success


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

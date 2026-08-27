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

import json
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
def library_database_mock():
    """Mock library manager for testing"""
    class MockLibraryDatabase:
        def __init__(self):
            self.tracks = {}

        # #4621: get_track_by_filepath() dropped — never invoked by any test
        # here, and the real facade no longer carries it.

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

    return MockLibraryDatabase()


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


# Tests for FingerprintExtractionQueue
#
# The job-queue API these tests used to cover (FingerprintJob, enqueue(),
# enqueue_batch(), max_queue_size, get_queue_size(), the 'queued' stat) no
# longer exists: workers pull unfingerprinted tracks straight from the database
# via FingerprintSchedulerRepository, which is what removed the pre-loading and
# backpressure problems that queue had. The tests below cover the pool as it is
# now; per-track timeout behaviour lives in test_fingerprint_queue_timeout_4837.py.

class TestFingerprintExtractionQueue:
    """Tests for the DB-pull fingerprint worker pool"""

    @staticmethod
    def _make_queue(extractor, **kwargs):
        from auralis.services.fingerprint_queue import FingerprintExtractionQueue

        return FingerprintExtractionQueue(
            fingerprint_extractor=extractor,
            get_repository_factory=lambda: None,
            enable_adaptive_scaling=False,
            **kwargs,
        )

    def test_queue_initialization(self, fingerprint_extractor_mock):
        """Worker count and stop flag reflect the constructor arguments"""
        queue = self._make_queue(fingerprint_extractor_mock, num_workers=4, max_workers=4)

        assert queue.num_workers == 4
        assert queue.workers == []  # no threads until start()
        assert queue.should_stop is False

    def test_worker_count_defaults_to_half_the_cpus(self, fingerprint_extractor_mock):
        """num_workers defaults to max(4, cpu_count * 0.5)"""
        import os

        queue = self._make_queue(fingerprint_extractor_mock)

        assert queue.num_workers == max(4, int((os.cpu_count() or 16) * 0.5))

    def test_processing_semaphore_is_at_least_eight_slots(self, fingerprint_extractor_mock):
        """The memory-aware semaphore starts fully available"""
        queue = self._make_queue(fingerprint_extractor_mock, num_workers=2, max_workers=2)

        in_use, capacity = queue.processing_semaphore.usage
        assert in_use == 0
        assert capacity >= 8

    def test_queue_statistics(self, fingerprint_extractor_mock):
        """Stats start at zero and expose the counters callers read"""
        queue = self._make_queue(fingerprint_extractor_mock, num_workers=2, max_workers=2)

        stats = queue.get_stats()

        assert stats['processing'] == 0
        assert stats['completed'] == 0
        assert stats['failed'] == 0
        assert stats['cached'] == 0
        assert 'queued' not in stats  # no job queue any more


# Tests for FingerprintQueueManager

class TestFingerprintQueueManager:
    """Tests for fingerprint queue manager lifecycle"""

    @pytest.mark.asyncio
    async def test_manager_initialization(self, fingerprint_extractor_mock, library_database_mock):
        """Test queue manager initialization"""
        from auralis.services.fingerprint_queue import FingerprintQueueManager

        manager = FingerprintQueueManager(
            fingerprint_extractor=fingerprint_extractor_mock,
            library_database=library_database_mock,
            num_workers=4
        )

        assert not manager.is_running
        assert manager.queue is not None

    @pytest.mark.asyncio
    async def test_manager_startup_shutdown(self, fingerprint_extractor_mock, library_database_mock):
        """Test manager startup and shutdown"""
        from auralis.services.fingerprint_queue import FingerprintQueueManager

        manager = FingerprintQueueManager(
            fingerprint_extractor=fingerprint_extractor_mock,
            library_database=library_database_mock,
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

    def test_scanner_does_not_take_a_fingerprint_queue(self, library_database_mock):
        """The scanner must not accept a queue it would silently ignore (#4648).

        It used to take one, store it, and read it only from
        `_enqueue_fingerprints` — a method with zero call sites since #2382 moved
        enqueueing to the caller (the scan path is synchronous, so
        `asyncio.create_task` from it raised `RuntimeError: no running event
        loop`). Callers were handing over a real queue that did nothing. These
        two tests previously asserted that dead surface existed.
        """
        import inspect

        from auralis.library.scanner import LibraryScanner

        params = inspect.signature(LibraryScanner.__init__).parameters
        assert 'fingerprint_queue' not in params, (
            'LibraryScanner accepts a fingerprint_queue again — it has no '
            'enqueue path, so the argument would be silently ignored (#4648)'
        )

        scanner = LibraryScanner(library_database=library_database_mock)
        assert not hasattr(scanner, 'fingerprint_queue')

    def test_scanner_has_no_enqueue_method(self, library_database_mock):
        """No async method on the synchronous scan path (#4648)."""
        from auralis.library.scanner import LibraryScanner

        assert not hasattr(LibraryScanner, '_enqueue_fingerprints')


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


# NOTE: the enqueue-throughput and max-queue-size tests that used to live here
# measured the removed job queue (enqueue()/max_queue_size). The DB-pull design
# has no enqueue path to benchmark — worker throughput is exercised end-to-end
# by tests/test_fingerprint_queue_timeout_4837.py and the integration suite.


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

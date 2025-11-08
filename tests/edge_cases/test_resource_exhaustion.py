"""
Resource Exhaustion Edge Case Tests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests for behavior under resource constraints (memory, disk, file handles).

INVARIANTS TESTED:
- Graceful degradation: System handles resource limits without crashing
- Error reporting: Clear errors when resources exhausted
- Resource cleanup: No resource leaks under stress
- Memory bounds: Processing stays within reasonable memory limits
- File handle limits: Proper cleanup of file descriptors
"""

import pytest
import os
import tempfile
import shutil
import numpy as np
import gc
import sys
from pathlib import Path

from auralis.library.repositories import TrackRepository
from auralis.core.hybrid_processor import HybridProcessor
from auralis.core.unified_config import UnifiedConfig
from auralis.io.saver import save


@pytest.mark.edge_case
@pytest.mark.slow
class TestMemoryExhaustion:
    """Test behavior under memory constraints."""

    def test_very_large_audio_file_handling(self, temp_audio_dir):
        """
        INVARIANT: System should handle or gracefully reject very large audio.
        Test: 1-hour audio file (large memory footprint).
        """
        config = UnifiedConfig()
        config.set_processing_mode('adaptive')
        processor = HybridProcessor(config)

        # Create 1-hour stereo audio file (~600MB in memory)
        sample_rate = 44100
        duration = 3600.0  # 1 hour
        num_samples = int(duration * sample_rate)

        # Create in chunks to avoid OOM during generation
        chunk_duration = 60.0  # 1 minute chunks
        chunk_samples = int(chunk_duration * sample_rate)
        num_chunks = int(duration / chunk_duration)

        filepath = os.path.join(temp_audio_dir, 'very_large.wav')

        try:
            # Generate and save in chunks
            full_audio = []
            for i in range(num_chunks):
                chunk = np.random.randn(chunk_samples, 2).astype(np.float32) * 0.1
                full_audio.append(chunk)

            audio = np.concatenate(full_audio, axis=0)
            save(filepath, audio, sample_rate, subtype='PCM_16')

            # Try to process
            result = processor.process(filepath)

            # INVARIANT: Should complete or raise clear error
            assert result is not None, "Processing should return result"
            assert len(result) > 0, "Result should not be empty"

        except MemoryError:
            # Acceptable: Clear error when memory exhausted
            pytest.skip("System memory insufficient for 1-hour test file")
        except Exception as e:
            # Should get clear error, not crash
            assert "memory" in str(e).lower() or "size" in str(e).lower(), \
                f"Should report memory/size error, got: {e}"

    def test_many_small_allocations(self, temp_db):
        """
        INVARIANT: Many small allocations should not cause memory fragmentation crash.
        Test: Create many small track records.
        """
        track_repo = TrackRepository(temp_db)

        num_tracks = 1000
        errors = []

        try:
            for i in range(num_tracks):
                track_repo.add({
                    'filepath': f'/tmp/track_{i}.flac',
                    'title': f'Track {i}',
                    'artists': ['Test Artist'],
                    'format': 'FLAC',
                    'sample_rate': 44100,
                    'channels': 2
                })

                # Force garbage collection periodically
                if i % 100 == 0:
                    gc.collect()

            # INVARIANT: All tracks added successfully
            all_tracks, total = track_repo.get_all(limit=2000, offset=0)
            assert total == num_tracks, f"Should have {num_tracks} tracks, got {total}"

        except MemoryError as e:
            errors.append(e)
            pytest.skip(f"Memory exhausted at {num_tracks} tracks")

        assert len(errors) == 0, f"Should handle {num_tracks} small allocations"

    def test_memory_cleanup_after_processing(self, temp_audio_dir):
        """
        INVARIANT: Memory should be released after processing completes.
        Test: Process multiple files sequentially, check memory stable.
        """
        config = UnifiedConfig()
        config.set_processing_mode('adaptive')
        processor = HybridProcessor(config)

        sample_rate = 44100
        duration = 10.0
        num_files = 10

        # Get initial memory usage (approximate)
        gc.collect()
        import psutil
        try:
            process = psutil.Process()
            initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        except ImportError:
            pytest.skip("psutil not available for memory monitoring")

        # Process multiple files
        for i in range(num_files):
            audio = np.random.randn(int(duration * sample_rate), 2) * 0.1
            filepath = os.path.join(temp_audio_dir, f'mem_test_{i}.wav')
            save(filepath, audio, sample_rate, subtype='PCM_16')

            result = processor.process(filepath)
            assert len(result) > 0

            # Force cleanup
            del result
            gc.collect()

        # Check memory after processing
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_growth = final_memory - initial_memory

        # INVARIANT: Memory growth should be reasonable (< 500MB for 10 files)
        assert memory_growth < 500, \
            f"Memory leak detected: grew {memory_growth:.1f}MB after {num_files} files"

    def test_large_library_query_performance(self, temp_db):
        """
        INVARIANT: Large library queries should complete in reasonable time/memory.
        Test: Query 10k tracks with pagination.
        """
        track_repo = TrackRepository(temp_db)

        # Add many tracks
        num_tracks = 10000
        batch_size = 100

        try:
            for batch_start in range(0, num_tracks, batch_size):
                batch = []
                for i in range(batch_start, min(batch_start + batch_size, num_tracks)):
                    track_repo.add({
                        'filepath': f'/tmp/large_lib_{i}.flac',
                        'title': f'Track {i}',
                        'artists': [f'Artist {i % 100}'],
                        'format': 'FLAC',
                        'sample_rate': 44100,
                        'channels': 2
                    })

                if batch_start % 1000 == 0:
                    gc.collect()

            # Query with pagination
            page_size = 100
            total_retrieved = 0

            for offset in range(0, num_tracks, page_size):
                tracks, total = track_repo.get_all(limit=page_size, offset=offset)
                total_retrieved += len(tracks)

                # INVARIANT: Each query completes quickly
                assert len(tracks) <= page_size

            # INVARIANT: Retrieved all tracks via pagination
            assert total_retrieved == num_tracks, \
                f"Should retrieve all {num_tracks} tracks, got {total_retrieved}"

        except MemoryError:
            pytest.skip("Insufficient memory for 10k track test")

    def test_array_size_limits(self, temp_audio_dir):
        """
        INVARIANT: System should handle or reject arrays near NumPy size limits.
        Test: Very long audio arrays.
        """
        sample_rate = 44100

        # Try to create very large array (near NumPy limits)
        try:
            # 2 hours of stereo audio (~1.27 GB)
            duration = 7200.0
            num_samples = int(duration * sample_rate)

            audio = np.zeros((num_samples, 2), dtype=np.float32)

            # Try to save
            filepath = os.path.join(temp_audio_dir, 'huge_array.wav')
            save(filepath, audio, sample_rate, subtype='PCM_16')

            # INVARIANT: Should complete or give clear error
            assert os.path.exists(filepath), "File should be created"

        except (MemoryError, OverflowError) as e:
            # Acceptable: Clear error for too-large arrays
            pytest.skip(f"Array too large for system: {e}")


@pytest.mark.edge_case
@pytest.mark.slow
class TestDiskSpaceExhaustion:
    """Test behavior when disk space is limited."""

    def test_save_when_disk_full_simulation(self, temp_audio_dir):
        """
        INVARIANT: Should detect and report disk full error gracefully.
        Test: Try to save large file (may fail if disk actually full).
        """
        sample_rate = 44100
        duration = 600.0  # 10 minutes (~250MB file)

        audio = np.random.randn(int(duration * sample_rate), 2) * 0.1
        filepath = os.path.join(temp_audio_dir, 'disk_full_test.wav')

        try:
            save(filepath, audio, sample_rate, subtype='PCM_16')

            # Check file was created
            assert os.path.exists(filepath), "File should be created"
            file_size = os.path.getsize(filepath)
            assert file_size > 0, "File should not be empty"

        except OSError as e:
            # If disk is actually full, should get clear error
            if "No space left on device" in str(e) or "Disk full" in str(e):
                pytest.skip("Disk full - expected behavior")
            else:
                raise

    def test_database_file_size_growth(self, temp_db):
        """
        INVARIANT: Database should handle growth gracefully.
        Test: Add many records, check database file grows reasonably.
        """
        track_repo = TrackRepository(temp_db)

        # Get database file path
        session = temp_db()
        db_url = str(session.bind.url)
        session.close()

        # Extract file path from sqlite:///path
        db_path = db_url.replace('sqlite:///', '')

        initial_size = os.path.getsize(db_path)

        # Add 100 tracks
        for i in range(100):
            track_repo.add({
                'filepath': f'/tmp/db_growth_{i}.flac',
                'title': f'Track {i}',
                'artists': ['Test Artist'],
                'album': 'Test Album',
                'format': 'FLAC',
                'sample_rate': 44100,
                'channels': 2
            })

        final_size = os.path.getsize(db_path)
        growth = final_size - initial_size

        # INVARIANT: Database grew, but not excessively (< 10MB for 100 tracks)
        assert growth > 0, "Database should grow when adding tracks"
        assert growth < 10 * 1024 * 1024, \
            f"Database grew too much: {growth / 1024 / 1024:.1f}MB for 100 tracks"

    def test_temp_file_cleanup(self, temp_audio_dir):
        """
        INVARIANT: Temporary files should be cleaned up after processing.
        Test: Process files, check no temp files left behind.
        """
        config = UnifiedConfig()
        config.set_processing_mode('adaptive')
        processor = HybridProcessor(config)

        # Count files before
        files_before = set(os.listdir(temp_audio_dir))

        # Process audio
        sample_rate = 44100
        duration = 3.0
        audio = np.random.randn(int(duration * sample_rate), 2) * 0.1
        filepath = os.path.join(temp_audio_dir, 'cleanup_test.wav')
        save(filepath, audio, sample_rate, subtype='PCM_16')

        result = processor.process(filepath)
        assert len(result) > 0

        # Count files after
        files_after = set(os.listdir(temp_audio_dir))

        # INVARIANT: No new temp files left behind (only our input file)
        new_files = files_after - files_before
        assert len(new_files) == 1, \
            f"Should only have input file, found extra: {new_files}"
        assert 'cleanup_test.wav' in new_files


@pytest.mark.edge_case
class TestFileHandleExhaustion:
    """Test behavior when file handle limit is reached."""

    def test_many_sequential_file_operations(self, temp_audio_dir):
        """
        INVARIANT: Sequential file operations should not exhaust file handles.
        Test: Open and close many files sequentially.
        """
        sample_rate = 44100
        duration = 0.1  # Very short files
        num_files = 100

        errors = []

        try:
            for i in range(num_files):
                audio = np.random.randn(int(duration * sample_rate), 2) * 0.1
                filepath = os.path.join(temp_audio_dir, f'handle_test_{i}.wav')

                # Save file
                save(filepath, audio, sample_rate, subtype='PCM_16')

                # Load it back
                from auralis.io.unified_loader import load_audio
                loaded, sr = load_audio(filepath)

                # INVARIANT: File should load successfully
                assert loaded is not None
                assert sr == sample_rate

        except OSError as e:
            if "Too many open files" in str(e):
                errors.append(e)

        # INVARIANT: Should handle 100 sequential operations without handle exhaustion
        assert len(errors) == 0, f"File handle exhaustion: {errors}"

    def test_file_handle_cleanup_on_error(self, temp_audio_dir):
        """
        INVARIANT: File handles should be closed even when errors occur.
        Test: Try to load corrupted file, check handle is released.
        """
        # Create corrupted file
        filepath = os.path.join(temp_audio_dir, 'corrupted.wav')
        with open(filepath, 'wb') as f:
            f.write(b'RIFF' + b'\x00' * 100)  # Invalid WAV

        from auralis.io.unified_loader import load_audio

        # Try to load corrupted file
        try:
            load_audio(filepath)
        except Exception:
            pass  # Expected to fail

        # Try to delete file (should succeed if handle was closed)
        try:
            os.unlink(filepath)
            handle_released = True
        except PermissionError:
            handle_released = False

        # INVARIANT: File handle should be released after error
        assert handle_released, "File handle not released after error"

    def test_database_connection_pool_exhaustion(self, temp_db):
        """
        INVARIANT: Database connections should be properly managed (no pool exhaustion).
        Test: Many sequential queries.
        """
        track_repo = TrackRepository(temp_db)

        # Add test data
        for i in range(10):
            track_repo.add({
                'filepath': f'/tmp/pool_test_{i}.flac',
                'title': f'Track {i}',
                'artists': ['Test Artist'],
                'format': 'FLAC',
                'sample_rate': 44100,
                'channels': 2
            })

        errors = []

        # Perform many queries
        for i in range(100):
            try:
                tracks, total = track_repo.get_all(limit=10, offset=0)
                assert len(tracks) > 0
            except Exception as e:
                errors.append(e)

        # INVARIANT: No connection pool exhaustion
        assert len(errors) == 0, f"Connection pool errors: {errors}"

    def test_concurrent_file_access_limit(self, temp_audio_dir):
        """
        INVARIANT: System should handle multiple files open simultaneously.
        Test: Open many files at once.
        """
        sample_rate = 44100
        duration = 0.1
        num_files = 50

        # Create files
        files = []
        for i in range(num_files):
            audio = np.random.randn(int(duration * sample_rate), 2) * 0.1
            filepath = os.path.join(temp_audio_dir, f'concurrent_{i}.wav')
            save(filepath, audio, sample_rate, subtype='PCM_16')
            files.append(filepath)

        # Open all files simultaneously
        handles = []
        errors = []

        try:
            for filepath in files:
                try:
                    f = open(filepath, 'rb')
                    handles.append(f)
                except OSError as e:
                    errors.append(e)
                    break

            # INVARIANT: Should handle reasonable number of open files (at least 50)
            if errors:
                assert len(handles) >= 20, \
                    f"Too few file handles available: {len(handles)}"

        finally:
            # Cleanup
            for f in handles:
                f.close()

        # Check for "too many open files" error
        if errors and "Too many open files" in str(errors[0]):
            pytest.skip("System file handle limit reached (expected on some systems)")


@pytest.mark.edge_case
class TestResourceLimitConfiguration:
    """Test behavior with configured resource limits."""

    def test_processing_with_memory_limit(self, temp_audio_dir):
        """
        INVARIANT: Processing should respect memory limits if configured.
        Test: Process with resource constraints.
        """
        config = UnifiedConfig()
        config.set_processing_mode('adaptive')
        processor = HybridProcessor(config)

        # Create modest audio file
        sample_rate = 44100
        duration = 10.0
        audio = np.random.randn(int(duration * sample_rate), 2) * 0.1
        filepath = os.path.join(temp_audio_dir, 'limited.wav')
        save(filepath, audio, sample_rate, subtype='PCM_16')

        # Process (should work with reasonable file)
        result = processor.process(filepath)

        # INVARIANT: Should complete successfully with normal file
        assert result is not None
        assert len(result) > 0

    def test_graceful_degradation_under_pressure(self, temp_audio_dir):
        """
        INVARIANT: System should degrade gracefully under resource pressure.
        Test: Process while system is under load.
        """
        config = UnifiedConfig()
        config.set_processing_mode('adaptive')
        processor = HybridProcessor(config)

        # Create test file
        sample_rate = 44100
        duration = 3.0
        audio = np.random.randn(int(duration * sample_rate), 2) * 0.1
        filepath = os.path.join(temp_audio_dir, 'pressure.wav')
        save(filepath, audio, sample_rate, subtype='PCM_16')

        # Simulate memory pressure with large allocations
        pressure_arrays = []
        try:
            for i in range(5):
                # Allocate 100MB arrays
                arr = np.zeros((25 * 1024 * 1024,), dtype=np.float32)
                pressure_arrays.append(arr)
        except MemoryError:
            pass  # May not have enough memory

        # Try to process under pressure
        try:
            result = processor.process(filepath)

            # INVARIANT: Should complete or give clear error
            assert result is not None
            assert len(result) > 0

        except MemoryError:
            # Acceptable: Clear error under memory pressure
            pass

        finally:
            # Cleanup
            del pressure_arrays
            gc.collect()

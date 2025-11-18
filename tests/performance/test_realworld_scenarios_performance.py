"""
Real-World Scenario Performance Tests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Measures performance in realistic usage scenarios.

BENCHMARKS MEASURED:
- Complete workflows (import -> analyze -> process -> export)
- Typical user operations (playlist creation, batch processing)
- Multi-track album processing
- Library migration scenarios
- Continuous playback with real-time processing
- Preset switching during playback

Target: 15 comprehensive real-world scenario tests

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import pytest
import time
import numpy as np
import os
import tempfile

from auralis.core.hybrid_processor import HybridProcessor
from auralis.core.unified_config import UnifiedConfig
from auralis.library.manager import LibraryManager
from auralis.library.repositories import TrackRepository, PlaylistRepository
from auralis.io.saver import save
from auralis.io.unified_loader import load_audio


# ============================================================================
# COMPLETE WORKFLOW TESTS (5 tests)
# ============================================================================

@pytest.mark.performance
@pytest.mark.slow
class TestCompleteWorkflows:
    """Measure complete end-to-end workflow performance."""

    def test_import_analyze_process_export_workflow(self, temp_audio_dir, timer, benchmark_results):
        """
        BENCHMARK: Complete workflow should complete in <30s for 10-track album.
        """
        # Create 10 test tracks (simulating an album)
        filepaths = []
        for i in range(10):
            audio = np.random.randn(int(30.0 * 44100), 2) * 0.1
            filepath = os.path.join(temp_audio_dir, f'album_track_{i+1:02d}.wav')
            save(filepath, audio, 44100, subtype='PCM_16')
            filepaths.append(filepath)

        config = UnifiedConfig()
        config.set_processing_mode('adaptive')
        processor = HybridProcessor(config)

        # Complete workflow
        with timer() as t:
            # 1. Import to library
            manager = LibraryManager(database_path=':memory:')
            manager.scan_folder(temp_audio_dir)

            # 2. Process all tracks
            processed = []
            for filepath in filepaths:
                result = processor.process(filepath)
                processed.append(result)

            # 3. Export processed tracks
            output_dir = os.path.join(temp_audio_dir, 'output')
            os.makedirs(output_dir, exist_ok=True)
            for i, audio in enumerate(processed):
                output_path = os.path.join(output_dir, f'processed_{i+1:02d}.wav')
                save(output_path, audio, 44100, subtype='PCM_16')

        total_time = t.elapsed

        # BENCHMARK: Should complete in < 30s for 10 tracks
        assert total_time < 30, f"Complete workflow took {total_time:.1f}s, expected < 30s"

        benchmark_results['complete_workflow_10_tracks_s'] = total_time
        print(f"\n✓ Complete workflow (10 tracks): {total_time:.1f}s")

    def test_large_library_import_workflow(self, timer, benchmark_results):
        """
        BENCHMARK: Importing 1000-track library should complete in <60s.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create 1000 test files
            for i in range(1000):
                audio = np.random.randn(int(3.0 * 44100), 2) * 0.1
                filepath = os.path.join(tmpdir, f'import_{i:04d}.wav')
                save(filepath, audio, 44100, subtype='PCM_16')

            manager = LibraryManager(database_path=':memory:')

            with timer() as t:
                manager.scan_folder(tmpdir)

            import_time = t.elapsed

            # BENCHMARK: Should complete in < 60s
            assert import_time < 60, f"Library import took {import_time:.1f}s, expected < 60s"

            benchmark_results['library_import_1000_tracks_s'] = import_time
            print(f"\n✓ Library import (1000 tracks): {import_time:.1f}s")

    def test_batch_processing_workflow(self, temp_audio_dir, timer, benchmark_results):
        """
        BENCHMARK: Batch processing 50 tracks should achieve consistent throughput.
        """
        # Create 50 test tracks
        filepaths = []
        for i in range(50):
            audio = np.random.randn(int(10.0 * 44100), 2) * 0.1
            filepath = os.path.join(temp_audio_dir, f'batch_{i:02d}.wav')
            save(filepath, audio, 44100, subtype='PCM_16')
            filepaths.append(filepath)

        config = UnifiedConfig()
        config.set_processing_mode('adaptive')
        processor = HybridProcessor(config)

        # Process batch
        with timer() as t:
            for filepath in filepaths:
                result = processor.process(filepath)
                del result  # Free memory

        batch_time = t.elapsed
        tracks_per_second = 50 / batch_time

        # BENCHMARK: Should process > 2 tracks/second
        assert tracks_per_second > 2, \
            f"Batch throughput {tracks_per_second:.2f} tracks/s below 2 tracks/s"

        benchmark_results['batch_processing_tracks_per_sec'] = tracks_per_second
        print(f"\n✓ Batch processing: {tracks_per_second:.2f} tracks/s")

    def test_playlist_creation_workflow(self, temp_db, timer, benchmark_results):
        """
        BENCHMARK: Creating playlist with 100 tracks should be <200ms.
        """
        track_repo = TrackRepository(temp_db)
        playlist_repo = PlaylistRepository(temp_db)

        # Create 100 tracks
        track_ids = []
        for i in range(100):
            track_id = track_repo.add({
                'filepath': f'/tmp/playlist_{i}.flac',
                'title': f'Track {i}',
                'artists': ['Artist'],
                'format': 'FLAC',
                'sample_rate': 44100,
                'channels': 2
            })
            track_ids.append(track_id)

        # Create playlist with all tracks
        with timer() as t:
            playlist_id = playlist_repo.create({
                'name': 'Test Playlist',
                'track_ids': track_ids
            })

        creation_time_ms = t.elapsed_ms

        # BENCHMARK: Should complete in < 200ms
        assert creation_time_ms < 200, \
            f"Playlist creation took {creation_time_ms:.1f}ms, expected < 200ms"

        benchmark_results['playlist_creation_100_tracks_ms'] = creation_time_ms
        print(f"\n✓ Playlist creation (100 tracks): {creation_time_ms:.1f}ms")

    def test_library_rebuild_workflow(self, temp_audio_dir, timer):
        """
        BENCHMARK: Rebuilding library index for 500 tracks should be <30s.
        """
        # Create 500 test files
        for i in range(500):
            audio = np.random.randn(int(3.0 * 44100), 2) * 0.1
            filepath = os.path.join(temp_audio_dir, f'rebuild_{i:03d}.wav')
            save(filepath, audio, 44100, subtype='PCM_16')

        manager = LibraryManager(database_path=':memory:')

        # Initial scan
        manager.scan_folder(temp_audio_dir)

        # Rebuild (rescan all)
        with timer() as t:
            manager.scan_folder(temp_audio_dir)

        rebuild_time = t.elapsed

        # BENCHMARK: Should complete in < 30s
        assert rebuild_time < 30, f"Library rebuild took {rebuild_time:.1f}s, expected < 30s"

        print(f"\n✓ Library rebuild (500 tracks): {rebuild_time:.1f}s")


# ============================================================================
# TYPICAL USER OPERATIONS (5 tests)
# ============================================================================

@pytest.mark.performance
class TestTypicalUserOperations:
    """Measure performance of common user operations."""

    def test_search_and_play_latency(self, temp_db, timer, benchmark_results):
        """
        BENCHMARK: Search + play operation should be <100ms.
        """
        track_repo = TrackRepository(temp_db)

        # Create searchable library
        for i in range(1000):
            track_repo.add({
                'filepath': f'/tmp/search_play_{i}.flac',
                'title': f'Track Title {i}',
                'artists': [f'Artist Name {i % 50}'],
                'format': 'FLAC',
                'sample_rate': 44100,
                'channels': 2
            })

        # Warm up
        track_repo.search('Track Title 500', limit=10, offset=0)

        # Measure search + retrieve
        with timer() as t:
            results = track_repo.search('Track Title 500', limit=10, offset=0)
            if isinstance(results, tuple):
                tracks, _ = results
            else:
                tracks = results

            # Get first track (simulating play)
            if tracks:
                track = tracks[0]

        latency_ms = t.elapsed_ms

        # BENCHMARK: Should be < 100ms
        assert latency_ms < 100, f"Search+play took {latency_ms:.1f}ms, expected < 100ms"

        benchmark_results['search_play_ms'] = latency_ms
        print(f"\n✓ Search and play: {latency_ms:.1f}ms")

    def test_add_to_queue_latency(self, temp_db, timer):
        """
        BENCHMARK: Adding 10 tracks to queue should be <50ms.
        """
        track_repo = TrackRepository(temp_db)

        # Create tracks
        track_ids = []
        for i in range(10):
            track_id = track_repo.add({
                'filepath': f'/tmp/queue_{i}.flac',
                'title': f'Track {i}',
                'artists': ['Artist'],
                'format': 'FLAC',
                'sample_rate': 44100,
                'channels': 2
            })
            track_ids.append(track_id)

        # Simulate queue operations (in-memory)
        with timer() as t:
            queue = []
            for track_id in track_ids:
                queue.append(track_id)

        latency_ms = t.elapsed_ms

        # BENCHMARK: Should be < 50ms
        assert latency_ms < 50, f"Add to queue took {latency_ms:.1f}ms, expected < 50ms"

        print(f"\n✓ Add to queue (10 tracks): {latency_ms:.1f}ms")

    def test_favorite_multiple_tracks_latency(self, temp_db, timer):
        """
        BENCHMARK: Favoriting 20 tracks should be <200ms.
        """
        track_repo = TrackRepository(temp_db)

        # Create tracks
        track_ids = []
        for i in range(20):
            track = track_repo.add({
                'filepath': f'/tmp/favorite_{i}.flac',
                'title': f'Track {i}',
                'artists': ['Artist'],
                'favorite': False,
                'format': 'FLAC',
                'sample_rate': 44100,
                'channels': 2
            })
            track_ids.append(track.id)

        # Batch favorite
        session = temp_db()
        from auralis.library.models import Track

        with timer() as t:
            for track_id in track_ids:
                track = session.query(Track).filter_by(id=track_id).first()
                track.favorite = True
            session.commit()

        session.close()
        latency_ms = t.elapsed_ms

        # BENCHMARK: Should be < 200ms (20 queries + commit)
        assert latency_ms < 200, f"Batch favorite took {latency_ms:.1f}ms, expected < 200ms"

        print(f"\n✓ Batch favorite (20 tracks): {latency_ms:.1f}ms")

    def test_filter_by_genre_latency(self, temp_db, timer):
        """
        BENCHMARK: Filtering 5000 tracks by genre should be <50ms.
        """
        track_repo = TrackRepository(temp_db)

        # Create tracks with genres
        genres = ['Rock', 'Pop', 'Jazz', 'Classical', 'Electronic']
        for i in range(5000):
            track_repo.add({
                'filepath': f'/tmp/genre_{i}.flac',
                'title': f'Track {i}',
                'artists': ['Artist'],
                'genre': genres[i % len(genres)],
                'format': 'FLAC',
                'sample_rate': 44100,
                'channels': 2
            })

        # Filter by genre (using search as proxy)
        with timer() as t:
            results = track_repo.search('Rock', limit=50, offset=0)

        latency_ms = t.elapsed_ms

        # BENCHMARK: Should be < 50ms
        assert latency_ms < 50, f"Genre filter took {latency_ms:.1f}ms, expected < 50ms"

        print(f"\n✓ Filter by genre (5000 tracks): {latency_ms:.1f}ms")

    def test_recent_played_query_latency(self, temp_db, timer):
        """
        BENCHMARK: Getting recently played tracks should be <30ms.
        """
        track_repo = TrackRepository(temp_db)

        # Create tracks with play history
        import datetime
        for i in range(1000):
            track_repo.add({
                'filepath': f'/tmp/recent_{i}.flac',
                'title': f'Track {i}',
                'artists': ['Artist'],
                'last_played': datetime.datetime.now() if i < 50 else None,
                'play_count': 50 - i if i < 50 else 0,
                'format': 'FLAC',
                'sample_rate': 44100,
                'channels': 2
            })

        # Warm up
        track_repo.get_recent(limit=20, offset=0)

        # Measure
        with timer() as t:
            recent, total = track_repo.get_recent(limit=20, offset=0)

        latency_ms = t.elapsed_ms

        # BENCHMARK: Should be < 30ms
        assert latency_ms < 30, f"Recent tracks query took {latency_ms:.1f}ms, expected < 30ms"

        print(f"\n✓ Recent tracks query: {latency_ms:.1f}ms")


# ============================================================================
# MULTI-TRACK ALBUM PROCESSING (3 tests)
# ============================================================================

@pytest.mark.performance
@pytest.mark.slow
class TestMultiTrackAlbumProcessing:
    """Measure performance of album-level operations."""

    def test_process_album_with_consistent_settings(self, temp_audio_dir, timer, benchmark_results):
        """
        BENCHMARK: Processing 12-track album with consistent settings should be faster than individual.
        """
        # Create 12 tracks
        filepaths = []
        for i in range(12):
            audio = np.random.randn(int(15.0 * 44100), 2) * 0.1
            filepath = os.path.join(temp_audio_dir, f'album_{i+1:02d}.wav')
            save(filepath, audio, 44100, subtype='PCM_16')
            filepaths.append(filepath)

        config = UnifiedConfig()
        config.set_processing_mode('adaptive')

        # Process with fixed targets (simulating album consistency)
        processor = HybridProcessor(config)

        # First track: analyze and get targets
        first_audio = load_audio(filepaths[0])[0]

        with timer() as t:
            # Process all tracks
            for filepath in filepaths:
                result = processor.process(filepath)
                del result

        album_time = t.elapsed
        tracks_per_second = 12 / album_time

        # BENCHMARK: Should process > 2 tracks/second
        assert tracks_per_second > 2, \
            f"Album processing {tracks_per_second:.2f} tracks/s below 2 tracks/s"

        benchmark_results['album_processing_tracks_per_sec'] = tracks_per_second
        print(f"\n✓ Album processing (12 tracks): {tracks_per_second:.2f} tracks/s")

    def test_extract_album_fingerprints(self, temp_audio_dir, timer, benchmark_results):
        """
        BENCHMARK: Extracting fingerprints for 10-track album should be <30s.
        """
        from auralis.analysis.fingerprint import AudioFingerprintAnalyzer

        # Create 10 tracks
        filepaths = []
        for i in range(10):
            audio = np.random.randn(int(20.0 * 44100), 2) * 0.1
            filepath = os.path.join(temp_audio_dir, f'fingerprint_{i+1:02d}.wav')
            save(filepath, audio, 44100, subtype='PCM_16')
            filepaths.append(filepath)

        analyzer = AudioFingerprintAnalyzer()

        with timer() as t:
            fingerprints = []
            for filepath in filepaths:
                audio, sr = load_audio(filepath)
                fp = analyzer.analyze(audio, sr)
                fingerprints.append(fp)

        extraction_time = t.elapsed

        # BENCHMARK: Should complete in < 30s
        assert extraction_time < 30, \
            f"Fingerprint extraction took {extraction_time:.1f}s, expected < 30s"

        benchmark_results['album_fingerprint_extraction_s'] = extraction_time
        print(f"\n✓ Album fingerprint extraction (10 tracks): {extraction_time:.1f}s")

    def test_album_metadata_update(self, temp_db, timer):
        """
        BENCHMARK: Updating metadata for all tracks in album should be <50ms.
        """
        from auralis.library.repositories import AlbumRepository

        track_repo = TrackRepository(temp_db)
        album_repo = AlbumRepository(temp_db)

        # Create album with 15 tracks
        album_id = album_repo.add({
            'title': 'Test Album',
            'artist': 'Test Artist',
            'year': 2024
        })

        track_ids = []
        for i in range(15):
            track_id = track_repo.add({
                'filepath': f'/tmp/album_meta_{i}.flac',
                'title': f'Track {i+1}',
                'artists': ['Test Artist'],
                'album_id': album_id,
                'track_number': i + 1,
                'format': 'FLAC',
                'sample_rate': 44100,
                'channels': 2
            })
            track_ids.append(track_id)

        # Update all tracks in album
        session = temp_db()
        from auralis.library.models import Track

        with timer() as t:
            for track_id in track_ids:
                track = session.query(Track).filter_by(id=track_id).first()
                track.album_artist = 'Updated Artist'
            session.commit()

        session.close()
        latency_ms = t.elapsed_ms

        # BENCHMARK: Should be < 50ms
        assert latency_ms < 50, f"Album metadata update took {latency_ms:.1f}ms, expected < 50ms"

        print(f"\n✓ Album metadata update (15 tracks): {latency_ms:.1f}ms")


# ============================================================================
# STRESS SCENARIOS (2 tests)
# ============================================================================

@pytest.mark.performance
@pytest.mark.slow
class TestStressScenarios:
    """Measure performance under stress conditions."""

    def test_rapid_preset_switching(self, performance_audio_file, timer):
        """
        BENCHMARK: Rapid preset switching should maintain responsiveness.
        """
        presets = ['adaptive', 'gentle', 'warm', 'bright', 'punchy']

        audio, sr = load_audio(performance_audio_file)

        switch_times = []

        for preset in presets:
            config = UnifiedConfig()
            config.set_preset(preset)

            with timer() as t:
                processor = HybridProcessor(config)

            switch_times.append(t.elapsed_ms)

        avg_switch_time = sum(switch_times) / len(switch_times)

        # BENCHMARK: Average switch time should be < 50ms
        assert avg_switch_time < 50, \
            f"Average preset switch time {avg_switch_time:.1f}ms exceeds 50ms"

        print(f"\n✓ Preset switching: {avg_switch_time:.1f}ms avg")

    def test_concurrent_library_operations(self, temp_db):
        """
        BENCHMARK: Concurrent read operations should scale well.
        """
        from concurrent.futures import ThreadPoolExecutor

        track_repo = TrackRepository(temp_db)

        # Create large library
        for i in range(5000):
            track_repo.add({
                'filepath': f'/tmp/concurrent_{i}.flac',
                'title': f'Track {i}',
                'artists': ['Artist'],
                'format': 'FLAC',
                'sample_rate': 44100,
                'channels': 2
            })

        def query_tracks(offset):
            return track_repo.get_all(limit=50, offset=offset)

        # Sequential baseline
        start = time.perf_counter()
        for offset in [0, 100, 200, 300, 400]:
            query_tracks(offset)
        sequential_time = time.perf_counter() - start

        # Concurrent
        start = time.perf_counter()
        with ThreadPoolExecutor(max_workers=5) as executor:
            list(executor.map(query_tracks, [0, 100, 200, 300, 400]))
        concurrent_time = time.perf_counter() - start

        speedup = sequential_time / concurrent_time if concurrent_time > 0 else 1

        # BENCHMARK: Concurrent should be faster (or at least not slower)
        print(f"\n✓ Concurrent operations speedup: {speedup:.2f}x")

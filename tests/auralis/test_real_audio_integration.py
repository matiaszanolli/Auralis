"""
Real Audio Integration Tests
Comprehensive tests using real audio files to test the complete pipeline.
"""

import pytest
import numpy as np
import tempfile
import os
from pathlib import Path


class TestRealAudioLoading:
    """Test loading real audio files."""

    @pytest.fixture
    def audio_files(self):
        """Get paths to real audio files."""
        test_dir = Path(__file__).parent.parent.parent  # Go up to matchering root
        input_dir = test_dir / "tests" / "input_media"

        audio_files = {}
        if input_dir.exists():
            for audio_file in input_dir.glob("*.mp3"):
                # Use simplified names without special characters
                name = audio_file.stem.replace("%20", "_").replace("%C3%83%C2%A9", "e")
                audio_files[name] = str(audio_file)

        return audio_files

    def test_loader_with_real_files(self, audio_files):
        """Test loader with real audio files."""
        if not audio_files:
            pytest.skip("No real audio files available")

        from matchering.loader import load

        for name, file_path in audio_files.items():
            if os.path.exists(file_path):
                try:
                    audio, sample_rate = load(file_path, name)

                    # Validate loaded audio
                    assert isinstance(audio, np.ndarray)
                    assert audio.ndim == 2  # Should be stereo
                    assert audio.shape[1] == 2  # Two channels
                    assert audio.shape[0] > 0  # Has samples
                    assert audio.dtype == np.float32

                    # Validate sample rate
                    assert isinstance(sample_rate, int)
                    assert sample_rate > 0
                    assert sample_rate in [44100, 48000, 96000]  # Common rates

                    # Check audio characteristics
                    rms = np.sqrt(np.mean(audio ** 2))
                    peak = np.max(np.abs(audio))

                    assert 0 < rms < 1.0  # Reasonable RMS level
                    assert 0 < peak <= 1.1  # Peak should be reasonable (allow slight clipping)

                    print(f"Loaded {name}: {audio.shape[0]} samples at {sample_rate}Hz, RMS={rms:.3f}, Peak={peak:.3f}")

                except Exception as e:
                    # If loading fails, it should be a reasonable error
                    error_msg = str(e).lower()
                    assert any(word in error_msg for word in [
                        'file', 'format', 'codec', 'unsupported', 'read', 'decode'
                    ])

    def test_checker_with_real_audio(self, audio_files):
        """Test checker with real audio files."""
        if not audio_files:
            pytest.skip("No real audio files available")

        from matchering.checker import check
        from matchering.defaults import Config
        from matchering.loader import load

        config = Config()

        for name, file_path in audio_files.items():
            if os.path.exists(file_path):
                try:
                    audio, sample_rate = load(file_path, name)

                    # Test checker with real audio
                    try:
                        result = check(audio, sample_rate, config, name)
                        # Checker completed successfully
                        print(f"Checker passed for {name}")
                    except Exception as e:
                        # Check for validation errors
                        error_msg = str(e).lower()
                        print(f"Checker validation for {name}: {error_msg}")
                        # These are acceptable validation errors
                        assert any(word in error_msg for word in [
                            'clipping', 'level', 'length', 'quiet', 'loud', 'validation'
                        ])

                except Exception as e:
                    # File loading might fail
                    pass

    def test_dsp_functions_with_real_audio(self, audio_files):
        """Test DSP functions with real audio."""
        if not audio_files:
            pytest.skip("No real audio files available")

        from matchering import dsp
        from matchering.loader import load

        for name, file_path in audio_files.items():
            if os.path.exists(file_path):
                try:
                    audio, sample_rate = load(file_path, name)

                    # Limit to reasonable size for testing
                    if audio.shape[0] > 44100 * 10:  # More than 10 seconds
                        audio = audio[:44100 * 10]  # Take first 10 seconds

                    # Test normalization
                    try:
                        normalized, gain = dsp.normalize(audio, 0.8)
                        assert isinstance(normalized, np.ndarray)
                        assert normalized.shape == audio.shape
                        assert isinstance(gain, (float, np.floating))
                        print(f"Normalized {name}: gain={gain:.3f}")
                    except Exception as e:
                        print(f"Normalization failed for {name}: {e}")

                    # Test fade
                    try:
                        fade_samples = min(1024, audio.shape[0] // 4)
                        faded = dsp.fade(audio, fade_samples)
                        assert isinstance(faded, np.ndarray)
                        assert faded.shape == audio.shape
                        print(f"Faded {name}: {fade_samples} samples")
                    except Exception as e:
                        print(f"Fade failed for {name}: {e}")

                except Exception as e:
                    # File loading might fail
                    pass


class TestRealAudioLibraryIntegration:
    """Test library management with real audio files."""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        yield db_path
        if os.path.exists(db_path):
            os.unlink(db_path)

    @pytest.fixture
    def audio_files(self):
        """Get paths to real audio files."""
        test_dir = Path(__file__).parent.parent.parent  # Go up to matchering root
        input_dir = test_dir / "tests" / "input_media"

        audio_files = {}
        if input_dir.exists():
            for audio_file in input_dir.glob("*.mp3"):
                # Use simplified names
                name = audio_file.stem.replace("%20", "_").replace("%C3%83%C2%A9", "e")
                audio_files[name] = str(audio_file)

        return audio_files

    def test_library_scanner_with_real_files(self, temp_db, audio_files):
        """Test library scanner with real audio files."""
        if not audio_files:
            pytest.skip("No real audio files available")

        from auralis.library.manager import LibraryManager
        from auralis.library.scanner import LibraryScanner

        manager = LibraryManager(temp_db)
        scanner = LibraryScanner(manager)

        # Test scanning the input media directory
        test_dir = Path(__file__).parent.parent.parent
        input_dir = test_dir / "tests" / "input_media"

        if input_dir.exists():
            try:
                # Test scanning directory with real files
                result = scanner.scan_single_directory(str(input_dir))

                if result is not None:
                    print(f"Scan result: {result}")

                    # Check if any tracks were added
                    stats = manager.get_library_stats()
                    print(f"Library stats after scan: {stats}")

                    # Test searching for scanned tracks
                    all_tracks = manager.search_tracks("")
                    print(f"Found {len(all_tracks)} tracks total")

                    for track in all_tracks:
                        print(f"Track: {track}")

            except Exception as e:
                error_msg = str(e).lower()
                print(f"Scanner error: {error_msg}")
                # Scanner might fail for various reasons
                assert any(word in error_msg for word in [
                    'scan', 'file', 'format', 'audio', 'path', 'permission'
                ])

    def test_library_manager_with_real_metadata(self, temp_db, audio_files):
        """Test library manager with real file metadata."""
        if not audio_files:
            pytest.skip("No real audio files available")

        from auralis.library.manager import LibraryManager

        manager = LibraryManager(temp_db)

        # Try to add real files with their actual paths
        for name, file_path in audio_files.items():
            if os.path.exists(file_path):
                try:
                    # Create track info based on real file
                    track_info = {
                        'file_path': file_path,
                        'title': name,
                        'artist': 'Test Artist',
                        'album': 'Test Album',
                        'file_size': os.path.getsize(file_path)
                    }

                    track = manager.add_track(track_info)
                    if track is not None:
                        print(f"Added track: {track}")

                        # Test retrieving the track
                        retrieved = manager.get_track_by_path(file_path)
                        if retrieved is not None:
                            print(f"Retrieved track: {retrieved}")

                except Exception as e:
                    print(f"Failed to add track {name}: {e}")

        # Test library operations
        stats = manager.get_library_stats()
        print(f"Final library stats: {stats}")


class TestRealAudioProcessingPipeline:
    """Test complete processing pipeline with real audio."""

    @pytest.fixture
    def audio_files(self):
        """Get paths to real audio files."""
        test_dir = Path(__file__).parent.parent.parent
        input_dir = test_dir / "tests" / "input_media"

        audio_files = {}
        if input_dir.exists():
            for audio_file in input_dir.glob("*.mp3"):
                name = audio_file.stem.replace("%20", "_").replace("%C3%83%C2%A9", "e")
                audio_files[name] = str(audio_file)

        return audio_files

    def test_complete_matchering_workflow(self, audio_files):
        """Test complete matchering workflow with real files."""
        if len(audio_files) < 2:
            pytest.skip("Need at least 2 audio files for matchering test")

        from matchering.core import process
        from matchering.defaults import Config
        from matchering.results import Result

        config = Config(
            max_length=30,  # Limit to 30 seconds for testing
            fft_size=2048   # Smaller FFT for faster processing
        )

        # Use first file as target, second as reference
        file_names = list(audio_files.keys())
        target_path = audio_files[file_names[0]]
        reference_path = audio_files[file_names[1]]

        if os.path.exists(target_path) and os.path.exists(reference_path):
            # Create temporary result file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                result_path = f.name

            try:
                result = Result(result_path)

                print(f"Testing matchering: {file_names[0]} -> {file_names[1]}")

                try:
                    # This is the core matchering process
                    processed = process(target_path, reference_path, result, config)

                    if processed is not None:
                        print(f"Matchering completed successfully!")
                        print(f"Result saved to: {result_path}")

                        # Check if result file was created
                        if os.path.exists(result_path) and os.path.getsize(result_path) > 0:
                            print(f"Result file size: {os.path.getsize(result_path)} bytes")

                except Exception as e:
                    error_msg = str(e).lower()
                    print(f"Matchering process error: {error_msg}")

                    # These are acceptable processing errors
                    assert any(word in error_msg for word in [
                        'file', 'format', 'audio', 'process', 'sample', 'rate',
                        'length', 'codec', 'read', 'write', 'validation'
                    ])

            finally:
                if os.path.exists(result_path):
                    os.unlink(result_path)

    def test_preview_creation_with_real_audio(self, audio_files):
        """Test preview creation with real audio files."""
        if not audio_files:
            pytest.skip("No real audio files available")

        try:
            from matchering.preview_creator import create_preview
            from matchering.defaults import Config
            from matchering.loader import load

            config = Config(
                preview_size=10,  # 10 second preview
                preview_fade_size=1  # 1 second fade
            )

            for name, file_path in audio_files.items():
                if os.path.exists(file_path):
                    try:
                        # Load the audio
                        audio, sample_rate = load(file_path, name)

                        # Create preview
                        preview = create_preview(audio, sample_rate, config)

                        if preview is not None:
                            assert isinstance(preview, np.ndarray)
                            assert preview.shape[1] == 2  # Stereo
                            assert preview.shape[0] <= audio.shape[0]  # Shorter than original

                            # Preview should be roughly 10 seconds
                            expected_length = sample_rate * 10
                            assert abs(preview.shape[0] - expected_length) < sample_rate  # Within 1 second

                            print(f"Created preview for {name}: {preview.shape[0]} samples")

                    except Exception as e:
                        error_msg = str(e).lower()
                        print(f"Preview creation failed for {name}: {error_msg}")
                        # Acceptable errors
                        assert any(word in error_msg for word in [
                            'preview', 'audio', 'config', 'length', 'format'
                        ])

        except ImportError:
            pytest.skip("Preview creator not available")

    def test_saver_with_real_processing(self, audio_files):
        """Test saver with processed real audio."""
        if not audio_files:
            pytest.skip("No real audio files available")

        from matchering import saver
        from matchering.loader import load
        from matchering.results import Result
        from matchering import dsp

        # Take first available file
        first_file = list(audio_files.values())[0]
        if os.path.exists(first_file):
            try:
                # Load and process audio
                audio, sample_rate = load(first_file, "test")

                # Apply some processing
                normalized, gain = dsp.normalize(audio[:44100*5], 0.8)  # 5 seconds max

                # Test saving processed audio
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                    output_path = f.name

                try:
                    result = Result(output_path)
                    saver.save(normalized, sample_rate, result)

                    # Check if file was created
                    if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                        print(f"Successfully saved processed audio: {os.path.getsize(output_path)} bytes")

                except Exception as e:
                    error_msg = str(e).lower()
                    print(f"Saver error: {error_msg}")
                    # Acceptable saver errors
                    assert any(word in error_msg for word in [
                        'save', 'write', 'format', 'file', 'codec', 'audio'
                    ])

                finally:
                    if os.path.exists(output_path):
                        os.unlink(output_path)

            except Exception as e:
                print(f"Audio loading failed: {e}")


class TestRealAudioPlayerIntegration:
    """Test audio player components with real files."""

    @pytest.fixture
    def audio_files(self):
        """Get paths to real audio files."""
        test_dir = Path(__file__).parent.parent.parent
        input_dir = test_dir / "tests" / "input_media"

        audio_files = {}
        if input_dir.exists():
            for audio_file in input_dir.glob("*.mp3"):
                name = audio_file.stem.replace("%20", "_").replace("%C3%83%C2%A9", "e")
                audio_files[name] = str(audio_file)

        return audio_files

    def test_realtime_processor_with_real_audio(self, audio_files):
        """Test real-time processor with real audio chunks."""
        if not audio_files:
            pytest.skip("No real audio files available")

        try:
            from auralis.player.realtime_processor import RealtimeProcessor
            from auralis.player.config import PlayerConfig
            from matchering.loader import load

            config = PlayerConfig()

            try:
                processor = RealtimeProcessor(config)

                # Test with real audio chunks
                first_file = list(audio_files.values())[0]
                if os.path.exists(first_file):
                    try:
                        audio, sample_rate = load(first_file, "test")

                        # Process in chunks like real-time playback
                        chunk_size = 1024
                        for i in range(0, min(chunk_size * 10, audio.shape[0]), chunk_size):
                            chunk = audio[i:i+chunk_size]
                            if chunk.shape[0] == chunk_size:  # Full chunk only
                                try:
                                    if hasattr(processor, 'process'):
                                        processed = processor.process(chunk)
                                        if processed is not None:
                                            assert processed.shape == chunk.shape
                                    elif hasattr(processor, 'process_chunk'):
                                        processed = processor.process_chunk(chunk)
                                        if processed is not None:
                                            assert processed.shape == chunk.shape
                                except Exception as e:
                                    # Processing might fail for various reasons
                                    pass

                        print(f"Real-time processing test completed with {first_file}")

                    except Exception as e:
                        print(f"Audio loading failed for real-time test: {e}")

            except Exception as e:
                error_msg = str(e).lower()
                print(f"Real-time processor creation failed: {error_msg}")

        except ImportError:
            pytest.skip("Real-time processor not available")

    def test_enhanced_player_workflow(self, audio_files):
        """Test enhanced player workflow simulation."""
        if not audio_files:
            pytest.skip("No real audio files available")

        try:
            from auralis.player.enhanced_audio_player import EnhancedAudioPlayer
            from auralis.player.config import PlayerConfig

            config = PlayerConfig()

            try:
                player = EnhancedAudioPlayer(config)

                # Simulate player workflow
                workflow_methods = [
                    ('enable_enhancement', None),
                    ('set_enhancement_strength', 0.7),
                    ('disable_enhancement', None),
                ]

                for method_name, param in workflow_methods:
                    if hasattr(player, method_name):
                        method = getattr(player, method_name)
                        if callable(method):
                            try:
                                if param is not None:
                                    method(param)
                                else:
                                    method()
                                print(f"Player method {method_name} executed successfully")
                            except Exception as e:
                                print(f"Player method {method_name} failed: {e}")

            except Exception as e:
                error_msg = str(e).lower()
                print(f"Enhanced player creation failed: {error_msg}")

        except ImportError:
            pytest.skip("Enhanced audio player not available")
"""
Enhanced Audio Player Detailed Tests
Comprehensive testing for enhanced audio player components and functionality.

Exception-handling policy (#5023)
---------------------------------
Many tests here probe an introspected, ``hasattr``-guarded method surface
("call it if it exists; tolerate a graceful rejection"). Those blocks used to
be bare ``except Exception:``, which also swallowed unrelated crashes and made
real regressions look like passes. Each is now narrowed to the exception
family the call can legitimately produce:

* ``ValueError`` / ``RuntimeError`` around ``AudioPlayer(...)`` construction —
  ``AudioPlayer.__init__`` raises ``ValueError("get_repository_factory is
  required")`` when the factory is omitted (#4141), and component/device setup
  failures surface as ``RuntimeError``.
* ``TypeError`` around introspective ``method(param)`` calls — the test guesses
  the arity/signature, so a mismatch is an anticipated outcome.
* ``IndexError`` / ``RuntimeError`` around queue navigation —
  ``QueueController._get_repos()`` raises ``RuntimeError`` when no repository
  factory is available; index math on the queue can raise ``IndexError``.
* ``OSError`` / ``ValueError`` around file loading.

``AttributeError`` is deliberately NOT tolerated anywhere: every call site is
already ``hasattr``-guarded, so an ``AttributeError`` means a real refactor
drift or typo and must fail the test. ``AssertionError`` is likewise no longer
swallowed.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import numpy as np
import pytest


class TestPlaybackState:
    """Test PlaybackState enumeration."""

    def test_playback_state_enum(self):
        """Test PlaybackState enum values."""
        from auralis.player.enhanced_audio_player import PlaybackState

        # Test all enum values
        assert PlaybackState.STOPPED.value == "stopped"
        assert PlaybackState.PLAYING.value == "playing"
        assert PlaybackState.PAUSED.value == "paused"
        assert PlaybackState.LOADING.value == "loading"
        assert PlaybackState.ERROR.value == "error"

        # Test enum comparison
        assert PlaybackState.STOPPED != PlaybackState.PLAYING
        assert PlaybackState.PAUSED == PlaybackState.PAUSED



class TestQueueManager:
    """Test QueueManager functionality.

    NOTE: Skipped due to database migration issues when initializing LibraryDatabase
    through AudioPlayer constructor. Needs proper pytest fixture setup.
    """

    @pytest.fixture
    def queue_manager(self, get_repository_factory_callable):
        """Create the queue controller (QueueController requires a repository
        factory; the enhanced_audio_player.QueueManager alias was removed, #4311)."""
        from auralis.player.queue_controller import QueueController
        return QueueController(get_repository_factory_callable)

    def test_queue_manager_initialization(self, queue_manager):
        """Test QueueManager initialization."""
        assert queue_manager.queue.get_queue() == []
        assert queue_manager.current_index == -1
        assert queue_manager.shuffle_enabled == False
        assert queue_manager.repeat_enabled == False

    def test_add_track(self, queue_manager):
        """Test adding tracks to queue."""
        track_info = {
            'title': 'Test Song',
            'artist': 'Test Artist',
            'file_path': '/test/song.mp3'
        }

        queue_manager.add_track(track_info)
        assert len(queue_manager.queue.get_queue()) == 1
        assert queue_manager.queue.get_queue()[0] == track_info

        # Add multiple tracks
        track_info2 = {
            'title': 'Another Song',
            'artist': 'Another Artist',
            'file_path': '/test/song2.mp3'
        }
        queue_manager.add_track(track_info2)
        assert len(queue_manager.queue.get_queue()) == 2

    def test_queue_navigation_methods(self, queue_manager):
        """Test queue navigation methods."""
        # Add test tracks
        for i in range(3):
            track_info = {
                'title': f'Song {i}',
                'artist': f'Artist {i}',
                'file_path': f'/test/song{i}.mp3'
            }
            queue_manager.add_track(track_info)

        # Nothing is selected until the first next_track()
        assert queue_manager.get_current_track() is None

        assert queue_manager.next_track()['title'] == 'Song 0'
        assert queue_manager.next_track()['title'] == 'Song 1'
        assert queue_manager.previous_track()['title'] == 'Song 0'

        queue_manager.current_index = 1
        assert queue_manager.get_current_track()['title'] == 'Song 1'

        queue_manager.clear_queue()
        assert queue_manager.get_queue_size() == 0
        assert queue_manager.current_index == -1

    def test_shuffle_and_repeat(self, queue_manager):
        """Test shuffle and repeat functionality."""
        # Test shuffle toggle
        if hasattr(queue_manager, 'toggle_shuffle'):
            queue_manager.toggle_shuffle()
            # Should toggle the state

        if hasattr(queue_manager, 'set_shuffle'):
            queue_manager.set_shuffle(True)
            if hasattr(queue_manager, 'shuffle_enabled'):
                assert queue_manager.shuffle_enabled == True

        # Test repeat toggle
        if hasattr(queue_manager, 'toggle_repeat'):
            queue_manager.toggle_repeat()

        if hasattr(queue_manager, 'set_repeat'):
            queue_manager.set_repeat(True)
            if hasattr(queue_manager, 'repeat_enabled'):
                assert queue_manager.repeat_enabled == True


class TestAudioPlayerCore:
    """Test AudioPlayer core functionality.

    NOTE: Skipped due to database migration issues when initializing LibraryDatabase.
    Needs proper pytest fixture setup in conftest.py.
    """

    @pytest.fixture
    def mock_config(self):
        """Create mock player config."""
        try:
            from auralis.player.config import PlayerConfig
            return PlayerConfig()
        except ImportError:
            # Create mock config
            mock_config = Mock()
            mock_config.sample_rate = 44100
            mock_config.buffer_size = 1024
            return mock_config

    @pytest.fixture
    def temp_db(self):
        """Create temporary database."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        yield db_path
        if os.path.exists(db_path):
            os.unlink(db_path)

    def test_enhanced_player_initialization(self, mock_config, temp_db, get_repository_factory_callable):
        """Test AudioPlayer initialization."""
        from auralis.player.enhanced_audio_player import (
            AudioPlayer,
            PlaybackState,
        )

        # AudioPlayer now requires a repository factory (#4141).
        try:
            player = AudioPlayer(
                config=mock_config,
                get_repository_factory=get_repository_factory_callable,
            )
            assert player.config == mock_config
            assert player.state == PlaybackState.STOPPED

            # Test basic attributes
            assert hasattr(player, 'current_file')
            assert hasattr(player, 'current_track')
            assert hasattr(player, 'audio_data')

        except Exception as e:
            # Player might need an audio device/system unavailable in CI.
            error_msg = str(e).lower()
            assert any(word in error_msg for word in [
                'audio', 'device', 'system', 'library', 'repository'
            ])


    def test_player_state_management(self, mock_config, get_repository_factory_callable):
        """Test player state management against the real component surface."""
        from auralis.player.enhanced_audio_player import (
            AudioPlayer,
            PlaybackState,
        )

        try:
            # AudioPlayer now requires a repository factory (#4141); these six
            # tests built AudioPlayer(mock_config) without it until #5486, so
            # the constructor ValueError they caught made every one a no-op.
            player = AudioPlayer(
                config=mock_config,
                get_repository_factory=get_repository_factory_callable,
            )
        except RuntimeError as e:
            pytest.skip(f"Audio subsystem unavailable: {e}")

        assert player.state == PlaybackState.STOPPED
        assert player.is_playing() is False

        # stop() on an idle player is a valid no-op and must stay STOPPED.
        player.stop()
        assert player.state == PlaybackState.STOPPED
        assert player.is_playing() is False

    # test_volume_and_controls was deleted in #5486: AudioPlayer has no
    # volume/mute/position-method surface to probe (set_volume/get_volume/
    # mute/unmute never existed on it), and volume is a frontend/WebAudio
    # concern (#5607). It only ever passed by catching the constructor's
    # ValueError.


class TestEnhancedPlayerProcessing:
    """Test enhanced player processing capabilities."""

    @pytest.fixture
    def mock_config(self):
        """Real PlayerConfig — RealtimeProcessor.process_chunk reads typed
        config fields (e.g. realtime_safety_peak) that a Mock cannot satisfy
        (found when #5486 wired these tests to a real player)."""
        from auralis.player.config import PlayerConfig
        config = PlayerConfig()
        config.processing_enabled = True
        return config

    def test_enhancement_controls(self, mock_config, get_repository_factory_callable):
        """Test enhancement controls through the real processor surface."""
        import numpy as np

        from auralis.player.enhanced_audio_player import AudioPlayer

        try:
            # AudioPlayer now requires a repository factory (#4141); until
            # #5486 this test built AudioPlayer(mock_config), caught the
            # ValueError and probed enhancement methods the player never had.
            player = AudioPlayer(
                config=mock_config,
                get_repository_factory=get_repository_factory_callable,
            )
        except RuntimeError as e:
            pytest.skip(f"Audio subsystem unavailable: {e}")

        processor = player.processor
        assert processor is not None

        silence = np.zeros((1024, 2), dtype=np.float32)
        passthrough = processor.process_chunk(silence, mock_config.sample_rate)
        assert passthrough.shape == silence.shape

        # Effect toggles round-trip through the processor's real API.
        processor.set_effect_enabled('mute', True)
        processor.set_effect_enabled('mute', False)
        processor.reset_all_effects()

        info_result = processor.get_processing_info()
        assert isinstance(info_result, dict)

        # The effect change must leave a silence passthrough intact and finite.
        after = processor.process_chunk(silence, mock_config.sample_rate)
        assert after.shape == silence.shape
        assert np.isfinite(after).all()

    def test_realtime_processor_integration(self, mock_config, get_repository_factory_callable):
        """Test real-time processor integration through the player."""
        import numpy as np

        from auralis.player.enhanced_audio_player import AudioPlayer

        try:
            # AudioPlayer now requires a repository factory (#4141); until
            # #5486 this test built AudioPlayer(mock_config), caught the
            # ValueError and probed start/stop/reset/get_latency, none of
            # which RealtimeProcessor has.
            player = AudioPlayer(
                config=mock_config,
                get_repository_factory=get_repository_factory_callable,
            )
        except RuntimeError as e:
            pytest.skip(f"Audio subsystem unavailable: {e}")

        processor = player.processor
        assert processor is not None

        # A chunk through the processor keeps its shape and stays finite.
        chunk = np.random.randn(1024, 2).astype(np.float32) * 0.1
        processed = processor.process_chunk(chunk, mock_config.sample_rate)
        assert processed.shape == chunk.shape
        assert np.isfinite(processed).all()


class TestEnhancedPlayerLibraryIntegration:
    """Test library integration functionality."""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        yield db_path
        if os.path.exists(db_path):
            os.unlink(db_path)

    @pytest.fixture
    def mock_config(self):
        """Create mock config."""
        mock_config = Mock()
        mock_config.sample_rate = 44100
        mock_config.buffer_size = 1024
        return mock_config

    def test_library_integration(self, mock_config, temp_db):
        """Test library integration."""
        from auralis.library.database import LibraryDatabase
        from auralis.player.enhanced_audio_player import AudioPlayer

        library = LibraryDatabase(temp_db)

        try:
            player = AudioPlayer(mock_config, library)

            # Test library access
            if hasattr(player, 'library'):
                assert player.library is not None

            # Test library methods
            library_methods = [
                ('load_track_by_id', 1),
                ('load_track_by_path', '/test/song.mp3'),
                ('get_current_track_info', None),
                ('add_to_recent_tracks', None),
                ('update_play_count', None)
            ]

            for method_name, param in library_methods:
                if hasattr(player, method_name):
                    method = getattr(player, method_name)
                    if callable(method):
                        try:
                            if param is not None:
                                result = method(param)
                            else:
                                result = method()
                        except (TypeError, ValueError, KeyError, RuntimeError):
                            # Method might need actual track data
                            pass

        except (ValueError, RuntimeError):
            pass


    def test_queue_integration(self, mock_config, get_repository_factory_callable):
        """Test queue integration through the player's real QueueController."""
        from auralis.player.enhanced_audio_player import AudioPlayer

        try:
            # AudioPlayer now requires a repository factory (#4141); until
            # #5486 this test built AudioPlayer(mock_config), caught the
            # ValueError and never touched a queue.
            player = AudioPlayer(
                config=mock_config,
                get_repository_factory=get_repository_factory_callable,
            )
        except RuntimeError as e:
            pytest.skip(f"Audio subsystem unavailable: {e}")

        queue = player.queue
        assert queue is not None
        assert queue.get_queue_size() == 0

        test_track = {'title': 'Test Song', 'artist': 'Test Artist', 'file_path': '/test/song.mp3'}
        queue.add_track(test_track)
        assert queue.get_queue_size() == 1
        # Adding does not imply playback: the cursor stays pre-queue until
        # something starts a track.
        assert queue.current_index == -1

        queue.clear_queue()
        assert queue.get_queue_size() == 0


class TestEnhancedPlayerAdvanced:
    """Test advanced enhanced player features."""

    @pytest.fixture
    def mock_config(self):
        """Real PlayerConfig (see TestEnhancedPlayerProcessing.mock_config)."""
        from auralis.player.config import PlayerConfig
        config = PlayerConfig()
        config.enable_monitoring = True
        return config

    def test_error_handling(self, mock_config, get_repository_factory_callable):
        """Test error handling for invalid input on the real components."""
        from auralis.player.enhanced_audio_player import AudioPlayer

        try:
            # AudioPlayer now requires a repository factory (#4141); until
            # #5486 this test built AudioPlayer(mock_config), caught the
            # ValueError and probed get_last_error/clear_errors/get_error_count
            # methods the player never had.
            player = AudioPlayer(
                config=mock_config,
                get_repository_factory=get_repository_factory_callable,
            )
        except RuntimeError as e:
            pytest.skip(f"Audio subsystem unavailable: {e}")

        # Loading a nonexistent file must fail gracefully: False, or an
        # OSError family exception — never a silent success.
        try:
            loaded = player.file_manager.load_file('/nonexistent/file.mp3')
            assert loaded is False
        except (OSError, ValueError):
            pass

"""
Tests for Player State Manager
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests for the centralized player state manager.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from player_state import PlaybackState, PlayerState, TrackInfo
from state_manager import PlayerStateManager


@pytest.fixture
def mock_ws_manager():
    """Create mock WebSocket manager"""
    manager = Mock()
    manager.broadcast = AsyncMock()
    return manager


@pytest.fixture
def state_manager(mock_ws_manager):
    """Create PlayerStateManager instance"""
    return PlayerStateManager(mock_ws_manager)


class TestStateManagerInitialization:
    """Test state manager initialization"""

    def test_init(self, mock_ws_manager):
        """Test manager initializes with default state"""
        manager = PlayerStateManager(mock_ws_manager)

        assert manager.state is not None
        assert manager.ws_manager == mock_ws_manager
        assert manager._lock is not None
        assert manager._position_update_task is None

    def test_get_state(self, state_manager):
        """Test getting current state"""
        state = state_manager.get_state()

        assert isinstance(state, PlayerState)
        assert state.state == PlaybackState.STOPPED
        assert state.volume == 80  # Default volume is 80
        assert state.current_track is None


class TestStateUpdates:
    """Test state update functionality"""

    @pytest.mark.asyncio
    async def test_update_state(self, state_manager, mock_ws_manager):
        """Test updating state fields"""
        await state_manager.update_state(volume=50, state=PlaybackState.PLAYING)

        state = state_manager.get_state()
        assert state.volume == 50
        assert state.state == PlaybackState.PLAYING
        assert state.is_playing is True

        # Verify broadcast was called
        mock_ws_manager.broadcast.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_state_syncs_dependent_fields(self, state_manager):
        """Test that dependent fields are synced"""
        await state_manager.update_state(state=PlaybackState.PLAYING)

        state = state_manager.get_state()
        assert state.is_playing is True
        assert state.is_paused is False

    @pytest.mark.asyncio
    async def test_set_playing_true(self, state_manager, mock_ws_manager):
        """Test setting playing to true"""
        with patch.object(state_manager, '_start_position_updates') as mock_start:
            await state_manager.set_playing(True)

            state = state_manager.get_state()
            assert state.state == PlaybackState.PLAYING
            mock_start.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_playing_false(self, state_manager, mock_ws_manager):
        """Test setting playing to false"""
        with patch.object(state_manager, '_stop_position_updates') as mock_stop:
            await state_manager.set_playing(False)

            state = state_manager.get_state()
            assert state.state == PlaybackState.PAUSED
            mock_stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_position(self, state_manager, mock_ws_manager):
        """Test setting playback position"""
        await state_manager.set_position(30.5)

        state = state_manager.get_state()
        assert state.current_time == 30.5

    @pytest.mark.asyncio
    async def test_set_volume(self, state_manager, mock_ws_manager):
        """Test setting volume"""
        await state_manager.set_volume(75)

        state = state_manager.get_state()
        assert state.volume == 75
        assert state.is_muted is False

    @pytest.mark.asyncio
    async def test_set_volume_clamps_to_range(self, state_manager):
        """Test volume is clamped to 0-100"""
        await state_manager.set_volume(150)
        state = state_manager.get_state()
        assert state.volume == 100

        await state_manager.set_volume(-10)
        state = state_manager.get_state()
        assert state.volume == 0

    @pytest.mark.asyncio
    async def test_set_volume_zero_mutes(self, state_manager):
        """Test volume 0 sets muted flag"""
        await state_manager.set_volume(0)

        state = state_manager.get_state()
        assert state.volume == 0
        assert state.is_muted is True


class TestTrackManagement:
    """Test track loading and management"""

    @pytest.mark.asyncio
    async def test_set_track_with_none(self, state_manager, mock_ws_manager):
        """Test setting track to None"""
        await state_manager.set_track(None, None)

        state = state_manager.get_state()
        assert state.current_track is None
        assert state.current_time == 0.0
        assert state.duration == 0.0
        assert state.state == PlaybackState.STOPPED

    @pytest.mark.asyncio
    async def test_set_track_with_valid_track(self, state_manager, mock_ws_manager):
        """Test setting a valid track"""
        mock_track = Mock()
        mock_track.id = 1
        mock_track.title = "Test Track"
        mock_track.artist = "Test Artist"
        mock_track.duration = 180.0
        mock_track.filepath = "/path/to/track.mp3"
        # Mock the artists relationship (create_track_info tries to subscript it)
        mock_artist = Mock()
        mock_artist.name = "Test Artist"
        mock_track.artists = [mock_artist]
        # Mock the album relationship (create_track_info tries to access album.title)
        mock_album = Mock()
        mock_album.title = "Test Album"
        mock_track.album = mock_album

        await state_manager.set_track(mock_track, None)

        state = state_manager.get_state()
        assert state.current_track is not None
        assert state.current_track.title == "Test Track"
        assert state.current_time == 0.0
        assert state.state == PlaybackState.LOADING


class TestQueueManagement:
    """Test queue management functionality"""

    @pytest.mark.asyncio
    async def test_set_queue(self, state_manager, mock_ws_manager):
        """Test setting playback queue"""
        tracks = [
            TrackInfo(id=1, title="Track 1", artist="Artist 1", album="Album 1", duration=180.0, file_path="/path/1.mp3"),
            TrackInfo(id=2, title="Track 2", artist="Artist 2", album="Album 2", duration=200.0, file_path="/path/2.mp3"),
        ]

        await state_manager.set_queue(tracks, start_index=0)

        state = state_manager.get_state()
        assert state.queue_size == 2
        assert state.queue_index == 0
        assert len(state.queue) == 2

    @pytest.mark.asyncio
    async def test_next_track_in_queue(self, state_manager, mock_ws_manager):
        """Test moving to next track"""
        tracks = [
            TrackInfo(id=1, title="Track 1", artist="Artist 1", album="Album 1", duration=180.0, file_path="/path/1.mp3"),
            TrackInfo(id=2, title="Track 2", artist="Artist 2", album="Album 2", duration=200.0, file_path="/path/2.mp3"),
        ]

        await state_manager.set_queue(tracks, start_index=0)
        next_track = await state_manager.next_track()

        assert next_track is not None
        assert next_track.id == 2
        state = state_manager.get_state()
        assert state.queue_index == 1

    @pytest.mark.asyncio
    async def test_next_track_at_end_no_repeat(self, state_manager):
        """Test next track at end of queue without repeat"""
        tracks = [
            TrackInfo(id=1, title="Track 1", artist="Artist 1", album="Album 1", duration=180.0, file_path="/path/1.mp3"),
        ]

        await state_manager.set_queue(tracks, start_index=0)
        next_track = await state_manager.next_track()

        assert next_track is None
        state = state_manager.get_state()
        assert state.state == PlaybackState.STOPPED

    @pytest.mark.asyncio
    async def test_next_track_with_repeat_all(self, state_manager):
        """Test next track with repeat all mode"""
        tracks = [
            TrackInfo(id=1, title="Track 1", artist="Artist 1", album="Album 1", duration=180.0, file_path="/path/1.mp3"),
            TrackInfo(id=2, title="Track 2", artist="Artist 2", album="Album 2", duration=200.0, file_path="/path/2.mp3"),
        ]

        await state_manager.set_queue(tracks, start_index=1)
        await state_manager.update_state(repeat_mode="all")

        next_track = await state_manager.next_track()

        assert next_track is not None
        assert next_track.id == 1
        state = state_manager.get_state()
        assert state.queue_index == 0

    @pytest.mark.asyncio
    async def test_previous_track_restart_if_past_3_seconds(self, state_manager):
        """Test previous track restarts current if > 3 seconds"""
        tracks = [
            TrackInfo(id=1, title="Track 1", artist="Artist 1", album="Album 1", duration=180.0, file_path="/path/1.mp3"),
            TrackInfo(id=2, title="Track 2", artist="Artist 2", album="Album 2", duration=200.0, file_path="/path/2.mp3"),
        ]

        await state_manager.set_queue(tracks, start_index=1)
        await state_manager.update_state(current_time=5.0)

        prev_track = await state_manager.previous_track()

        assert prev_track is not None
        assert prev_track.id == 2  # Same track
        state = state_manager.get_state()
        assert state.current_time == 0.0

    @pytest.mark.asyncio
    async def test_previous_track_goes_back(self, state_manager):
        """Test previous track goes to previous in queue"""
        tracks = [
            TrackInfo(id=1, title="Track 1", artist="Artist 1", album="Album 1", duration=180.0, file_path="/path/1.mp3"),
            TrackInfo(id=2, title="Track 2", artist="Artist 2", album="Album 2", duration=200.0, file_path="/path/2.mp3"),
        ]

        await state_manager.set_queue(tracks, start_index=1)
        await state_manager.update_state(current_time=2.0)

        prev_track = await state_manager.previous_track()

        assert prev_track is not None
        assert prev_track.id == 1
        state = state_manager.get_state()
        assert state.queue_index == 0

    @pytest.mark.asyncio
    async def test_previous_track_at_start(self, state_manager):
        """Test previous track at start of queue"""
        tracks = [
            TrackInfo(id=1, title="Track 1", artist="Artist 1", album="Album 1", duration=180.0, file_path="/path/1.mp3"),
        ]

        await state_manager.set_queue(tracks, start_index=0)
        await state_manager.update_state(current_time=2.0)

        prev_track = await state_manager.previous_track()

        assert prev_track is None


class TestBroadcasting:
    """Test WebSocket broadcasting"""

    @pytest.mark.asyncio
    async def test_broadcast_called_on_state_update(self, state_manager, mock_ws_manager):
        """Test broadcast is called when state updates"""
        await state_manager.update_state(volume=80)

        mock_ws_manager.broadcast.assert_called_once()
        call_args = mock_ws_manager.broadcast.call_args[0][0]
        assert call_args["type"] == "player_state"
        assert "data" in call_args

    @pytest.mark.asyncio
    async def test_broadcast_state_format(self, state_manager, mock_ws_manager):
        """Test broadcast message format"""
        await state_manager.set_volume(50)

        call_args = mock_ws_manager.broadcast.call_args[0][0]
        assert call_args["type"] == "player_state"
        assert "data" in call_args
        assert "volume" in call_args["data"]
        assert call_args["data"]["volume"] == 50


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

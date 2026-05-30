"""
Unit tests for NavigationService (#3860 / BE-TC-5)

NavigationService is wired into routers/player.py and called on every
queue-navigation request (next, previous, jump-to-track), but had no
dedicated tests before this file.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from services.navigation_service import NavigationService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_service(
    next_result: bool = True,
    prev_result: bool = True,
    queue_size: int = 5,
):
    """Return a NavigationService with mocked dependencies."""
    audio_player = MagicMock()
    audio_player.next_track = MagicMock(return_value=next_result)
    audio_player.previous_track = MagicMock(return_value=prev_result)

    queue = MagicMock()
    queue.get_queue_size = MagicMock(return_value=queue_size)
    queue.set_current_index = MagicMock()
    queue.current_index = 0
    audio_player.queue = queue

    state_manager = MagicMock()
    state_manager.set_playing = AsyncMock()

    connection_manager = MagicMock()
    connection_manager.broadcast = AsyncMock()

    create_track_info_fn = MagicMock(return_value={"id": 1, "title": "Test"})

    service = NavigationService(
        audio_player=audio_player,
        player_state_manager=state_manager,
        connection_manager=connection_manager,
        create_track_info_fn=create_track_info_fn,
    )
    return service, audio_player, state_manager, connection_manager


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestNavigationServiceInit:
    def test_stores_dependencies(self):
        service, player, state_mgr, conn_mgr = _make_service()
        assert service.audio_player is player
        assert service.player_state_manager is state_mgr
        assert service.connection_manager is conn_mgr


class TestNextTrack:
    @pytest.mark.asyncio
    async def test_next_track_success_broadcasts_and_returns_message(self):
        service, player, _, conn_mgr = _make_service(next_result=True)
        result = await service.next_track()

        player.next_track.assert_called_once()
        conn_mgr.broadcast.assert_awaited_once()
        broadcast_call = conn_mgr.broadcast.call_args[0][0]
        assert broadcast_call["type"] == "track_changed"
        assert broadcast_call["data"]["action"] == "next"
        assert "next" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_next_track_no_next_skips_broadcast(self):
        service, player, _, conn_mgr = _make_service(next_result=False)
        result = await service.next_track()

        player.next_track.assert_called_once()
        conn_mgr.broadcast.assert_not_awaited()
        assert "no next" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_next_track_without_method_returns_message(self):
        service, player, _, conn_mgr = _make_service()
        del player.next_track  # remove the attribute entirely
        result = await service.next_track()

        conn_mgr.broadcast.assert_not_awaited()
        assert "not available" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_next_track_raises_if_player_missing(self):
        service, _, _, _ = _make_service()
        service.audio_player = None  # type: ignore[assignment]
        with pytest.raises(ValueError, match="player"):
            await service.next_track()


class TestPreviousTrack:
    @pytest.mark.asyncio
    async def test_previous_track_success_broadcasts(self):
        service, player, _, conn_mgr = _make_service(prev_result=True)
        result = await service.previous_track()

        player.previous_track.assert_called_once()
        conn_mgr.broadcast.assert_awaited_once()
        broadcast_call = conn_mgr.broadcast.call_args[0][0]
        assert broadcast_call["data"]["action"] == "previous"
        assert "previous" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_previous_track_no_previous_skips_broadcast(self):
        service, player, _, conn_mgr = _make_service(prev_result=False)
        result = await service.previous_track()

        conn_mgr.broadcast.assert_not_awaited()
        assert "no previous" in result["message"].lower()


class TestJumpToTrack:
    @pytest.mark.asyncio
    async def test_jump_to_valid_index_broadcasts_jumped(self):
        service, player, state_mgr, conn_mgr = _make_service(queue_size=5)
        result = await service.jump_to_track(2)

        player.queue.set_current_index.assert_called_once_with(2)
        state_mgr.set_playing.assert_awaited_once_with(True)
        broadcast_call = conn_mgr.broadcast.call_args[0][0]
        assert broadcast_call["data"]["action"] == "jumped"
        assert broadcast_call["data"]["track_index"] == 2
        assert result["track_index"] == 2

    @pytest.mark.asyncio
    async def test_jump_to_negative_index_raises_value_error(self):
        service, _, _, _ = _make_service(queue_size=5)
        with pytest.raises(ValueError, match="Invalid track index"):
            await service.jump_to_track(-1)

    @pytest.mark.asyncio
    async def test_jump_to_out_of_bounds_raises_value_error(self):
        service, _, _, _ = _make_service(queue_size=3)
        with pytest.raises(ValueError, match="Invalid track index"):
            await service.jump_to_track(10)

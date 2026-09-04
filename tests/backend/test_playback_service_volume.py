"""
Regression tests: /api/player/volume is broadcast-only (#3722, test debt #3736)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Volume is a client-side concern: the backend never mixes audio for playback —
bytes leave the engine and go straight to the WebSocket, and the frontend
AudioPlaybackEngine applies gain via a Web Audio API GainNode.

PlaybackService.set_volume used to be wrapped in
`if hasattr(self.audio_player, 'set_volume'):`, a silent no-op because the
engine method has never existed. #3722 removed the guard and documented the
route as broadcast-only. These tests pin that contract: the broadcast fires with
the 0-100 payload, and the engine is never asked to change gain.

A MagicMock audio player auto-creates any attribute, so `hasattr` is always True
against it — asserting `set_volume` was *not called* is what catches a
re-introduced engine call.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from services.playback_service import PlaybackService


def _make_service():
    """Return (service, audio_player, connection_manager) with mocked deps."""
    audio_player = MagicMock()

    state_manager = MagicMock()
    state_manager.set_playing = AsyncMock()

    connection_manager = MagicMock()
    connection_manager.broadcast = AsyncMock()

    service = PlaybackService(
        audio_player=audio_player,
        player_state_manager=state_manager,
        connection_manager=connection_manager,
    )
    return service, audio_player, connection_manager


class TestSetVolumeBroadcastsOnly:
    """The route's only job is telling every client what the slider now reads."""

    @pytest.mark.asyncio
    async def test_broadcasts_volume_on_0_to_100_scale(self):
        service, _player, connections = _make_service()

        result = await service.set_volume(0.5)

        connections.broadcast.assert_awaited_once()
        message = connections.broadcast.await_args.args[0]
        assert message["type"] == "volume_changed"
        assert message["data"]["volume"] == 50
        assert isinstance(message["data"]["seq"], int)
        assert result == {"message": "Volume set", "volume": 50}

    @pytest.mark.asyncio
    async def test_engine_set_volume_is_never_called(self):
        """#3722: the engine has no set_volume; nothing may try to call one."""
        service, player, _connections = _make_service()

        await service.set_volume(0.75)

        player.set_volume.assert_not_called()
        # No other engine transport call should be triggered either.
        player.play.assert_not_called()
        player.pause.assert_not_called()
        player.stop.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "volume,expected",
        # 0.006 -> 0.6 and 0.336 -> 33.6 both truncate to a different value
        # than they round to, so they fail if round() is ever swapped for int().
        [(0.0, 0), (0.006, 1), (0.336, 34), (0.5, 50), (0.999, 100), (1.0, 100)],
    )
    async def test_volume_scaling_is_rounded_not_truncated(self, volume, expected):
        service, _player, connections = _make_service()

        result = await service.set_volume(volume)

        assert result["volume"] == expected
        assert connections.broadcast.await_args.args[0]["data"]["volume"] == expected

    @pytest.mark.asyncio
    async def test_state_manager_is_not_touched(self):
        """Volume is not part of the sequenced transport state (#4751)."""
        service, _player, _connections = _make_service()

        await service.set_volume(0.3)

        service.player_state_manager.set_playing.assert_not_awaited()


class TestSetVolumeValidation:
    """Out-of-range and unavailable-player paths raise before broadcasting."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("volume", [-0.01, 1.01, 2.0, -5.0])
    async def test_out_of_range_volume_raises_and_does_not_broadcast(self, volume):
        service, _player, connections = _make_service()

        with pytest.raises(ValueError, match="between 0.0 and 1.0"):
            await service.set_volume(volume)

        connections.broadcast.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_missing_audio_player_raises(self):
        service, _player, connections = _make_service()
        service.audio_player = None

        with pytest.raises(ValueError, match="Audio player not available"):
            await service.set_volume(0.5)

        connections.broadcast.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_broadcast_failure_propagates(self):
        """A failing broadcast is an error, not a silently-swallowed no-op."""
        service, _player, connections = _make_service()
        connections.broadcast.side_effect = RuntimeError("socket gone")

        with pytest.raises(RuntimeError, match="socket gone"):
            await service.set_volume(0.5)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

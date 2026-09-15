"""
PlaybackService raises typed ServiceError subclasses, not bare ValueError
(#5338)

get_status/play/pause/stop/seek used to raise a plain ValueError for both
"the audio player / state manager is not available" (an outage, should map
to 503) and "the caller supplied bad input" (should map to 400) alike --
indistinguishable by type, so routers/player.py hard-coded one status per
call site regardless of which one actually happened (set_volume was fixed
for this same bug class in #5268; this closes the remaining sites). Both
ServiceUnavailable and InvalidRequest subclass ValueError, so any
pre-existing `except ValueError`/`pytest.raises(ValueError, ...)` caller
keeps working unchanged.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from services.errors import InvalidRequest, ServiceUnavailable
from services.playback_service import PlaybackService


def _make_service(audio_player=True, player_state_manager=True):
    """Return a PlaybackService with mocked deps; pass False to omit one."""
    player = MagicMock() if audio_player else None
    state_manager = MagicMock() if player_state_manager else None
    if state_manager is not None:
        state_manager.set_playing = AsyncMock()
    connection_manager = MagicMock()
    connection_manager.broadcast = AsyncMock()

    return PlaybackService(
        audio_player=player,
        player_state_manager=state_manager,
        connection_manager=connection_manager,
    )


class TestOutageConditionsRaiseServiceUnavailable:
    @pytest.mark.asyncio
    async def test_get_status_without_state_manager(self):
        service = _make_service(player_state_manager=False)
        with pytest.raises(ServiceUnavailable):
            await service.get_status()

    @pytest.mark.asyncio
    async def test_play_without_audio_player(self):
        service = _make_service(audio_player=False)
        with pytest.raises(ServiceUnavailable):
            await service.play()

    @pytest.mark.asyncio
    async def test_play_without_state_manager(self):
        service = _make_service(player_state_manager=False)
        with pytest.raises(ServiceUnavailable):
            await service.play()

    @pytest.mark.asyncio
    async def test_pause_without_audio_player(self):
        service = _make_service(audio_player=False)
        with pytest.raises(ServiceUnavailable):
            await service.pause()

    @pytest.mark.asyncio
    async def test_pause_without_state_manager(self):
        service = _make_service(player_state_manager=False)
        with pytest.raises(ServiceUnavailable):
            await service.pause()

    @pytest.mark.asyncio
    async def test_stop_without_audio_player(self):
        service = _make_service(audio_player=False)
        with pytest.raises(ServiceUnavailable):
            await service.stop()

    @pytest.mark.asyncio
    async def test_seek_without_audio_player(self):
        service = _make_service(audio_player=False)
        with pytest.raises(ServiceUnavailable):
            await service.seek(10.0)

    @pytest.mark.asyncio
    async def test_set_volume_without_audio_player(self):
        """Pins #5268's original fix, now via the shared InvalidRequest
        import in this file rather than a one-off."""
        service = _make_service(audio_player=False)
        with pytest.raises(ServiceUnavailable):
            await service.set_volume(0.5)


class TestBadInputRaisesInvalidRequest:
    @pytest.mark.asyncio
    async def test_seek_negative_position(self):
        """The headline bug (#5338): a negative seek position used to be
        indistinguishable from an outage at the router, which hard-coded
        503 for every ValueError from this method."""
        service = _make_service()
        with pytest.raises(InvalidRequest):
            await service.seek(-1.0)

    @pytest.mark.asyncio
    async def test_set_volume_out_of_range(self):
        service = _make_service()
        with pytest.raises(InvalidRequest):
            await service.set_volume(1.5)

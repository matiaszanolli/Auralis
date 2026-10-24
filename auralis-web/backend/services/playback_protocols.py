"""
Playback Protocols
~~~~~~~~~~~~~~~~~~

The local typing stubs ``PlaybackService`` programs against, split out of
playback_service.py (#6271): the real implementations are the engine's player
(``AudioPlayer``) and ``core.state_manager.PlayerStateManager`` — these
Protocols exist so the service does not import the engine.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from typing import Any, Protocol


class AudioPlayer(Protocol):
    """Protocol for audio player interface."""

    def play(self) -> None:
        """Start playback."""
        ...

    def pause(self) -> None:
        """Pause playback."""
        ...

    def stop(self) -> None:
        """Stop playback."""
        ...

    def seek(self, position: float) -> None:
        """Seek to position in seconds."""
        ...

    # #3722: deliberately NO set_volume method. Volume is applied
    # client-side via Web Audio API GainNode; the /api/player/volume
    # route exists only to broadcast volume state for cross-client
    # mirroring. The engine never mixes audio for playback.


class PlayerStateManager(Protocol):
    """Protocol for player state manager interface."""

    async def set_playing(
        self, playing: bool, *, broadcast: bool = True
    ) -> Any:
        """Update playing state."""
        ...

    async def broadcast_state(self, state: Any) -> None:
        """Broadcast a previously sequenced state snapshot."""
        ...

    async def set_track(self, track: Any) -> None:
        """Set current track."""
        ...

    def get_state(self) -> Any:
        """Get current state."""
        ...

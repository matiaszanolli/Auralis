"""
Playback Service Base
~~~~~~~~~~~~~~~~~~~~~

The collaborator plumbing ``PlaybackService`` inherits: the process-wide
transport lock (with its #3734/#5294/#4581/#4751 ordering history), the
deferred-snapshot broadcast helper and the read-only status view. Split from
playback_service.py in #6271 so the command module holds only the five
transport commands.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import logging
from typing import TYPE_CHECKING, Any, cast

from services.playback_event_sequencer import playback_event_sequencer

from .errors import require_collaborators
from .playback_protocols import PlayerStateManager

if TYPE_CHECKING:
    from player_state import PlayerState

logger = logging.getLogger(__name__)


class PlaybackServiceBase:
    """Hosts set ``player_state_manager`` in ``__init__`` (see PlaybackService)."""

    player_state_manager: PlayerStateManager

    @property
    def _playback_lock(self) -> asyncio.Lock:
        """Compatibility name for the process-wide transition lock.

        A setter-backed override preserves the lightweight ``__new__`` test
        seam used by the broadcast-timeout regression suite. Normal service
        construction never sets it and always resolves the shared lock.
        """
        override: asyncio.Lock | None = getattr(self, "_playback_lock_override", None)
        if override is not None:
            return override
        return playback_event_sequencer.transition_lock

    @_playback_lock.setter
    def _playback_lock(self, lock: asyncio.Lock) -> None:
        self._playback_lock_override = lock

    async def _broadcast_state_snapshot(self, snapshot: Any) -> None:
        """Send a deferred state snapshot when the collaborator returned one."""
        if snapshot is not None:
            await self.player_state_manager.broadcast_state(snapshot)

    async def get_status(self) -> "PlayerState":
        """
        Get current player status.

        Returns the ``PlayerState`` model itself, not ``model_dump()``: the
        route validates its result against ``response_model=PlayerState``, and
        a dump drops ``TrackInfo.filepath`` (``exclude=True``, #3205) while the
        field is still required, so any loaded track or queued entry made the
        validation fail with a 500 (#6422). FastAPI serializes the model with
        the exclusion applied.

        Returns:
            PlayerState: Player state with track info, playback status, queue

        Raises:
            Exception: If unable to retrieve status
        """
        require_collaborators(player_state_manager=self.player_state_manager)

        try:
            state = self.player_state_manager.get_state()
            return cast("PlayerState", state)
        except Exception as e:
            logger.error(f"Failed to get player status: {e}")
            raise


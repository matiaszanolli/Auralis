"""
Queue Service

Manages audio queue operations: get, set, add, remove, reorder, shuffle, clear.
Coordinates with AudioPlayer and PlayerStateManager to keep queue state synchronized.

QueueService is composed from per-concern mixins (#5237), all building on
QueueServiceBase (collaborators, set-queue sequencing state, the
``queue_changed`` broadcast):

- ``queue_set_mixin.QueueSetMixin``: set_queue
- ``queue_edit_mixin.QueueEditMixin``: add_track_to_queue, remove_track_from_queue, clear_queue
- ``queue_order_mixin.QueueOrderMixin``: reorder_queue, move_track_in_queue,
  shuffle_queue, unshuffle_queue

The one read operation, get_queue_info, lives here.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
from typing import Any

from .errors import ServiceUnavailable
from .queue_edit_mixin import QueueEditMixin
from .queue_order_mixin import QueueOrderMixin
from .queue_set_mixin import QueueSetMixin

logger = logging.getLogger(__name__)

# #5232: nothing outside this module ever imported AudioPlayerWithQueue or
# QueueManager via queue_service, so neither is re-exported; both live in
# queue_protocols.
__all__ = ['QueueService']


class QueueService(QueueSetMixin, QueueEditMixin, QueueOrderMixin):
    """
    Service for managing audio playback queue.

    Encapsulates queue manipulation logic and state synchronization.
    Coordinates between audio player queue and state manager.
    """

    async def get_queue_info(self) -> dict[str, Any]:
        """
        Get current playback queue info.

        Returns:
            dict: Queue data with tracks, current index, total tracks

        Raises:
            Exception: If unable to retrieve queue
        """
        if not self.audio_player:
            raise ServiceUnavailable("Audio player not available")

        try:
            queue_obj = getattr(self.audio_player, 'queue', None)
            if queue_obj is None:
                return {"tracks": [], "current_index": 0, "track_count": 0}

            if hasattr(queue_obj, 'get_queue_info'):
                info = dict(queue_obj.get_queue_info())
            else:
                info = {
                    "tracks": list(queue_obj.queue),
                    "current_index": queue_obj.current_index,
                    "track_count": len(queue_obj.queue),
                }

            # The engine queue is the source of truth for order/contents but
            # stores only filepaths; enrich those into full TrackInfo so the
            # response matches its schema instead of leaking bare dicts (#4374).
            raw_current = info.get("current_track")
            tracks = await self._enricher.enrich_tracks(info.get("tracks", []))
            info["tracks"] = tracks
            info["current_track"] = self._enricher.resolve_current_track(
                tracks, raw_current, info.get("current_index", 0)
            )
            info["repeat_mode"] = self._enricher.resolve_repeat_mode(info)
            return info
        except Exception as e:
            logger.error(f"Failed to get queue info: {e}")
            raise

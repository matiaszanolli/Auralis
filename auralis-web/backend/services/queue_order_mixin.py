"""
Queue Order Operations

Reorder, move a single track, shuffle and unshuffle.

Part of QueueService, split out of services/queue_service.py (#5237).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import logging
from typing import Any

from websocket.outbound_messages import broadcast_typed

from .errors import InvalidRequest, OperationFailed
from .queue_service_base import QueueServiceBase

logger = logging.getLogger(__name__)


class QueueOrderMixin(QueueServiceBase):
    """Operations that change queue order without adding or removing entries."""

    async def reorder_queue(self, new_order: list[int]) -> dict[str, Any]:
        """
        Reorder the playback queue.

        Args:
            new_order: New order of track indices

        Returns:
            dict: Success message and queue size

        Raises:
            Exception: If order invalid or operation fails
        """
        self._require_queue()

        try:
            queue_manager = self.audio_player.queue

            # Validate new_order
            queue_size = queue_manager.get_queue_size()
            if len(new_order) != queue_size:
                raise InvalidRequest(
                    f"new_order length ({len(new_order)}) must match queue size ({queue_size})"
                )

            if set(new_order) != set(range(queue_size)):
                raise InvalidRequest(
                    "new_order must contain all indices from 0 to queue_size-1 exactly once"
                )

            async with self._queue_mutation():
                # Reorder queue
                success = queue_manager.reorder_tracks(new_order)
                if not success:
                    raise OperationFailed("Failed to reorder queue")

                # Get updated queue
                updated_queue = queue_manager.get_queue()

            # Broadcast queue update (fixes #3492)
            await self._broadcast_queue_changed(
                action="reordered",
                queue_size=len(updated_queue),
            )

            logger.info(f"Queue reordered with {len(updated_queue)} tracks")
            return {
                "message": "Queue reordered successfully",
                "queue_size": len(updated_queue)
            }

        except Exception as e:
            logger.error(f"Failed to reorder queue: {e}")
            raise

    async def move_track_in_queue(self, from_index: int, to_index: int) -> dict[str, Any]:
        """
        Move a track within the queue (drag-and-drop).

        Args:
            from_index: Current index of track
            to_index: Destination index

        Returns:
            dict: Success message and updated indices

        Raises:
            Exception: If indices invalid or operation fails
        """
        self._require_queue()

        try:
            queue_manager = self.audio_player.queue
            current_queue = await asyncio.to_thread(queue_manager.get_queue)

            # Validate indices
            queue_size = len(current_queue)
            if from_index < 0 or from_index >= queue_size:
                raise InvalidRequest(f"Invalid from_index: {from_index}")
            if to_index < 0 or to_index >= queue_size:
                raise InvalidRequest(f"Invalid to_index: {to_index}")

            async with self._queue_mutation():
                # Move under QueueManager's lock so the playing track is
                # preserved by identity and no stale current_index is
                # reapplied (#4776).
                success = await asyncio.to_thread(
                    queue_manager.move_track, from_index, to_index
                )
                if not success:
                    raise OperationFailed("Failed to move track")

            # Broadcast queue update (fixes #3492)
            await self._broadcast_queue_changed(
                action="reordered",
                from_index=from_index,
                to_index=to_index,
                queue_size=len(current_queue),
            )

            logger.info(f"Track moved from index {from_index} to {to_index}")
            return {
                "message": "Track moved successfully",
                "from_index": from_index,
                "to_index": to_index,
                "queue_size": len(current_queue)
            }

        except Exception as e:
            logger.error(f"Failed to move track in queue: {e}")
            raise

    async def _record_shuffle_state(self, enabled: bool) -> None:
        """Mirror the engine's shuffle flag into PlayerState.

        Nothing wrote ``shuffle_enabled`` there, so every ``player_state`` snapshot carried
        False and the next one (a repeat toggle, a reconnect push) switched the UI's shuffle
        off while the queue stayed shuffled (#5899). Best-effort: a failed state update must
        not fail the shuffle that already happened.
        """
        if self.player_state_manager is None:
            return
        try:
            await self.player_state_manager.update_state(shuffle_enabled=enabled)
        except Exception as e:
            logger.warning(f"Could not record shuffle state in PlayerState: {e}")

    async def shuffle_queue(self) -> dict[str, Any]:
        """
        Shuffle the playback queue (keeps current track in place).

        Returns:
            dict: Success message and queue size

        Raises:
            Exception: If operation fails
        """
        self._require_queue()

        try:
            queue_manager = self.audio_player.queue

            async with self._queue_mutation():
                # Shuffle queue
                queue_manager.shuffle()

                # Get updated queue
                updated_queue = queue_manager.get_queue()

            # Broadcast queue update (fixes #3492 — also emit queue_shuffled
            # so the dedicated frontend subscriber gets the is_shuffled flag)
            await self._broadcast_queue_changed(
                action="shuffled",
                queue_size=len(updated_queue),
            )
            await broadcast_typed(
                self.connection_manager,
                "queue_shuffled",
                {"is_shuffled": True},
            )
            await self._record_shuffle_state(True)

            logger.info(f"Queue shuffled ({len(updated_queue)} tracks)")
            return {
                "message": "Queue shuffled successfully",
                "queue_size": len(updated_queue)
            }

        except Exception as e:
            logger.error(f"Failed to shuffle queue: {e}")
            raise

    async def unshuffle_queue(self) -> dict[str, Any]:
        """
        Restore the pre-shuffle queue order.

        Returns:
            dict: Success message and queue size

        Raises:
            Exception: If operation fails
        """
        self._require_queue()

        try:
            queue_manager = self.audio_player.queue

            async with self._queue_mutation():
                if not queue_manager.unshuffle():
                    # The snapshot is gone (an edit dropped it) but shuffle is off now, and the
                    # UI has already flipped; keep PlayerState in step (#5936).
                    await self._record_shuffle_state(False)
                    return {
                        "message": "No shuffle to undo",
                        "queue_size": queue_manager.get_queue_size()
                    }

                updated_queue = queue_manager.get_queue()

            await self._broadcast_queue_changed(
                action="unshuffled",
                queue_size=len(updated_queue),
            )
            await broadcast_typed(
                self.connection_manager,
                "queue_shuffled",
                {"is_shuffled": False},
            )
            await self._record_shuffle_state(False)

            logger.info(f"Queue unshuffled ({len(updated_queue)} tracks)")
            return {
                "message": "Queue restored to original order",
                "queue_size": len(updated_queue)
            }

        except Exception as e:
            logger.error(f"Failed to unshuffle queue: {e}")
            raise

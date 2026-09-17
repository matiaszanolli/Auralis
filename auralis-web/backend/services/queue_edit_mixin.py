"""
Queue Edit Operations

Add a track, remove a track, clear the queue.

Part of QueueService, split out of services/queue_service.py (#5237).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import logging
from typing import Any

from .errors import (
    InvalidRequest,
    OperationFailed,
    ResourceNotFound,
    ServiceUnavailable,
)
from .queue_service_base import QueueServiceBase

logger = logging.getLogger(__name__)


class QueueEditMixin(QueueServiceBase):
    """Operations that add or remove queue entries."""

    async def add_track_to_queue(self, track_id: int, position: int | None = None) -> dict[str, Any]:
        """
        Add a track to queue at specific position.

        Args:
            track_id: Track ID to add
            position: Position to insert at (None = append to end)

        Returns:
            dict: Success message and updated queue info

        Raises:
            Exception: If track not found or operation fails
        """
        if not self.audio_player or not hasattr(self.audio_player, 'queue'):
            raise ServiceUnavailable("Queue manager not available")
        if not self.library_database:
            raise ServiceUnavailable("Library manager not available")

        try:
            # Get track from library — sync DB call, offload (#3554).
            track = await asyncio.to_thread(
                self.library_database.tracks.get_by_id, track_id
            )
            if not track:
                raise ResourceNotFound(f"Track {track_id} not found")

            queue_manager = self.audio_player.queue
            track_info = {'id': track.id, 'filepath': track.filepath}

            # #5320: invalidate any in-flight set_queue request before
            # mutating the engine, and serialize the mutation itself against
            # set_queue's own engine section — see
            # QueueServiceBase._invalidate_set_queue_generation.
            await self._invalidate_set_queue_generation()
            async with self._set_queue_engine_lock:
                # Add to queue at position
                if position is not None:
                    position = await asyncio.to_thread(
                        queue_manager.insert_track, position, track_info
                    )
                else:
                    # QueueController exposes add_track; add_to_queue never
                    # existed and made every default append request fail (#4870).
                    await asyncio.to_thread(queue_manager.add_track, track_info)

                # Get updated queue for broadcasting
                updated_queue = await asyncio.to_thread(queue_manager.get_queue)

            # Broadcast queue update (fixes #3492 — was `queue_updated` which
            # the frontend never subscribed to)
            await self._broadcast_queue_changed(
                action="added",
                track_id=track_id,
                position=position,
                queue_size=len(updated_queue),
            )

            logger.info(f"Track {track_id} added to queue at position {position}")
            return {
                "message": "Track added to queue",
                "track_id": track_id,
                "position": position,
                "queue_size": len(updated_queue)
            }

        except Exception as e:
            logger.error(f"Failed to add track to queue: {e}")
            raise

    async def remove_track_from_queue(self, index: int) -> dict[str, Any]:
        """
        Remove track from queue at specified index.

        Args:
            index: Track index to remove

        Returns:
            dict: Success message and updated queue size

        Raises:
            Exception: If index invalid or operation fails
        """
        if not self.audio_player or not hasattr(self.audio_player, 'queue'):
            raise ServiceUnavailable("Queue manager not available")

        try:
            queue_manager = self.audio_player.queue

            # Validate index
            queue_size = queue_manager.get_queue_size()
            if index < 0 or index >= queue_size:
                raise InvalidRequest(f"Invalid index: {index}")

            # #5320: invalidate any in-flight set_queue request before
            # mutating the engine, and serialize the mutation itself against
            # set_queue's own engine section — see
            # QueueServiceBase._invalidate_set_queue_generation.
            await self._invalidate_set_queue_generation()
            async with self._set_queue_engine_lock:
                # #5360: check whether the currently-playing track is the one
                # being removed, and remove it, in one atomic call — a
                # separate `index == queue_manager.current_index` read
                # followed by a separate remove_track(index) call left a gap
                # where auto-advance/next/previous/a second remove could move
                # current_index in between, staling the #2403 was_current
                # determination this reload/stop follow-up depends on.
                success, was_current = queue_manager.remove_if_index_matches_current(index)
                if not success:
                    raise OperationFailed("Failed to remove track")

                # If the removed track was playing, stop current audio and load the
                # new current track (or stop entirely if the queue is now empty).
                if was_current and self.audio_player:
                    new_current = queue_manager.get_current_track()
                    if new_current and hasattr(self.audio_player, 'load_file'):
                        file_path = new_current.get('filepath') or new_current.get('file_path')
                        if file_path:
                            await asyncio.to_thread(self.audio_player.load_file, file_path)
                            logger.info(f"Removed current track; loaded next: {new_current.get('id')}")
                    elif hasattr(self.audio_player, 'playback') and hasattr(self.audio_player.playback, 'stop'):
                        await asyncio.to_thread(self.audio_player.playback.stop)
                        logger.info("Removed only/last track; stopped playback")

                # Get updated queue
                updated_queue = queue_manager.get_queue()

            # Broadcast queue update (fixes #3492)
            await self._broadcast_queue_changed(
                action="removed",
                index=index,
                queue_size=len(updated_queue),
            )

            logger.info(f"Track at index {index} removed from queue")
            return {
                "message": "Track removed from queue",
                "index": index,
                "queue_size": len(updated_queue)
            }

        except Exception as e:
            logger.error(f"Failed to remove from queue: {e}")
            raise

    async def clear_queue(self) -> dict[str, Any]:
        """
        Clear the entire playback queue.

        Returns:
            dict: Success message

        Raises:
            Exception: If operation fails
        """
        if not self.audio_player or not hasattr(self.audio_player, 'queue'):
            raise ServiceUnavailable("Queue manager not available")
        if not self.player_state_manager:
            raise ServiceUnavailable("Player state manager not available")

        try:
            queue_manager = self.audio_player.queue

            # #5320: invalidate any in-flight set_queue request before
            # mutating the engine, and serialize the mutation itself against
            # set_queue's own engine section — see
            # QueueServiceBase._invalidate_set_queue_generation. This is the
            # exact race the issue describes: without it, a set_queue request
            # between its generation check and its engine-mutating steps
            # would still run load_file()/play() after this clear.
            await self._invalidate_set_queue_generation()
            async with self._set_queue_engine_lock:
                # Clear queue
            queue_manager.clear_queue()

                # Stop playback
                if hasattr(self.audio_player, 'stop'):
                    await asyncio.to_thread(self.audio_player.stop)

            # Update player state — outside the engine lock: set_playing/
            # set_track broadcast internally by default, and #4825 requires
            # _set_queue_engine_lock never cover a broadcast.
            await self.player_state_manager.set_playing(False)
            await self.player_state_manager.set_track(None, None)

            # Broadcast queue update (fixes #3492)
            await self._broadcast_queue_changed(
                action="cleared",
                queue_size=0,
            )

            logger.info("Queue cleared")
            return {"message": "Queue cleared successfully"}

        except Exception as e:
            logger.error(f"Failed to clear queue: {e}")
            raise

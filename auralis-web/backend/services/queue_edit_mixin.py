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

            # Add to queue at position
            if position is not None:
                position = await asyncio.to_thread(
                    queue_manager.insert_track, position, track_info
                )
            else:
                # QueueController exposes add_track; add_to_queue never existed
                # and made every default append request fail (#4870).
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

            # Detect whether the currently-playing track is the one being removed
            # (fixes #2403: without this check, audio continues from the removed track
            # while get_current_track() returns the next one — metadata/audio desync).
            was_current = (index == queue_manager.current_index)

            # Remove track from queue
            success = queue_manager.remove_track(index)
            if not success:
                raise OperationFailed("Failed to remove track")

            # If the removed track was playing, stop current audio and load the new
            # current track (or stop entirely if the queue is now empty).
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

            # Clear queue
            queue_manager.clear()

            # Stop playback
            if hasattr(self.audio_player, 'stop'):
                await asyncio.to_thread(self.audio_player.stop)

            # Update player state
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

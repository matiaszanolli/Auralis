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
    require_collaborators,
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
        self._require_queue()
        require_collaborators(library_manager=self.library_database)

        try:
            # Get track from library — sync DB call, offload (#3554).
            track = await asyncio.to_thread(
                self.library_database.tracks.get_by_id, track_id
            )
            if not track:
                raise ResourceNotFound(f"Track {track_id} not found")

            queue_manager = self.audio_player.queue
            track_info = {'id': track.id, 'filepath': track.filepath}

            async with self._queue_mutation():
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

    async def add_tracks_to_queue(self, track_ids: list[int]) -> dict[str, Any]:
        """
        Add multiple tracks to the queue, appending in the order given.

        Batch equivalent of `add_track_to_queue` used by the library's bulk
        "Add to queue" (#5651). Firing N single-add requests races their
        `asyncio.to_thread` DB lookups, so tracks appended in thread-pool
        completion order rather than selection order, and each request
        broadcast its own whole-queue `queue_changed`. Here the tracks are
        resolved in one offloaded batch and appended under a single engine
        lock with one broadcast.

        Missing tracks (removed by a scan between selection and submit) are
        skipped rather than failing the batch — same contract as the
        playlist batch add.

        Args:
            track_ids: Ordered track IDs to append.

        Returns:
            dict: Counts and updated queue size.

        Raises:
            ServiceUnavailable: If the queue manager or library is unavailable.
            InvalidRequest: If track_ids is empty.
            ResourceNotFound: If no requested track exists.
        """
        self._require_queue()
        require_collaborators(library_manager=self.library_database)
        if not track_ids:
            raise InvalidRequest("track_ids must not be empty")

        try:
            tracks_db = self.library_database.tracks

            def resolve() -> list[dict[str, Any]]:
                # Sequential inside one worker thread: order is the request's
                # order by construction, unlike N concurrent to_thread calls.
                found = []
                for track_id in track_ids:
                    track = tracks_db.get_by_id(track_id)
                    if track:
                        found.append({'id': track.id, 'filepath': track.filepath})
                return found

            track_infos = await asyncio.to_thread(resolve)
            if not track_infos:
                raise ResourceNotFound("None of the requested tracks were found")

            queue_manager = self.audio_player.queue

            async with self._queue_mutation():
                # QueueController.add_tracks appends in list order.
                await asyncio.to_thread(queue_manager.add_tracks, track_infos)

                # Get updated queue for broadcasting
                updated_queue = await asyncio.to_thread(queue_manager.get_queue)

            # One broadcast for the whole batch (#5651) — N single-adds
            # produced N whole-queue broadcasts each.
            await self._broadcast_queue_changed(
                action="added",
                queue_size=len(updated_queue),
            )

            added = len(track_infos)
            logger.info(f"Added {added} track(s) to queue ({len(track_ids)} requested)")
            return {
                "message": f"Added {added} track(s) to queue",
                "added_count": added,
                "requested_count": len(track_ids),
                "queue_size": len(updated_queue),
            }

        except Exception as e:
            logger.error(f"Failed to add tracks to queue: {e}")
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
        self._require_queue()

        try:
            queue_manager = self.audio_player.queue

            # Validate index
            queue_size = queue_manager.get_queue_size()
            if index < 0 or index >= queue_size:
                raise InvalidRequest(f"Invalid index: {index}")

            async with self._queue_mutation():
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
        self._require_queue()
        require_collaborators(player_state_manager=self.player_state_manager)

        try:
            queue_manager = self.audio_player.queue

            async with self._queue_mutation():
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

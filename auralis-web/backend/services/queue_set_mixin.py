"""
Queue Set Operation

``set_queue``: replace the whole queue from track IDs, sequenced by request
generation so concurrent calls cannot interleave (#3721/#4825).

Part of QueueService, split out of services/queue_service.py (#5237).

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import asyncio
import logging
from typing import Any

from .errors import InvalidRequest, ServiceUnavailable
from .queue_service_base import QueueServiceBase

logger = logging.getLogger(__name__)


class QueueSetMixin(QueueServiceBase):
    """Generation-sequenced whole-queue replacement."""

    async def set_queue(self, track_ids: list[int], start_index: int = 0) -> dict[str, Any]:
        """
        Set the playback queue from track IDs (updates single source of truth).

        #3721/#4825: requests receive a generation under `_set_queue_lock`.
        Slow lookups, broadcasts, and player calls run after release; stale
        generations stop before they can overwrite a newer request.

        Args:
            track_ids: List of track IDs to add to queue
            start_index: Index to start playback from

        Returns:
            dict: Success message and queue info

        Raises:
            Exception: If operation fails
        """
        if not self.audio_player:
            raise ServiceUnavailable("Audio player not available")
        if not self.player_state_manager:
            raise ServiceUnavailable("Player state manager not available")
        if not self.library_database:
            raise ServiceUnavailable("Library manager not available")

        async with self._set_queue_lock:
            self._next_set_queue_generation += 1
            generation = self._next_set_queue_generation
        return await self._set_queue_impl(track_ids, start_index, generation)

    async def _set_queue_impl(
        self, track_ids: list[int], start_index: int, generation: int
    ) -> dict[str, Any]:
        """Resolve and commit one generation of a set-queue request."""
        try:
            # Get tracks from library by IDs — single batched query via
            # get_by_ids when available, otherwise individual lookups in a
            # thread (fixes #3554 / BE-NEW-96: per-track sync calls
            # previously blocked the event loop for hundreds of ms on
            # large queues).
            tracks_repo = self.library_database.tracks
            if hasattr(tracks_repo, 'get_by_ids'):
                # TrackRepository.get_by_ids returns dict[int, Track] keyed by
                # track id — iterating it yields ints, not Track objects.
                # Previously this path built `{t.id: t for t in ...}` which
                # raised AttributeError on every set-queue call (#3554 batched
                # path regression).
                by_id = await asyncio.to_thread(tracks_repo.get_by_ids, track_ids) or {}
                # Preserve caller-supplied order, drop unknown ids.
                db_tracks = [by_id[tid] for tid in track_ids if tid in by_id]
            else:
                def _fetch_individually() -> list[Any]:
                    out: list[Any] = []
                    for track_id in track_ids:
                        t = tracks_repo.get_by_id(track_id)
                        if t:
                            out.append(t)
                    return out
                db_tracks = await asyncio.to_thread(_fetch_individually)

            if not db_tracks:
                raise InvalidRequest("No valid tracks found")

            # Convert to TrackInfo for state
            track_infos = [self.create_track_info_fn(t) for t in db_tracks]
            track_infos = [t for t in track_infos if t is not None]

            result = {
                "message": "Queue set successfully",
                "track_count": len(track_infos),
                "start_index": start_index
            }

            # Only the sequenced state mutation belongs in _set_queue_lock.
            # The snapshot broadcast happens after release (#4825).
            async with self._set_queue_lock:
                if generation < self._set_queue_generation:
                    return result
                # Only a request that resolved at least one valid track can
                # supersede an earlier request. A later invalid request must
                # not cancel a valid transition already in flight.
                self._set_queue_generation = generation
                queue_snapshot = await self.player_state_manager.set_queue(
                    track_infos, start_index, broadcast=False
                )

            if queue_snapshot is not None:
                await self.player_state_manager.broadcast_state(queue_snapshot)

            deferred_snapshots: list[Any] = []
            async with self._set_queue_engine_lock:
                async with self._set_queue_lock:
                    if generation != self._set_queue_generation:
                        return result

                # Sync player calls remain ordered, but never hold the state
                # mutation lock or a lock that also covers a broadcast.
                if hasattr(self.audio_player, 'queue'):
                    await asyncio.to_thread(
                        self.audio_player.queue.set_queue,
                        [t.filepath for t in db_tracks],
                        start_index,
                    )

                async with self._set_queue_lock:
                    if generation != self._set_queue_generation:
                        return result

                if start_index >= 0 and start_index < len(db_tracks):
                    current_track = db_tracks[start_index]

                    async with self._set_queue_lock:
                        if generation != self._set_queue_generation:
                            return result
                        track_snapshot = await self.player_state_manager.set_track(
                            current_track,
                            self.library_database,
                            broadcast=False,
                        )
                    if track_snapshot is not None:
                        deferred_snapshots.append(track_snapshot)

                    await asyncio.to_thread(
                        self.audio_player.load_file, current_track.filepath
                    )
                    async with self._set_queue_lock:
                        if generation != self._set_queue_generation:
                            return result

                    await asyncio.to_thread(self.audio_player.play)
                    async with self._set_queue_lock:
                        if generation != self._set_queue_generation:
                            return result
                        playing_snapshot = await self.player_state_manager.set_playing(
                            True, broadcast=False
                        )
                    if playing_snapshot is not None:
                        deferred_snapshots.append(playing_snapshot)

            for snapshot in deferred_snapshots:
                await self.player_state_manager.broadcast_state(snapshot)

            logger.info(f"Queue set to {len(track_infos)} tracks, starting at index {start_index}")
            return result

        except Exception as e:
            logger.error(f"Failed to set queue: {e}")
            raise

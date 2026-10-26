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
from collections.abc import Awaitable, Callable
from typing import Any

from .errors import InvalidRequest, require_collaborators
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
        require_collaborators(audio_player=self.audio_player, player_state_manager=self.player_state_manager, library=self.library_database)

        async with self._set_queue_lock:
            self._next_set_queue_generation += 1
            generation = self._next_set_queue_generation
        return await self._set_queue_impl(track_ids, start_index, generation)

    async def _superseded(self, generation: int) -> bool:
        """True when a later set-queue request has superseded *generation*.

        The check takes ``_set_queue_lock`` for the comparison only; it is a
        read, not part of any state mutation.
        """
        async with self._set_queue_lock:
            return generation != self._set_queue_generation

    async def _if_current_generation(
        self, generation: int, operation: Callable[[], Awaitable[Any]]
    ) -> tuple[bool, Any]:
        """Run *operation* under ``_set_queue_lock`` iff *generation* is current.

        Returns ``(True, result)``, or ``(False, None)`` when superseded. The
        check and the state mutation share one lock hold, exactly as the
        inlined ``async with lock: if stale: return`` blocks did.
        """
        async with self._set_queue_lock:
            if generation != self._set_queue_generation:
                return False, None
            return True, await operation()

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
                if await self._superseded(generation):
                    return result

                # Sync player calls remain ordered, but never hold the state
                # mutation lock or a lock that also covers a broadcast.
                if hasattr(self.audio_player, 'queue'):
                    await asyncio.to_thread(
                        self.audio_player.queue.set_queue,
                        [t.filepath for t in db_tracks],
                        start_index,
                    )

                if await self._superseded(generation):
                    return result

                if start_index >= 0 and start_index < len(db_tracks):
                    current_track = db_tracks[start_index]

                    current, track_snapshot = await self._if_current_generation(
                        generation,
                        lambda: self.player_state_manager.set_track(
                            current_track, broadcast=False
                        ),
                    )
                    if not current:
                        return result
                    if track_snapshot is not None:
                        deferred_snapshots.append(track_snapshot)

                    # current_track.filepath is deliberately NOT passed through
                    # validate_file_path (#5303): the accepted #4823 scanner
                    # policy follows symlinked subdirectories with no
                    # containment, so a legitimate library track can resolve
                    # outside get_allowed_directories() — and it must play.
                    # See validate_file_path's "Deliberate non-callers" note.
                    await asyncio.to_thread(
                        self.audio_player.load_file, current_track.filepath
                    )
                    if await self._superseded(generation):
                        return result

                    await asyncio.to_thread(self.audio_player.play)
                    current, playing_snapshot = await self._if_current_generation(
                        generation,
                        lambda: self.player_state_manager.set_playing(True, broadcast=False),
                    )
                    if not current:
                        return result
                    if playing_snapshot is not None:
                        deferred_snapshots.append(playing_snapshot)

            for snapshot in deferred_snapshots:
                await self.player_state_manager.broadcast_state(snapshot)

            logger.info(f"Queue set to {len(track_infos)} tracks, starting at index {start_index}")
            return result

        except Exception as e:
            logger.error(f"Failed to set queue: {e}")
            raise

"""
Queue Service

Manages audio queue operations: get, set, add, remove, reorder, shuffle, clear.
Coordinates with AudioPlayer and PlayerStateManager to keep queue state synchronized.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

import asyncio
import logging
from collections.abc import Callable
from typing import Any, Unpack

from websocket.outbound_messages import (
    QueueChangeAction,
    QueueChangedExtras,
    QueueChangedPayload,
    broadcast_typed,
)

from .errors import (
    InvalidRequest,
    OperationFailed,
    ResourceNotFound,
    ServiceUnavailable,
)
from .queue_enrichment import QueueEnricher
from .queue_protocols import AudioPlayerWithQueue, QueueManager

logger = logging.getLogger(__name__)

# Re-exported for backwards compatibility: these were defined here before
# #4260 split them out, and `QueueManager` is referenced by the Protocol's own
# consumers via this module.
__all__ = ['AudioPlayerWithQueue', 'QueueManager', 'QueueService']


class QueueService:
    """
    Service for managing audio playback queue.

    Encapsulates queue manipulation logic and state synchronization.
    Coordinates between audio player queue and state manager.
    """

    def __init__(
        self,
        audio_player: AudioPlayerWithQueue,
        player_state_manager: Any,
        library_database: Any,
        connection_manager: Any,
        create_track_info_fn: Callable[[Any], Any],
    ) -> None:
        """
        Initialize QueueService.

        Args:
            audio_player: AudioPlayer instance with queue support
            player_state_manager: PlayerStateManager instance
            library_database: LibraryDatabase (or any object exposing the
                repository accessors) used to resolve track rows
            connection_manager: WebSocket connection manager for broadcasts
            create_track_info_fn: Function to convert DB track to TrackInfo

        Raises:
            ValueError: If any required component is not available
        """
        self.audio_player: AudioPlayerWithQueue = audio_player
        self.player_state_manager: Any = player_state_manager
        self.library_database: Any = library_database
        self.connection_manager: Any = connection_manager
        self.create_track_info_fn: Callable[[Any], Any] = create_track_info_fn
        # Read-model derivation lives in QueueEnricher (#4260); it needs the
        # same three collaborators and no queue state of its own.
        self._enricher = QueueEnricher(
            player_state_manager, library_database, create_track_info_fn
        )
        # #3721: serialise concurrent set_queue() calls. set_queue runs
        # 7 awaitable steps with WS broadcasts and engine I/O; without
        # a service-level lock two near-simultaneous POSTs (double-click
        # "Play album", rapid playlist switch within RTT) can interleave
        # so the state-manager publishes track-B while the engine ends
        # up loaded+playing track-A. Resolution requires manual user
        # intervention. The lock only serialises set_queue; the other
        # mutating methods (add/remove/clear/reorder) each take their
        # own narrow snapshot under the existing audio_player.queue
        # _lock and are not in the same race class.
        self._set_queue_lock = asyncio.Lock()
        self._next_set_queue_generation = 0
        self._set_queue_generation = 0
        # Player calls still need ordered execution to preserve the original
        # #3721 engine consistency guarantee, but this lock never covers a WS
        # broadcast and does not block queue-state mutation (#4825).
        self._set_queue_engine_lock = asyncio.Lock()

    async def _broadcast_queue_changed(
        self,
        action: QueueChangeAction,
        **extras: Unpack[QueueChangedExtras],
    ) -> None:
        """Emit a `queue_changed` WS message with the canonical payload that
        the frontend's QueueChangedMessage type expects (fixes #3492).

        Hydrates the current queue from the audio_player's queue dicts (which
        only carry id + filepath) into full TrackInfo dicts via library
        lookups. Falls back to the raw dict if hydration fails.
        """
        try:
            if hasattr(self.audio_player, 'queue'):
                queue_obj = self.audio_player.queue
                if hasattr(queue_obj, 'get_queue_info'):
                    info = await asyncio.to_thread(queue_obj.get_queue_info)
                    raw_tracks = info.get('tracks', [])
                    current_index = info.get('current_index', -1)
                else:
                    raw_tracks = list(getattr(queue_obj, 'queue', []))
                    current_index = getattr(queue_obj, 'current_index', -1)
            else:
                raw_tracks = []
                current_index = -1
        except Exception as exc:
            logger.warning(f"queue_changed broadcast: failed to read queue: {exc}")
            raw_tracks = []
            current_index = -1

        track_ids: list[int] = []
        for entry in raw_tracks:
            if not isinstance(entry, dict):
                continue
            tid = entry.get('id')
            if tid is None:
                tid = entry.get('track_id')
            if isinstance(tid, int) and not isinstance(tid, bool):
                track_ids.append(tid)

        by_id: dict[int, Any] = {}
        if track_ids and self.library_database is not None:
            try:
                unique_ids = list(dict.fromkeys(track_ids))
                by_id = await asyncio.to_thread(
                    self.library_database.tracks.get_by_ids, unique_ids
                ) or {}
            except Exception as exc:
                logger.debug(f"queue_changed batch hydration failed: {exc}")

        hydrated: list[dict[str, Any]] = []
        for entry in raw_tracks:
            track_dict: dict[str, Any] | None = None
            try:
                if isinstance(entry, dict):
                    tid = entry.get('id')
                    if tid is None:
                        tid = entry.get('track_id')
                    db_track = (
                        by_id.get(tid)
                        if isinstance(tid, int) and not isinstance(tid, bool)
                        else None
                    )
                    if db_track is not None:
                        ti = self.create_track_info_fn(db_track)
                        if ti is not None and hasattr(ti, 'model_dump'):
                            track_dict = ti.model_dump()
                if track_dict is None:
                    # Fall back to raw queue entry shape
                    if isinstance(entry, dict):
                        track_dict = dict(entry)
                    else:
                        track_dict = {'filepath': entry}
            except Exception as exc:
                logger.debug(f"queue_changed hydration skipped one entry: {exc}")
                if isinstance(entry, dict):
                    track_dict = dict(entry)
                else:
                    track_dict = {'filepath': entry}
            hydrated.append(track_dict)

        payload: QueueChangedPayload = {
            'tracks': hydrated,
            'current_index': current_index,
            'action': action,
            **extras,
        }
        await broadcast_typed(self.connection_manager, "queue_changed", payload)

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
        if not self.audio_player or not hasattr(self.audio_player, 'queue'):
            raise ServiceUnavailable("Queue manager not available")

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
        if not self.audio_player or not hasattr(self.audio_player, 'queue'):
            raise ServiceUnavailable("Queue manager not available")

        try:
            queue_manager = self.audio_player.queue
            current_queue = await asyncio.to_thread(queue_manager.get_queue)

            # Validate indices
            queue_size = len(current_queue)
            if from_index < 0 or from_index >= queue_size:
                raise InvalidRequest(f"Invalid from_index: {from_index}")
            if to_index < 0 or to_index >= queue_size:
                raise InvalidRequest(f"Invalid to_index: {to_index}")

            # Move under QueueManager's lock so the playing track is preserved
            # by identity and no stale current_index is reapplied (#4776).
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

    async def shuffle_queue(self) -> dict[str, Any]:
        """
        Shuffle the playback queue (keeps current track in place).

        Returns:
            dict: Success message and queue size

        Raises:
            Exception: If operation fails
        """
        if not self.audio_player or not hasattr(self.audio_player, 'queue'):
            raise ServiceUnavailable("Queue manager not available")

        try:
            queue_manager = self.audio_player.queue

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
        if not self.audio_player or not hasattr(self.audio_player, 'queue'):
            raise ServiceUnavailable("Queue manager not available")

        try:
            queue_manager = self.audio_player.queue

            if not queue_manager.unshuffle():
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

            logger.info(f"Queue unshuffled ({len(updated_queue)} tracks)")
            return {
                "message": "Queue restored to original order",
                "queue_size": len(updated_queue)
            }

        except Exception as e:
            logger.error(f"Failed to unshuffle queue: {e}")
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

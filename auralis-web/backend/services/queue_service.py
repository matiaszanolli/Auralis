"""
Queue Service

Manages audio queue operations: get, set, add, remove, reorder, shuffle, clear.
Coordinates with AudioPlayer and PlayerStateManager to keep queue state synchronized.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

import logging
from typing import Dict, Any, List, Optional, Callable, Protocol, Tuple

logger = logging.getLogger(__name__)


class QueueManager(Protocol):
    """Protocol for queue manager interface."""

    def get_queue(self) -> List[Any]:
        """Get current queue."""
        ...

    def get_queue_size(self) -> int:
        """Get queue size."""
        ...

    def set_queue(self, queue: List[Any], index: int) -> None:
        """Set queue with start index."""
        ...

    def add_to_queue(self, item: Any) -> None:
        """Add item to queue."""
        ...

    def remove_track(self, index: int) -> bool:
        """Remove track at index."""
        ...

    def reorder_tracks(self, new_order: List[int]) -> bool:
        """Reorder tracks."""
        ...

    def shuffle(self) -> None:
        """Shuffle queue."""
        ...

    def clear(self) -> None:
        """Clear queue."""
        ...

    @property
    def current_index(self) -> int:
        """Get current index."""
        ...


class AudioPlayerWithQueue(Protocol):
    """Protocol for audio player with queue support."""

    @property
    def queue(self) -> QueueManager:
        """Get queue manager."""
        ...

    def load_file(self, path: str) -> None:
        """Load audio file."""
        ...

    def play(self) -> None:
        """Start playback."""
        ...

    def stop(self) -> None:
        """Stop playback."""
        ...


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
        library_manager: Any,
        connection_manager: Any,
        create_track_info_fn: Callable[[Any], Any],
    ) -> None:
        """
        Initialize QueueService.

        Args:
            audio_player: EnhancedAudioPlayer instance with queue support
            player_state_manager: PlayerStateManager instance
            library_manager: LibraryManager instance
            connection_manager: WebSocket connection manager for broadcasts
            create_track_info_fn: Function to convert DB track to TrackInfo

        Raises:
            ValueError: If any required component is not available
        """
        self.audio_player: AudioPlayerWithQueue = audio_player
        self.player_state_manager: Any = player_state_manager
        self.library_manager: Any = library_manager
        self.connection_manager: Any = connection_manager
        self.create_track_info_fn: Callable[[Any], Any] = create_track_info_fn

    async def get_queue_info(self) -> Dict[str, Any]:
        """
        Get current playback queue info.

        Returns:
            dict: Queue data with tracks, current index, total tracks

        Raises:
            Exception: If unable to retrieve queue
        """
        if not self.audio_player:
            raise ValueError("Audio player not available")

        try:
            if hasattr(self.audio_player, 'queue'):
                queue_obj = self.audio_player.queue
                if hasattr(queue_obj, 'get_queue_info'):
                    return queue_obj.get_queue_info()
                else:
                    return {
                        "tracks": list(queue_obj.queue),
                        "current_index": queue_obj.current_index,
                        "total_tracks": len(queue_obj.queue)
                    }
            else:
                return {"tracks": [], "current_index": 0, "total_tracks": 0}
        except Exception as e:
            logger.error(f"Failed to get queue info: {e}")
            raise

    async def set_queue(self, track_ids: List[int], start_index: int = 0) -> Dict[str, Any]:
        """
        Set the playback queue from track IDs (updates single source of truth).

        Args:
            track_ids: List of track IDs to add to queue
            start_index: Index to start playback from

        Returns:
            dict: Success message and queue info

        Raises:
            Exception: If operation fails
        """
        if not self.audio_player:
            raise ValueError("Audio player not available")
        if not self.player_state_manager:
            raise ValueError("Player state manager not available")
        if not self.library_manager:
            raise ValueError("Library manager not available")

        try:
            # Get tracks from library by IDs
            db_tracks = []
            for track_id in track_ids:
                track = self.library_manager.tracks.get_by_id(track_id)
                if track:
                    db_tracks.append(track)

            if not db_tracks:
                raise ValueError("No valid tracks found")

            # Convert to TrackInfo for state
            track_infos = [self.create_track_info_fn(t) for t in db_tracks]
            track_infos = [t for t in track_infos if t is not None]

            # Update state manager (broadcasts automatically)
            await self.player_state_manager.set_queue(track_infos, start_index)

            # Set queue in actual player
            if hasattr(self.audio_player, 'queue'):
                self.audio_player.queue.set_queue([t.filepath for t in db_tracks], start_index)

            # Load and start playing if requested
            if start_index >= 0 and start_index < len(db_tracks):
                current_track = db_tracks[start_index]

                # Update state with current track
                await self.player_state_manager.set_track(current_track, self.library_manager)

                # Load the track in player
                self.audio_player.load_file(current_track.filepath)

                # Start playback
                self.audio_player.play()

                # Update playing state
                await self.player_state_manager.set_playing(True)

            logger.info(f"Queue set to {len(track_infos)} tracks, starting at index {start_index}")
            return {
                "message": "Queue set successfully",
                "track_count": len(track_infos),
                "start_index": start_index
            }

        except Exception as e:
            logger.error(f"Failed to set queue: {e}")
            raise

    async def add_track_to_queue(self, track_id: int, position: Optional[int] = None) -> Dict[str, Any]:
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
            raise ValueError("Queue manager not available")
        if not self.library_manager:
            raise ValueError("Library manager not available")

        try:
            # Get track from library
            track = self.library_manager.tracks.get_by_id(track_id)
            if not track:
                raise ValueError(f"Track {track_id} not found")

            queue_manager = self.audio_player.queue

            # Add to queue at position
            if position is not None:
                # Insert at specific position
                current_queue = queue_manager.get_queue()
                current_queue.insert(position, track.filepath)
                queue_manager.set_queue(current_queue, queue_manager.current_index)
            else:
                # Append to end
                queue_manager.add_to_queue(track.filepath)

            # Get updated queue for broadcasting
            updated_queue = queue_manager.get_queue()

            # Broadcast queue update
            await self.connection_manager.broadcast({
                "type": "queue_updated",
                "data": {
                    "action": "added",
                    "track_id": track_id,
                    "position": position,
                    "queue_size": len(updated_queue)
                }
            })

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

    async def remove_track_from_queue(self, index: int) -> Dict[str, Any]:
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
            raise ValueError("Queue manager not available")

        try:
            queue_manager = self.audio_player.queue

            # Validate index
            queue_size = queue_manager.get_queue_size()
            if index < 0 or index >= queue_size:
                raise ValueError(f"Invalid index: {index}")

            # Remove track from queue
            success = queue_manager.remove_track(index)
            if not success:
                raise ValueError("Failed to remove track")

            # Get updated queue
            updated_queue = queue_manager.get_queue()

            # Broadcast queue update
            await self.connection_manager.broadcast({
                "type": "queue_updated",
                "data": {
                    "action": "removed",
                    "index": index,
                    "queue_size": len(updated_queue)
                }
            })

            logger.info(f"Track at index {index} removed from queue")
            return {
                "message": "Track removed from queue",
                "index": index,
                "queue_size": len(updated_queue)
            }

        except Exception as e:
            logger.error(f"Failed to remove from queue: {e}")
            raise

    async def reorder_queue(self, new_order: List[int]) -> Dict[str, Any]:
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
            raise ValueError("Queue manager not available")

        try:
            queue_manager = self.audio_player.queue

            # Validate new_order
            queue_size = queue_manager.get_queue_size()
            if len(new_order) != queue_size:
                raise ValueError(
                    f"new_order length ({len(new_order)}) must match queue size ({queue_size})"
                )

            if set(new_order) != set(range(queue_size)):
                raise ValueError(
                    "new_order must contain all indices from 0 to queue_size-1 exactly once"
                )

            # Reorder queue
            success = queue_manager.reorder_tracks(new_order)
            if not success:
                raise ValueError("Failed to reorder queue")

            # Get updated queue
            updated_queue = queue_manager.get_queue()

            # Broadcast queue update
            await self.connection_manager.broadcast({
                "type": "queue_updated",
                "data": {
                    "action": "reordered",
                    "queue_size": len(updated_queue)
                }
            })

            logger.info(f"Queue reordered with {len(updated_queue)} tracks")
            return {
                "message": "Queue reordered successfully",
                "queue_size": len(updated_queue)
            }

        except Exception as e:
            logger.error(f"Failed to reorder queue: {e}")
            raise

    async def move_track_in_queue(self, from_index: int, to_index: int) -> Dict[str, Any]:
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
            raise ValueError("Queue manager not available")

        try:
            queue_manager = self.audio_player.queue
            current_queue = queue_manager.get_queue()

            # Validate indices
            queue_size = len(current_queue)
            if from_index < 0 or from_index >= queue_size:
                raise ValueError(f"Invalid from_index: {from_index}")
            if to_index < 0 or to_index >= queue_size:
                raise ValueError(f"Invalid to_index: {to_index}")

            # Move track
            track = current_queue.pop(from_index)
            current_queue.insert(to_index, track)

            # Update queue
            queue_manager.set_queue(current_queue, queue_manager.current_index)

            # Broadcast queue update
            await self.connection_manager.broadcast({
                "type": "queue_updated",
                "data": {
                    "action": "moved",
                    "from_index": from_index,
                    "to_index": to_index,
                    "queue_size": len(current_queue)
                }
            })

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

    async def shuffle_queue(self) -> Dict[str, Any]:
        """
        Shuffle the playback queue (keeps current track in place).

        Returns:
            dict: Success message and queue size

        Raises:
            Exception: If operation fails
        """
        if not self.audio_player or not hasattr(self.audio_player, 'queue'):
            raise ValueError("Queue manager not available")

        try:
            queue_manager = self.audio_player.queue

            # Shuffle queue
            queue_manager.shuffle()

            # Get updated queue
            updated_queue = queue_manager.get_queue()

            # Broadcast queue update
            await self.connection_manager.broadcast({
                "type": "queue_updated",
                "data": {
                    "action": "shuffled",
                    "queue_size": len(updated_queue)
                }
            })

            logger.info(f"Queue shuffled ({len(updated_queue)} tracks)")
            return {
                "message": "Queue shuffled successfully",
                "queue_size": len(updated_queue)
            }

        except Exception as e:
            logger.error(f"Failed to shuffle queue: {e}")
            raise

    async def clear_queue(self) -> Dict[str, Any]:
        """
        Clear the entire playback queue.

        Returns:
            dict: Success message

        Raises:
            Exception: If operation fails
        """
        if not self.audio_player or not hasattr(self.audio_player, 'queue'):
            raise ValueError("Queue manager not available")
        if not self.player_state_manager:
            raise ValueError("Player state manager not available")

        try:
            queue_manager = self.audio_player.queue

            # Clear queue
            queue_manager.clear()

            # Stop playback
            if hasattr(self.audio_player, 'stop'):
                self.audio_player.stop()

            # Update player state
            await self.player_state_manager.set_playing(False)
            await self.player_state_manager.set_track(None, None)

            # Broadcast queue update
            await self.connection_manager.broadcast({
                "type": "queue_updated",
                "data": {
                    "action": "cleared",
                    "queue_size": 0
                }
            })

            logger.info("Queue cleared")
            return {"message": "Queue cleared successfully"}

        except Exception as e:
            logger.error(f"Failed to clear queue: {e}")
            raise

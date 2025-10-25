"""
Player State Manager
~~~~~~~~~~~~~~~~~~~

Centralized state management and broadcasting for Auralis player.
Single source of truth that broadcasts state changes via WebSocket.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

import asyncio
import threading
import logging
from typing import Optional, List, Callable
from player_state import PlayerState, PlaybackState, TrackInfo, create_track_info

logger = logging.getLogger(__name__)


class PlayerStateManager:
    """
    Centralized player state manager.

    Maintains the single source of truth for player state and broadcasts
    changes to all connected clients via WebSocket.
    """

    def __init__(self, websocket_manager):
        """
        Initialize state manager

        Args:
            websocket_manager: WebSocket connection manager for broadcasting
        """
        self.state = PlayerState()
        self.ws_manager = websocket_manager
        self._lock = threading.Lock()
        self._position_update_task = None

    def get_state(self) -> PlayerState:
        """Get current player state (thread-safe)"""
        with self._lock:
            return self.state.model_copy(deep=True)

    async def update_state(self, **kwargs):
        """
        Update player state and broadcast changes

        Args:
            **kwargs: Fields to update in PlayerState
        """
        with self._lock:
            # Update state fields
            for key, value in kwargs.items():
                if hasattr(self.state, key):
                    setattr(self.state, key, value)

            # Sync dependent fields
            self.state.is_playing = (self.state.state == PlaybackState.PLAYING)
            self.state.is_paused = (self.state.state == PlaybackState.PAUSED)

            if self.state.current_track:
                self.state.duration = self.state.current_track.duration

            # Get snapshot for broadcasting
            state_snapshot = self.state.model_copy(deep=True)

        # Broadcast to all connected clients
        await self._broadcast_state(state_snapshot)

    async def set_track(self, track, library_manager):
        """
        Set current track and broadcast

        Args:
            track: Track object from database
            library_manager: Library manager to fetch track details
        """
        if track is None:
            await self.update_state(
                current_track=None,
                current_time=0.0,
                duration=0.0,
                state=PlaybackState.STOPPED
            )
            return

        # Convert to TrackInfo
        track_info = create_track_info(track)

        await self.update_state(
            current_track=track_info,
            current_time=0.0,
            duration=track_info.duration if track_info else 0.0,
            state=PlaybackState.LOADING
        )

    async def set_playing(self, playing: bool):
        """Set playing state"""
        new_state = PlaybackState.PLAYING if playing else PlaybackState.PAUSED
        await self.update_state(state=new_state)

        # Start/stop position updates
        if playing:
            self._start_position_updates()
        else:
            self._stop_position_updates()

    async def set_position(self, position: float):
        """Set playback position"""
        await self.update_state(current_time=position)

    async def set_volume(self, volume: int):
        """Set volume level"""
        await self.update_state(
            volume=max(0, min(100, volume)),
            is_muted=(volume == 0)
        )

    async def set_queue(self, tracks: List[TrackInfo], start_index: int = 0):
        """Set playback queue"""
        current_track = tracks[start_index] if tracks and 0 <= start_index < len(tracks) else None
        await self.update_state(
            queue=tracks,
            queue_size=len(tracks),
            queue_index=start_index,
            current_track=current_track
        )

    async def next_track(self):
        """Move to next track in queue"""
        # Determine next track while holding lock (don't await inside lock)
        with self._lock:
            if self.state.queue_index < len(self.state.queue) - 1:
                new_index = self.state.queue_index + 1
                next_track = self.state.queue[new_index]
                has_next = True
            elif self.state.repeat_mode == "all":
                new_index = 0
                next_track = self.state.queue[0] if self.state.queue else None
                has_next = True
            else:
                # No next track
                has_next = False
                new_index = None
                next_track = None

        # Update state outside lock to avoid deadlock
        if not has_next:
            await self.update_state(state=PlaybackState.STOPPED)
            return None

        await self.update_state(
            queue_index=new_index,
            current_track=next_track,
            current_time=0.0
        )
        return next_track

    async def previous_track(self):
        """Move to previous track in queue"""
        # Determine action while holding lock (don't await inside lock)
        with self._lock:
            if self.state.current_time > 3.0:
                # Restart current track if > 3 seconds
                should_restart = True
                current_track = self.state.current_track
            elif self.state.queue_index > 0:
                should_restart = False
                new_index = self.state.queue_index - 1
                prev_track = self.state.queue[new_index]
            else:
                # No previous track
                return None

        # Execute state changes outside lock to avoid deadlock
        if should_restart:
            await self.set_position(0.0)
            return current_track

        await self.update_state(
            queue_index=new_index,
            current_track=prev_track,
            current_time=0.0
        )
        return prev_track

    async def _broadcast_state(self, state: PlayerState):
        """Broadcast state to all WebSocket clients"""
        await self.ws_manager.broadcast({
            "type": "player_state",
            "data": state.model_dump()
        })

    def _start_position_updates(self):
        """Start periodic position updates (called when playback starts)"""
        if self._position_update_task is None or self._position_update_task.done():
            self._position_update_task = asyncio.create_task(self._position_update_loop())

    def _stop_position_updates(self):
        """Stop position updates (called when playback pauses)"""
        if self._position_update_task and not self._position_update_task.done():
            self._position_update_task.cancel()
            self._position_update_task = None

    async def _position_update_loop(self):
        """Update position every second while playing"""
        try:
            while True:
                await asyncio.sleep(1.0)
                with self._lock:
                    if self.state.is_playing and self.state.current_track:
                        # Increment position
                        new_time = min(
                            self.state.current_time + 1.0,
                            self.state.duration
                        )
                        self.state.current_time = new_time

                        # Check if track ended
                        if new_time >= self.state.duration:
                            asyncio.create_task(self.next_track())
                            return

                        # Broadcast position update
                        state_snapshot = self.state.model_copy(deep=True)

                await self._broadcast_state(state_snapshot)
        except asyncio.CancelledError:
            pass  # Normal cancellation

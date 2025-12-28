# -*- coding: utf-8 -*-

"""
GaplessPlaybackEngine - Handles prebuffering and seamless track transitions

Responsibilities:
- Background prebuffering of next track
- Seamless track transitions (gapless playback)
- Thread management for prebuffering
- Buffer validation and synchronization
"""

import threading
import time
from typing import Any, Callable, Dict, Optional

import numpy as np

from ..io.loader import load
from ..utils.logging import debug, info, warning
from .audio_file_manager import AudioFileManager
from .queue_controller import QueueController


class GaplessPlaybackEngine:
    """
    Manages prebuffering and gapless playback transitions.

    Decoupled from playback state and queue management.
    Handles threading and buffer management for seamless transitions.
    """

    def __init__(
        self,
        file_manager: AudioFileManager,
        queue_controller: QueueController,
        prebuffer_enabled: bool = True
    ) -> None:
        self.file_manager = file_manager
        self.queue = queue_controller
        self.prebuffer_enabled = prebuffer_enabled

        # Prebuffer state
        self.next_track_buffer: Optional[np.ndarray] = None
        self.next_track_info: Optional[Dict[str, Any]] = None
        self.next_track_sample_rate: Optional[int] = None
        self.prebuffer_thread: Optional[threading.Thread] = None

        # Threading
        self.update_lock = threading.Lock()
        self.prebuffer_callbacks: list[Callable[[Dict[str, Any]], None]] = []

    def add_prebuffer_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Register callback when prebuffering completes"""
        self.prebuffer_callbacks.append(callback)

    def _notify_prebuffer_callbacks(self, track_info: Dict[str, Any]) -> None:
        """Notify callbacks that prebuffering completed"""
        for callback in self.prebuffer_callbacks:
            try:
                callback(track_info)
            except Exception as e:
                debug(f"Prebuffer callback error: {e}")

    def start_prebuffering(self) -> None:
        """
        Start background prebuffering of next track.

        Safe to call multiple times—won't start duplicate threads.
        """
        if not self.prebuffer_enabled:
            return

        # Only start if not already running
        if self.prebuffer_thread and self.prebuffer_thread.is_alive():
            debug("Prebuffer thread already running")
            return

        # Start background thread
        self.prebuffer_thread = threading.Thread(
            target=self._prebuffer_worker,
            daemon=True,
            name="GaplessPlayback-Prebuffer"
        )
        self.prebuffer_thread.start()
        debug("Started prebuffer thread")

    def _prebuffer_worker(self) -> None:
        """
        Background worker thread for prebuffering.

        Loads next track from queue without blocking playback.
        """
        try:
            # Get next track from queue (without advancing)
            next_track = self.queue.peek_next_track()
            if not next_track:
                info("No next track to prebuffer")
                return

            file_path = next_track.get('file_path') or next_track.get('path')
            if not file_path:
                warning("Next track has no file path")
                return

            info(f"Prebuffering next track: {file_path}")

            # Load audio
            audio_data, sample_rate = load(file_path, "target")

            # Store in buffer (thread-safe)
            with self.update_lock:
                self.next_track_buffer = audio_data
                self.next_track_info = next_track
                self.next_track_sample_rate = sample_rate

            info(f"Prebuffered: {file_path} ({len(audio_data) / sample_rate:.1f}s)")
            self._notify_prebuffer_callbacks(next_track)

        except Exception as e:
            warning(f"Prebuffering failed: {e}")
            with self.update_lock:
                self.next_track_buffer = None
                self.next_track_info = None
                self.next_track_sample_rate = None

    def has_prebuffered_track(self) -> bool:
        """Check if next track is prebuffered and ready"""
        with self.update_lock:
            return (self.next_track_buffer is not None and
                    self.next_track_info is not None)

    def get_prebuffered_track(self) -> tuple[Optional[np.ndarray], Optional[int]]:
        """
        Get prebuffered track data if available.

        Returns:
            (audio_data, sample_rate) or (None, None) if not ready
        """
        with self.update_lock:
            if self.has_prebuffered_track():
                audio = self.next_track_buffer
                sr = self.next_track_sample_rate
                return audio, sr
        return None, None

    def advance_with_prebuffer(self, was_playing: bool) -> bool:
        """
        Advance to next track using prebuffered audio if available.

        This provides gapless playback (<10ms gap vs ~100ms for normal load).

        Args:
            was_playing: Whether playback was active before transition

        Returns:
            bool: True if successfully advanced, False if no next track
        """
        # Get next track from queue (advances queue index)
        next_track = self.queue.next_track()
        if not next_track:
            info("No next track to advance to")
            return False

        file_path = next_track.get('file_path') or next_track.get('path')
        if not file_path:
            return False

        # Check for prebuffered track
        audio_data, sample_rate = self.get_prebuffered_track()

        if audio_data is not None and sample_rate is not None:
            # Use prebuffered audio (gapless!)
            info(f"Using prebuffered track (gapless): {file_path}")

            with self.update_lock:
                # Load directly into file manager
                self.file_manager.audio_data = audio_data
                self.file_manager.sample_rate = sample_rate
                self.file_manager.current_file = file_path

                # Clear prebuffer
                self.next_track_buffer = None
                self.next_track_info = None
                self.next_track_sample_rate = None

            info(f"Gapless transition complete: {file_path}")
        else:
            # Fallback to normal loading
            info(f"Prebuffer not available, loading: {file_path}")
            if not self.file_manager.load_file(file_path):
                return False

        # Start prebuffering next track for smooth chain
        self.start_prebuffering()

        return True

    def invalidate_prebuffer(self) -> None:
        """
        Invalidate prebuffered track.

        Call when queue changes unexpectedly.
        """
        with self.update_lock:
            self.next_track_buffer = None
            self.next_track_info = None
            self.next_track_sample_rate = None
        info("Prebuffer invalidated")

    def cleanup(self) -> None:
        """Clean up threads and resources"""
        if self.prebuffer_thread and self.prebuffer_thread.is_alive():
            # Give thread time to finish
            self.prebuffer_thread.join(timeout=2.0)

        self.invalidate_prebuffer()
        info("GaplessPlaybackEngine cleaned up")

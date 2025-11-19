# -*- coding: utf-8 -*-

"""
Enhanced Auralis Audio Player (Refactored)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Real-time audio player with advanced DSP processing and library integration

Refactored from monolithic design into 5 focused components:
- PlaybackController: State machine (PLAYING, PAUSED, STOPPED, etc.)
- AudioFileManager: File I/O and audio data access
- QueueController: Queue and playlist management
- GaplessPlaybackEngine: Prebuffering and seamless transitions
- IntegrationManager: Library, callbacks, statistics

Uses Facade pattern to maintain backward-compatible API.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
from typing import Optional, Dict, Any, List, Callable

from .config import PlayerConfig
from .realtime_processor import RealtimeProcessor
from .playback_controller import PlaybackController, PlaybackState
from .audio_file_manager import AudioFileManager
from .queue_controller import QueueController
from .gapless_playback_engine import GaplessPlaybackEngine
from .integration_manager import IntegrationManager
from ..core.processor import process as core_process
from ..library.manager import LibraryManager
from ..utils.logging import debug, info, warning, error

# Backward compatibility alias for old test code
QueueManager = QueueController


class EnhancedAudioPlayer:
    """
    Enhanced real-time audio player with advanced DSP and library integration.

    Facade that coordinates 5 specialized components for clean separation of concerns:
    - PlaybackController: State machine
    - AudioFileManager: File I/O
    - QueueController: Queue/playlist
    - GaplessPlaybackEngine: Prebuffering
    - IntegrationManager: Library/callbacks

    Features:
    - Advanced real-time DSP processing
    - Automatic mastering with multiple profiles
    - Queue management and playlist support
    - Gapless playback with prebuffering
    - Library integration and auto-reference selection
    - Performance monitoring and statistics

    API compatible with original EnhancedAudioPlayer.
    """

    def __init__(
        self,
        config: PlayerConfig = None,
        library_manager: LibraryManager = None
    ):
        """Initialize the enhanced audio player with components"""
        if config is None:
            config = PlayerConfig()

        self.config = config

        # Initialize components
        self.playback = PlaybackController()
        self.file_manager = AudioFileManager(config.sample_rate)
        self.queue = QueueController(library_manager)
        self.processor = RealtimeProcessor(config)
        self.gapless = GaplessPlaybackEngine(self.file_manager, self.queue)
        self.integration = IntegrationManager(
            self.playback,
            self.file_manager,
            self.queue,
            self.processor,
            library_manager
        )

        # Control flags
        self.auto_advance = True

        info("Enhanced AudioPlayer initialized (refactored architecture)")

    # ========== Playback Control (delegates to PlaybackController) ==========

    def play(self) -> bool:
        """Start playback"""
        if not self.file_manager.is_loaded():
            warning("No audio file loaded")
            return False
        return self.playback.play()

    def pause(self) -> bool:
        """Pause playback"""
        return self.playback.pause()

    def stop(self) -> bool:
        """Stop playback"""
        return self.playback.stop()

    def seek(self, position_seconds: float) -> bool:
        """
        Seek to a position in seconds.

        Args:
            position_seconds: Target position in seconds

        Returns:
            bool: True if successful
        """
        max_samples = self.file_manager.get_total_samples()
        position_samples = int(position_seconds * self.file_manager.sample_rate)
        return self.playback.seek(position_samples, max_samples)

    @property
    def state(self) -> PlaybackState:
        """Get current playback state"""
        return self.playback.state

    @state.setter
    def state(self, value: PlaybackState):
        """Set playback state (for compatibility)"""
        self.playback.state = value

    def is_playing(self) -> bool:
        """Check if currently playing"""
        return self.playback.is_playing()

    # ========== File Loading (delegates to AudioFileManager) ==========

    def load_file(self, file_path: str) -> bool:
        """
        Load an audio file for playback.

        Args:
            file_path: Path to the audio file

        Returns:
            bool: True if successful
        """
        self.playback.set_loading()

        if self.file_manager.load_file(file_path):
            self.playback.stop()

            # Start prebuffering next track
            self.gapless.start_prebuffering()

            self.integration._notify_callbacks({
                'action': 'file_loaded',
                'file': file_path
            })
            return True
        else:
            self.playback.set_error()
            return False

    def load_reference(self, file_path: str) -> bool:
        """
        Load a reference file for real-time mastering.

        Args:
            file_path: Path to the reference audio file

        Returns:
            bool: True if successful
        """
        success = self.file_manager.load_reference(file_path)
        if success:
            self.processor.set_reference_audio(self.file_manager.reference_data)
            self.integration._notify_callbacks({
                'action': 'reference_loaded',
                'file': file_path
            })
        return success

    def load_track_from_library(self, track_id: int) -> bool:
        """
        Load a track from the library by ID.

        Args:
            track_id: Database ID of the track

        Returns:
            bool: True if successful
        """
        self.playback.set_loading()

        if self.integration.load_track_from_library(track_id):
            self.playback.stop()
            self.gapless.start_prebuffering()
            return True
        else:
            self.playback.set_error()
            return False

    # ========== Queue Management (delegates to QueueController) ==========

    def next_track(self) -> bool:
        """
        Skip to next track in queue with gapless playback support.

        Returns:
            bool: True if advanced, False if no next track
        """
        was_playing = self.playback.is_playing()

        if self.gapless.advance_with_prebuffer(was_playing):
            self.integration.record_track_completion()

            if was_playing:
                self.playback.play()

            return True

        return False

    def previous_track(self) -> bool:
        """Skip to previous track in queue"""
        prev_track = self.queue.previous_track()
        if prev_track:
            file_path = prev_track.get('file_path') or prev_track.get('path')
            if file_path and self.load_file(file_path):
                if self.playback.is_playing():
                    self.playback.play()
                return True
        return False

    def add_to_queue(self, track_info: Dict[str, Any]):
        """Add a track to the playback queue"""
        self.queue.add_track(track_info)

        # If nothing is loaded, load this track
        if not self.file_manager.is_loaded():
            file_path = track_info.get('file_path') or track_info.get('filepath')
            track_id = track_info.get('id')

            if track_id:
                self.load_track_from_library(track_id)
            elif file_path:
                self.load_file(file_path)

    def add_track_to_queue(self, track_id: int) -> bool:
        """Add a track from the library to the queue"""
        return self.queue.add_track_from_library(track_id)

    def search_and_add_to_queue(self, query: str, limit: int = 10) -> int:
        """Search library and add results to queue"""
        return self.queue.search_and_add(query, limit)

    def load_playlist(self, playlist_id: int, start_index: int = 0) -> bool:
        """Load a playlist from the library"""
        if self.queue.load_playlist(playlist_id, start_index):
            current = self.queue.get_current_track()
            if current:
                track_id = current.get('id')
                if track_id:
                    return self.load_track_from_library(track_id)
        return False

    def clear_queue(self):
        """Clear the playback queue"""
        self.queue.clear_queue()
        self.gapless.invalidate_prebuffer()

    # ========== Audio Output (delegates to AudioFileManager + Processor) ==========

    def get_audio_chunk(self, chunk_size: int = None) -> np.ndarray:
        """
        Get a chunk of processed audio for playback.

        Args:
            chunk_size: Size of audio chunk to return

        Returns:
            Processed audio chunk (stereo, float32)
        """
        if chunk_size is None:
            chunk_size = self.config.buffer_size

        # Return silence if not playing
        if not self.file_manager.is_loaded() or not self.playback.is_playing():
            return np.zeros((chunk_size, 2), dtype=np.float32)

        # Get raw audio chunk
        chunk = self.file_manager.get_audio_chunk(
            self.playback.position,
            chunk_size
        )

        # Update position
        self.playback.position += len(chunk)

        # Check for end of track
        if self.playback.position >= self.file_manager.get_total_samples():
            if self.auto_advance and not self.queue.is_queue_empty():
                # Auto-advance in background
                import threading
                threading.Thread(
                    target=self._auto_advance_delayed,
                    daemon=True
                ).start()

        # Apply advanced real-time processing
        processed_chunk = self.processor.process_chunk(chunk)

        return processed_chunk

    def _auto_advance_delayed(self):
        """Delayed auto-advance to next track (background thread)"""
        import time
        time.sleep(0.1)  # Small delay to avoid race conditions
        if self.playback.is_playing():
            self.next_track()

    # ========== Effects Control (delegates to IntegrationManager) ==========

    def set_effect_enabled(self, effect_name: str, enabled: bool):
        """Enable/disable specific DSP effects"""
        self.integration.set_effect_enabled(effect_name, enabled)

    def set_auto_master_profile(self, profile: str):
        """Set auto-mastering profile"""
        self.integration.set_auto_master_profile(profile)

    # ========== Callbacks and State (delegates to various components) ==========

    def add_callback(self, callback: Callable):
        """Add callback for state updates"""
        self.integration.add_callback(callback)
        self.playback.add_callback(callback)

    def get_playback_info(self) -> Dict[str, Any]:
        """Get comprehensive playback information"""
        return self.integration.get_playback_info()

    def get_queue_info(self) -> Dict[str, Any]:
        """Get detailed queue information"""
        return self.queue.get_queue_info()

    # ========== Shuffle and Repeat (delegates to QueueController) ==========

    def set_shuffle(self, enabled: bool):
        """Enable/disable shuffle mode"""
        self.queue.set_shuffle(enabled)
        self.integration._notify_callbacks({'action': 'shuffle_changed', 'enabled': enabled})

    def set_repeat(self, enabled: bool):
        """Enable/disable repeat mode"""
        self.queue.set_repeat(enabled)
        self.integration._notify_callbacks({'action': 'repeat_changed', 'enabled': enabled})

    # ========== Properties for backward compatibility ==========

    @property
    def current_file(self) -> Optional[str]:
        """Get current audio file path"""
        return self.file_manager.current_file

    @property
    def current_track(self):
        """Get current track object from library"""
        return self.integration.current_track

    @current_track.setter
    def current_track(self, value):
        """Set current track (for compatibility)"""
        self.integration.current_track = value

    @property
    def reference_file(self) -> Optional[str]:
        """Get current reference file path"""
        return self.file_manager.reference_file

    @property
    def audio_data(self):
        """Get raw audio data"""
        return self.file_manager.audio_data

    @audio_data.setter
    def audio_data(self, value):
        """Set audio data (for compatibility)"""
        self.file_manager.audio_data = value

    @property
    def reference_data(self):
        """Get raw reference audio data"""
        return self.file_manager.reference_data

    @reference_data.setter
    def reference_data(self, value):
        """Set reference data (for compatibility)"""
        self.file_manager.reference_data = value

    @property
    def position(self) -> int:
        """Get current position in samples"""
        return self.playback.position

    @position.setter
    def position(self, value: int):
        """Set position (for compatibility)"""
        self.playback.position = value

    @property
    def sample_rate(self) -> int:
        """Get current sample rate"""
        return self.file_manager.sample_rate

    @sample_rate.setter
    def sample_rate(self, value: int):
        """Set sample rate (for compatibility)"""
        self.file_manager.sample_rate = value

    # ========== Cleanup ==========

    def cleanup(self):
        """Clean up resources"""
        self.stop()
        self.gapless.cleanup()
        self.integration.cleanup()
        info("AudioPlayer cleanup completed")

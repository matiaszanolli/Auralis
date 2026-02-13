"""
AudioFileManager - Handles audio file I/O operations

Responsibilities:
- Loading audio files (target and reference)
- Managing loaded audio data
- Providing audio chunks for playback
- Auto-resampling to target sample rate
"""

import os
from typing import cast

import numpy as np

from ..io.loader import load
from ..utils.logging import error, info


class AudioFileManager:
    """
    Manages audio file loading and data access.

    Decoupled from playback state, queue management, and processing.
    Only handles file I/O and audio data storage.
    """

    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate

        # Audio data
        self.audio_data: np.ndarray | None = None
        self.current_file: str | None = None

        # Reference audio
        self.reference_data: np.ndarray | None = None
        self.reference_file: str | None = None

    def load_file(self, file_path: str) -> bool:
        """
        Load an audio file for playback.

        Args:
            file_path: Path to the audio file

        Returns:
            bool: True if successful
        """
        try:
            if not os.path.exists(file_path):
                error(f"File not found: {file_path}")
                return False

            # Load audio using Auralis loader
            self.audio_data, loaded_sample_rate = load(file_path, "target")
            self.current_file = file_path
            self.sample_rate = loaded_sample_rate

            info(f"Loaded audio file: {file_path}")
            info(f"Duration: {self.get_duration():.1f}s")
            info(f"Sample rate: {self.sample_rate} Hz")
            info(f"Channels: {self.get_channel_count()}")

            return True

        except Exception as e:
            error(f"Failed to load file {file_path}: {e}")
            return False

    def load_reference(self, file_path: str) -> bool:
        """
        Load a reference file for mastering.

        Args:
            file_path: Path to the reference audio file

        Returns:
            bool: True if successful
        """
        try:
            if not os.path.exists(file_path):
                error(f"Reference file not found: {file_path}")
                return False

            # Load reference audio
            self.reference_data, ref_sample_rate = load(file_path, "reference")
            self.reference_file = file_path

            info(f"Reference loaded: {file_path}")
            info(f"Reference duration: {len(self.reference_data) / ref_sample_rate:.1f}s")

            return True

        except Exception as e:
            error(f"Failed to load reference {file_path}: {e}")
            return False

    def get_audio_chunk(
        self,
        start_position: int,
        chunk_size: int
    ) -> np.ndarray:
        """
        Get a chunk of audio data for playback.

        Args:
            start_position: Starting position in samples
            chunk_size: Number of samples to retrieve

        Returns:
            Audio chunk as numpy array (stereo, float32)
        """
        if self.audio_data is None:
            return np.zeros((chunk_size, 2), dtype=np.float32)

        # Extract chunk
        end = min(start_position + chunk_size, len(self.audio_data))
        chunk = self.audio_data[start_position:end].copy()

        # Ensure stereo format
        if len(chunk.shape) == 1:
            chunk = np.column_stack([chunk, chunk])
        elif chunk.shape[1] == 1:
            chunk = np.column_stack([chunk[:, 0], chunk[:, 0]])

        # Pad if necessary
        if len(chunk) < chunk_size:
            padding = np.zeros((chunk_size - len(chunk), 2), dtype=np.float32)
            chunk = np.vstack([chunk, padding])

        return chunk

    def get_duration(self) -> float:
        """Get current audio duration in seconds"""
        if self.audio_data is None:
            return 0.0
        return len(self.audio_data) / self.sample_rate

    def get_total_samples(self) -> int:
        """Get total number of samples in current audio"""
        if self.audio_data is None:
            return 0
        return len(self.audio_data)

    def get_channel_count(self) -> int:
        """Get number of audio channels"""
        if self.audio_data is None:
            return 0
        if len(self.audio_data.shape) == 1:
            return 1
        return cast(int, self.audio_data.shape[1])

    def is_loaded(self) -> bool:
        """Check if audio file is loaded"""
        return self.audio_data is not None

    def has_reference(self) -> bool:
        """Check if reference audio is loaded"""
        return self.reference_data is not None

    def clear_audio(self) -> None:
        """Clear loaded audio data"""
        self.audio_data = None
        self.current_file = None

    def clear_reference(self) -> None:
        """Clear loaded reference data"""
        self.reference_data = None
        self.reference_file = None

    def clear_all(self) -> None:
        """Clear all loaded audio"""
        self.clear_audio()
        self.clear_reference()

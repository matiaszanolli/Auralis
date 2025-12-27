"""
Level Manager
~~~~~~~~~~~~~

Manages RMS levels and smooth transitions between audio chunks.
Prevents audible volume jumps during chunk transitions.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# Configuration
MAX_LEVEL_CHANGE_DB = 1.5  # Maximum allowed level change between chunks in dB


class LevelManager:
    """
    Track and manage audio levels across chunks.

    Maintains RMS history and applies level smoothing to prevent
    audible volume jumps between chunk boundaries.
    """

    def __init__(self, max_level_change_db: float = MAX_LEVEL_CHANGE_DB):
        """
        Initialize LevelManager.

        Args:
            max_level_change_db: Maximum allowed RMS change between chunks (default: 1.5 dB)
        """
        self.max_level_change_db = max_level_change_db

        # History tracking
        self.rms_history: List[float] = []  # RMS levels of processed chunks (dB)
        self.gain_history: List[float] = []  # Gain adjustments applied (dB)

    @property
    def history(self) -> List[float]:
        """Get RMS history for analysis and visualization."""
        return self.rms_history.copy()

    @property
    def gain_adjustments(self) -> List[float]:
        """Get gain adjustment history."""
        return self.gain_history.copy()

    @property
    def current_rms(self) -> Optional[float]:
        """Get the last recorded RMS level, or None if no history."""
        return self.rms_history[-1] if self.rms_history else None

    def reset(self) -> None:
        """Reset history for a new track."""
        self.rms_history.clear()
        self.gain_history.clear()
        logger.debug("LevelManager reset for new track")

    def calculate_rms(self, audio: np.ndarray) -> float:
        """
        Calculate RMS level of audio in dB.

        Args:
            audio: Audio samples (can be 1D or 2D)

        Returns:
            RMS level in dB
        """
        if len(audio) == 0:
            logger.warning("RMS calculation for empty audio, returning -inf")
            return -np.inf

        rms = np.sqrt(np.mean(audio ** 2))
        rms_db = 20 * np.log10(rms + 1e-10)  # Add epsilon to avoid log(0)

        return float(rms_db)

    def smooth_transition(
        self,
        chunk: np.ndarray,
        chunk_index: int,
        apply_adjustment: bool = True
    ) -> Tuple[np.ndarray, float, bool]:
        """
        Smooth level transitions between chunks.

        Limits maximum level changes to prevent audible volume jumps.
        Applies gain adjustment if needed, or returns chunk unchanged if acceptable.

        Args:
            chunk: Processed audio chunk
            chunk_index: Index of this chunk
            apply_adjustment: Whether to apply gain adjustment (default: True)

        Returns:
            Tuple of (chunk, gain_adjustment_db, was_adjusted)
            - chunk: Original or gain-adjusted audio
            - gain_adjustment_db: Gain adjustment applied (dB)
            - was_adjusted: Whether adjustment was applied
        """
        # First chunk or no history: establish baseline
        if chunk_index == 0 or len(self.rms_history) == 0:
            current_rms = self.calculate_rms(chunk)
            self.rms_history.append(current_rms)
            self.gain_history.append(0.0)
            logger.debug(f"Chunk {chunk_index}: Established baseline (RMS: {current_rms:.1f} dB)")
            return chunk, 0.0, False

        # Calculate current and previous RMS
        current_rms = self.calculate_rms(chunk)
        previous_rms = self.rms_history[-1]

        # Calculate level difference
        level_diff_db = current_rms - previous_rms

        # Check if adjustment needed
        if abs(level_diff_db) > self.max_level_change_db:
            if not apply_adjustment:
                # Just record the difference without applying adjustment
                self.rms_history.append(current_rms)
                self.gain_history.append(0.0)
                logger.info(
                    f"Chunk {chunk_index}: Large level difference detected but not adjusted "
                    f"(RMS: {current_rms:.1f} dB, diff: {level_diff_db:.1f} dB)"
                )
                return chunk, 0.0, False

            # Calculate required gain adjustment to stay within limits
            target_diff = (
                self.max_level_change_db
                if level_diff_db > 0
                else -self.max_level_change_db
            )
            required_adjustment_db = target_diff - level_diff_db

            # Convert dB to linear gain
            gain_adjustment = 10 ** (required_adjustment_db / 20)

            # Apply gain adjustment
            chunk_adjusted = chunk * gain_adjustment

            # Verify adjustment
            adjusted_rms = self.calculate_rms(chunk_adjusted)

            logger.info(
                f"Chunk {chunk_index}: Smoothed level transition "
                f"(original RMS: {current_rms:.1f} dB, "
                f"adjusted RMS: {adjusted_rms:.1f} dB, "
                f"diff from previous: {level_diff_db:.1f} dB -> {target_diff:.1f} dB, "
                f"gain: {required_adjustment_db:.2f} dB)"
            )

            # Store adjusted values
            self.rms_history.append(adjusted_rms)
            self.gain_history.append(required_adjustment_db)

            return chunk_adjusted, required_adjustment_db, True

        else:
            # Level change is acceptable, no adjustment needed
            logger.debug(
                f"Chunk {chunk_index}: Level transition OK "
                f"(RMS: {current_rms:.1f} dB, diff: {level_diff_db:.1f} dB)"
            )
            self.rms_history.append(current_rms)
            self.gain_history.append(0.0)
            return chunk, 0.0, False

    def apply_gain(self, audio: np.ndarray, gain_db: float) -> np.ndarray:
        """
        Apply gain adjustment to audio.

        Args:
            audio: Audio samples
            gain_db: Gain adjustment in dB

        Returns:
            Gain-adjusted audio
        """
        if gain_db == 0.0:
            return audio

        gain_linear = 10 ** (gain_db / 20)
        return audio * gain_linear

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about level history.

        Returns:
            Dictionary with statistics (mean RMS, max adjustment, etc.)
        """
        if not self.rms_history:
            return {
                "mean_rms": None,
                "min_rms": None,
                "max_rms": None,
                "total_adjustments": 0,
                "total_chunks": 0,
            }

        return {
            "mean_rms": float(np.mean(self.rms_history)),
            "min_rms": float(np.min(self.rms_history)),
            "max_rms": float(np.max(self.rms_history)),
            "total_adjustments": sum(1 for g in self.gain_history if abs(g) > 0.01),
            "total_chunks": len(self.rms_history),
            "max_gain_adjustment": float(np.max(np.abs(self.gain_history))) if self.gain_history else 0.0,
        }

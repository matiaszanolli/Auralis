"""
Level Manager
~~~~~~~~~~~~~

Manages RMS levels and smooth transitions between audio chunks.
Prevents audible volume jumps during chunk transitions.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
from collections import deque
from typing import cast

import numpy as np

logger = logging.getLogger(__name__)

from .level_constants import (  # noqa: E402  (body-used below; see level_constants.py)
    GAIN_RAMP_SECONDS,
    LEVEL_SMOOTHING_GATE_DB,
    MAX_GAIN_CORRECTION_DB,
    MAX_LEVEL_CHANGE_DB,
    _clamp_gain_db,
)
from .level_transition import LevelTransitionMixin
class LevelManager(LevelTransitionMixin):
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

        # History tracking — capped at 256 entries so long sessions don't grow unboundedly
        self.rms_history: deque[float] = deque(maxlen=256)
        self.gain_history: deque[float] = deque(maxlen=256)

    @property
    def history(self) -> list[float]:
        """Get RMS history for analysis and visualization."""
        return list(self.rms_history)

    @property
    def gain_adjustments(self) -> list[float]:
        """Get gain adjustment history."""
        return list(self.gain_history)

    @property
    def current_rms(self) -> float | None:
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

        if not np.all(np.isfinite(audio)):
            # A NaN/Inf chunk must never enter rms_history (#4672): NaN
            # comparisons are always False, so `abs(level_diff_db) >
            # self.max_level_change_db` in smooth_transition silently takes
            # the no-adjustment branch and every later chunk in the track
            # compares against nan forever — smoothing stops applying with
            # no error. Fall back to the last known-good level so history
            # stays finite and smoothing keeps working for later chunks;
            # LEVEL_SMOOTHING_GATE_DB if there is no prior level yet.
            logger.warning("RMS calculation received non-finite audio; using last known level")
            return self.current_rms if self.current_rms is not None else LEVEL_SMOOTHING_GATE_DB

        rms = np.sqrt(np.mean(audio ** 2))
        rms_db = 20 * np.log10(rms + 1e-10)  # Add epsilon to avoid log(0)

        return float(rms_db)

    def record_cached_level(
        self,
        chunk: np.ndarray | None,
        chunk_index: int,
        gain_db: float = 0.0,
        rms_db: float | None = None,
    ) -> None:
        """Record a cache-hit chunk's true RMS and trailing gain (#4367).

        smooth_transition(apply_adjustment=False) always appends 0.0 to
        gain_history regardless of the gain actually baked into the cached
        samples, desyncing gain_history from what was really emitted — a
        subsequent cache-MISS chunk would then ramp from unity even though
        the cached chunk it followed ended at a non-zero gain. `gain_db` is
        the trailing gain captured when the chunk was originally processed
        and cached, so gain_history stays truthful.

        `rms_db` (#4669) is the cached chunk's already-known RMS, for callers
        that hold only a path to the cached WAV and must not pay a decode just
        to record a level. When it is None the RMS is computed from `chunk`,
        which must then be supplied.
        """
        if rms_db is None:
            if chunk is None:
                raise ValueError(
                    "record_cached_level requires either `chunk` or a precomputed `rms_db`"
                )
            rms_db = self.calculate_rms(chunk)
        current_rms = rms_db
        is_baseline = chunk_index == 0 or len(self.rms_history) == 0
        self.rms_history.append(current_rms)
        # Clamped (#4729) so a stale/unclamped legacy gain can't poison history.
        self.gain_history.append(0.0 if is_baseline else _clamp_gain_db(gain_db))

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

        # Type the scalar to the input so float32 stays float32 (#3831 sibling —
        # `audio * pyfloat` would promote to float64).
        gain_linear = audio.dtype.type(10 ** (gain_db / 20))
        return cast(np.ndarray, audio * gain_linear)

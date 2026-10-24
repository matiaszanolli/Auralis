#!/usr/bin/env python3

"""
Level Transition
~~~~~~~~~~~~~~~~

``smooth_transition`` and its gain-envelope helper, split out of
``LevelManager`` as a mixin (#6270): the chunk-to-chunk smoothing/ramping
math is independent of the RMS bookkeeping it reads. Hosts provide
``rms_history``, ``gain_history``, ``max_level_change_db`` and
``calculate_rms``.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
from collections import deque
from typing import TYPE_CHECKING

import numpy as np

from .level_constants import (
    GAIN_RAMP_SECONDS,
    LEVEL_SMOOTHING_GATE_DB,
    MAX_GAIN_CORRECTION_DB,
    _clamp_gain_db,
)

logger = logging.getLogger(__name__)


class LevelTransitionMixin:
    """Hosts provide ``rms_history``, ``gain_history``,
    ``max_level_change_db`` and ``calculate_rms(chunk) -> float``."""

    if TYPE_CHECKING:
        rms_history: deque[float]
        gain_history: deque[float]
        max_level_change_db: float

        def calculate_rms(self, audio: np.ndarray) -> float: ...  # pragma: no cover


    def _gain_envelope(
        self,
        n_samples: int,
        prev_gain: float,
        new_gain: float,
        sample_rate: int,
        dtype: np.dtype,
    ) -> np.ndarray:
        """Build a per-sample gain envelope: ramp prev_gain → new_gain over the
        first GAIN_RAMP_SECONDS, then hold new_gain (#3831).

        Returned in `dtype` so multiplying a float32 chunk stays float32 (no
        float64 promotion). A linear ramp from the previous chunk's gain keeps
        the boundary continuous instead of stepping by the full adjustment.
        """
        ramp_len = min(n_samples, max(1, int(round(GAIN_RAMP_SECONDS * sample_rate))))
        env = np.empty(n_samples, dtype=dtype)
        env[:ramp_len] = np.linspace(prev_gain, new_gain, ramp_len, dtype=dtype)
        env[ramp_len:] = dtype.type(new_gain)
        return env

    def smooth_transition(
        self,
        chunk: np.ndarray,
        chunk_index: int,
        apply_adjustment: bool = True,
        sample_rate: int = 44100,
    ) -> tuple[np.ndarray, float, bool]:
        """
        Smooth level transitions between chunks.

        Limits maximum level changes to prevent audible volume jumps.
        Applies gain adjustment if needed, or returns chunk unchanged if acceptable.

        Args:
            chunk: Processed audio chunk
            chunk_index: Index of this chunk
            apply_adjustment: Whether to apply gain adjustment (default: True)
            sample_rate: Sample rate of the chunk, used to size the gain ramp
                window (default: 44100)

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

        # A silent (or floored) chunk on either side carries no real level
        # information worth smoothing against — treating it as one produces a
        # runaway correction that bursts the following chunk (#4729). Record
        # the true RMS so history stays accurate, but apply no gain.
        if current_rms <= LEVEL_SMOOTHING_GATE_DB or previous_rms <= LEVEL_SMOOTHING_GATE_DB:
            self.rms_history.append(current_rms)
            self.gain_history.append(0.0)
            logger.debug(
                f"Chunk {chunk_index}: below silence floor "
                f"(current: {current_rms:.1f} dB, previous: {previous_rms:.1f} dB) "
                f"- skipping level adjustment"
            )
            return chunk, 0.0, False

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
            # Clamped as a last-resort safety net (#4729) — see MAX_GAIN_CORRECTION_DB.
            required_adjustment_db = _clamp_gain_db(target_diff - level_diff_db)

            # Convert dB to linear gain, typed to the chunk so float32 stays
            # float32 (#3831 — avoids the float64 promotion of `chunk * pyfloat`).
            new_gain = float(10 ** (required_adjustment_db / 20))
            # Ramp from the gain the previous chunk ended at, so the boundary is
            # continuous instead of stepping by the full adjustment (#3831).
            # Clamped (#4729) in case history already holds an unclamped legacy value.
            prev_gain_db = _clamp_gain_db(self.gain_history[-1] if self.gain_history else 0.0)
            prev_gain = float(10 ** (prev_gain_db / 20))

            env = self._gain_envelope(
                n_samples=len(chunk),
                prev_gain=prev_gain,
                new_gain=new_gain,
                sample_rate=sample_rate,
                dtype=chunk.dtype,
            )
            # Broadcast across channels for 2D (n, ch); multiply directly for 1D.
            # New array — never mutate the caller's chunk in place.
            chunk_adjusted = chunk * (env[:, None] if chunk.ndim == 2 else env)

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

            # #4352: the previous chunk may have ended holding a non-zero gain
            # across its whole body (the #3831 adjustment branch holds
            # `new_gain` flat after its ramp-in). Snapping straight back to
            # unity here would step the boundary by the full held gain. Ramp
            # back to unity over the same window #3831 uses instead — but
            # only for the live path (apply_adjustment=True); a cache-hit
            # recording call (apply_adjustment=False) must leave the
            # already-emitted chunk untouched (#3832).
            # Clamped (#4729) in case history already holds an unclamped legacy value.
            prev_gain_db = _clamp_gain_db(self.gain_history[-1] if self.gain_history else 0.0)
            if apply_adjustment and prev_gain_db != 0.0:
                prev_gain = float(10 ** (prev_gain_db / 20))
                env = self._gain_envelope(
                    n_samples=len(chunk),
                    prev_gain=prev_gain,
                    new_gain=1.0,
                    sample_rate=sample_rate,
                    dtype=chunk.dtype,
                )
                chunk = chunk * (env[:, None] if chunk.ndim == 2 else env)
                current_rms = self.calculate_rms(chunk)

            self.rms_history.append(current_rms)
            self.gain_history.append(0.0)
            return chunk, 0.0, False


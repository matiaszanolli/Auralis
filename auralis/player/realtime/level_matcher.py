"""
Real-time Level Matcher
~~~~~~~~~~~~~~~~~~~~~~~

Real-time RMS level matching with reference audio

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import threading
from typing import Any

import numpy as np

from ...utils.logging import debug, info
from ..config import PlayerConfig
from .gain_smoother import AdaptiveGainSmoother
from .peak_ceiling import StreamingPeakCeiling


class RealtimeLevelMatcher:
    """Real-time RMS level matching with reference audio"""

    def __init__(self, config: PlayerConfig):
        self.config = config
        self.enabled = False
        self.reference_rms: float | None = None
        self.target_rms_alpha = 0.01  # Smoothing for RMS calculation
        self.current_target_rms = 0.0  # 0 = unseeded; set_reference_audio() seeds it

        # Serialises concurrent calls to process() / set_reference_audio() so
        # the playback thread and any prefetch/lookahead thread cannot interleave
        # reads and writes to current_target_rms or gain_smoother (#2426).
        self._lock = threading.Lock()

        # Gain smoothing for artifact-free transitions
        self.gain_smoother = AdaptiveGainSmoother(
            attack_alpha=0.02,   # Fairly quick attack
            release_alpha=0.005  # Slower release to avoid pumping
        )

        # 0.95 ceiling as a per-sample envelope carried across chunks (#5721),
        # not a per-chunk `0.95 / max(|chunk|)` scalar that stepped at chunk edges.
        self.peak_ceiling = StreamingPeakCeiling(config.sample_rate)

        debug("RealtimeLevelMatcher initialized")

    def set_reference_audio(self, reference: np.ndarray | None) -> bool:
        """Set reference audio for level matching"""
        with self._lock:
            if reference is None:
                self.reference_rms = None
                self.enabled = False
                return False

            # Calculate RMS of reference audio
            self.reference_rms = np.sqrt(np.mean(reference ** 2))
            # Seed the smoothed target on the first reference after construction
            # or reset(): process() eases toward reference_rms from here, and from
            # 0 the first chunks got gain ~0.01 and faded in over ~7 s (#5707).
            # A later reference change still glides from the previous target.
            if self.current_target_rms == 0.0:
                self.current_target_rms = float(self.reference_rms)
            self.enabled = True
            info(f"Reference RMS set: {self.reference_rms:.6f}")
            return True

    def set_enabled(self, enabled: bool) -> None:
        """Enable/disable level matching under `_lock` (#4340).

        `process()` reads `self.enabled` under the same lock; a raw
        attribute write from the owning RealtimeProcessor (under its own,
        different lock) does not serialise against a concurrent process()
        call.
        """
        with self._lock:
            self.enabled = enabled

    def reset(self) -> None:
        """Reset to initial state under `_lock` (#4340).

        Mirrors AutoMasterProcessor's locked reset — `reference_rms`,
        `enabled`, and `gain_smoother` must only be mutated while holding
        this lock, since `process()` reads all three under it.
        """
        with self._lock:
            self.reference_rms = None
            self.current_target_rms = 0.0
            self.enabled = False
            self.gain_smoother = AdaptiveGainSmoother(
                attack_alpha=0.02,
                release_alpha=0.005,
            )
            self.peak_ceiling.reset()

    def process(self, audio: np.ndarray) -> np.ndarray:
        """Process audio chunk with level matching"""
        with self._lock:
            if not self.enabled or self.reference_rms is None or self.reference_rms == 0:
                return audio

            # Calculate current RMS
            current_rms = np.sqrt(np.mean(audio ** 2))

            if current_rms == 0:
                return audio

            # Smooth the target RMS to avoid sudden changes
            target_rms = self.reference_rms
            self.current_target_rms += (target_rms - self.current_target_rms) * self.target_rms_alpha

            # Calculate gain needed
            gain = self.current_target_rms / current_rms

            # Apply gain smoothing — returns a per-sample 1-D ramp (issue #2209)
            self.gain_smoother.set_target(gain)
            smooth_gain = self.gain_smoother.process(len(audio))  # shape (num_samples,)

        # Broadcast ramp over channels: (samples,) → (samples, 1) for 2-D audio
        if audio.ndim > 1:
            smooth_gain = smooth_gain[:, np.newaxis]

        # Apply gain with soft limiting to prevent clipping
        processed: np.ndarray = audio * smooth_gain

        # Limiter to prevent harsh clipping (#5721: smoothed across chunks)
        peak_limited: np.ndarray = self.peak_ceiling.apply(processed, 0.95)
        return peak_limited

    def get_stats(self) -> dict[str, Any]:
        """Get level matching statistics under `_lock` (#4551).

        The reader half of #4340, which locked this class's writers but left
        this method unguarded. `reset()` rebinds `gain_smoother` while holding
        `_lock`, so an unlocked read of `current_gain` and `target_gain` could
        straddle the swap and pair values from two different smoother
        instances; `enabled` and `reference_rms` could likewise be read from
        either side of a `reset()` / `set_reference_audio()` update.

        The critical section is four attribute reads with no I/O and no nested
        acquisition — strictly shorter than `process()`'s. Callers already
        establish the RealtimeProcessor.lock -> RealtimeLevelMatcher._lock
        ordering (`get_processing_info`, `reset_all_effects`), which is the
        same order `AutoMasterProcessor.get_stats` is called under, so this
        adds no new deadlock edge.
        """
        with self._lock:
            return {
                'enabled': self.enabled,
                'reference_loaded': self.reference_rms is not None,
                'reference_rms': self.reference_rms or 0.0,
                'current_gain': self.gain_smoother.current_gain,
                'target_gain': self.gain_smoother.target_gain,
            }

"""
Dynamic Loud Branch
~~~~~~~~~~~~~~~~~~~~

Processing strategy for dynamic loud (well-mastered) material (#4252).

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np

from ..mastering_config import SimpleMasteringConfig
from ..stages.hf_budget import hf_lift_factor
from ..utils import FingerprintUnpacker, StageRecorder
from .base import ProcessingBranch


class DynamicLoudBranch(ProcessingBranch):
    """
    Handle dynamic loud material (LUFS > -12, crest >= 13).

    Well-mastered tracks with good dynamics. Preserve the original character
    with minimal intervention - just gentle spectral enhancements.

    Processing steps:
    1. Pass-through (preserve dynamic range)
    2. Stereo width expansion (optional)
    3. Pre-EQ headroom reduction
    4. Gentle presence + air enhancements (reduced intensity)
    5. Safety limiter
    6. Mark for output normalization

    Defers final loudness/peak normalization to the unified pipeline stage
    (``needs_output_normalize=True``). See ``ProcessingBranch`` for the full
    canonical stage order and the gain-staging contract (#4103).
    """

    def apply(
        self,
        audio: np.ndarray,
        unpacker: FingerprintUnpacker,
        peak_db: float,
        effective_intensity: float,
        sample_rate: int,
        config: SimpleMasteringConfig,
        verbose: bool
    ) -> tuple[np.ndarray, dict]:
        """Apply dynamic loud material processing."""

        processed = audio.copy()
        recorder = StageRecorder()

        # Resonance notches — surgical, no harm if there are none to apply.
        processed, notch_info = self.pipeline._apply_resonance_notches(
            processed, sample_rate, verbose
        )
        recorder.add(notch_info)

        if verbose:
            print(f"   Dynamic loud → preserving original")
        recorder.add({'stage': 'passthrough'})

        # Stereo expansion for narrow mixes (brightness-aware)
        processed, width_info = self.pipeline._apply_stereo_expansion(
            processed, unpacker.stereo_width, effective_intensity, sample_rate, verbose,
            unpacker.bass_pct, unpacker.spectral_centroid, unpacker.air_pct, unpacker.phase_correlation
        )
        recorder.add(width_info)

        # Pre-EQ headroom: attenuate before spectral boosts
        pre_eq_headroom_db = config.PRE_EQ_HEADROOM_DB
        pre_eq_gain = 10 ** (pre_eq_headroom_db / 20)
        processed = processed * pre_eq_gain

        processed = self._assert_finite(processed, "DynamicLoud after dynamics/stereo")

        # Shared HF lift budget — see DynamicLoudBranch for rationale.
        hf_lift = hf_lift_factor(unpacker.presence_pct, unpacker.air_pct)

        # Harmonic exciter (only engages on dark/bandwidth-limited material).
        # Runs BEFORE presence/air so those shelves can lift the new harmonics.
        processed, exciter_info = self.pipeline._apply_harmonic_exciter(
            processed, unpacker.presence_pct, unpacker.air_pct, unpacker.spectral_rolloff,
            effective_intensity * config.DYNAMIC_LOUD_INTENSITY_FACTOR,
            sample_rate, verbose, hf_lift
        )
        recorder.add(exciter_info)

        # Clarity boost — Up-Mid bell for vocal/snare definition.
        processed, clarity_info = self.pipeline._apply_clarity_boost(
            processed, unpacker.upper_mid_pct,
            effective_intensity * config.DYNAMIC_LOUD_INTENSITY_FACTOR,
            sample_rate, verbose, hf_lift
        )
        recorder.add(clarity_info)

        # Gentle spectral enhancements (reduced intensity for well-mastered tracks)
        processed, presence_info = self.pipeline._apply_presence_enhancement(
            processed, unpacker.presence_pct, unpacker.upper_mid_pct,
            effective_intensity * config.DYNAMIC_LOUD_INTENSITY_FACTOR,
            sample_rate, verbose, hf_lift
        )
        recorder.add(presence_info)

        processed, air_info = self.pipeline._apply_air_enhancement(
            processed, unpacker.air_pct, unpacker.spectral_rolloff,
            effective_intensity * config.DYNAMIC_LOUD_INTENSITY_FACTOR,
            sample_rate, verbose, hf_lift
        )
        recorder.add(air_info)

        processed = self._assert_finite(processed, "DynamicLoud after spectral")

        # Safety peak limit after enhancements
        processed = self.pipeline._apply_safety_limiter(processed, verbose)
        processed = self._assert_finite(processed, "DynamicLoud after safety limiter")

        # Return with normalization flag
        info = recorder.to_dict()
        info['needs_output_normalize'] = True
        return processed, info

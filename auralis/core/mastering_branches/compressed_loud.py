"""
Compressed Loud Branch
~~~~~~~~~~~~~~~~~~~~~~~

Processing strategy for compressed loud material (#4252).

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np

from ..mastering_config import SimpleMasteringConfig
from ..processing.base import ExpansionStrategies
from ..stages.hf_budget import hf_lift_factor
from ..utils import FingerprintUnpacker, StageRecorder
from .base import ProcessingBranch


class CompressedLoudBranch(ProcessingBranch):
    """
    Handle compressed loud material (LUFS > -12, crest < 13).

    Modern mastering with loudness war compression. Needs gentle expansion
    to restore dynamics without pumping artifacts.

    Processing steps:
    1. RMS reduction expansion (skip if hyper-compressed)
    2. Stereo width expansion (brightness-aware)
    3. Pre-EQ headroom reduction
    4. Presence + air enhancements (moderate intensity)
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
        """Apply compressed loud material processing."""

        processed = audio.copy()
        recorder = StageRecorder()

        # Resonance notches first — surgical narrow cuts before any broad EQ,
        # so subsequent stages see the post-notch energy balance.
        processed, notch_info = self.pipeline._apply_resonance_notches(
            processed, sample_rate, verbose
        )
        recorder.add(notch_info)

        # Check for hyper-compression
        if unpacker.crest_db < config.HYPER_COMPRESSED_THRESHOLD_CREST:
            # Hyper-compressed: skip expansion entirely
            if verbose:
                print(f"   Hyper-compressed (LUFS {unpacker.lufs:.1f}, crest {unpacker.crest_db:.1f}) → skip expansion")
            recorder.add({'stage': 'skip_expansion', 'reason': 'hyper_compressed'})
        else:
            # Moderately compressed: gentle RMS reduction expansion
            target_crest_increase = min(
                config.MAX_TARGET_CREST_INCREASE_DB,
                config.MODERATE_COMPRESSED_MIN_CREST - unpacker.crest_db
            )
            expansion_amount = config.RMS_EXPANSION_AMOUNT

            if verbose:
                print(f"   Compressed loud (LUFS {unpacker.lufs:.1f}, crest {unpacker.crest_db:.1f}) → RMS expansion +{target_crest_increase:.1f} dB")

            # Apply RMS reduction expansion
            exp_params = {
                'target_crest_increase': target_crest_increase,
                'amount': expansion_amount
            }
            processed = ExpansionStrategies.apply_rms_reduction_expansion(processed, exp_params)
            recorder.add({'stage': 'rms_expansion', 'target_crest': target_crest_increase})

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

        processed = self._assert_finite(processed, "CompressedLoud after dynamics/stereo")

        # Shared HF lift budget — restrains the exciter + clarity + presence +
        # air stages from stacking into fizz on HF-dead sources (#engine).
        hf_lift = hf_lift_factor(unpacker.presence_pct, unpacker.air_pct)

        # Harmonic exciter (only engages on dark/bandwidth-limited material).
        # Runs BEFORE presence/air so those shelves can lift the new harmonics.
        processed, exciter_info = self.pipeline._apply_harmonic_exciter(
            processed, unpacker.presence_pct, unpacker.air_pct, unpacker.spectral_rolloff,
            effective_intensity * config.COMPRESSED_LOUD_INTENSITY_FACTOR,
            sample_rate, verbose, hf_lift
        )
        recorder.add(exciter_info)

        # Clarity boost — Up-Mid bell for sources missing vocal/snare definition.
        processed, clarity_info = self.pipeline._apply_clarity_boost(
            processed, unpacker.upper_mid_pct,
            effective_intensity * config.COMPRESSED_LOUD_INTENSITY_FACTOR,
            sample_rate, verbose, hf_lift
        )
        recorder.add(clarity_info)

        # Spectral enhancements (presence & air)
        processed, presence_info = self.pipeline._apply_presence_enhancement(
            processed, unpacker.presence_pct, unpacker.upper_mid_pct,
            effective_intensity * config.COMPRESSED_LOUD_INTENSITY_FACTOR,
            sample_rate, verbose, hf_lift
        )
        recorder.add(presence_info)

        processed, air_info = self.pipeline._apply_air_enhancement(
            processed, unpacker.air_pct, unpacker.spectral_rolloff,
            effective_intensity * config.COMPRESSED_LOUD_INTENSITY_FACTOR,
            sample_rate, verbose, hf_lift
        )
        recorder.add(air_info)

        processed = self._assert_finite(processed, "CompressedLoud after spectral")

        # Safety peak limit after enhancements
        processed = self.pipeline._apply_safety_limiter(processed, verbose)
        processed = self._assert_finite(processed, "CompressedLoud after safety limiter")

        # Return with normalization flag
        info = recorder.to_dict()
        info['needs_output_normalize'] = True
        return processed, info

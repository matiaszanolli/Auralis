"""
Continuous Mastering Path
~~~~~~~~~~~~~~~~~~~~~~~~~

One measurement-driven processing path for every source.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Any

import numpy as np

from ...dsp.basic import amplify, normalize
from ...dsp.utils.adaptive_loudness import AdaptiveLoudnessControl
from ..mastering_config import SimpleMasteringConfig
from ..processing.continuous_space import ProcessingSpaceMapper
from ..stages.hf_budget import hf_lift_factor
from ..utils import FingerprintUnpacker, StageRecorder
from .base import ProcessingBranch
from .soft_clip_params import compute_soft_clip_threshold


class ContinuousMasteringBranch(ProcessingBranch):
    """
    Apply one continuous signal path without classifying the source.

    Processing steps:
    1. Calculate adaptive makeup gain
    2. Apply makeup gain
    3. Bass enhancement
    4. Sub-bass control
    5. Mid warmth
    6. Presence + air enhancements
    7. Adaptive soft clipping (multi-dimensional awareness)
    8. Stereo width expansion
    9. Peak normalize to target LUFS

    The strength of each stage is derived from numeric fingerprint measurements.
    No whole-track label chooses a branch or prevents processing.
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
    ) -> tuple[np.ndarray, dict[str, Any]]:
        """Apply the continuous mastering path."""

        from ...dsp.dynamics.soft_clipper import soft_clip

        processed = audio.copy()
        recorder = StageRecorder()

        # Resonance notches first — surgical narrow cuts in 150-1200 Hz so all
        # subsequent EQ stages see the post-notch energy balance. No-op if no
        # resonances were detected for this file.
        processed, notch_info = self.pipeline._apply_resonance_notches(
            processed, sample_rate, verbose
        )
        recorder.add(notch_info)

        # Calculate adaptive makeup gain
        makeup_gain, _ = AdaptiveLoudnessControl.calculate_adaptive_gain(
            unpacker.lufs, effective_intensity, unpacker.crest_db,
            unpacker.bass_pct, unpacker.transient_density, peak_db
        )

        # Apply makeup gain with modest safety margin for headroom
        makeup_gain = max(0.0, makeup_gain - 0.5)
        if makeup_gain > 0.0:
            if verbose:
                print(f"   Makeup gain: +{makeup_gain:.1f} dB")
            processed = amplify(processed, makeup_gain)
            recorder.add({'stage': 'makeup_gain', 'gain_db': makeup_gain})

        # Bass enhancement OR de-congestion (bidirectional based on bass_pct).
        # mid_pct/upper_mid_pct feed the de-mask cut that lowers the masking
        # bass when the voice is buried (paired with the clarity-boost lift).
        processed, bass_info = self.pipeline._apply_bass_enhancement(
            processed, unpacker.bass_pct, effective_intensity, sample_rate, verbose,
            unpacker.mid_pct, unpacker.upper_mid_pct, unpacker.presence_pct
        )
        recorder.add(bass_info)

        # Sub-bass control - tighten rumble (with HP for bursty rumble)
        processed, sub_bass_info = self.pipeline._apply_sub_bass_control(
            processed, unpacker.sub_bass_pct, unpacker.bass_pct,
            effective_intensity, sample_rate, verbose
        )
        recorder.add(sub_bass_info)

        # Transient shaper — restore attack on compressed kick/bass. Applied
        # after bass EQ (so we shape the final levels) but before mid-warmth
        # (so the warmth doesn't sustain over the restored attacks).
        processed, transient_info = self.pipeline._apply_transient_shaper(
            processed, unpacker.bass_pct, unpacker.low_mid_pct,
            unpacker.crest_db, effective_intensity, sample_rate, verbose
        )
        recorder.add(transient_info)

        # Mid-range warmth for thin mixes
        processed, warmth_info = self.pipeline._apply_mid_warmth(
            processed, unpacker.low_mid_pct, unpacker.mid_pct,
            effective_intensity, sample_rate, verbose
        )
        recorder.add(warmth_info)

        processed = self._assert_finite(processed, "continuous path after low-end/warmth")

        # Shared HF response from the corpus-calibrated spectral coordinate.
        # This prevents a source with high upper-mid/presence energy from being
        # treated as "dark" merely because a normalized rolloff is far below 1.
        spectral_balance = ProcessingSpaceMapper().map_fingerprint_to_space(
            unpacker.as_dict()
        ).spectral_balance
        hf_lift = hf_lift_factor(spectral_balance)

        # Harmonic exciter — generate new HF content for bandwidth-limited
        # sources. Runs after mid-warmth (donor band is now shaped) and before
        # presence/air (so those shelves can lift the new harmonics). Its wet
        # amplitude follows the same continuous corpus-calibrated response.
        #
        # Crest factor attenuates excitation smoothly. The asymptotic floor
        # preserves a small response without a bypass boundary.
        crest_preservation = 0.5 + 0.5 * np.tanh(
            (unpacker.crest_db - 16.0) / 4.0
        )
        exciter_factor = 1.0 - 0.85 * crest_preservation
        exciter_intensity = effective_intensity * exciter_factor

        processed, exciter_info = self.pipeline._apply_harmonic_exciter(
            processed, unpacker.presence_pct, unpacker.air_pct, unpacker.spectral_rolloff,
            exciter_intensity, sample_rate, verbose, hf_lift
        )
        recorder.add(exciter_info)

        # Clarity boost — Up-Mid bell for vocal/snare definition. Sits between
        # the exciter (which fed new harmonics into 4-8 kHz) and the presence
        # shelf (which lifts 2-8 kHz broadly). The clarity bell narrows the
        # focus to 1.5-3.5 kHz where consonants and attack-snap live. bass_pct/
        # mid_pct enable the relative vocal-masking trigger (voice buried under
        # a dominant bass), which the absolute Up-Mid deficit alone misses.
        processed, clarity_info = self.pipeline._apply_clarity_boost(
            processed, unpacker.upper_mid_pct,
            effective_intensity, sample_rate, verbose, hf_lift,
            unpacker.bass_pct, unpacker.mid_pct
        )
        recorder.add(clarity_info)

        # Presence enhancement for dull mixes
        processed, presence_info = self.pipeline._apply_presence_enhancement(
            processed, unpacker.presence_pct, unpacker.upper_mid_pct,
            effective_intensity, sample_rate, verbose, hf_lift
        )
        recorder.add(presence_info)

        # Air enhancement for dark mixes
        processed, air_info = self.pipeline._apply_air_enhancement(
            processed, unpacker.air_pct, unpacker.spectral_rolloff,
            effective_intensity, sample_rate, verbose, hf_lift
        )
        recorder.add(air_info)

        processed = self._assert_finite(processed, "continuous path after spectral")

        # Soft clipping with multi-dimensional awareness.
        threshold_db, ceiling = compute_soft_clip_threshold(unpacker, config, verbose)

        # Larger crest factors move the knee continuously toward 0 dB, so the
        # stage becomes asymptotically transparent without a hard bypass.
        clip_transparency = 0.5 + 0.5 * np.tanh(
            (unpacker.crest_db - 18.0) / 3.0
        )
        threshold_db *= 1.0 - clip_transparency
        ceiling += clip_transparency * (0.97 - ceiling)
        threshold_linear = 10 ** (threshold_db / 20.0)
        if verbose:
            print(f"   Soft clip: {threshold_db:.1f} dB, ceiling {ceiling*100:.0f}%")
        processed = soft_clip(processed, threshold=threshold_linear, ceiling=ceiling)
        recorder.add({'stage': 'soft_clip', 'threshold_db': threshold_db})

        # Stereo expansion for narrow mixes (brightness-aware)
        processed, width_info = self.pipeline._apply_stereo_expansion(
            processed, unpacker.stereo_width, effective_intensity, sample_rate, verbose,
            unpacker.spectral_centroid, unpacker.air_pct, unpacker.phase_correlation
        )
        recorder.add(width_info)

        # Continuous file-level loudness/crest response. Runs after stereo
        # expansion so the limiter catches any mid/side peaks the widening
        # introduced, and before the final normalization. Its pre-gain
        # approaches transparency smoothly as source loudness rises.
        # Prefer the accurate ITU-R BS.1770 loudness measured per-file in
        # master_file; fall back to the fingerprint values on the direct
        # _process() path (e.g. unit tests) where it was not measured.
        src_lufs = self.pipeline._source_lufs
        src_crest = self.pipeline._source_crest_db
        processed, loudness_info = self.pipeline._apply_loudness_maximizer(
            processed,
            src_lufs if src_lufs is not None else unpacker.lufs,
            src_crest if src_crest is not None else unpacker.crest_db,
            sample_rate, verbose
        )
        recorder.add(loudness_info)

        # Final normalization — useful level with inter-sample headroom.
        #
        # A pure peak-normalize is gain only, so crest factor (transient punch)
        # is preserved exactly. Keep about 1.0-1.5 dB of sample-peak headroom so
        # reconstructed true peaks do not cross the -0.5 dBTP safety ceiling.
        # Loudness is established by the maximizer above, not by forcing every
        # source close to full scale.
        target_peak, _ = AdaptiveLoudnessControl.calculate_adaptive_peak_target(unpacker.lufs)
        # target_peak is 0.85 (loud) … 0.90 (quiet).
        adapted_peak = float(np.clip(target_peak - 0.01, 0.84, 0.89))

        if verbose:
            print(
                f"   Normalize: {adapted_peak*100:.0f}% peak "
                "(true-peak headroom, crest-preserving)"
            )

        processed = normalize(processed, adapted_peak)
        recorder.add({'stage': 'normalize', 'target_peak': adapted_peak})

        processed = self._assert_finite(
            processed, "continuous path after soft-clip/stereo/normalize"
        )

        # This path performs its own final normalization.
        info = recorder.to_dict()
        info['needs_output_normalize'] = False
        return processed, info

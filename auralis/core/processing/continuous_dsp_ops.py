"""
Continuous-Mode DSP Primitives
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The individual DSP operations the continuous-space stage sequence drives: EQ,
dynamics, stereo width, and final loudness/peak normalization.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)

Split out of ``continuous_mode.py`` as a mixin (#4254). These are the "how" to
``continuous_stages.py``'s "in what order, and guarded against what" — the two
change for different reasons and are read for different reasons. Mixed in rather
than composed for the same reason as the stage sequence: each primitive reads
processor state and must stay individually callable, which several regression
tests (#4104, #4237, #4503, #5108) do directly.
"""

from auralis.dsp.utils.conversion import amplitude_to_db
from typing import Any

import numpy as np

from ...dsp.basic import amplify, rms
from ...dsp.dynamics.brick_wall_limiter import create_brick_wall_limiter
from ...dsp.utils.adaptive import (
    MAX_NORMALIZATION_GAIN_DB,
    SILENCE_FLOOR_LUFS,
    SILENCE_KNEE_DB,
    calculate_loudness_units,
)
from ...dsp.utils.stereo import (
    WIDTH_FACTOR_UNITY,
    stereo_width_analysis,
)
from ...utils.audio_validation import MAX_IN_STAGE_REPAIR_FRACTION, validate_audio_finite
from ...utils.logging import debug
from ..config import UnifiedConfig
from .base import (
    CompressionStrategies,
    StereoWidthProcessor,
)
from .cross_dimensional_guard import smooth_gate


# -0.3 dBFS ceiling preserves headroom for inter-sample peaks.
SAFE_CEILING_DB = -0.3


class ContinuousDSPOpsMixin:
    """The DSP primitives, mixed into :class:`ContinuousMode`."""

    # Concrete-processor state these primitives read. Declared, never assigned
    # here: `ContinuousMode.__init__` owns the values. Spelling the contract out
    # is what keeps the mixin type-checkable on its own (#4254).
    config: UnifiedConfig
    last_fingerprint: dict[str, Any] | None

    def _apply_eq(self, audio: np.ndarray, eq_processor: Any, params: Any) -> np.ndarray:
        """Apply EQ using the continuously generated parameters."""

        eq_curve = dict(params.eq_curve)

        # Create targets dict using EQProcessor._targets_to_eq_curve() key names
        targets = {
            'bass_boost_db': eq_curve['low_shelf_gain'],
            'preset_low_mid_gain': eq_curve['low_mid_gain'],
            'midrange_clarity_db': eq_curve['mid_gain'],
            'preset_high_mid_gain': eq_curve['high_mid_gain'],
            'treble_enhancement_db': eq_curve['high_shelf_gain'],
            'eq_blend': params.eq_blend,
        }

        # Create content profile with fingerprint
        content_profile = {'fingerprint': self.last_fingerprint}

        # Apply EQ
        audio = eq_processor.apply_psychoacoustic_eq(audio, targets, content_profile)

        debug(f"[EQ] Applied curve with blend {params.eq_blend:.2f}: "
              f"bass {eq_curve['low_shelf_gain']:+.1f} dB, "
              f"mid {eq_curve['low_mid_gain']:+.1f} dB, "
              f"air {eq_curve['high_shelf_gain']:+.1f} dB")

        return audio

    def _apply_dynamics(self, audio: np.ndarray, params: Any) -> np.ndarray:
        """Apply offline dynamics from continuous fingerprint measurements.

        The offline path deliberately uses its OWN dynamics here
        (``CompressionStrategies.apply_clip_blend_compression``, tuned by
        the continuous-space coordinates) rather than
        ``HybridProcessor.dynamics_processor``. That ``DynamicsProcessor`` is the
        *realtime* streaming engine; this stage is instead integrated with the
        continuous-space ``PipelineJournal`` / ``CrossDimensionalGuard`` and the
        LUFS-target normalizer. Routing the realtime processor in here would
        double-compress and fight those systems, so the offline/realtime
        divergence is intentional, not an oversight (#2897).
        """

        compression_params = params.compression_params.copy()

        audio = self._apply_compression(audio, compression_params)

        # #5561: the expansion stage (apply_rms_reduction_expansion) was a
        # scalar gain — peak and RMS moved together, so crest factor was
        # invariant and the downstream LUFS normalization re-boosted the
        # attenuation. Removed following #5309's precedent for the same
        # class of placebo stage; the generator's expansion_params remain
        # available as reporting data.
        return audio

    def _apply_compression(self, audio: np.ndarray, comp_params: dict[str, Any]) -> np.ndarray:
        """Apply simple compression to reduce crest factor"""

        # Validate input - handle empty or very short audio gracefully
        if len(audio) == 0:
            return audio  # Return as-is if empty

        return CompressionStrategies.apply_clip_blend_compression(audio, comp_params)

    def _apply_stereo_width(self, audio: np.ndarray, params: Any) -> np.ndarray:
        """Apply the continuously generated stereo-width target.

        The #5108 smooth peak knee and the multiband application live in the
        shared `StereoWidthProcessor.apply_stereo_width_safe` (#6192) — the
        same code path AdaptiveMode runs, so both modes widen identically.
        """

        # Only process stereo audio
        if not StereoWidthProcessor.validate_stereo(audio):
            return audio

        # `target_width` is a WIDTH FACTOR (side-gain axis, 0.5 = unchanged);
        # `stereo_width_analysis` returns DECORRELATION (0 = mono). Different
        # axes — see the module docstring in dsp/utils/stereo.py (#4503). The
        # decorrelation reading is for logging only; it must never be compared
        # with or subtracted from a width factor.
        target_width = params.stereo_width_target
        pre_decorrelation = stereo_width_analysis(audio)
        pre_peak_db = StereoWidthProcessor.get_peak_db(audio)

        audio = StereoWidthProcessor.apply_stereo_width_safe(
            audio, pre_decorrelation, target_width, pre_peak_db,
            self.config.internal_sample_rate,
        )

        post_decorrelation = stereo_width_analysis(audio)
        debug(
            f"[Stereo Width] decorrelation {pre_decorrelation:.2f} → "
            f"{post_decorrelation:.2f} (width factor: {target_width:.2f}, "
            f"unity={WIDTH_FACTOR_UNITY})"
        )

        return audio

    def _normalize_chunk_loudness(self, audio: np.ndarray, target_lufs: float) -> np.ndarray:
        """Per-chunk LUFS normalisation, for targets with no track-level source loudness.

        Used when the chunk is all we know about the track (the per-chunk
        fingerprint path, and legacy fixed targets without ``source_lufs``).
        """
        current_lufs = calculate_loudness_units(audio, self.config.internal_sample_rate)

        # Silence / near-silence needs no normalisation. The meter floors
        # silence at a finite -70 LUFS (it never returns -inf), so the old
        # `isfinite` guard (#4104) was unreachable after #5221 and a quiet but
        # non-zero chunk was raised by up to +140 dB to programme loudness
        # (#5551). Compare against an explicit floor instead; this also keeps
        # #4104's invariant that silence never yields an inf/NaN gain.
        if not np.isfinite(current_lufs) or current_lufs <= SILENCE_FLOOR_LUFS:
            debug(
                f"[LUFS Normalization] SKIPPED - {current_lufs:.1f} LUFS is at or "
                f"below the silence floor ({SILENCE_FLOOR_LUFS:.0f} LUFS)"
            )
            return audio

        adjustment = float(np.clip(
            target_lufs - current_lufs,
            -MAX_NORMALIZATION_GAIN_DB,
            MAX_NORMALIZATION_GAIN_DB,
        ))

        # #5578: ramp tiny corrections to zero instead of a hard >0.5 dB gate.
        # #6108: and fade the correction in over the first SILENCE_KNEE_DB above the
        # silence floor, so a 0.2 dB level change cannot swing the gain by 22 dB.
        effective_adjustment = (
            adjustment
            * smooth_gate(abs(adjustment), 0.0, 0.5)
            * smooth_gate(current_lufs, SILENCE_FLOOR_LUFS, SILENCE_FLOOR_LUFS + SILENCE_KNEE_DB)
        )
        if abs(effective_adjustment) > 1e-6:
            audio = amplify(audio, effective_adjustment)
            new_lufs = calculate_loudness_units(audio, self.config.internal_sample_rate)
            debug(f"[LUFS Normalization] {current_lufs:.1f} → {new_lufs:.1f} LUFS")
        return audio

    def _apply_final_normalization(self, audio: np.ndarray, params: Any) -> np.ndarray:
        """Apply final loudness and peak normalization using unified pipeline"""

        # Catch general NaN/Inf from upstream stages before any measurement
        # below (fixes #4237). This is IN ADDITION to the #4104 guard just
        # below, which only covers the narrower silence-induced -inf LUFS
        # case — an arbitrary NaN/Inf already present in `audio` itself
        # (e.g. from an upstream DSP bug) would otherwise reach
        # calculate_loudness_units/amplify unguarded.
        # The repair is bounded (#6105): a mostly non-finite buffer raises
        # instead of being zeroed, so the HybridProcessor fail-fast guard
        # and the pipeline's unprocessed-audio fallback still fire.
        audio = validate_audio_finite(
            audio,
            context="continuous_mode final normalization",
            repair=True,
            repair_max_fraction=MAX_IN_STAGE_REPAIR_FRACTION,
        )

        # Step 1: LUFS-based normalization to target loudness.
        # #3665 moved this off raw RMS, which diverged 3-6 dB with spectral
        # content (bass-heavy under-normalized, bright over-normalized), and
        # onto calculate_loudness_units(). #5221: that only looked like a fix
        # — the function was still unweighted RMS, just shifted by the EBU
        # R128 *target* (-23.0) as if it were a dBFS->LUFS offset, so it read
        # ~25 LU below `target_lufs`'s true-LUFS scale and this step became a
        # ~+25 dB over-boost that Step 2 clawed back to the ceiling. It is now
        # genuinely K-weighted per BS.1770-4. The per-chunk fingerprint path's
        # target is converted onto that scale in
        # ContinuousMode._resolve_parameters (#5700); the fixed-target path
        # keeps source and target both on the fingerprint's proxy scale, so
        # only their difference (the lift) is used.
        target_lufs = params.target_lufs
        source_lufs = getattr(params, 'source_lufs', None)

        if source_lufs is not None and np.isfinite(source_lufs):
            # Fixed-targets path: the targets describe the WHOLE track, so move
            # every chunk by the same gain. Re-measuring each chunk and pulling
            # it to the track-wide target made a -36 LUFS verse and a -11 LUFS
            # chorus both land at -14 (#5552). Silence needs no special case:
            # a constant gain on zeros is zeros.
            adjustment = float(np.clip(
                target_lufs - source_lufs,
                -MAX_NORMALIZATION_GAIN_DB,
                MAX_NORMALIZATION_GAIN_DB,
            ))
            if abs(adjustment) > 1e-3:
                audio = amplify(audio, adjustment)
            debug(
                f"[LUFS Normalization] track-level gain {adjustment:+.2f} dB "
                f"(source {source_lufs:.1f}, target {target_lufs:.1f})"
            )
        else:
            audio = self._normalize_chunk_loudness(audio, target_lufs)

        # Step 2: peak ceiling at -0.3 dBFS (headroom for inter-sample peaks).
        # #5701: this used to be ONE gain for the whole buffer
        # (`amplify(audio, ceiling - max_peak)`), so a transient present in one
        # rendering of an overlapped region and absent from the other rescaled
        # the entire window: the two renderings differed by up to ~4 dB RMS and,
        # tiled without a crossfade, stepped at the seam. A sample-local
        # look-ahead limiter touches only the neighbourhood of the peak, so
        # both renderings of the shared audio agree away from it. The constant
        # track-level gain of Step 1 (#5552) is left intact.
        final_peak_pre = amplitude_to_db(np.max(np.abs(audio)))
        if final_peak_pre > SAFE_CEILING_DB:
            audio = create_brick_wall_limiter(
                self.config.internal_sample_rate, threshold_db=SAFE_CEILING_DB
            ).process(audio)
            debug(f"[Peak Limiting] {final_peak_pre:.2f} → {SAFE_CEILING_DB:.2f} dB (sample-local limiter)")
        else:
            debug(f"[Peak Limiting] SKIPPED - audio peak at {final_peak_pre:.2f} dB is safe")

        # Final measurements
        final_peak = np.max(np.abs(audio))
        final_peak_db = amplitude_to_db(final_peak)
        final_lufs = calculate_loudness_units(audio, self.config.internal_sample_rate)
        final_rms = rms(audio)
        final_rms_db = amplitude_to_db(final_rms)
        final_crest = final_peak_db - final_rms_db

        debug(f"[Final] Peak: {final_peak_db:.2f} dB, RMS: {final_rms_db:.2f} dB, "
              f"Crest: {final_crest:.2f} dB, LUFS: {final_lufs:.1f}")

        return audio

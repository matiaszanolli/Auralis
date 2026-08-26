"""
Continuous-Mode DSP Primitives
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The individual DSP operations the continuous-space stage sequence drives: EQ,
dynamics, stereo width, and final loudness/peak normalization.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.

Split out of ``continuous_mode.py`` as a mixin (#4254). These are the "how" to
``continuous_stages.py``'s "in what order, and guarded against what" — the two
change for different reasons and are read for different reasons. Mixed in rather
than composed for the same reason as the stage sequence: each primitive reads
processor state and must stay individually callable, which several regression
tests (#4104, #4237, #4503, #5108) do directly.
"""

from typing import Any

import numpy as np

from ...dsp.basic import amplify, rms
from ...dsp.utils.adaptive import calculate_loudness_units
from ...dsp.utils.stereo import (
    WIDTH_FACTOR_UNITY,
    adjust_stereo_width_multiband,
    stereo_width_analysis,
)
from ...utils.audio_validation import validate_audio_finite
from ...utils.logging import debug
from ..config import UnifiedConfig
from .base import (
    CompressionStrategies,
    DBConversion,
    ExpansionStrategies,
    StereoWidthProcessor,
)
from .continuous_guards import WIDTH_PEAK_KNEE_END, WIDTH_PEAK_KNEE_START
from .cross_dimensional_guard import smooth_gate


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
        (``CompressionStrategies.apply_clip_blend_compression`` /
        ``ExpansionStrategies.apply_rms_reduction_expansion``, tuned by the
        continuous-space coordinates) rather than
        ``HybridProcessor.dynamics_processor``. That ``DynamicsProcessor`` is the
        *realtime* streaming engine; this stage is instead integrated with the
        continuous-space ``PipelineJournal`` / ``CrossDimensionalGuard`` and the
        LUFS-target normalizer. Routing the realtime processor in here would
        double-compress and fight those systems, so the offline/realtime
        divergence is intentional, not an oversight (#2897).
        """

        compression_params = params.compression_params.copy()
        expansion_params = params.expansion_params.copy()

        audio = self._apply_compression(audio, compression_params)
        audio = self._apply_expansion(audio, expansion_params)

        return audio

    def _apply_compression(self, audio: np.ndarray, comp_params: dict[str, Any]) -> np.ndarray:
        """Apply simple compression to reduce crest factor"""

        # Validate input - handle empty or very short audio gracefully
        if len(audio) == 0:
            return audio  # Return as-is if empty

        return CompressionStrategies.apply_clip_blend_compression(audio, comp_params)

    def _apply_expansion(self, audio: np.ndarray, exp_params: dict[str, Any]) -> np.ndarray:
        """Apply expansion to increase crest factor (de-mastering)"""
        return ExpansionStrategies.apply_rms_reduction_expansion(audio, exp_params)

    def _apply_stereo_width(self, audio: np.ndarray, params: Any) -> np.ndarray:
        """Apply the continuously generated stereo-width target."""

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

        # Check peak levels before expansion (safety)
        pre_peak_db = StereoWidthProcessor.get_peak_db(audio)

        # Ease expansion off as the signal approaches clipping. "Does this
        # widen?" is answered against unity, not against a measurement:
        # untouched audio is at unity side gain by definition. An earlier
        # version compared the width factor against the decorrelation reading,
        # so a narrowing request on a near-mono source (e.g. factor 0.4 vs
        # decorrelation 0.1) read as "widening" and was suppressed, while a
        # genuine widening request on a decorrelated source (factor 0.7 vs
        # decorrelation 0.9) slipped past the clipping guard entirely (#4503).
        #
        # #5108: ramp the widening away as the peak approaches clipping instead
        # of switching it off. This was `if pre_peak_db > -2.0 and target_width
        # > WIDTH_FACTOR_UNITY: return audio` — the fourth cross-dimensional
        # guard in this method, and the one #4860 never migrated to
        # smooth_gate(). Two masters 0.01 dB apart straddling -2.0 dBFS got
        # either full adjust_stereo_width_multiband() treatment or none: an
        # audible stereo-image difference from an inaudible input difference,
        # in a peak region the pipeline's own -0.3 dBFS ceiling makes common.
        #
        # Only widening is gated; a narrowing request cannot push peaks up, so
        # it passes through untouched (preserving #4503's width-factor vs
        # decorrelation axis correction).
        if target_width > WIDTH_FACTOR_UNITY:
            # gate: 0 well below the knee (widen fully), 1 at/above it (unity).
            gate = smooth_gate(
                pre_peak_db, WIDTH_PEAK_KNEE_START, WIDTH_PEAK_KNEE_END
            )
            target_width = target_width + (WIDTH_FACTOR_UNITY - target_width) * gate
            if gate > 0.0:
                debug(
                    f"[Stereo Width] peak {pre_peak_db:.2f} dB — widening eased "
                    f"toward unity (gate={gate:.2f}, target={target_width:.3f})"
                )

        # Multiband so sub-300 Hz stays (near-)mono — protects kick/bass punch
        # and mono compatibility, matching the SimpleMastering path (#4504).
        audio = adjust_stereo_width_multiband(
            audio, target_width, self.config.internal_sample_rate
        )
        post_decorrelation = stereo_width_analysis(audio)
        debug(
            f"[Stereo Width] decorrelation {pre_decorrelation:.2f} → "
            f"{post_decorrelation:.2f} (width factor: {target_width:.2f}, "
            f"unity={WIDTH_FACTOR_UNITY})"
        )

        return audio

    def _apply_final_normalization(self, audio: np.ndarray, params: Any) -> np.ndarray:
        """Apply final loudness and peak normalization using unified pipeline"""

        # Catch general NaN/Inf from upstream stages before any measurement
        # below (fixes #4237). This is IN ADDITION to the #4104 guard just
        # below, which only covers the narrower silence-induced -inf LUFS
        # case — an arbitrary NaN/Inf already present in `audio` itself
        # (e.g. from an upstream DSP bug) would otherwise reach
        # calculate_loudness_units/amplify unguarded.
        audio = validate_audio_finite(audio, context="continuous_mode final normalization", repair=True)

        # Step 1: LUFS-based normalization to target loudness.
        # #3665 moved this off raw RMS, which diverged 3-6 dB with spectral
        # content (bass-heavy under-normalized, bright over-normalized), and
        # onto calculate_loudness_units(). #5221: that only looked like a fix
        # — the function was still unweighted RMS, just shifted by the EBU
        # R128 *target* (-23.0) as if it were a dBFS->LUFS offset, so it read
        # ~25 LU below `target_lufs`'s true-LUFS scale and this step became a
        # ~+25 dB over-boost that Step 2 clawed back to the ceiling. It is now
        # genuinely K-weighted per BS.1770-4 and the two sides share a scale.
        current_lufs = calculate_loudness_units(audio, self.config.internal_sample_rate)
        if not np.isfinite(current_lufs):
            # Fall back to RMS for very short or silent segments where
            # LUFS gating discards every block.
            from ...dsp.basic import rms as calculate_rms
            current_rms = calculate_rms(audio.ravel() if audio.ndim == 2 else audio)
            current_lufs = DBConversion.to_db(current_rms)
            # #4104: pure silence (rms == 0) -> to_db returns -inf. Without this
            # guard, adjustment = target_lufs - (-inf) = +inf and
            # amplify(silence, +inf) = 0.0 * inf = NaN across the whole buffer,
            # which then trips validate_audio_finite(repair=False) downstream and
            # crashes the stream. Silence needs no normalization — return it
            # unchanged (mirrors HybridProcessor's all-zeros early return).
            if not np.isfinite(current_lufs):
                return audio

        target_lufs = params.target_lufs
        adjustment = target_lufs - current_lufs

        if abs(adjustment) > 0.5:
            audio = amplify(audio, adjustment)
            new_lufs = calculate_loudness_units(audio, self.config.internal_sample_rate)
            debug(
                f"[LUFS Normalization] {current_lufs:.1f} → {new_lufs:.1f} LUFS "
                f"({adjustment:+.1f} dB, target {target_lufs:.1f})"
            )

        # Step 2: Peak normalization (DISABLED - use LUFS normalization instead)
        # Peak normalization can cause excessive gain when EQ processing has
        # changed the peak-to-RMS relationship. LUFS normalization is more
        # perceptually meaningful and is already applied in step 1.
        # Only apply peak limiting if absolutely necessary to prevent clipping.
        current_peak_db = DBConversion.to_db(np.max(np.abs(audio)))

        # -0.3 dBFS ceiling preserves headroom for inter-sample peaks
        SAFE_CEILING_DB = -0.3

        if current_peak_db > SAFE_CEILING_DB:
            # Audio exceeds safe ceiling - apply peak limiting
            peak_adjustment = min(SAFE_CEILING_DB - current_peak_db, 0.0)
            audio = amplify(audio, peak_adjustment)
            debug(f"[Peak Limiting] {current_peak_db:.2f} → {SAFE_CEILING_DB:.2f} dB (emergency limiting)")
        else:
            debug(f"[Peak Normalization] SKIPPED - audio peak at {current_peak_db:.2f} dB is safe")

        # Step 3: HF-aware safety limiter (Phase 5). Pre/de-emphasis around
        # the wideband soft-clip preserves cymbal/sibilance transient char
        # that the naive wideband path used to flatten — the second half of
        # the user's "Iron Maiden HF overdrive" complaint.
        from .hf_aware_limiter import apply_hf_aware_limiter
        audio, limiter_applied = apply_hf_aware_limiter(audio, self.config.internal_sample_rate)

        # Final measurements
        final_peak = np.max(np.abs(audio))
        final_peak_db = DBConversion.to_db(final_peak)
        final_lufs = calculate_loudness_units(audio, self.config.internal_sample_rate)
        final_rms = rms(audio)
        final_rms_db = DBConversion.to_db(final_rms)
        final_crest = final_peak_db - final_rms_db

        debug(f"[Final] Peak: {final_peak_db:.2f} dB, RMS: {final_rms_db:.2f} dB, "
              f"Crest: {final_crest:.2f} dB, LUFS: {final_lufs:.1f}")

        return audio

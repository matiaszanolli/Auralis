"""
Compression and Expansion Strategies
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Unified compression and expansion strategies for different processing modes.
Consolidates compression/expansion logic used across adaptive_mode and continuous_mode.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""


import numpy as np

from ....dsp.basic import amplify
from ....dsp.dynamics.soft_clipper import soft_clip
from .audio_measurement import MeasurementUtilities

# The keys each strategy below indexes with `[...]` — i.e. the ones whose
# absence is a KeyError, not a defaulted value.
#
# Two independent producers build these dicts: the fixed-targets fast path in
# `fixed_target_params.convert_targets_to_parameters` and the fingerprint path
# in `ContinuousParameterGenerator`. Nothing tied their schemas together, so they
# drifted: the fast path omitted `target_crest_increase` entirely and every
# `.25d`-sidecar track crashed here (#4856). Declared next to the readers so a
# contract test can assert every producer satisfies them —
# tests/auralis/core/test_processing_params_contract_4856.py.
COMPRESSION_REQUIRED_KEYS = frozenset({'ratio', 'amount'})
EXPANSION_REQUIRED_KEYS = frozenset({'target_crest_increase', 'amount'})

# Peaks below this are treated as silence by the clip-blend compressor.
_SILENCE_PEAK = 1e-6

# The clip-blend threshold is 0.8 - (ratio - 1) * 0.1 of the reference level: it reaches 0 at 9:1
# and goes negative beyond, so the ratio is held to 8:1 (threshold 0.1) (#6117).
_MAX_CLIP_BLEND_RATIO = 8.0


class CompressionStrategies:
    """
    Unified compression strategies for different processing modes.
    Consolidates compression logic used across adaptive_mode and continuous_mode.
    """

    @staticmethod
    def apply_soft_knee_compression(audio: np.ndarray, compression_amount: float) -> np.ndarray:
        """
        Apply soft-knee compression using manual threshold-based reduction.
        Used by adaptive_mode - reduces crest factor through soft clipping.

        Args:
            audio: Input audio array
            compression_amount: Intensity of compression (0.1-1.0)

        Returns:
            Compressed audio array
        """
        # Never modify input array in-place
        audio = audio.copy()

        before = MeasurementUtilities.measure_audio(audio)

        # Calculate target crest reduction based on compression amount
        # compression_amount = 0.85 means reduce crest by ~3 dB (from Matchering data)
        target_crest_reduction = compression_amount * 4.5  # Max ~3.8 dB reduction

        # Simple soft clipping: reduce peaks while preserving RMS
        target_crest = before.crest - target_crest_reduction
        clip_threshold_db = before.rms_db + target_crest
        clip_threshold_linear = 10 ** (clip_threshold_db / 20)

        # Apply soft clipping
        audio_abs = np.abs(audio)
        over_threshold = audio_abs > clip_threshold_linear

        if np.any(over_threshold):
            # Soft knee compression with adaptive ratio
            compression_ratio = 3.0 + compression_amount * 4.0  # 3:1 to 7:1
            excess = audio_abs[over_threshold] - clip_threshold_linear
            compressed_excess = excess / compression_ratio
            new_amplitude = clip_threshold_linear + compressed_excess

            # Apply compression while preserving sign
            audio[over_threshold] = np.sign(audio[over_threshold]) * new_amplitude

        after = MeasurementUtilities.measure_audio(audio)

        info_str = f"target: {-target_crest_reduction:.2f} dB"
        MeasurementUtilities.log_processing_step(
            "DIY Compressor (Soft-Knee)",
            before,
            after,
            info_str
        )

        return audio

    @staticmethod
    def apply_clip_blend_compression(audio: np.ndarray, comp_params: dict[str, float]) -> np.ndarray:
        """
        Apply compression using soft_clip() with blend formula.
        Used by continuous_mode - reduces crest through library soft clipping + blending.

        The soft-clip threshold and ceiling are fractions of the input's own
        peak, so the effect depends on the material's dynamics rather than on
        how loud the file happens to be (#5576): this stage runs before
        normalization, where the level is simply the source's, and the former
        absolute threshold (~0.72 at 1.8:1) left material peaking below it
        untouched. Scaling the input down scales the output down by the same
        factor and the crest-factor reduction is unchanged. A peak at or above
        full scale (over-range after EQ) is referenced to 1.0, so such
        material is still pulled under the 0.95 ceiling.

        ``comp_params`` carries ``threshold``/``attack``/``release`` as well
        (reporting values, see ``generate_compression``); this stage is an
        instantaneous waveshaper and reads only ``ratio`` and ``amount``.

        Args:
            audio: Input audio array
            comp_params: Dictionary with 'ratio' and 'amount' keys
                - ratio: Compression ratio (e.g., 2.0 for 2:1)
                - amount: Blend amount (0.0-1.0)

        Returns:
            Compressed audio array
        """
        audio = audio.copy()
        before = MeasurementUtilities.measure_audio(audio)

        # Plain Python floats (a numpy scalar is strongly typed under NEP 50 and promotes a float32
        # blend to float64), clamped to the range the formula is valid on: ratio past ~9 drives the
        # soft-clip threshold below zero and inverts small samples' sign (#6117).
        ratio = min(max(float(comp_params['ratio']), 1.0), _MAX_CLIP_BLEND_RATIO)
        amount = min(max(float(comp_params['amount']), 0.0), 1.0)

        peak = float(np.max(np.abs(audio))) if audio.size else 0.0
        if not np.isfinite(peak) or peak < _SILENCE_PEAK:
            # Silence (nothing to compress) or non-finite samples (not this
            # stage's to repair; soft_clip would only spread the NaN).
            return audio
        reference = min(peak, 1.0)

        # Lower threshold = more compression, higher ratio = lower ceiling.
        # Fractions of the reference level: 1.5:1 -> 0.75, 2.0:1 -> 0.70.
        threshold = reference * (0.8 - (ratio - 1.0) * 0.1)
        ceiling = reference * 0.95

        compressed = soft_clip(audio, threshold=threshold, ceiling=ceiling)

        # Blend with original based on amount
        audio = audio * (1.0 - amount) + compressed * amount

        after = MeasurementUtilities.measure_audio(audio)

        info_str = f"{ratio:.1f}:1 @ {amount:.0%}"
        MeasurementUtilities.log_processing_step(
            "Compression (Clip-Blend)",
            before,
            after,
            info_str
        )

        return audio


class ExpansionStrategies:
    """
    Unified expansion strategies for different processing modes.
    Consolidates expansion logic used across adaptive_mode and continuous_mode.
    """

    @staticmethod
    def apply_peak_enhancement_expansion(audio: np.ndarray, expansion_amount: float) -> np.ndarray:
        """
        Apply expansion by enhancing peaks (used by adaptive_mode).
        Increases crest factor through selective peak boosting.

        Args:
            audio: Input audio array
            expansion_amount: Intensity of expansion (0.1-1.0)

        Returns:
            Expanded audio array
        """
        # Never modify input array in-place
        audio = audio.copy()

        before = MeasurementUtilities.measure_audio(audio)

        # Calculate target crest expansion
        # expansion_amount = 0.7 means expand crest by ~4-6 dB
        target_crest_expansion = expansion_amount * 6.0  # Max ~4.2 dB expansion

        # Expansion threshold: 3 dB above RMS
        expansion_threshold_db = before.rms_db + 3.0
        expansion_threshold_linear = 10 ** (expansion_threshold_db / 20)

        # Apply expansion on samples above threshold
        audio_abs = np.abs(audio)
        above_threshold = audio_abs > expansion_threshold_linear

        if np.any(above_threshold):
            # Expansion ratio: 1:2 means for every 1 dB above threshold, add 2 dB
            expansion_ratio = 1.0 + expansion_amount  # 1.1 to 1.7
            excess = audio_abs[above_threshold] - expansion_threshold_linear

            # Convert to dB, apply expansion, convert back
            excess_db = 20 * np.log10(excess / expansion_threshold_linear + 1.0)
            expanded_excess_db = excess_db * expansion_ratio
            expanded_excess_linear = (10 ** (expanded_excess_db / 20) - 1.0) * expansion_threshold_linear

            new_amplitude = expansion_threshold_linear + expanded_excess_linear

            # Apply expansion while preserving sign
            audio[above_threshold] = np.sign(audio[above_threshold]) * new_amplitude

        after = MeasurementUtilities.measure_audio(audio)

        info_str = f"target: +{target_crest_expansion:.2f} dB"
        MeasurementUtilities.log_processing_step(
            "DIY Expander (Peak Enhancement)",
            before,
            after,
            info_str
        )

        return audio

    @staticmethod
    def apply_rms_reduction_expansion(audio: np.ndarray, exp_params: dict[str, float]) -> np.ndarray:
        """
        Apply expansion by reducing RMS (used by continuous_mode).
        Increases crest factor through RMS reduction.

        Args:
            audio: Input audio array
            exp_params: Dictionary with 'target_crest_increase' and 'amount' keys
                - target_crest_increase: Target crest increase in dB
                - amount: Application amount (0.0-1.0)

        Returns:
            Expanded audio array
        """
        audio = audio.copy()
        before = MeasurementUtilities.measure_audio(audio)

        target_increase = exp_params['target_crest_increase']
        amount = exp_params['amount']

        # Expansion strategy: Reduce RMS while keeping peaks (increases crest)
        rms_reduction_db = target_increase * amount

        # Apply RMS reduction (makes audio quieter, increasing crest)
        audio = amplify(audio, -rms_reduction_db)

        after = MeasurementUtilities.measure_audio(audio)

        info_str = f"Target +{target_increase:.1f} dB @ {amount:.0%}"
        MeasurementUtilities.log_processing_step(
            "Expansion (RMS Reduction)",
            before,
            after,
            info_str
        )

        return audio

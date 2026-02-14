"""
Compression and Expansion Strategies
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Unified compression and expansion strategies for different processing modes.
Consolidates compression/expansion logic used across adaptive_mode and continuous_mode.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""


import numpy as np

from ....dsp.basic import amplify
from ....dsp.dynamics.soft_clipper import soft_clip
from .audio_measurement import MeasurementUtilities


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

        Args:
            audio: Input audio array
            comp_params: Dictionary with 'ratio' and 'amount' keys
                - ratio: Compression ratio (e.g., 2.0 for 2:1)
                - amount: Blend amount (0.0-1.0)

        Returns:
            Compressed audio array
        """
        before = MeasurementUtilities.measure_audio(audio)

        ratio = comp_params['ratio']
        amount = comp_params['amount']

        # Calculate soft clip threshold based on ratio
        # Lower threshold = more compression, higher ratio = lower ceiling
        threshold = 0.8 - (ratio - 1.0) * 0.1  # 1.5:1 → 0.75, 2.0:1 → 0.70
        ceiling = 0.95

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

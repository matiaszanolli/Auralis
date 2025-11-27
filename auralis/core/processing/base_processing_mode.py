# -*- coding: utf-8 -*-

"""
Base Processing Mode
~~~~~~~~~~~~~~~~~~~~

Shared utilities and base class for audio processing modes.
Consolidates common measurement and debug boilerplate across modes.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
from typing import Dict, Any, Union, Optional, Tuple
from ...dsp.basic import rms, amplify
from ...dsp.dynamics.soft_clipper import soft_clip
from ...dsp.unified import stereo_width_analysis, adjust_stereo_width
from ...utils.logging import debug


class AudioMeasurement:
    """Represents audio measurements (peak, RMS, crest factor)"""

    def __init__(self, peak: float, rms_val: float, peak_db: float = None, rms_db: float = None):
        """
        Initialize audio measurement

        Args:
            peak: Peak amplitude (linear, 0-1)
            rms_val: RMS level (linear, 0-1)
            peak_db: Peak in dB (optional, calculated if not provided)
            rms_db: RMS in dB (optional, calculated if not provided)
        """
        self.peak = peak
        self.rms = rms_val
        self.peak_db = peak_db if peak_db is not None else (20 * np.log10(peak) if peak > 0 else -np.inf)
        self.rms_db = rms_db if rms_db is not None else (20 * np.log10(rms_val) if rms_val > 0 else -np.inf)
        self.crest = self.peak_db - self.rms_db

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary"""
        return {
            'peak': self.peak,
            'rms': self.rms,
            'peak_db': self.peak_db,
            'rms_db': self.rms_db,
            'crest': self.crest
        }


class MeasurementUtilities:
    """
    Shared measurement and logging utilities for audio processing.

    Consolidates boilerplate code used across adaptive_mode, continuous_mode, etc.
    """

    @staticmethod
    def measure_audio(audio: np.ndarray, label: str = "") -> AudioMeasurement:
        """
        Measure audio signal: peak, RMS, crest factor.

        Args:
            audio: Audio array to measure
            label: Optional label for debug output

        Returns:
            AudioMeasurement object with peak, RMS, crest factor
        """
        peak = np.max(np.abs(audio))
        rms_val = rms(audio)
        measurement = AudioMeasurement(peak, rms_val)

        if label:
            debug(f"[{label}] Peak: {measurement.peak_db:.2f} dB, "
                  f"RMS: {measurement.rms_db:.2f} dB, "
                  f"Crest: {measurement.crest:.2f} dB")

        return measurement

    @staticmethod
    def log_processing_step(step_name: str, before: AudioMeasurement,
                           after: AudioMeasurement,
                           additional_info: str = "") -> None:
        """
        Log before/after measurements for a processing step.

        Args:
            step_name: Name of processing step (e.g., "Compression", "Expansion")
            before: AudioMeasurement before processing
            after: AudioMeasurement after processing
            additional_info: Optional additional info to log
        """
        peak_delta = after.peak_db - before.peak_db
        rms_delta = after.rms_db - before.rms_db
        crest_delta = after.crest - before.crest

        debug(f"[{step_name}] Peak: {before.peak_db:.2f} → {after.peak_db:.2f} dB "
              f"(Δ {peak_delta:+.2f} dB)")
        debug(f"[{step_name}] RMS: {before.rms_db:.2f} → {after.rms_db:.2f} dB "
              f"(Δ {rms_delta:+.2f} dB)")
        debug(f"[{step_name}] Crest: {before.crest:.2f} → {after.crest:.2f} dB "
              f"(Δ {crest_delta:+.2f} dB)")

        if additional_info:
            debug(f"[{step_name}] {additional_info}")

    @staticmethod
    def crest_delta_info(before: AudioMeasurement, after: AudioMeasurement) -> str:
        """
        Get human-readable crest factor change info.

        Args:
            before: Measurement before processing
            after: Measurement after processing

        Returns:
            Formatted string describing the crest change
        """
        crest_delta = after.crest - before.crest
        return f"Crest {before.crest:.2f} → {after.crest:.2f} dB (Δ {crest_delta:+.2f} dB)"


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
    def apply_clip_blend_compression(audio: np.ndarray, comp_params: Dict[str, float]) -> np.ndarray:
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


class DBConversion:
    """
    Unified dB conversion utilities to eliminate duplicate 20*log10 patterns.
    Replaces 17+ instances of the same calculation across processing modes.
    """

    @staticmethod
    def to_db(value: float, default: float = -np.inf) -> float:
        """
        Convert linear amplitude to dB with safe handling of zero/negative values.

        Args:
            value: Linear amplitude value (typically 0-1 for audio)
            default: Value to return if input is <= 0 (default: -np.inf)

        Returns:
            Amplitude in dB (20 * log10(value)) or default if value <= 0
        """
        return 20 * np.log10(value) if value > 0 else default

    @staticmethod
    def to_linear(db: float) -> float:
        """
        Convert dB to linear amplitude.

        Args:
            db: Value in dB

        Returns:
            Linear amplitude (10^(db/20))
        """
        return 10 ** (db / 20)

    @staticmethod
    def db_delta(before_db: float, after_db: float) -> float:
        """
        Calculate change in dB with safe handling of -inf values.

        Args:
            before_db: Before value in dB
            after_db: After value in dB

        Returns:
            Change in dB (after - before), handling -inf gracefully
        """
        if np.isinf(before_db) or np.isinf(after_db):
            return 0.0 if np.isinf(before_db) and np.isinf(after_db) else np.inf
        return after_db - before_db


class StereoWidthProcessor:
    """
    Unified stereo width processing with safety checks.
    Consolidates 70% duplicate logic between adaptive and continuous modes.
    """

    @staticmethod
    def validate_stereo(audio: np.ndarray) -> bool:
        """
        Check if audio is valid stereo.

        Args:
            audio: Audio array

        Returns:
            True if audio is 2D with 2 channels, False otherwise
        """
        return audio.ndim == 2 and audio.shape[1] == 2

    @staticmethod
    def get_peak_db(audio: np.ndarray) -> float:
        """
        Get peak amplitude in dB.

        Args:
            audio: Audio array

        Returns:
            Peak in dB using DBConversion
        """
        peak = np.max(np.abs(audio))
        return DBConversion.to_db(peak)

    @staticmethod
    def apply_stereo_width_safe(
        audio: np.ndarray,
        current_width: float,
        target_width: float,
        peak_db: float,
        safety_mode: str = "adaptive"
    ) -> np.ndarray:
        """
        Apply stereo width adjustment with safety checks to prevent peak clipping.

        Args:
            audio: Input audio array (must be stereo)
            current_width: Current stereo width (0-1)
            target_width: Target stereo width (0-1)
            peak_db: Current peak in dB
            safety_mode: Safety strategy ("adaptive" = limit expansion for loud material,
                                        "conservative" = skip expansion if peak > threshold)

        Returns:
            Audio with adjusted stereo width
        """
        # Strategy 1: Limit expansion for already-loud material (adaptive mode)
        if safety_mode == "adaptive":
            # For loud material with positive peaks, limit expansion
            if peak_db > 3.0 and target_width > current_width:
                max_width_increase = 0.6
                target_width = min(target_width, current_width + max_width_increase)
                debug(f"[Stereo Width] Limited expansion for loud material: target reduced to {target_width:.2f}")

        # Strategy 2: Skip expansion if peak is critically high (conservative mode)
        elif safety_mode == "conservative":
            if peak_db > 3.0 and target_width > current_width:
                debug(f"[Stereo Width] SKIPPED expansion due to high peak ({peak_db:.2f} dB)")
                return audio  # Return unmodified

        # Apply stereo width only if change is meaningful
        if abs(current_width - target_width) > 0.1:
            audio = adjust_stereo_width(audio, target_width)
            new_peak_db = StereoWidthProcessor.get_peak_db(audio)
            debug(f"[Stereo Width] Peak: {peak_db:.2f} → {new_peak_db:.2f} dB "
                  f"(width: {current_width:.2f} → {target_width:.2f})")

        return audio


class ProcessingLogger:
    """
    Unified logging for processing steps.
    Consolidates 41+ duplicate print/debug statement patterns across modes.
    """

    @staticmethod
    def pre_stage(stage_name: str, peak_db: float, rms_db: float, crest_db: float = None):
        """Log measurements before a processing stage."""
        if crest_db is not None:
            print(f"[{stage_name}] Peak: {peak_db:.2f} dB, RMS: {rms_db:.2f} dB, Crest: {crest_db:.2f} dB")
        else:
            print(f"[{stage_name}] Peak: {peak_db:.2f} dB, LUFS: {rms_db:.1f}")

    @staticmethod
    def post_stage(stage_name: str, before_db: float, after_db: float, metric_type: str = "Peak"):
        """Log measurement change after a processing stage."""
        delta = after_db - before_db
        print(f"[{stage_name}] {metric_type}: {before_db:.2f} → {after_db:.2f} dB (change: {delta:+.2f} dB)")

    @staticmethod
    def safety_check(reason: str, peak_db: float = None):
        """Log safety check decisions."""
        if peak_db is not None:
            print(f"[{reason}] Peak {peak_db:.2f} dB")
        else:
            print(f"[{reason}]")

    @staticmethod
    def stereo_width_change(stage_name: str, before_width: float, after_width: float,
                           before_peak_db: float = None, after_peak_db: float = None):
        """Log stereo width adjustments."""
        if before_peak_db is not None and after_peak_db is not None:
            print(f"[{stage_name}] Peak: {before_peak_db:.2f} → {after_peak_db:.2f} dB "
                  f"(width: {before_width:.2f} → {after_width:.2f})")
        else:
            print(f"[{stage_name}] {before_width:.2f} → {after_width:.2f} (target: {after_width:.2f})")

    @staticmethod
    def gain_applied(stage_name: str, gain_db: float, target_db: float = None):
        """Log gain/boost application."""
        if target_db is not None:
            print(f"[{stage_name}] Applied {gain_db:+.2f} dB (target: {target_db:.1f} dB)")
        else:
            print(f"[{stage_name}] Applied {gain_db:+.2f} dB")

    @staticmethod
    def skipped(reason: str, detail: str = None):
        """Log when an operation is skipped."""
        if detail:
            print(f"[{reason}] SKIPPED - {detail}")
        else:
            print(f"[{reason}] SKIPPED")

    @staticmethod
    def limited(reason: str, original: float, limited: float):
        """Log when a value is limited/clamped."""
        print(f"[{reason}] Limited: {original:.2f} → {limited:.2f}")


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
    def apply_rms_reduction_expansion(audio: np.ndarray, exp_params: Dict[str, float]) -> np.ndarray:
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

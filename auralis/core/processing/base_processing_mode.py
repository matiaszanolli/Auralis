# -*- coding: utf-8 -*-

"""
Base Processing Mode
~~~~~~~~~~~~~~~~~~~~

Shared utilities and base class for audio processing modes.
Consolidates common measurement and debug boilerplate across modes.

DEPRECATED: This file is maintained for backward compatibility only.
New code should import from auralis.core.processing.base module instead:
    from auralis.core.processing.base import (
        AudioMeasurement,
        MeasurementUtilities,
        CompressionStrategies,
        ExpansionStrategies,
        DBConversion,
        StereoWidthProcessor,
        ProcessingLogger,
        SafetyLimiter,
        PeakNormalizer,
        NormalizationStep,
        FullAudioMeasurement
    )

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Any, Dict, Optional, Tuple, Union

import numpy as np

from ...dsp.basic import amplify, rms
from ...dsp.dynamics.soft_clipper import soft_clip
from ...dsp.unified import (
    adjust_stereo_width,
    calculate_loudness_units,
    stereo_width_analysis,
)
from ...utils.logging import debug


class AudioMeasurement:
    """Represents audio measurements (peak, RMS, crest factor)"""

    def __init__(self, peak: float, rms_val: float, peak_db: Optional[float] = None, rms_db: Optional[float] = None) -> None:
        """
        Initialize audio measurement

        Args:
            peak: Peak amplitude (linear, 0-1)
            rms_val: RMS level (linear, 0-1)
            peak_db: Peak in dB (optional, calculated if not provided)
            rms_db: RMS in dB (optional, calculated if not provided)
        """
        self.peak: float = peak
        self.rms: float = rms_val
        self.peak_db: float = peak_db if peak_db is not None else (20 * np.log10(peak) if peak > 0 else -np.inf)
        self.rms_db: float = rms_db if rms_db is not None else (20 * np.log10(rms_val) if rms_val > 0 else -np.inf)
        self.crest: float = self.peak_db - self.rms_db

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
    def pre_stage(stage_name: str, peak_db: float, rms_db: float, crest_db: Optional[float] = None) -> None:
        """Log measurements before a processing stage."""
        if crest_db is not None:
            print(f"[{stage_name}] Peak: {peak_db:.2f} dB, RMS: {rms_db:.2f} dB, Crest: {crest_db:.2f} dB")
        else:
            print(f"[{stage_name}] Peak: {peak_db:.2f} dB, LUFS: {rms_db:.1f}")

    @staticmethod
    def post_stage(stage_name: str, before_db: float, after_db: float, metric_type: str = "Peak") -> None:
        """Log measurement change after a processing stage."""
        delta = after_db - before_db
        print(f"[{stage_name}] {metric_type}: {before_db:.2f} → {after_db:.2f} dB (change: {delta:+.2f} dB)")

    @staticmethod
    def safety_check(reason: str, peak_db: Optional[float] = None) -> None:
        """Log safety check decisions."""
        if peak_db is not None:
            print(f"[{reason}] Peak {peak_db:.2f} dB")
        else:
            print(f"[{reason}]")

    @staticmethod
    def stereo_width_change(stage_name: str, before_width: float, after_width: float,
                           before_peak_db: Optional[float] = None, after_peak_db: Optional[float] = None) -> None:
        """Log stereo width adjustments."""
        if before_peak_db is not None and after_peak_db is not None:
            print(f"[{stage_name}] Peak: {before_peak_db:.2f} → {after_peak_db:.2f} dB "
                  f"(width: {before_width:.2f} → {after_width:.2f})")
        else:
            print(f"[{stage_name}] {before_width:.2f} → {after_width:.2f} (target: {after_width:.2f})")

    @staticmethod
    def gain_applied(stage_name: str, gain_db: float, target_db: Optional[float] = None) -> None:
        """Log gain/boost application."""
        if target_db is not None:
            print(f"[{stage_name}] Applied {gain_db:+.2f} dB (target: {target_db:.1f} dB)")
        else:
            print(f"[{stage_name}] Applied {gain_db:+.2f} dB")

    @staticmethod
    def skipped(reason: str, detail: Optional[str] = None) -> None:
        """Log when an operation is skipped."""
        if detail:
            print(f"[{reason}] SKIPPED - {detail}")
        else:
            print(f"[{reason}] SKIPPED")

    @staticmethod
    def limited(reason: str, original: float, limited: float) -> None:
        """Log when a value is limited/clamped."""
        print(f"[{reason}] Limited: {original:.2f} → {limited:.2f}")


class SafetyLimiter:
    """
    Unified safety limiter to prevent digital clipping.
    Consolidates safety checks across normalization pipelines.
    """

    SAFETY_THRESHOLD_DB = 1.0    # dBFS - threshold for applying limiter (allow more boost headroom)
    SOFT_CLIP_THRESHOLD = 0.89   # Linear amplitude threshold for soft_clip (~-1 dB)

    @staticmethod
    def apply_if_needed(audio: np.ndarray) -> Tuple[np.ndarray, bool]:
        """
        Apply soft clipping limiter if peak exceeds safety threshold.

        The soft clipping curve (tanh) provides gentle, musical peak limiting
        that prevents digital clipping without introducing hard distortion.

        Args:
            audio: Input audio array

        Returns:
            Tuple of (processed audio, was_limiter_applied: bool)
        """
        final_peak = np.max(np.abs(audio))
        final_peak_db = DBConversion.to_db(final_peak)

        if final_peak_db > SafetyLimiter.SAFETY_THRESHOLD_DB:
            ProcessingLogger.safety_check("Safety Limiter", final_peak_db)
            audio = soft_clip(audio, threshold=SafetyLimiter.SOFT_CLIP_THRESHOLD)

            # Measure result
            final_peak = np.max(np.abs(audio))
            final_peak_db = DBConversion.to_db(final_peak)
            print(f"[Safety Limiter] Peak reduced to {final_peak_db:.2f} dB")

            return audio, True

        return audio, False


class PeakNormalizer:
    """
    Unified peak normalization logic.
    Consolidates peak-based gain adjustments across processing modes.
    """

    @staticmethod
    def normalize_to_target(audio: np.ndarray, target_peak_db: float,
                           preset_name: Optional[str] = None) -> Tuple[np.ndarray, float]:
        """
        Normalize audio peak to target level.

        Args:
            audio: Input audio array
            target_peak_db: Target peak level in dB
            preset_name: Optional preset name for logging

        Returns:
            Tuple of (normalized audio, previous_peak_db)
        """
        peak = np.max(np.abs(audio))
        peak_db = DBConversion.to_db(peak)

        if preset_name:
            print(f"[Peak Normalization] Preset: {preset_name}, Target: {target_peak_db:.2f} dB")

        if peak > 0.001:  # Avoid division by zero
            target_peak = DBConversion.to_linear(target_peak_db)
            audio = audio * (target_peak / peak)
            ProcessingLogger.post_stage("Peak Normalization", peak_db, target_peak_db, "Peak")
            return audio, peak_db

        return audio, peak_db


class NormalizationStep:
    """
    Represents a single gain adjustment step in the normalization pipeline.
    Consolidates the measure-adjust-remeasure pattern.
    """

    def __init__(self, step_name: str, stage_label: Optional[str] = None) -> None:
        """
        Initialize normalization step.

        Args:
            step_name: Name of the step (e.g., "RMS Boost", "LUFS Normalization")
            stage_label: Optional pre-logging label (e.g., "Pre-Final")
        """
        self.step_name: str = step_name
        self.stage_label: Optional[str] = stage_label
        self.before_measurement: Optional[Dict[str, float]] = None
        self.after_measurement: Optional[Dict[str, float]] = None
        self.gain_applied_db: float = 0.0

    def measure_before(self, audio: np.ndarray, use_lufs: bool = False,
                      sample_rate: Optional[int] = None) -> Dict[str, float]:
        """
        Measure audio before adjustment.

        Args:
            audio: Audio array
            use_lufs: Whether to include LUFS measurement
            sample_rate: Sample rate (required if use_lufs=True)

        Returns:
            Dictionary with measurements (peak_db, rms_db, crest, [lufs])
        """
        peak = np.max(np.abs(audio))
        peak_db = DBConversion.to_db(peak)
        rms_val = rms(audio)
        rms_db = DBConversion.to_db(rms_val)
        crest = peak_db - rms_db

        measurement = {
            'peak_db': peak_db,
            'rms_db': rms_db,
            'crest': crest,
            'peak': peak,
            'rms': rms_val
        }

        if use_lufs and sample_rate:
            from ...dsp.unified import calculate_loudness_units
            lufs = calculate_loudness_units(audio, sample_rate)
            measurement['lufs'] = lufs

        self.before_measurement = measurement

        if self.stage_label:
            if 'lufs' in measurement:
                ProcessingLogger.pre_stage(self.stage_label, peak_db, measurement['lufs'])
            else:
                ProcessingLogger.pre_stage(self.stage_label, peak_db, rms_db, crest)

        return measurement

    def apply_gain(self, audio: np.ndarray, gain_db: float) -> np.ndarray:
        """
        Apply gain adjustment to audio.

        Args:
            audio: Input audio
            gain_db: Gain to apply in dB

        Returns:
            Audio with gain applied
        """
        if abs(gain_db) > 0.01:  # Only apply if meaningful change
            audio = amplify(audio, gain_db)
            self.gain_applied_db = gain_db

        return audio

    def measure_after(self, audio: np.ndarray, use_lufs: bool = False,
                     sample_rate: Optional[int] = None) -> Dict[str, float]:
        """
        Measure audio after adjustment.

        Args:
            audio: Audio array
            use_lufs: Whether to include LUFS measurement
            sample_rate: Sample rate (required if use_lufs=True)

        Returns:
            Dictionary with measurements
        """
        peak = np.max(np.abs(audio))
        peak_db = DBConversion.to_db(peak)
        rms_val = rms(audio)
        rms_db = DBConversion.to_db(rms_val)
        crest = peak_db - rms_db

        measurement: Dict[str, float] = {
            'peak_db': peak_db,
            'rms_db': rms_db,
            'crest': crest,
            'peak': peak,
            'rms': rms_val
        }

        if use_lufs and sample_rate:
            from ...dsp.unified import calculate_loudness_units
            lufs = calculate_loudness_units(audio, sample_rate)
            measurement['lufs'] = lufs

        self.after_measurement = measurement
        return measurement

    def log_summary(self) -> None:
        """Log before/after summary for this step."""
        if self.before_measurement and self.after_measurement:
            if 'lufs' in self.before_measurement:
                # LUFS-based logging (continuous mode)
                lufs_delta = (self.after_measurement.get('lufs', 0) -
                            self.before_measurement.get('lufs', 0))
                peak_delta = (self.after_measurement['peak_db'] -
                            self.before_measurement['peak_db'])
                print(f"[{self.step_name}] LUFS: {self.before_measurement.get('lufs', 0):.1f} → "
                      f"{self.after_measurement.get('lufs', 0):.1f} (Δ {lufs_delta:+.1f}), "
                      f"Peak: {self.before_measurement['peak_db']:.2f} → "
                      f"{self.after_measurement['peak_db']:.2f} dB (Δ {peak_delta:+.2f})")
            else:
                # RMS/Crest-based logging (adaptive mode)
                peak_delta = (self.after_measurement['peak_db'] -
                            self.before_measurement['peak_db'])
                rms_delta = (self.after_measurement['rms_db'] -
                           self.before_measurement['rms_db'])
                crest_delta = (self.after_measurement['crest'] -
                             self.before_measurement['crest'])
                print(f"[{self.step_name}] Peak: {self.before_measurement['peak_db']:.2f} → "
                      f"{self.after_measurement['peak_db']:.2f} dB (Δ {peak_delta:+.2f}), "
                      f"RMS: {self.before_measurement['rms_db']:.2f} → "
                      f"{self.after_measurement['rms_db']:.2f} dB (Δ {rms_delta:+.2f})")


class FullAudioMeasurement:
    """
    Complete audio measurement at any point in processing pipeline.
    Consolidates all measurement types (peak, RMS, crest, LUFS) in one place.
    """

    def __init__(self, audio: np.ndarray, sample_rate: Optional[int] = None, label: Optional[str] = None) -> None:
        """
        Initialize with comprehensive audio analysis.

        Args:
            audio: Audio array to measure
            sample_rate: Sample rate (optional, for LUFS calculation)
            label: Optional label for identification
        """
        self.label: Optional[str] = label
        self.peak: float = np.max(np.abs(audio))
        self.peak_db: float = DBConversion.to_db(self.peak)
        self.rms: float = rms(audio)
        self.rms_db: float = DBConversion.to_db(self.rms)
        self.crest: float = self.peak_db - self.rms_db
        self.lufs: Optional[float] = None

        if sample_rate:
            from ...dsp.unified import calculate_loudness_units
            self.lufs = calculate_loudness_units(audio, sample_rate)

    def to_dict(self) -> Dict[str, float]:
        """Convert measurement to dictionary."""
        data: Dict[str, float] = {
            'peak': self.peak,
            'peak_db': self.peak_db,
            'rms': self.rms,
            'rms_db': self.rms_db,
            'crest': self.crest
        }
        if self.lufs is not None:
            data['lufs'] = self.lufs
        return data

    def __str__(self) -> str:
        """String representation of measurement."""
        if self.lufs is not None:
            return (f"[{self.label or 'Measurement'}] Peak: {self.peak_db:.2f} dB, "
                   f"RMS: {self.rms_db:.2f} dB, Crest: {self.crest:.2f} dB, LUFS: {self.lufs:.1f}")
        else:
            return (f"[{self.label or 'Measurement'}] Peak: {self.peak_db:.2f} dB, "
                   f"RMS: {self.rms_db:.2f} dB, Crest: {self.crest:.2f} dB")


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

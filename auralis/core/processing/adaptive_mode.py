"""
Adaptive Mode Processing
~~~~~~~~~~~~~~~~~~~~~~~~~

Spectrum-based adaptive processing without reference tracks

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from typing import Any

import numpy as np

from ...dsp.basic import amplify, rms
from ...dsp.utils.adaptive import calculate_loudness_units
from ...dsp.utils.adaptive_loudness import AdaptiveLoudnessControl
from ...dsp.utils.conversion import peak_db
from ...dsp.utils.stereo import stereo_width_analysis
from ...utils.audio_validation import validate_audio_finite
from ...utils.logging import debug
from .base import (
    CompressionStrategies,
    DBConversion,
    ExpansionStrategies,
    NormalizationStep,
    PeakNormalizer,
    ProcessingLogger,
    SafetyLimiter,
    StereoWidthProcessor,
)


from .adaptive_normalization import apply_final_normalization


class AdaptiveMode:
    """
    Adaptive processing mode - intelligent mastering without reference tracks
    Uses spectrum-based analysis to determine optimal processing parameters

    Legacy path. The adaptive engine is ``ContinuousMode``; ``AdaptiveMode`` is
    retained as the adaptive component of the ``hybrid`` and ``reference``
    mastering modes (see ``HybridMode``). Do not remove it without also
    retiring those modes. See docs/development/STREAMLINING_PLAN.md #5.
    """

    def __init__(self, config: Any, content_analyzer: Any, target_generator: Any, spectrum_mapper: Any) -> None:
        """
        Initialize adaptive mode processor

        Args:
            config: UnifiedConfig instance
            content_analyzer: ContentAnalyzer instance
            target_generator: AdaptiveTargetGenerator instance
            spectrum_mapper: SpectrumMapper instance
        """
        self.config = config
        self.content_analyzer = content_analyzer
        self.target_generator = target_generator
        self.spectrum_mapper = spectrum_mapper
        self.last_content_profile: dict[str, Any] | None = None

    def process(self, target_audio: np.ndarray, eq_processor: Any) -> np.ndarray:
        """
        Process audio using adaptive mastering

        Args:
            target_audio: Input audio array
            eq_processor: EQ processor instance for psychoacoustic EQ

        Returns:
            Processed audio array
        """
        debug("Applying spectrum-based adaptive processing")

        processed_audio = target_audio.copy()

        # Analyze content first
        content_profile = self.content_analyzer.analyze_content(processed_audio)

        # Store content profile for potential user learning
        self.last_content_profile = content_profile

        # Analyze input level and add to content profile
        input_level_info = self.content_analyzer.analyze_input_level(processed_audio)
        content_profile['input_level_info'] = input_level_info

        # SPECTRUM-BASED PROCESSING: Get position on spectrum
        spectrum_position = self.spectrum_mapper.analyze_to_spectrum_position(content_profile)

        # Get user's preset as a hint (not a rigid rule)
        preset_profile = self.config.get_preset_profile()
        preset_hint = preset_profile.name.lower() if preset_profile else 'adaptive'

        # Calculate processing parameters from spectrum position
        spectrum_params = self.spectrum_mapper.calculate_processing_parameters(
            spectrum_position,
            user_preset_hint=preset_hint
        )

        debug(f"[Spectrum Position] Level:{spectrum_position.input_level:.2f} "
              f"Dynamics:{spectrum_position.dynamic_range:.2f} "
              f"Balance:{spectrum_position.spectral_balance:.2f} "
              f"Energy:{spectrum_position.energy:.2f}")

        debug(f"[Spectrum Params] Compression:{spectrum_params.compression_ratio:.2f}@{spectrum_params.compression_amount:.2f} "
              f"InputGain:{spectrum_params.input_gain:+.1f}dB "
              f"TargetRMS:{spectrum_params.output_target_rms:.1f}dB")

        # Apply input gain from spectrum calculation
        if abs(spectrum_params.input_gain) > 0.5:
            processed_audio = amplify(processed_audio, spectrum_params.input_gain)
            debug(f"[Spectrum Gain Staging] Applied {spectrum_params.input_gain:+.2f} dB input gain")

        # Track loudness through each processing stage
        before_eq_lufs = calculate_loudness_units(processed_audio, self.config.internal_sample_rate)
        debug(f"[STAGE 1] Before EQ: {before_eq_lufs:.2f} LUFS")

        # Generate adaptive targets
        targets = self.target_generator.generate_targets(content_profile)

        # Apply psychoacoustic EQ adjustments with content awareness
        processed_audio = eq_processor.apply_psychoacoustic_eq(processed_audio, targets, content_profile)

        after_eq_lufs = calculate_loudness_units(processed_audio, self.config.internal_sample_rate)
        peak_after_eq_db = peak_db(processed_audio)
        debug(f"[After EQ] Peak: {peak_after_eq_db:.2f} dB")
        debug(f"[STAGE 2] After EQ: {after_eq_lufs:.2f} LUFS (change: {after_eq_lufs - before_eq_lufs:+.2f} dB)")

        # Apply dynamics processing
        processed_audio = self._apply_dynamics_processing(processed_audio, spectrum_params)

        # Apply stereo width adjustment
        processed_audio = self._apply_stereo_width(processed_audio, targets)

        # Apply final normalization
        processed_audio = self._apply_final_normalization(
            processed_audio, spectrum_params
        )

        return processed_audio

    def _apply_dynamics_processing(self, audio: np.ndarray,
                                   spectrum_params: Any) -> np.ndarray:
        """Apply continuously weighted compression and expansion."""

        source_lufs = calculate_loudness_units(audio, self.config.internal_sample_rate)
        current_peak = np.max(np.abs(audio))
        current_peak_db = DBConversion.to_db(current_peak)
        current_rms = rms(audio)
        current_rms_db = DBConversion.to_db(current_rms)
        crest_factor_db = current_peak_db - current_rms_db

        loudness_coordinate = 0.5 + 0.5 * np.tanh(
            (source_lufs + 14.3887) / (2.0 * 2.7732)
        )
        crest_coordinate = 0.5 + 0.5 * np.tanh(
            (crest_factor_db - 13.4207) / (2.0 * 1.7884)
        )
        expansion_response = loudness_coordinate * (1.0 - crest_coordinate)

        base_compression = float(np.clip(spectrum_params.compression_amount, 0.0, 1.0))
        base_expansion = float(np.clip(spectrum_params.expansion_amount, 0.0, 1.0))
        spectrum_params.compression_amount = (
            base_compression * (1.0 - expansion_response)
        )
        spectrum_params.expansion_amount = (
            1.0 - (1.0 - base_expansion) * (1.0 - expansion_response)
        )

        debug(
            f"[2D dynamics] LUFS {source_lufs:.1f}, crest {crest_factor_db:.1f}, "
            f"compression {spectrum_params.compression_amount:.2f}, "
            f"expansion {spectrum_params.expansion_amount:.2f}"
        )

        audio = self._apply_compression(audio, spectrum_params)
        audio = self._apply_expansion(audio, spectrum_params)
        audio = amplify(audio, -0.5 * expansion_response)

        return audio

    def _apply_compression(self, audio: np.ndarray, spectrum_params: Any) -> np.ndarray:
        """Apply DIY compression to reduce crest factor"""
        return CompressionStrategies.apply_soft_knee_compression(
            audio,
            spectrum_params.compression_amount
        )

    def _apply_expansion(self, audio: np.ndarray, spectrum_params: Any) -> np.ndarray:
        """Apply DIY expansion to increase crest factor (de-mastering)"""
        return ExpansionStrategies.apply_peak_enhancement_expansion(
            audio,
            spectrum_params.expansion_amount
        )

    def _apply_stereo_width(self, audio: np.ndarray, targets: dict[str, Any]) -> np.ndarray:
        """Apply stereo width adjustment through the shared safety gate.

        The hard ``input_level > 0.8`` clamp this stage used to run inline is
        gone: ``StereoWidthProcessor.apply_stereo_width_safe`` is the single
        implementation and carries #5108's smooth peak knee, so widening eases
        off toward clipping instead of stepping (#6192).
        """

        if not StereoWidthProcessor.validate_stereo(audio):
            return audio

        peak_before_stereo_db = StereoWidthProcessor.get_peak_db(audio)
        # Measurement (decorrelation, 0 = mono) vs instruction (width factor,
        # 0.5 = unchanged) — different axes, never compare them (#4503).
        current_decorrelation = stereo_width_analysis(audio)

        return StereoWidthProcessor.apply_stereo_width_safe(
            audio, current_decorrelation, targets["stereo_width"],
            peak_before_stereo_db, self.config.internal_sample_rate,
        )

    def _apply_final_normalization(self, audio: np.ndarray, spectrum_params: Any) -> np.ndarray:
        return apply_final_normalization(self, audio, spectrum_params)

    def get_last_content_profile(self) -> dict[str, Any] | None:
        """Get the last analyzed content profile"""
        return self.last_content_profile

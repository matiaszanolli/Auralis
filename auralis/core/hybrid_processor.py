# -*- coding: utf-8 -*-

"""
Hybrid Audio Processor
~~~~~~~~~~~~~~~~~~~~~~

Unified processor supporting both reference-based and adaptive mastering

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.

Main processing engine that bridges Matchering and Auralis systems
"""

import numpy as np
from typing import Optional, Union, List, Tuple, Dict, Any
from pathlib import Path

from .unified_config import UnifiedConfig, GenreProfile
from ..dsp.unified import (
    rms, normalize, amplify, spectral_centroid, spectral_rolloff,
    zero_crossing_rate, crest_factor, tempo_estimate, adaptive_gain_calculation,
    psychoacoustic_weighting, smooth_parameter_transition,
    calculate_loudness_units, stereo_width_analysis, adjust_stereo_width
)
from ..utils.logging import debug, info
from ..io.results import Result


class ContentAnalyzer:
    """Basic content analysis for adaptive processing"""

    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self.genre_confidence_threshold = 0.6

    def analyze_content(self, audio: np.ndarray) -> Dict[str, Any]:
        """
        Analyze audio content for adaptive processing

        Args:
            audio: Audio signal to analyze

        Returns:
            Dictionary containing content analysis results
        """
        debug("Analyzing audio content for adaptive processing")

        if audio.ndim == 2:
            # Convert stereo to mono for analysis
            mono_audio = np.mean(audio, axis=1)
        else:
            mono_audio = audio

        # Basic audio features
        rms_value = rms(audio)
        peak_value = np.max(np.abs(audio))
        crest_factor_db = crest_factor(audio)

        # Spectral features
        centroid = spectral_centroid(mono_audio, self.sample_rate)
        rolloff = spectral_rolloff(mono_audio, self.sample_rate)
        zcr = zero_crossing_rate(mono_audio)

        # Temporal features
        estimated_tempo = tempo_estimate(mono_audio, self.sample_rate)

        # Stereo analysis (if applicable)
        stereo_info = {}
        if audio.ndim == 2 and audio.shape[1] == 2:
            stereo_info = {
                "width": stereo_width_analysis(audio),
                "is_stereo": True
            }
        else:
            stereo_info = {
                "width": 0.5,
                "is_stereo": False
            }

        # Simple genre classification based on features
        genre_info = self._classify_genre(
            centroid, rolloff, zcr, estimated_tempo, crest_factor_db
        )

        content_profile = {
            # Basic properties
            "rms": float(rms_value),
            "peak": float(peak_value),
            "crest_factor_db": float(crest_factor_db),
            "estimated_lufs": float(calculate_loudness_units(audio, self.sample_rate)),

            # Spectral properties
            "spectral_centroid": float(centroid),
            "spectral_rolloff": float(rolloff),
            "zero_crossing_rate": float(zcr),

            # Temporal properties
            "estimated_tempo": float(estimated_tempo),

            # Stereo properties
            "stereo_info": stereo_info,

            # Genre classification
            "genre_info": genre_info,

            # Energy characteristics
            "energy_level": self._categorize_energy_level(rms_value),
            "dynamic_range": self._estimate_dynamic_range(audio)
        }

        debug(f"Content analysis complete: genre={genre_info['primary']}, "
              f"energy={content_profile['energy_level']}, "
              f"tempo={estimated_tempo:.1f} BPM")

        return content_profile

    def _classify_genre(self, centroid: float, rolloff: float, zcr: float,
                       tempo: float, crest_factor_db: float) -> Dict[str, Any]:
        """Simple genre classification based on audio features"""

        # Genre classification rules (simplified)
        genre_scores = {
            "classical": 0.0,
            "rock": 0.0,
            "electronic": 0.0,
            "jazz": 0.0,
            "pop": 0.0,
            "hip_hop": 0.0,
            "acoustic": 0.0,
            "ambient": 0.0
        }

        # Tempo-based classification
        if tempo < 80:
            genre_scores["ambient"] += 0.3
            genre_scores["classical"] += 0.2
        elif tempo > 140:
            genre_scores["electronic"] += 0.3
            genre_scores["rock"] += 0.2

        # Spectral centroid-based classification
        if centroid > 3000:
            genre_scores["electronic"] += 0.2
            genre_scores["rock"] += 0.2
        elif centroid < 1500:
            genre_scores["classical"] += 0.2
            genre_scores["ambient"] += 0.2

        # Zero crossing rate-based classification
        if zcr > 0.1:
            genre_scores["rock"] += 0.2
            genre_scores["electronic"] += 0.1
        elif zcr < 0.05:
            genre_scores["classical"] += 0.2

        # Crest factor-based classification
        if crest_factor_db > 15:
            genre_scores["classical"] += 0.3
            genre_scores["jazz"] += 0.2
        elif crest_factor_db < 8:
            genre_scores["electronic"] += 0.2
            genre_scores["pop"] += 0.2

        # Find the genre with highest score
        primary_genre = max(genre_scores, key=genre_scores.get)
        confidence = genre_scores[primary_genre]

        # If confidence is too low, use "pop" as safe default
        if confidence < self.genre_confidence_threshold:
            primary_genre = "pop"
            confidence = 0.5

        return {
            "primary": primary_genre,
            "confidence": confidence,
            "scores": genre_scores
        }

    def _categorize_energy_level(self, rms_value: float) -> str:
        """Categorize energy level of audio"""
        if rms_value > 0.3:
            return "high"
        elif rms_value > 0.1:
            return "medium"
        else:
            return "low"

    def _estimate_dynamic_range(self, audio: np.ndarray) -> float:
        """Estimate dynamic range in dB"""
        if len(audio) == 0:
            return 0.0

        # Calculate RMS in 1-second windows
        window_size = 44100  # 1 second at 44.1 kHz
        rms_values = []

        for i in range(0, len(audio) - window_size, window_size // 2):
            window = audio[i:i + window_size]
            if audio.ndim == 2:
                window_rms = np.sqrt(np.mean(np.mean(window, axis=1) ** 2))
            else:
                window_rms = np.sqrt(np.mean(window ** 2))
            rms_values.append(window_rms)

        if len(rms_values) < 2:
            return 20.0  # Default dynamic range

        rms_values = np.array(rms_values)
        rms_values = rms_values[rms_values > 1e-6]  # Remove silence

        if len(rms_values) == 0:
            return 20.0

        # Calculate dynamic range as difference between 95th and 10th percentile
        loud_level = np.percentile(rms_values, 95)
        quiet_level = np.percentile(rms_values, 10)

        if quiet_level > 0:
            dynamic_range = 20 * np.log10(loud_level / quiet_level)
            return float(np.clip(dynamic_range, 0, 60))
        else:
            return 20.0


class AdaptiveTargetGenerator:
    """Generate adaptive processing targets based on content analysis"""

    def __init__(self, config: UnifiedConfig):
        self.config = config

    def generate_targets(self, content_profile: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate adaptive processing targets

        Args:
            content_profile: Content analysis results

        Returns:
            Dictionary containing processing targets
        """
        debug("Generating adaptive processing targets")

        # Get base genre profile
        genre = content_profile["genre_info"]["primary"]
        genre_profile = self.config.get_genre_profile(genre)

        # Adapt targets based on content characteristics
        targets = self._adapt_targets_to_content(genre_profile, content_profile)

        debug(f"Generated targets for {genre}: LUFS={targets['target_lufs']:.1f}, "
              f"compression={targets['compression_ratio']:.1f}")

        return targets

    def _adapt_targets_to_content(self, genre_profile: GenreProfile,
                                 content_profile: Dict[str, Any]) -> Dict[str, Any]:
        """Adapt generic genre targets to specific content characteristics"""

        # Start with genre profile
        targets = {
            "target_lufs": genre_profile.target_lufs,
            "bass_boost_db": genre_profile.bass_boost_db,
            "midrange_clarity_db": genre_profile.midrange_clarity_db,
            "treble_enhancement_db": genre_profile.treble_enhancement_db,
            "compression_ratio": genre_profile.compression_ratio,
            "stereo_width": genre_profile.stereo_width,
            "mastering_intensity": genre_profile.mastering_intensity
        }

        # Adapt based on energy level
        energy_level = content_profile["energy_level"]
        if energy_level == "low":
            targets["target_lufs"] += 2.0  # Boost quiet content
            targets["compression_ratio"] *= 1.2
        elif energy_level == "high":
            targets["target_lufs"] -= 1.0  # Be more conservative with loud content
            targets["compression_ratio"] *= 0.8

        # Adapt based on dynamic range
        dynamic_range = content_profile["dynamic_range"]
        if dynamic_range > 25:  # High dynamic range
            targets["compression_ratio"] *= 0.7  # Less compression
            targets["mastering_intensity"] *= 0.8
        elif dynamic_range < 10:  # Low dynamic range (already compressed)
            targets["compression_ratio"] *= 0.5  # Much less compression
            targets["target_lufs"] -= 2.0  # Don't push it louder

        # Adapt based on spectral characteristics
        centroid = content_profile["spectral_centroid"]
        if centroid > 3500:  # Very bright content
            targets["treble_enhancement_db"] -= 1.0
        elif centroid < 1000:  # Very dark content
            targets["treble_enhancement_db"] += 1.0
            targets["midrange_clarity_db"] += 0.5

        # Adapt based on stereo information
        if content_profile["stereo_info"]["is_stereo"]:
            stereo_width = content_profile["stereo_info"]["width"]
            if stereo_width < 0.3:  # Narrow stereo
                targets["stereo_width"] = min(targets["stereo_width"] * 1.2, 1.0)
            elif stereo_width > 0.8:  # Very wide stereo
                targets["stereo_width"] = max(targets["stereo_width"] * 0.8, 0.3)

        # Apply adaptation strength from config
        adaptation_strength = self.config.adaptive.adaptation_strength
        for key in targets:
            if key != "target_lufs":  # Don't scale LUFS target
                # Get the corresponding genre profile value
                if key == "bass_boost_db":
                    genre_value = genre_profile.bass_boost_db
                elif key == "midrange_clarity_db":
                    genre_value = genre_profile.midrange_clarity_db
                elif key == "treble_enhancement_db":
                    genre_value = genre_profile.treble_enhancement_db
                elif key == "compression_ratio":
                    genre_value = genre_profile.compression_ratio
                elif key == "stereo_width":
                    genre_value = genre_profile.stereo_width
                else:
                    genre_value = targets[key]  # Use adapted value if no match

                # Blend between genre default and adapted value
                targets[key] = (genre_value * (1 - adaptation_strength) +
                              targets[key] * adaptation_strength)

        return targets


class HybridProcessor:
    """
    Main hybrid processor supporting reference-based and adaptive mastering
    """

    def __init__(self, config: UnifiedConfig):
        self.config = config
        self.content_analyzer = ContentAnalyzer(config.internal_sample_rate)
        self.target_generator = AdaptiveTargetGenerator(config)

        # Processing state
        self.current_targets = None
        self.processing_history = []

        debug(f"Hybrid processor initialized in {config.adaptive.mode} mode")

    def process(
        self,
        target: Union[str, np.ndarray],
        reference: Optional[Union[str, np.ndarray]] = None,
        results: Union[str, List[str], Result, List[Result]] = None,
        preview_target: Optional[Result] = None,
        preview_result: Optional[Result] = None
    ) -> Optional[np.ndarray]:
        """
        Main processing function supporting both reference and adaptive modes

        Args:
            target: Target audio file path or array
            reference: Reference audio file path or array (optional for adaptive mode)
            results: Output file path(s) or Result object(s)
            preview_target: Preview target result (optional)
            preview_result: Preview result output (optional)

        Returns:
            Processed audio array (if no file output specified)
        """
        info(f"Starting hybrid processing in {self.config.adaptive.mode} mode")

        # Load target audio (simplified for now - will be enhanced with unified I/O)
        if isinstance(target, str):
            target_audio = self._load_audio_placeholder(target)
        else:
            target_audio = target

        # Process based on mode
        if self.config.is_reference_mode() and reference is not None:
            return self._process_reference_mode(target_audio, reference, results)
        elif self.config.is_adaptive_mode():
            return self._process_adaptive_mode(target_audio, results)
        elif self.config.is_hybrid_mode():
            return self._process_hybrid_mode(target_audio, reference, results)
        else:
            raise ValueError(f"Invalid processing mode: {self.config.adaptive.mode}")

    def _process_reference_mode(self, target_audio: np.ndarray,
                               reference: Union[str, np.ndarray],
                               results) -> np.ndarray:
        """Process using traditional reference-based matching"""
        info("Processing in reference mode")

        # Load reference audio
        if isinstance(reference, str):
            reference_audio = self._load_audio_placeholder(reference)
        else:
            reference_audio = reference

        # Traditional Matchering-style processing
        return self._apply_reference_matching(target_audio, reference_audio)

    def _process_adaptive_mode(self, target_audio: np.ndarray, results) -> np.ndarray:
        """Process using adaptive mastering without reference"""
        info("Processing in adaptive mode")

        # Analyze content
        content_profile = self.content_analyzer.analyze_content(target_audio)

        # Generate adaptive targets
        targets = self.target_generator.generate_targets(content_profile)

        # Apply adaptive processing
        return self._apply_adaptive_processing(target_audio, targets)

    def _process_hybrid_mode(self, target_audio: np.ndarray,
                            reference: Optional[Union[str, np.ndarray]],
                            results) -> np.ndarray:
        """Process using hybrid approach combining reference and adaptive"""
        info("Processing in hybrid mode")

        # Always analyze content for hybrid mode
        content_profile = self.content_analyzer.analyze_content(target_audio)

        if reference is not None:
            # Use reference with adaptive enhancement
            if isinstance(reference, str):
                reference_audio = self._load_audio_placeholder(reference)
            else:
                reference_audio = reference

            return self._apply_hybrid_processing(target_audio, reference_audio, content_profile)
        else:
            # Fall back to pure adaptive mode
            targets = self.target_generator.generate_targets(content_profile)
            return self._apply_adaptive_processing(target_audio, targets)

    def _apply_reference_matching(self, target_audio: np.ndarray,
                                 reference_audio: np.ndarray) -> np.ndarray:
        """Apply traditional reference-based matching"""
        debug("Applying reference-based matching")

        # Calculate RMS levels
        target_rms = rms(target_audio)
        reference_rms = rms(reference_audio)

        # Calculate gain to match RMS levels
        if target_rms > 0:
            gain_factor = reference_rms / target_rms
            # Limit gain to reasonable range
            gain_factor = np.clip(gain_factor, 0.1, 10.0)
        else:
            gain_factor = 1.0

        # Apply gain
        matched_audio = target_audio * gain_factor

        # Apply gentle normalization to prevent clipping
        return normalize(matched_audio, 0.98)

    def _apply_adaptive_processing(self, target_audio: np.ndarray,
                                  targets: Dict[str, Any]) -> np.ndarray:
        """Apply adaptive processing based on generated targets"""
        debug("Applying adaptive processing")

        processed_audio = target_audio.copy()

        # Apply loudness adjustment
        current_lufs = calculate_loudness_units(processed_audio, self.config.internal_sample_rate)
        target_lufs = targets["target_lufs"]

        if abs(current_lufs - target_lufs) > 1.0:  # Only adjust if significant difference
            lufs_gain_db = target_lufs - current_lufs
            # Limit gain adjustment
            lufs_gain_db = np.clip(lufs_gain_db, -12, 12)
            processed_audio = amplify(processed_audio, lufs_gain_db)

        # Apply simple EQ adjustments (placeholder - will be enhanced)
        processed_audio = self._apply_simple_eq(processed_audio, targets)

        # Apply stereo width adjustment
        if processed_audio.ndim == 2 and processed_audio.shape[1] == 2:
            current_width = stereo_width_analysis(processed_audio)
            target_width = targets["stereo_width"]
            if abs(current_width - target_width) > 0.1:
                processed_audio = adjust_stereo_width(processed_audio, target_width)

        # Apply gentle normalization
        return normalize(processed_audio, 0.98)

    def _apply_hybrid_processing(self, target_audio: np.ndarray,
                                reference_audio: np.ndarray,
                                content_profile: Dict[str, Any]) -> np.ndarray:
        """Apply hybrid processing combining reference and adaptive approaches"""
        debug("Applying hybrid processing")

        # Start with reference matching
        reference_matched = self._apply_reference_matching(target_audio, reference_audio)

        # Generate adaptive targets
        targets = self.target_generator.generate_targets(content_profile)

        # Apply adaptive enhancements with reduced intensity
        adaptation_strength = self.config.adaptive.adaptation_strength * 0.5  # Reduced for hybrid

        # Blend reference matching with adaptive processing
        adaptive_processed = self._apply_adaptive_processing(target_audio, targets)

        # Blend the two results
        blended_audio = (reference_matched * (1 - adaptation_strength) +
                        adaptive_processed * adaptation_strength)

        return normalize(blended_audio, 0.98)

    def _apply_simple_eq(self, audio: np.ndarray, targets: Dict[str, Any]) -> np.ndarray:
        """Apply simple EQ adjustments (placeholder implementation)"""
        # This is a simplified placeholder - will be enhanced with proper EQ
        processed = audio.copy()

        # Very basic frequency adjustment using simple filtering
        bass_gain_db = targets.get("bass_boost_db", 0.0)
        treble_gain_db = targets.get("treble_enhancement_db", 0.0)

        # Apply very gentle adjustments (limited for safety)
        if abs(bass_gain_db) > 0.5:
            bass_gain_linear = 10 ** (np.clip(bass_gain_db, -6, 6) / 20)
            # This is a placeholder - proper EQ implementation will come later
            processed = processed * (1.0 + (bass_gain_linear - 1.0) * 0.1)

        if abs(treble_gain_db) > 0.5:
            treble_gain_linear = 10 ** (np.clip(treble_gain_db, -6, 6) / 20)
            # This is a placeholder - proper EQ implementation will come later
            processed = processed * (1.0 + (treble_gain_linear - 1.0) * 0.1)

        return processed

    def _load_audio_placeholder(self, file_path: str) -> np.ndarray:
        """Placeholder for audio loading - will be replaced with unified I/O"""
        # This is a placeholder - will be replaced with proper audio loading
        debug(f"Loading audio file: {file_path}")
        # For now, return dummy audio data
        return np.random.randn(44100 * 5, 2) * 0.1  # 5 seconds of dummy stereo audio

    def get_processing_info(self) -> Dict[str, Any]:
        """Get information about current processing configuration"""
        return {
            "mode": self.config.adaptive.mode,
            "sample_rate": self.config.internal_sample_rate,
            "fft_size": self.config.fft_size,
            "adaptation_strength": self.config.adaptive.adaptation_strength,
            "enable_genre_detection": self.config.adaptive.enable_genre_detection,
            "available_genres": list(self.config.genre_profiles.keys()),
            "current_targets": self.current_targets
        }

    def set_processing_mode(self, mode: str):
        """Change processing mode"""
        if mode in ["reference", "adaptive", "hybrid"]:
            self.config.set_processing_mode(mode)
            debug(f"Processing mode changed to: {mode}")
        else:
            raise ValueError(f"Invalid processing mode: {mode}")


# Convenience functions for quick processing
def process_adaptive(target: Union[str, np.ndarray],
                    config: Optional[UnifiedConfig] = None) -> np.ndarray:
    """Quick adaptive processing function"""
    if config is None:
        config = UnifiedConfig()
        config.set_processing_mode("adaptive")

    processor = HybridProcessor(config)
    return processor.process(target)


def process_reference(target: Union[str, np.ndarray],
                     reference: Union[str, np.ndarray],
                     config: Optional[UnifiedConfig] = None) -> np.ndarray:
    """Quick reference-based processing function"""
    if config is None:
        config = UnifiedConfig()
        config.set_processing_mode("reference")

    processor = HybridProcessor(config)
    return processor.process(target, reference)


def process_hybrid(target: Union[str, np.ndarray],
                  reference: Optional[Union[str, np.ndarray]] = None,
                  config: Optional[UnifiedConfig] = None) -> np.ndarray:
    """Quick hybrid processing function"""
    if config is None:
        config = UnifiedConfig()
        config.set_processing_mode("hybrid")

    processor = HybridProcessor(config)
    return processor.process(target, reference)
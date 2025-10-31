# -*- coding: utf-8 -*-

"""
EQ Processor
~~~~~~~~~~~~

Psychoacoustic EQ integration and processing

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
from typing import Dict, Any, Optional
from ...dsp.psychoacoustic_eq import PsychoacousticEQ
from ...utils.logging import debug


class EQProcessor:
    """
    Manages psychoacoustic EQ processing with content awareness
    """

    def __init__(self, psychoacoustic_eq: PsychoacousticEQ):
        """
        Initialize EQ processor

        Args:
            psychoacoustic_eq: PsychoacousticEQ instance
        """
        self.psychoacoustic_eq = psychoacoustic_eq

    def apply_psychoacoustic_eq(self, audio: np.ndarray, targets: Dict[str, Any],
                                content_profile: Optional[Dict[str, Any]] = None) -> np.ndarray:
        """
        Apply psychoacoustic EQ adjustments based on adaptive targets and content analysis

        Args:
            audio: Input audio array
            targets: Processing targets dictionary
            content_profile: Optional content analysis profile

        Returns:
            EQ-processed audio array
        """
        debug("Applying psychoacoustic EQ processing")

        try:
            # Create EQ curve from targets and content analysis
            eq_curve = self._targets_to_eq_curve(targets, content_profile)

            # Apply psychoacoustic EQ using real-time processing
            processed = self._process_with_psychoacoustic_eq(audio, eq_curve, content_profile)

            debug("Psychoacoustic EQ processing completed successfully")
            return processed

        except Exception as e:
            debug(f"Psychoacoustic EQ failed, falling back to simple EQ: {e}")
            return self._apply_simple_eq_fallback(audio, targets)

    def _targets_to_eq_curve(self, targets: Dict[str, Any],
                            content_profile: Optional[Dict[str, Any]] = None) -> Dict[str, float]:
        """
        Convert adaptive targets to EQ curve parameters with content awareness

        Args:
            targets: Processing targets
            content_profile: Optional content analysis

        Returns:
            EQ curve parameters dictionary
        """
        # Base EQ curve from targets
        eq_curve = {
            # Bass frequencies (20-250 Hz)
            'bass_boost': targets.get("bass_boost_db", 0.0),

            # Low-midrange (250-500 Hz) - Use preset-specific if available
            'low_mid_boost': targets.get("preset_low_mid_gain", targets.get("bass_boost_db", 0.0) * 0.5),

            # Midrange (500-2000 Hz)
            'mid_boost': targets.get("midrange_clarity_db", 0.0),

            # High-midrange (2000-4000 Hz) - Use preset-specific if available
            'high_mid_boost': targets.get("preset_high_mid_gain", targets.get("midrange_clarity_db", 0.0) * 0.7),

            # Treble (4000+ Hz)
            'treble_boost': targets.get("treble_enhancement_db", 0.0),

            # Overall intensity
            'mastering_intensity': targets.get("mastering_intensity", 0.5)
        }

        # Apply content-aware adjustments
        if content_profile:
            eq_curve = self._apply_content_adjustments(eq_curve, content_profile)

        return eq_curve

    def _apply_content_adjustments(self, eq_curve: Dict[str, float],
                                   content_profile: Dict[str, Any]) -> Dict[str, float]:
        """
        Adjust EQ curve based on content analysis

        Args:
            eq_curve: Base EQ curve
            content_profile: Content analysis profile

        Returns:
            Adjusted EQ curve
        """
        # Adjust based on spectral characteristics
        centroid = content_profile.get("spectral_centroid", 2000)
        if centroid > 3500:  # Very bright content
            eq_curve['treble_boost'] *= 0.7  # Reduce treble boost
            eq_curve['high_mid_boost'] *= 0.8
        elif centroid < 1000:  # Very dark content
            eq_curve['treble_boost'] *= 1.3  # Increase treble boost
            eq_curve['mid_boost'] *= 1.2

        # Adjust based on genre
        genre_info = content_profile.get("genre_info", {})
        primary_genre = genre_info.get("primary", "pop")

        if primary_genre == "electronic":
            eq_curve['bass_boost'] *= 1.2
            eq_curve['treble_boost'] *= 1.1
        elif primary_genre == "classical":
            eq_curve['bass_boost'] *= 0.8
            eq_curve['mid_boost'] *= 1.2
        elif primary_genre == "rock":
            eq_curve['mid_boost'] *= 1.3
            eq_curve['high_mid_boost'] *= 1.2

        # Adjust based on dynamic range
        dynamic_range = content_profile.get("dynamic_range", 20)
        if dynamic_range > 25:  # High dynamic range - be gentler
            for key in eq_curve:
                if key != 'mastering_intensity':
                    eq_curve[key] *= 0.8
        elif dynamic_range < 10:  # Low dynamic range - be more aggressive
            for key in eq_curve:
                if key != 'mastering_intensity':
                    eq_curve[key] *= 1.2

        return eq_curve

    def _process_with_psychoacoustic_eq(self, audio: np.ndarray, eq_curve: Dict[str, float],
                                       content_profile: Optional[Dict[str, Any]] = None) -> np.ndarray:
        """
        Process audio using psychoacoustic EQ with content awareness

        Args:
            audio: Input audio
            eq_curve: EQ curve parameters
            content_profile: Optional content profile

        Returns:
            Processed audio
        """
        # Convert EQ curve dict to target curve array
        target_curve = self._eq_curve_to_array(eq_curve)

        # Process audio in chunks for psychoacoustic EQ
        chunk_size = self.psychoacoustic_eq.fft_size
        processed_audio = np.zeros_like(audio)

        for i in range(0, len(audio), chunk_size // 2):  # 50% overlap
            end_idx = min(i + chunk_size, len(audio))
            chunk = audio[i:end_idx]

            # Pad chunk if necessary
            if len(chunk) < chunk_size:
                padded_chunk = np.zeros((chunk_size,) + chunk.shape[1:])
                padded_chunk[:len(chunk)] = chunk
                chunk = padded_chunk

            # Process chunk with psychoacoustic EQ
            processed_chunk = self.psychoacoustic_eq.process_realtime_chunk(
                chunk, target_curve, content_profile
            )

            # Extract only the valid part (remove padding)
            valid_length = end_idx - i
            if audio.ndim == 2:
                processed_audio[i:end_idx] = processed_chunk[:valid_length]
            else:
                processed_audio[i:end_idx] = processed_chunk[:valid_length]

        return processed_audio

    def _eq_curve_to_array(self, eq_curve: Dict[str, float]) -> np.ndarray:
        """
        Convert EQ curve dictionary to array format expected by psychoacoustic EQ

        Args:
            eq_curve: EQ curve parameters

        Returns:
            Target curve array (26 bands)
        """
        # Create target curve for 26 critical bands
        num_bands = len(self.psychoacoustic_eq.critical_bands)
        target_curve = np.zeros(num_bands)

        # Map frequency ranges to bands
        bass_bands = range(0, 4)        # ~20-250 Hz
        low_mid_bands = range(4, 8)     # ~250-500 Hz
        mid_bands = range(8, 16)        # ~500-2000 Hz
        high_mid_bands = range(16, 20)  # ~2000-4000 Hz
        treble_bands = range(20, 26)    # ~4000+ Hz

        # Apply gains to appropriate bands
        for band_idx in bass_bands:
            target_curve[band_idx] = eq_curve.get('bass_boost', 0.0)

        for band_idx in low_mid_bands:
            target_curve[band_idx] = eq_curve.get('low_mid_boost', 0.0)

        for band_idx in mid_bands:
            target_curve[band_idx] = eq_curve.get('mid_boost', 0.0)

        for band_idx in high_mid_bands:
            target_curve[band_idx] = eq_curve.get('high_mid_boost', 0.0)

        for band_idx in treble_bands:
            target_curve[band_idx] = eq_curve.get('treble_boost', 0.0)

        # Apply mastering intensity scaling
        intensity = eq_curve.get('mastering_intensity', 0.5)
        target_curve *= intensity

        return target_curve

    def _apply_simple_eq_fallback(self, audio: np.ndarray, targets: Dict[str, Any]) -> np.ndarray:
        """
        Fallback simple EQ implementation for safety

        Args:
            audio: Input audio
            targets: Processing targets

        Returns:
            EQ-processed audio (simple fallback)
        """
        processed = audio.copy()

        # Very basic frequency adjustment using simple filtering
        bass_gain_db = targets.get("bass_boost_db", 0.0)
        treble_gain_db = targets.get("treble_enhancement_db", 0.0)

        # Apply very gentle adjustments (limited for safety)
        if abs(bass_gain_db) > 0.5:
            bass_gain_linear = 10 ** (np.clip(bass_gain_db, -6, 6) / 20)
            processed = processed * (1.0 + (bass_gain_linear - 1.0) * 0.1)

        if abs(treble_gain_db) > 0.5:
            treble_gain_linear = 10 ** (np.clip(treble_gain_db, -6, 6) / 20)
            processed = processed * (1.0 + (treble_gain_linear - 1.0) * 0.1)

        return processed

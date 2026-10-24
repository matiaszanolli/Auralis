"""
EQ Processor
~~~~~~~~~~~~

Psychoacoustic EQ integration and processing

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from typing import Any

import numpy as np
from scipy.signal.windows import hann

from ...dsp.eq.psychoacoustic_eq import PsychoacousticEQ
from ...utils.logging import debug, warning


from .eq_curve import process_with_psychoacoustic_eq


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

    def apply_psychoacoustic_eq(self, audio: np.ndarray, targets: dict[str, Any],
                                content_profile: dict[str, Any] | None = None) -> np.ndarray:
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

        except (AssertionError, ValueError, TypeError):
            raise  # Programming errors must not be swallowed
        except Exception as e:
            # #4972: the old "simple EQ fallback" was a wideband scalar
            # multiply masquerading as spectral shaping — a silent tonal
            # no-op that looked like it worked. The #4217 root cause that
            # made it the NORMAL path is gone, so an unexpected EQ failure
            # now propagates and surfaces the underlying bug instead.
            warning(f"Psychoacoustic EQ failed: {e}")
            raise

    def _targets_to_eq_curve(self, targets: dict[str, Any],
                            content_profile: dict[str, Any] | None = None) -> dict[str, float]:
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

            # Overall intensity (continuous mode uses 'eq_blend' key)
            'mastering_intensity': targets.get("mastering_intensity", targets.get("eq_blend", 0.5))
        }

        # Apply content-aware adjustments
        if content_profile:
            eq_curve = self._apply_content_adjustments(eq_curve, content_profile)

        return eq_curve

    def _apply_content_adjustments(self, eq_curve: dict[str, float],
                                   content_profile: dict[str, Any]) -> dict[str, float]:
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

    def _process_with_psychoacoustic_eq(self, audio: np.ndarray,
                                          eq_curve: dict[str, float],
                                          content_profile: dict[str, Any] | None = None) -> np.ndarray:
        return process_with_psychoacoustic_eq(self, audio, eq_curve, content_profile)

    def _eq_curve_to_array(self, eq_curve: dict[str, float]) -> np.ndarray:
        """
        Convert EQ curve dictionary to array format expected by psychoacoustic EQ

        Args:
            eq_curve: EQ curve parameters

        Returns:
            Target curve array, one gain per critical band.
        """
        # Assign gains by each band's actual center frequency rather than by
        # hardcoded indices. The Bark scale yields 25 bands (26 boundaries),
        # so the old `range(20, 26)` indexed band 25 — out of range — making
        # this method always raise IndexError and silently fall back to the
        # simple EQ. Frequency-based mapping is correct and robust to the band
        # count.
        bands = self.psychoacoustic_eq.critical_bands
        target_curve = np.zeros(len(bands))

        for i, band in enumerate(bands):
            center = band.center_freq
            if center < 250.0:          # Bass (~20-250 Hz)
                target_curve[i] = eq_curve.get('bass_boost', 0.0)
            elif center < 500.0:        # Low-mid (~250-500 Hz)
                target_curve[i] = eq_curve.get('low_mid_boost', 0.0)
            elif center < 2000.0:       # Mid (~500-2000 Hz)
                target_curve[i] = eq_curve.get('mid_boost', 0.0)
            elif center < 4000.0:       # High-mid (~2000-4000 Hz)
                target_curve[i] = eq_curve.get('high_mid_boost', 0.0)
            else:                       # Treble (~4000+ Hz)
                target_curve[i] = eq_curve.get('treble_boost', 0.0)

        # Apply mastering intensity scaling
        intensity = eq_curve.get('mastering_intensity', 0.5)
        target_curve *= intensity

        return target_curve


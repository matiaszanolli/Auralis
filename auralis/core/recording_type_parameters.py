"""
Recording Type Parameters
~~~~~~~~~~~~~~~~~~~~~~~~~

The four per-recording-type parameter tables (studio/bootleg/metal/default),
split from recording_type_detector.py (#6272). The detector is offline-
scripts-only by design (#4873/#5780); the tables are data.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from .utils import SmoothCurveUtilities
from .utils.fingerprint_unpacker import FingerprintUnpacker
from dataclasses import dataclass

from .recording_type_detector import RecordingType, _centroid_hz



@dataclass
class AdaptiveParameters:
    """
    Adaptive mastering parameters derived from recording type and fingerprint.

    Instead of rigid presets, these parameters guide the 25D spectrum-based
    processing system to achieve the appropriate mastering philosophy.
    """
    # Frequency response targets (EQ guidance)
    bass_adjustment_db: float          # Target bass adjustment relative to mid
    mid_adjustment_db: float           # Midrange adjustment for clarity
    treble_adjustment_db: float        # Treble adjustment for presence/warmth

    # Spectral targets (not absolute, but guidance for 25D system)
    target_spectral_centroid_hz: float # Ideal brightness for this recording type
    spectral_adjustment_guidance: str  # "brighten", "darken", or "maintain"

    # Stereo processing
    stereo_width_target: float         # Target stereo width (0-1)
    stereo_strategy: str               # "narrow", "maintain", or "expand"

    # Dynamics handling
    crest_factor_target_min: float     # Minimum transient preservation
    crest_factor_target_max: float     # Maximum transient preservation
    dr_expansion_db: float             # How much to expand dynamic range

    # Loudness strategy
    rms_adjustment_db: float           # RMS level adjustment
    peak_headroom_db: float            # How much headroom to maintain

    # Processing philosophy (for adaptive decision-making)
    mastering_philosophy: str          # "enhance", "correct", or "punch"

    # Confidence level (0-1) in this classification
    confidence: float

    def __repr__(self) -> str:
        return (
            f"AdaptiveParameters(\n"
            f"  philosophy={self.mastering_philosophy},\n"
            f"  bass={self.bass_adjustment_db:+.2f}dB,\n"
            f"  mid={self.mid_adjustment_db:+.2f}dB,\n"
            f"  treble={self.treble_adjustment_db:+.2f}dB,\n"
            f"  stereo={self.stereo_strategy}({self.stereo_width_target:.2f}),\n"
            f"  rms={self.rms_adjustment_db:+.2f}dB,\n"
            f"  confidence={self.confidence:.1%}\n"
            f")"
        )



class RecordingTypeParameterTables:
    """Hosts (the detector) call these as functions of (fingerprint, confidence)."""

    def _parameters_studio(self, fingerprint: dict[str, float], confidence: float) -> AdaptiveParameters:
        """
        Generate parameters for studio recording (Deep Purple philosophy).

        Philosophy: "Enhance & refine" - already well-balanced, just optimize.
        """
        # Base parameters from Steven Wilson reference
        bass_adjustment = 1.5
        mid_adjustment = -1.0
        treble_adjustment = 2.0

        # Fine-tune based on actual spectral content (25D guidance)
        # Only apply fine-tuning if fingerprint data is provided
        spectral_centroid_hz = _centroid_hz(fingerprint)
        if spectral_centroid_hz is not None:
            if spectral_centroid_hz < 600:
                # Already dark, reduce bass boost
                bass_adjustment = 1.0
            elif spectral_centroid_hz > 800:
                # Bright, might need less treble boost
                treble_adjustment = 1.5

        return AdaptiveParameters(
            bass_adjustment_db=bass_adjustment,
            mid_adjustment_db=mid_adjustment,
            treble_adjustment_db=treble_adjustment,
            target_spectral_centroid_hz=675,
            spectral_adjustment_guidance="maintain",
            stereo_width_target=0.39,
            stereo_strategy="maintain",
            crest_factor_target_min=6.0,
            crest_factor_target_max=6.5,
            dr_expansion_db=0,  # Studio already mastered
            rms_adjustment_db=-0.51,  # Maintain dynamics
            peak_headroom_db=-0.24,
            mastering_philosophy="enhance",
            confidence=confidence
        )

    def _parameters_bootleg(self, fingerprint: dict[str, float], confidence: float) -> AdaptiveParameters:
        """
        Generate parameters for bootleg concert recording (Matchering philosophy).

        Philosophy: "Correct & transform" - fix fundamental recording issues.
        """
        # Base parameters from Porcupine Tree analysis
        bass_adjustment = -4.0
        treble_adjustment = 4.0

        # Fine-tune based on actual darkness (25D guidance)
        spectral_centroid_hz = _centroid_hz(fingerprint, default_normalized=0.3)
        bass_to_mid = FingerprintUnpacker.from_dict(fingerprint).bass_mid_ratio

        # More aggressive correction if darker than reference
        assert spectral_centroid_hz is not None  # a default was supplied
        if spectral_centroid_hz < 450:
            treble_adjustment = 4.5
        if bass_to_mid > 15:
            bass_adjustment = -4.5

        return AdaptiveParameters(
            bass_adjustment_db=bass_adjustment,
            mid_adjustment_db=-3.5,  # Average of Matchering range
            treble_adjustment_db=treble_adjustment,
            target_spectral_centroid_hz=990,  # Average of brightened range
            spectral_adjustment_guidance="brighten",
            stereo_width_target=0.40,  # Expanded from 0.20
            stereo_strategy="expand",
            crest_factor_target_min=4.6,
            crest_factor_target_max=6.0,
            dr_expansion_db=23.5,
            rms_adjustment_db=2.0,  # Increase loudness
            peak_headroom_db=-0.02,
            mastering_philosophy="correct",
            confidence=confidence
        )

    def _parameters_metal(self, fingerprint: dict[str, float], confidence: float) -> AdaptiveParameters:
        """
        Generate parameters for metal recording (Unique Matchering approach).

        Philosophy: "Punch & aggression" - enhance punch, warm the tone.
        """
        # Base parameters from Iron Maiden analysis
        bass_adjustment = 3.85
        mid_adjustment = -5.70
        treble_adjustment = -1.22  # UNIQUE: reduction not boost

        # Fine-tune based on actual brightness (25D guidance)
        # Only apply fine-tuning if fingerprint data is provided
        spectral_centroid_hz = _centroid_hz(fingerprint)
        if spectral_centroid_hz is not None:
            # More aggressive if brighter than reference (1340 Hz)
            if spectral_centroid_hz > 1340:
                treble_adjustment = -1.5
            elif spectral_centroid_hz < 1200:
                # Less reduction needed if not as bright
                treble_adjustment = -0.95

        # Adjust mid reduction based on compression if provided
        if 'crest_db' in fingerprint:
            crest_factor = fingerprint['crest_db']
            if crest_factor < 3.5:
                mid_adjustment = -5.5  # Less aggressive

        return AdaptiveParameters(
            bass_adjustment_db=bass_adjustment,
            mid_adjustment_db=mid_adjustment,
            treble_adjustment_db=treble_adjustment,  # Negative = reduction
            target_spectral_centroid_hz=930,  # Warm, punchy target
            spectral_adjustment_guidance="darken",
            stereo_width_target=0.263,  # Narrowed from 0.418
            stereo_strategy="narrow",
            crest_factor_target_min=5.0,
            crest_factor_target_max=5.3,
            dr_expansion_db=23.2,
            rms_adjustment_db=-3.93,  # Aggressive reduction for headroom
            peak_headroom_db=-0.40,
            mastering_philosophy="punch",
            confidence=confidence
        )

    def _parameters_default(self, confidence: float) -> AdaptiveParameters:
        """
        Generate neutral parameters when type cannot be confidently determined.

        Falls back to enhanced studio-like approach with warmth focus.

        Phase 6.4 Validation (45 samples, 6+ genres):
        - 11 bass mentions across 38 UNKNOWN samples (29% of themes)
        - Pattern held across full quality spectrum (1-5 stars)
        - Cross-validated: rock, electronic, Latin, metal, thrash, pop (1970s-2020s)
        - Confidence: 98%
        """
        return AdaptiveParameters(
            bass_adjustment_db=1.8,  # +0.3 dB from user feedback validation
            mid_adjustment_db=0.0,
            treble_adjustment_db=1.0,
            target_spectral_centroid_hz=700,
            spectral_adjustment_guidance="maintain",
            stereo_width_target=0.4,
            stereo_strategy="maintain",
            crest_factor_target_min=5.5,
            crest_factor_target_max=6.5,
            dr_expansion_db=2.0,
            rms_adjustment_db=0.0,
            peak_headroom_db=-0.2,
            mastering_philosophy="enhance",
            confidence=confidence
        )

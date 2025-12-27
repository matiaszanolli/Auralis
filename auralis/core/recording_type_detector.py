# -*- coding: utf-8 -*-

"""
Recording Type Detector
~~~~~~~~~~~~~~~~~~~~~~~

Detects recording type (studio/bootleg/metal) from 25D audio fingerprint
and generates adaptive mastering parameters.

Uses the reference data from three world-class masters:
- Deep Purple "Smoke On The Water" (Steven Wilson remix): Studio approach
- Porcupine Tree "Rockpalast 2006" (Matchering): Bootleg approach
- Iron Maiden "Wasted Years" (Matchering): Metal approach

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional, Tuple

import numpy as np

from ..analysis.fingerprint import AudioFingerprintAnalyzer
from ..utils.logging import debug, info


class RecordingType(Enum):
    """Recording type classification."""
    STUDIO = "studio"        # Professional studio mix (balanced)
    BOOTLEG = "bootleg"      # Concert bootleg (dark, bass-heavy, narrow)
    METAL = "metal"          # Metal recording (bright, compressed)
    UNKNOWN = "unknown"      # Unable to classify confidently


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


class RecordingTypeDetector:
    """
    Detects recording type from 25D audio fingerprint.

    Based on analysis of three professional references:
    1. Studio Rock: Deep Purple (Steven Wilson) - well-balanced professional mix
    2. Bootleg: Porcupine Tree (Matchering) - dark, bass-heavy, narrow stereo
    3. Metal: Iron Maiden (Matchering) - bright, compressed, punchy
    """

    def __init__(self) -> None:
        """Initialize detector with fingerprint analyzer."""
        self.fingerprint_analyzer = AudioFingerprintAnalyzer()
        self.confidence_threshold = 0.65  # Minimum confidence to classify

    def detect(self, audio: np.ndarray, sr: int) -> Tuple[RecordingType, AdaptiveParameters]:
        """
        Detect recording type and generate adaptive parameters.

        Args:
            audio: Audio signal (stereo or mono)
            sr: Sample rate

        Returns:
            Tuple of (RecordingType, AdaptiveParameters)
        """
        # Extract 25D fingerprint
        fingerprint = self.fingerprint_analyzer.analyze(audio, sr)

        # Detect recording type based on fingerprint
        recording_type, confidence = self._classify(fingerprint)

        # Generate adaptive parameters for this type
        params = self._generate_parameters(recording_type, fingerprint, confidence)

        debug(
            f"Recording detection: {recording_type.value} "
            f"(confidence={confidence:.1%}) - {params.mastering_philosophy}"
        )

        return recording_type, params

    def _classify(self, fingerprint: Dict[str, float]) -> Tuple[RecordingType, float]:
        """
        Classify recording type from fingerprint features.

        PHASE 6.2 RECALIBRATION: Updated boundaries based on actual library audio.

        Reference data analysis (from actual library measurements):
        - Deep Purple In Rock: 7,658 Hz centroid, +1.62 dB bass-to-mid, 0.13 stereo, 11.95 CF
        - Iron Maiden Wasted: 7,754 Hz centroid, +0.65 dB bass-to-mid, 0.11 stereo, 18.89 CF
        - Both indicate "HD Bright Transparent" mastering style (very bright, narrow, excellent transients)

        Legacy reference data (from Phase 4 - kept for compatibility):
        - Studio: 664 Hz, +1.15 dB bass-to-mid, 0.39 stereo, 6.53 CF
        - Bootleg: 374-571 Hz, +13-17 dB bass-to-mid, 0.17-0.23 stereo, 4-6 CF
        - Metal: 1344 Hz, +9.58 dB bass-to-mid, 0.418 stereo, 3.54 CF
        """
        spectral_centroid = fingerprint.get('spectral_centroid', 0.5)
        bass_to_mid = fingerprint.get('bass_mid_ratio', 1.0)  # in dB
        stereo_width = fingerprint.get('stereo_width', 0.5)
        crest_factor = fingerprint.get('crest_db', 5.0)  # in dB

        # Denormalize spectral centroid to Hz (assuming normalized 0-1 to 0-20kHz)
        spectral_centroid_hz = spectral_centroid * 20000

        # Classification logic - now with HD Bright profile support
        scores = {
            RecordingType.STUDIO: self._score_studio(spectral_centroid_hz, bass_to_mid, stereo_width, crest_factor),
            RecordingType.BOOTLEG: self._score_bootleg(spectral_centroid_hz, bass_to_mid, stereo_width),
            RecordingType.METAL: self._score_metal(spectral_centroid_hz, bass_to_mid, stereo_width, crest_factor),
        }

        # Find best match
        best_type = max(scores.items(), key=lambda x: x[1])[0]
        confidence = max(scores.values())

        # Return UNKNOWN if confidence is too low
        if confidence < self.confidence_threshold:
            return RecordingType.UNKNOWN, confidence

        return best_type, confidence

    def _score_bootleg(self, spectral_hz: float, bass_to_mid: float, stereo_width: float) -> float:
        """
        Score likelihood of bootleg recording.

        Bootleg characteristics:
        - Very dark: spectral centroid 374-571 Hz (very low)
        - Bass-heavy: bass-to-mid +13.6 to +16.8 dB (very high)
        - Narrow stereo: width 0.17-0.23 (very narrow)
        """
        score = 0.0

        # Spectral centroid: Lower is better for bootleg
        if spectral_hz < 500:
            score += 0.4  # Strong bootleg indicator
        elif spectral_hz < 600:
            score += 0.2

        # Bass-to-mid ratio: Very high is bootleg
        if bass_to_mid > 12:
            score += 0.4  # Strong bootleg indicator
        elif bass_to_mid > 10:
            score += 0.2

        # Stereo width: Narrow is bootleg
        if stereo_width < 0.3:
            score += 0.2  # Bootleg indicator

        return min(score, 1.0)

    def _score_metal(self, spectral_hz: float, bass_to_mid: float, stereo_width: float, crest_db: Optional[float] = None) -> float:
        """
        Score likelihood of metal recording.

        Metal characteristics:
        - Very bright: spectral centroid 1344 Hz (very high)
        - Moderate bass: bass-to-mid +9.58 dB (moderate)
        - Good stereo: width 0.418 (good)
        - Compressed: crest factor 3.54 (low)
        """
        score = 0.0

        # Spectral centroid: Very high is metal
        if spectral_hz > 1000:
            score += 0.4  # Strong metal indicator
        elif spectral_hz > 800:
            score += 0.2

        # Bass-to-mid ratio: Moderate is metal
        if 8 < bass_to_mid < 11:
            score += 0.2  # Metal indicator

        # Stereo width: Good width is metal
        if stereo_width > 0.35:
            score += 0.2  # Metal indicator

        # Crest factor: Low indicates compression (metal)
        if crest_db is not None and crest_db < 4.5:
            score += 0.2  # Metal indicator

        return min(score, 1.0)

    def _score_studio(self, spectral_hz: float, bass_to_mid: float, stereo_width: float, crest_db: Optional[float] = None) -> float:
        """
        Score likelihood of studio recording.

        PHASE 6.2: Now handles both legacy and HD Bright profiles

        Legacy studio characteristics (warm, balanced):
        - Normal brightness: spectral centroid ~664 Hz (moderate)
        - Modest bass: bass-to-mid +1.15 dB (low-moderate)
        - Good stereo: width 0.39 (good)
        - Crest factor: 6.53 (moderate transients)

        HD Bright Transparent characteristics (new library style):
        - Very bright: spectral centroid ~7,700 Hz (presence boost)
        - Low bass: bass-to-mid +0.65-1.62 dB (minimal bass)
        - Narrow stereo: width 0.11-0.13 (tight imaging)
        - Excellent transients: crest factor 11-19 dB
        """
        score = 0.0

        # Profile 1: HD Bright Transparent (most common in actual library)
        # Very specific boundaries for high confidence
        if 7500 <= spectral_hz <= 8000:
            score += 0.35  # Very strong HD Bright indicator
            if -2 <= bass_to_mid <= 3:
                score += 0.20  # Confirms HD Bright
            if 0.08 <= stereo_width <= 0.16:
                score += 0.20  # Confirms narrow stereo
            if crest_db is not None and 10 <= crest_db <= 20:
                score += 0.10  # Confirms excellent transients

        # Profile 2: Legacy warm/balanced studio (for compatibility)
        # Broader boundaries for flexibility
        elif 600 < spectral_hz < 800:
            score += 0.35  # Strong legacy studio indicator
            if bass_to_mid < 5:
                score += 0.25  # Modest bass
            if 0.30 < stereo_width < 0.50:
                score += 0.15  # Good stereo width
        elif 500 < spectral_hz < 900:
            score += 0.15
            if bass_to_mid < 8:
                score += 0.15

        return min(score, 1.0)

    def _generate_parameters(
        self,
        recording_type: RecordingType,
        fingerprint: Dict[str, float],
        confidence: float
    ) -> AdaptiveParameters:
        """
        Generate adaptive parameters based on recording type and fingerprint.

        Uses fingerprint to fine-tune parameters rather than rigid presets.
        """
        if recording_type == RecordingType.BOOTLEG:
            return self._parameters_bootleg(fingerprint, confidence)
        elif recording_type == RecordingType.METAL:
            return self._parameters_metal(fingerprint, confidence)
        elif recording_type == RecordingType.STUDIO:
            return self._parameters_studio(fingerprint, confidence)
        else:
            return self._parameters_default(confidence)

    def _parameters_studio(self, fingerprint: Dict[str, float], confidence: float) -> AdaptiveParameters:
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
        if 'spectral_centroid' in fingerprint:
            spectral_centroid = fingerprint['spectral_centroid'] * 20000
            if spectral_centroid < 600:
                # Already dark, reduce bass boost
                bass_adjustment = 1.0
            elif spectral_centroid > 800:
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

    def _parameters_bootleg(self, fingerprint: Dict[str, float], confidence: float) -> AdaptiveParameters:
        """
        Generate parameters for bootleg concert recording (Matchering philosophy).

        Philosophy: "Correct & transform" - fix fundamental recording issues.
        """
        # Base parameters from Porcupine Tree analysis
        bass_adjustment = -4.0
        treble_adjustment = 4.0

        # Fine-tune based on actual darkness (25D guidance)
        spectral_centroid = fingerprint.get('spectral_centroid', 0.3) * 20000
        bass_to_mid = fingerprint.get('bass_mid_ratio', 15.0)

        # More aggressive correction if darker than reference
        if spectral_centroid < 450:
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

    def _parameters_metal(self, fingerprint: Dict[str, float], confidence: float) -> AdaptiveParameters:
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
        if 'spectral_centroid' in fingerprint:
            spectral_centroid = fingerprint['spectral_centroid'] * 20000

            # More aggressive if brighter than reference (1340 Hz)
            if spectral_centroid > 1340:
                treble_adjustment = -1.5
            elif spectral_centroid < 1200:
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

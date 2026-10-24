"""
Recording Type Detector
~~~~~~~~~~~~~~~~~~~~~~~

.. note::

    **OFFLINE SCRIPTS ONLY — not on the shipped app's audio path (#4873).**

    The only non-test callers are ``scripts/rate_track.py`` and
    ``scripts/analyze_feedback.py``. The Electron app's audio goes
    ``HybridProcessor.process()`` -> ``ContinuousMode``, which derives its
    parameters from the continuous fingerprint space rather than from a
    categorical recording-type branch — the architecture this module predates.

    This is a **deliberate, recorded decision**, not an oversight: #4873
    evaluated deleting it and chose to keep it because those two scripts still
    use it. Do not re-file it as "dead code", and do not wire it into the
    mastering path without first re-opening the categorical-vs-continuous
    decision.

Detects recording type (studio/bootleg/metal) from 25D audio fingerprint
and generates adaptive mastering parameters.

Uses the reference data from three world-class masters:
- Deep Purple "Smoke On The Water" (Steven Wilson remix): Studio approach
- Porcupine Tree "Rockpalast 2006" (Matchering): Bootleg approach
- Iron Maiden "Wasted Years" (Matchering): Metal approach

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from dataclasses import dataclass
from enum import Enum

import numpy as np

from ..analysis.fingerprint import AudioFingerprintAnalyzer
from ..analysis.fingerprint.schema import centroid_to_hz
from ..utils.logging import debug
from .utils.fingerprint_unpacker import FingerprintUnpacker


def _centroid_hz(
    fingerprint: dict[str, float],
    default_normalized: float | None = None,
) -> float | None:
    """Spectral centroid in Hz from the normalized 25D dimension.

    The single denormalization point for this class (#4538). ``_classify()``
    was fixed in 7f937cca to use ``centroid_to_hz`` (8 kHz), but the three
    parameter generators kept a hand-rolled ``* 20000`` and so drove every
    per-recording-type EQ decision from a value 2.5x too large. Re-deriving Hz
    at four call sites inside one class is the mechanism of that bug, so the
    derivation now lives here and nowhere else.

    Args:
        fingerprint: 25D fingerprint dict, ``spectral_centroid`` normalized 0-1.
        default_normalized: Fallback in *normalized* units (not Hz), so a
            missing key still round-trips through ``centroid_to_hz``.

    Returns:
        Centroid in Hz, or ``None`` when the key is absent and no default was
        supplied — callers gate their fine-tuning on that.
    """
    value = fingerprint.get('spectral_centroid', default_normalized)
    if value is None:
        return None
    return centroid_to_hz(value)


class RecordingType(Enum):
    """Recording type classification."""
    STUDIO = "studio"        # Professional studio mix (balanced)
    BOOTLEG = "bootleg"      # Concert bootleg (dark, bass-heavy, narrow)
    METAL = "metal"          # Metal recording (bright, compressed)
    UNKNOWN = "unknown"      # Unable to classify confidently


from .recording_type_parameters import (  # noqa: E402  (defined there since #6272)
    AdaptiveParameters,
    RecordingTypeParameterTables,
)


class RecordingTypeDetector(RecordingTypeParameterTables):
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

    def detect(self, audio: np.ndarray, sr: int) -> tuple[RecordingType, AdaptiveParameters]:
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

    def _classify(self, fingerprint: dict[str, float]) -> tuple[RecordingType, float]:
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
        fp = FingerprintUnpacker.from_dict(fingerprint)
        spectral_centroid = fp.spectral_centroid
        bass_to_mid = fp.bass_mid_ratio  # in dB
        stereo_width = fp.stereo_width
        crest_factor = fp.crest_db  # in dB

        # Denormalize spectral centroid to Hz via the schema's canonical
        # constant (8 kHz, NOT 20 kHz — the fingerprint clips at 8 kHz so
        # 0-1 was previously stretched 2.5× too far and every source landed
        # past the "metal" centroid threshold). Shared with the parameter
        # generators via _centroid_hz so the two cannot desynchronize (#4538).
        spectral_centroid_hz = centroid_to_hz(spectral_centroid)

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

    def _score_metal(self, spectral_hz: float, bass_to_mid: float, stereo_width: float, crest_db: float | None = None) -> float:
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

    def _score_studio(self, spectral_hz: float, bass_to_mid: float, stereo_width: float, crest_db: float | None = None) -> float:
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
        fingerprint: dict[str, float],
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

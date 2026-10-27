"""
Frequency Response Assessment
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Assess audio frequency response quality

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from typing import Any

import numpy as np

from auralis.analysis.quality_assessors.base_assessor import BaseAssessor
from auralis.analysis.quality_assessors.utilities.scoring_ops import ScoringOperations
from auralis.analysis.spectrum_bands import populated_band_mask
from auralis.analysis.spectrum_operations import SpectrumOperations


# Reference tilt: -3 dB per octave, the slope of pink noise and of typical
# music, in the dB-of-mean-FFT-magnitude domain the spectrum analyzer reports.
REFERENCE_TILT_DB_PER_OCTAVE = -3.0
REFERENCE_TILT_ANCHOR_HZ = 1000.0
# Mean band level (dB of FFT magnitude) under which there is no signal to judge:
# digital silence sits at the analyzer's -100 dB floor, a flat shape that the
# level-free comparison would otherwise score as a fine response.
SILENT_SPECTRUM_DB = -80.0


class FrequencyResponseAssessor(BaseAssessor):
    """Assess frequency response quality.

    Scores the *shape* of the spectrum against a tilted reference: the overall
    level is removed (a quiet and a loud copy of the same mix have the same
    response), the analyzer's frequency weighting is undone, and bands the FFT
    never resolved are left out (#5745). The previous flat 0 dB reference
    compared absolute FFT magnitudes to zero, so white noise outscored pink and
    no real input could exceed ~74.
    """

    def __init__(self, frequency_bins: np.ndarray, sample_rate: int | None = None,
                 fft_size: int | None = None):
        """
        Initialize frequency response assessor

        Args:
            frequency_bins: Array of frequency bin values
            sample_rate: Analysis sample rate; with ``fft_size`` it tells which
                bands contain no FFT bin. Omitted, every band counts.
            fft_size: FFT length the spectrum was computed with
        """
        super().__init__()
        self.frequency_bins = frequency_bins
        self.reference_curve = self._create_reference_curve()
        if sample_rate is not None and fft_size is not None:
            self.populated_bands = populated_band_mask(
                np.fft.rfftfreq(fft_size, 1 / sample_rate), frequency_bins
            )
        else:
            self.populated_bands = np.ones(len(frequency_bins), dtype=bool)

    def _create_reference_curve(self) -> np.ndarray:
        """
        Create reference frequency response curve for quality assessment

        A pink-noise tilt with the realistic band-edge rolloff. Only its shape
        matters: ``_deviation`` removes the level.
        """
        freqs = np.asarray(self.frequency_bins, dtype=float)
        reference: np.ndarray = REFERENCE_TILT_DB_PER_OCTAVE * np.log2(
            np.maximum(freqs, 1.0) / REFERENCE_TILT_ANCHOR_HZ
        )
        reference[freqs < 20] -= 20     # Roll off below 20Hz
        reference[(freqs >= 20) & (freqs < 50)] -= 6    # Gentle rise
        reference[(freqs >= 16000) & (freqs < 20000)] -= 3   # Gentle rolloff
        reference[freqs >= 20000] -= 12  # Steeper rolloff above 20kHz
        return reference

    def _deviation(self, spectrum_result: dict[str, Any]) -> tuple[np.ndarray, np.ndarray]:
        """(deviation in dB from the reference shape, per-band weights).

        Weights are zero for bands without an FFT bin, so those bands neither
        count toward the score nor toward the level that is removed; all are
        zero for a silent spectrum, which has no response to assess.
        """
        if 'spectrum' not in spectrum_result:
            # SpectrumAnalyzer.analyze_file() returns {} for audio shorter than
            # its FFT; callers (the quality gate) catch ValueError (#5712).
            raise ValueError("No spectrum: the audio is shorter than the analysis FFT")
        spectrum = np.array(spectrum_result['spectrum'], dtype=float)
        weighting = spectrum_result.get('settings', {}).get('weighting')
        if weighting:
            # The analyzer adds a perceptual weighting; the reference describes
            # the physical spectrum, so undo it rather than weight twice.
            spectrum = spectrum - SpectrumOperations.get_weighting_curve(
                self.frequency_bins, weighting
            )
        weights = self._calculate_frequency_weights() * self.populated_bands
        if np.sum(weights) > 0 and np.average(spectrum, weights=weights) < SILENT_SPECTRUM_DB:
            weights = np.zeros_like(weights)
        deviation = spectrum - self.reference_curve
        if np.sum(weights) > 0:
            deviation = deviation - np.average(deviation, weights=weights)
        return deviation, weights

    def assess(self, spectrum_result: dict[str, Any]) -> float:  # type: ignore[override]
        """
        Assess frequency response quality (0-100)

        Args:
            spectrum_result: Dictionary with 'spectrum' and 'frequency_bins'

        Returns:
            Quality score (0-100, higher is better)
        """
        deviation, weights = self._deviation(spectrum_result)
        if np.sum(weights) == 0:
            return 0.0

        # More weight to mid frequencies
        weighted_deviation = np.average(np.abs(deviation), weights=weights)

        # Convert to score (lower deviation = higher score)
        score = ScoringOperations.linear_scale_score(
            weighted_deviation, 0, 50, inverted=True
        )

        return float(score)

    def detailed_analysis(self, spectrum_result: dict[str, Any]) -> dict[str, Any]:  # type: ignore[override]
        """
        Perform detailed frequency response analysis

        Args:
            spectrum_result: Dictionary with spectrum analysis

        Returns:
            Dictionary with detailed frequency metrics
        """
        deviation, weights = self._deviation(spectrum_result)
        measured = np.abs(deviation[weights > 0])
        if measured.size == 0:
            return {'weighted_deviation_db': 0.0, 'max_deviation_db': 0.0,
                    'mean_deviation_db': 0.0, 'deviation_std_db': 0.0}

        return {
            'weighted_deviation_db': float(np.average(np.abs(deviation), weights=weights)),
            'max_deviation_db': float(np.max(measured)),
            'mean_deviation_db': float(np.mean(measured)),
            'deviation_std_db': float(np.std(measured))
        }

    def _calculate_frequency_weights(self) -> np.ndarray:
        """
        Calculate frequency-dependent weights for assessment

        Returns:
            Array of weights for each frequency bin
        """
        weights = np.ones_like(self.frequency_bins)

        # Higher weight for critical frequency ranges
        for i, freq in enumerate(self.frequency_bins):
            if 200 <= freq <= 5000:  # Critical vocal/instrument range
                weights[i] = 2.0
            elif 50 <= freq <= 200 or 5000 <= freq <= 16000:  # Important ranges
                weights[i] = 1.5

        return weights

    def identify_frequency_issues(self, spectrum_result: dict[str, Any],
                                 threshold_db: float = 6.0) -> dict[str, Any]:
        """
        Identify specific frequency response issues

        Args:
            spectrum_result: Dictionary with spectrum analysis
            threshold_db: Deviation threshold to flag as issue

        Returns:
            Dictionary with identified issues
        """
        deviation, weights = self._deviation(spectrum_result)
        measured = weights > 0

        issues: dict[str, Any] = {
            'excessive_bass': False,
            'lacking_bass': False,
            'harsh_mids': False,
            'muddy_mids': False,
            'bright_highs': False,
            'dull_highs': False,
            'problem_frequencies': []
        }

        # Check bass (20-200 Hz)
        bass_mask = (self.frequency_bins >= 20) & (self.frequency_bins <= 200) & measured
        bass_deviation = np.mean(deviation[bass_mask]) if np.any(bass_mask) else 0.0
        if bass_deviation > threshold_db:
            issues['excessive_bass'] = True
        elif bass_deviation < -threshold_db:
            issues['lacking_bass'] = True

        # Check mids (200-2000 Hz)
        mid_mask = (self.frequency_bins >= 200) & (self.frequency_bins <= 2000) & measured
        mid_deviation = np.mean(deviation[mid_mask]) if np.any(mid_mask) else 0.0
        if mid_deviation > threshold_db:
            issues['harsh_mids'] = True
        elif mid_deviation < -threshold_db:
            issues['muddy_mids'] = True

        # Check highs (4000-16000 Hz)
        high_mask = (self.frequency_bins >= 4000) & (self.frequency_bins <= 16000) & measured
        high_deviation = np.mean(deviation[high_mask]) if np.any(high_mask) else 0.0
        if high_deviation > threshold_db:
            issues['bright_highs'] = True
        elif high_deviation < -threshold_db:
            issues['dull_highs'] = True

        # Identify specific problem frequencies
        for freq, dev, is_measured in zip(self.frequency_bins, deviation, measured):
            if is_measured and abs(dev) > threshold_db * 1.5:  # More stringent threshold
                issues['problem_frequencies'].append({
                    'frequency': float(freq),
                    'deviation_db': float(dev)
                })

        return issues

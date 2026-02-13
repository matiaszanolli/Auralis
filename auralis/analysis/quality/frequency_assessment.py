"""
Frequency Response Assessment
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Assess audio frequency response quality

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Any

import numpy as np

from auralis.analysis.quality_assessors.base_assessor import BaseAssessor
from auralis.analysis.quality_assessors.utilities.scoring_ops import ScoringOperations


class FrequencyResponseAssessor(BaseAssessor):
    """Assess frequency response quality"""

    def __init__(self, frequency_bins: np.ndarray):
        """
        Initialize frequency response assessor

        Args:
            frequency_bins: Array of frequency bin values
        """
        super().__init__()
        self.frequency_bins = frequency_bins
        self.reference_curve = self._create_reference_curve()

    def _create_reference_curve(self) -> np.ndarray:
        """
        Create reference frequency response curve for quality assessment

        Returns ideal "flat" response with realistic rolloff characteristics
        """
        reference = np.zeros_like(self.frequency_bins)

        for i, freq in enumerate(self.frequency_bins):
            if freq < 20:
                reference[i] = -20  # Roll off below 20Hz
            elif freq < 50:
                reference[i] = -6   # Gentle rise
            elif freq < 16000:
                reference[i] = 0    # Flat response
            elif freq < 20000:
                reference[i] = -3   # Gentle rolloff
            else:
                reference[i] = -12  # Steeper rolloff above 20kHz

        return reference

    def assess(self, spectrum_result: dict[str, Any]) -> float:  # type: ignore[override]
        """
        Assess frequency response quality (0-100)

        Args:
            spectrum_result: Dictionary with 'spectrum' and 'frequency_bins'

        Returns:
            Quality score (0-100, higher is better)
        """
        spectrum = np.array(spectrum_result['spectrum'])

        # Compare to reference curve
        deviation = np.abs(spectrum - self.reference_curve)

        # Calculate weighted deviation (more weight to mid frequencies)
        weights = self._calculate_frequency_weights()
        weighted_deviation = np.average(deviation, weights=weights)

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
        spectrum = np.array(spectrum_result['spectrum'])
        deviation = np.abs(spectrum - self.reference_curve)
        weights = self._calculate_frequency_weights()
        weighted_deviation = np.average(deviation, weights=weights)

        return {
            'weighted_deviation_db': float(weighted_deviation),
            'max_deviation_db': float(np.max(deviation)),
            'mean_deviation_db': float(np.mean(deviation)),
            'deviation_std_db': float(np.std(deviation))
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
        spectrum = np.array(spectrum_result['spectrum'])
        deviation = spectrum - self.reference_curve

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
        bass_mask = (self.frequency_bins >= 20) & (self.frequency_bins <= 200)
        bass_deviation = np.mean(deviation[bass_mask])
        if bass_deviation > threshold_db:
            issues['excessive_bass'] = True
        elif bass_deviation < -threshold_db:
            issues['lacking_bass'] = True

        # Check mids (200-2000 Hz)
        mid_mask = (self.frequency_bins >= 200) & (self.frequency_bins <= 2000)
        mid_deviation = np.mean(deviation[mid_mask])
        if mid_deviation > threshold_db:
            issues['harsh_mids'] = True
        elif mid_deviation < -threshold_db:
            issues['muddy_mids'] = True

        # Check highs (4000-16000 Hz)
        high_mask = (self.frequency_bins >= 4000) & (self.frequency_bins <= 16000)
        high_deviation = np.mean(deviation[high_mask])
        if high_deviation > threshold_db:
            issues['bright_highs'] = True
        elif high_deviation < -threshold_db:
            issues['dull_highs'] = True

        # Identify specific problem frequencies
        for i, (freq, dev) in enumerate(zip(self.frequency_bins, deviation)):
            if abs(dev) > threshold_db * 1.5:  # More stringent threshold
                issues['problem_frequencies'].append({
                    'frequency': float(freq),
                    'deviation_db': float(dev)
                })

        return issues

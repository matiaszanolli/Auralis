# -*- coding: utf-8 -*-

"""
Frequency Response Assessment
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Assess audio frequency response quality

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
from typing import Dict


class FrequencyResponseAssessor:
    """Assess frequency response quality"""

    def __init__(self, frequency_bins: np.ndarray):
        """
        Initialize frequency response assessor

        Args:
            frequency_bins: Array of frequency bin values
        """
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

    def assess(self, spectrum_result: Dict) -> float:
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
        score = max(0, 100 - weighted_deviation * 2)

        return float(score)

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

    def identify_frequency_issues(self, spectrum_result: Dict,
                                 threshold_db: float = 6.0) -> Dict:
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

        issues = {
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

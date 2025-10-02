# -*- coding: utf-8 -*-

"""
Stereo Imaging Assessment
~~~~~~~~~~~~~~~~~~~~~~~~~

Assess stereo imaging and spatial quality

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Dict


class StereoImagingAssessor:
    """Assess stereo imaging quality"""

    def assess(self, phase_result: Dict) -> float:
        """
        Assess stereo imaging quality (0-100)

        Args:
            phase_result: Dictionary with correlation, phase, width, mono compatibility

        Returns:
            Quality score (0-100, higher is better)
        """
        correlation = phase_result['correlation']
        phase_correlation = phase_result['phase_correlation']
        stereo_width = phase_result['stereo_width']
        mono_compatibility = phase_result['mono_compatibility']

        # Individual component scores
        corr_score = self._score_correlation(correlation)
        phase_score = phase_correlation * 100
        width_score = self._score_stereo_width(stereo_width)
        mono_score = mono_compatibility * 100

        # Combined score (weighted average)
        total_score = (
            corr_score * 0.3 +
            phase_score * 0.2 +
            width_score * 0.2 +
            mono_score * 0.3
        )

        return float(total_score)

    def _score_correlation(self, correlation: float) -> float:
        """
        Score correlation between left and right channels

        Ideal correlation is positive but not too high (indicates good stereo width
        while maintaining coherence)

        Args:
            correlation: Correlation coefficient (-1 to 1)

        Returns:
            Score 0-100
        """
        if 0.3 <= correlation <= 0.8:
            return 100.0
        elif correlation > 0.8:
            # Penalty for too high correlation (too narrow stereo image)
            return max(0, 100 - (correlation - 0.8) * 200)
        elif correlation >= 0:
            # Lower correlation is less ideal but acceptable
            return correlation * 100 / 0.3
        else:
            # Negative correlation is problematic (phase issues)
            return 0.0

    def _score_stereo_width(self, stereo_width: float) -> float:
        """
        Score stereo width

        Moderate width is ideal - too narrow or too wide can be problematic

        Args:
            stereo_width: Stereo width factor (0-1)

        Returns:
            Score 0-100
        """
        if 0.3 <= stereo_width <= 0.8:
            return 100.0
        elif stereo_width < 0.3:
            # Too narrow
            return stereo_width * 100 / 0.3
        else:
            # Too wide
            return max(0, 100 - (stereo_width - 0.8) * 100 / 0.2)

    def identify_stereo_issues(self, phase_result: Dict) -> Dict:
        """
        Identify specific stereo imaging issues

        Args:
            phase_result: Phase correlation analysis results

        Returns:
            Dictionary with identified issues
        """
        correlation = phase_result['correlation']
        stereo_width = phase_result['stereo_width']
        mono_compatibility = phase_result['mono_compatibility']

        issues = {
            'phase_issues': correlation < 0,
            'too_narrow': stereo_width < 0.2,
            'too_wide': stereo_width > 0.9,
            'mono_incompatible': mono_compatibility < 0.5,
            'high_correlation': correlation > 0.9,
            'out_of_phase': correlation < -0.3,
            'warnings': []
        }

        # Generate warnings
        if issues['phase_issues']:
            issues['warnings'].append(
                "Phase issues detected - left and right channels are negatively correlated"
            )
        if issues['too_narrow']:
            issues['warnings'].append(
                "Stereo image is very narrow - consider widening"
            )
        if issues['too_wide']:
            issues['warnings'].append(
                "Stereo image is excessively wide - may cause mono compatibility issues"
            )
        if issues['mono_incompatible']:
            issues['warnings'].append(
                "Poor mono compatibility - signal may cancel when summed to mono"
            )
        if issues['out_of_phase']:
            issues['warnings'].append(
                "Severe out-of-phase issues detected - check polarity"
            )

        return issues

    def categorize_stereo_image(self, phase_result: Dict) -> Dict:
        """
        Categorize stereo image characteristics

        Args:
            phase_result: Phase correlation analysis results

        Returns:
            Dictionary with categorization
        """
        stereo_width = phase_result['stereo_width']
        correlation = phase_result['correlation']

        if stereo_width < 0.2:
            width_category = "Narrow"
            width_description = "Very narrow stereo image, almost mono"
        elif stereo_width < 0.4:
            width_category = "Moderate-Narrow"
            width_description = "Somewhat narrow stereo image"
        elif stereo_width < 0.7:
            width_category = "Normal"
            width_description = "Good stereo width"
        elif stereo_width < 0.9:
            width_category = "Wide"
            width_description = "Wide stereo image"
        else:
            width_category = "Very Wide"
            width_description = "Extremely wide stereo image"

        if correlation > 0.8:
            coherence = "High"
        elif correlation > 0.5:
            coherence = "Good"
        elif correlation > 0.2:
            coherence = "Moderate"
        elif correlation >= 0:
            coherence = "Low"
        else:
            coherence = "Poor (phase issues)"

        return {
            'width_category': width_category,
            'width_description': width_description,
            'coherence': coherence,
            'stereo_width': float(stereo_width),
            'correlation': float(correlation)
        }

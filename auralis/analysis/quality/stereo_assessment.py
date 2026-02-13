"""
Stereo Imaging Assessment
~~~~~~~~~~~~~~~~~~~~~~~~~

Assess stereo imaging and spatial quality

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Any


from auralis.analysis.quality_assessors.base_assessor import BaseAssessor
from auralis.analysis.quality_assessors.utilities.scoring_ops import ScoringOperations


class StereoImagingAssessor(BaseAssessor):
    """Assess stereo imaging quality"""

    def assess(self, phase_result: dict[str, Any]) -> float:  # type: ignore[override]
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

        # Score correlation using band scoring
        corr_score = ScoringOperations.band_score(correlation, [
            (-1.0, 0.0),      # Negative = phase issues
            (0.0, 33.0),      # Low correlation
            (0.3, 100.0),     # Optimal range starts
            (0.8, 100.0),     # Optimal range ends
            (1.0, 50.0)       # Too high = narrow image
        ])

        phase_score = phase_correlation * 100

        # Score stereo width using band scoring
        width_score = ScoringOperations.band_score(stereo_width, [
            (0.0, 0.0),       # Too narrow
            (0.3, 100.0),     # Optimal range
            (0.8, 100.0),     # Optimal range
            (1.0, 0.0)        # Too wide
        ])

        mono_score = mono_compatibility * 100

        # Combined score (weighted average)
        total_score = ScoringOperations.weighted_score([
            (corr_score, 0.3),
            (phase_score, 0.2),
            (width_score, 0.2),
            (mono_score, 0.3)
        ])

        return float(total_score)

    def detailed_analysis(self, phase_result: dict[str, Any]) -> dict[str, Any]:  # type: ignore[override]
        """
        Perform detailed stereo imaging analysis

        Args:
            phase_result: Phase correlation analysis results

        Returns:
            Dictionary with detailed stereo metrics
        """
        correlation = phase_result['correlation']
        stereo_width = phase_result['stereo_width']
        mono_compatibility = phase_result['mono_compatibility']

        return {
            'correlation': float(correlation),
            'stereo_width': float(stereo_width),
            'mono_compatibility': float(mono_compatibility),
            'correlation_score': ScoringOperations.band_score(correlation, [
                (-1.0, 0.0), (0.0, 33.0), (0.3, 100.0), (0.8, 100.0), (1.0, 50.0)
            ]),
            'width_score': ScoringOperations.band_score(stereo_width, [
                (0.0, 0.0), (0.3, 100.0), (0.8, 100.0), (1.0, 0.0)
            ])
        }

    def identify_stereo_issues(self, phase_result: dict[str, Any]) -> dict[str, Any]:
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

    def categorize_stereo_image(self, phase_result: dict[str, Any]) -> dict[str, Any]:
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

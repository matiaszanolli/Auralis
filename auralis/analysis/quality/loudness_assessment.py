# -*- coding: utf-8 -*-

"""
Loudness Assessment
~~~~~~~~~~~~~~~~~~

Assess audio loudness quality and compliance

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Dict, Any
from auralis.analysis.quality_assessors.base_assessor import BaseAssessor
from auralis.analysis.quality_assessors.utilities.scoring_ops import ScoringOperations
from auralis.analysis.quality_assessors.utilities.assessment_constants import AssessmentConstants


class LoudnessAssessor(BaseAssessor):
    """Assess loudness quality and standards compliance"""

    def assess(self, loudness_result: Any) -> float:  # type: ignore[override]
        """
        Assess loudness quality (0-100)

        Evaluates adherence to loudness standards and dynamic range

        Args:
            loudness_result: Loudness measurement result object

        Returns:
            Quality score (0-100, higher is better)
        """
        integrated_lufs = loudness_result.integrated_lufs
        loudness_range = loudness_result.loudness_range
        true_peak = loudness_result.true_peak_dbfs

        # Score individual components using standard ranges
        lufs_score = ScoringOperations.range_based_score(
            integrated_lufs,
            optimal_range=(-16, -14),
            acceptable_range=(-20, -10)
        )

        lra_score = ScoringOperations.range_based_score(
            loudness_range,
            optimal_range=AssessmentConstants.TARGET_LOUDNESS_RANGE_LU,
            acceptable_range=AssessmentConstants.ACCEPTABLE_LOUDNESS_RANGE_LU
        )

        peak_score = ScoringOperations.threshold_score(
            true_peak,
            threshold=AssessmentConstants.SPOTIFY_MAX_TRUE_PEAK,
            max_penalty=100.0
        )

        # Combined score (weighted average)
        total_score = ScoringOperations.weighted_score([
            (lufs_score, 0.5),
            (lra_score, 0.3),
            (peak_score, 0.2)
        ])

        return float(total_score)

    def detailed_analysis(self, loudness_result: Any) -> Dict[str, Any]:  # type: ignore[override]
        """
        Perform detailed loudness analysis

        Args:
            loudness_result: Loudness measurement result

        Returns:
            Dictionary with detailed loudness metrics
        """
        integrated_lufs = loudness_result.integrated_lufs
        loudness_range = loudness_result.loudness_range
        true_peak = loudness_result.true_peak_dbfs

        return {
            'integrated_lufs': float(integrated_lufs),
            'loudness_range': float(loudness_range),
            'true_peak_dbfs': float(true_peak),
            'lufs_score': ScoringOperations.range_based_score(
                integrated_lufs,
                optimal_range=(-16, -14),
                acceptable_range=(-20, -10)
            ),
            'lra_score': ScoringOperations.range_based_score(
                loudness_range,
                optimal_range=AssessmentConstants.TARGET_LOUDNESS_RANGE_LU,
                acceptable_range=AssessmentConstants.ACCEPTABLE_LOUDNESS_RANGE_LU
            ),
            'peak_score': ScoringOperations.threshold_score(
                true_peak,
                threshold=AssessmentConstants.SPOTIFY_MAX_TRUE_PEAK,
                max_penalty=100.0
            )
        }

    def check_standards_compliance(self, loudness_result: Any) -> Dict[str, Any]:
        """
        Check compliance with various loudness standards

        Args:
            loudness_result: Loudness measurement result

        Returns:
            Dictionary with compliance status for different standards
        """
        integrated_lufs = loudness_result.integrated_lufs
        loudness_range = loudness_result.loudness_range
        true_peak = loudness_result.true_peak_dbfs

        compliance = {}
        for standard in ['spotify', 'apple_music', 'youtube', 'tidal', 'ebu_r128', 'atsc_a85']:
            targets = AssessmentConstants.get_standard_compliance_targets(standard)
            if targets:
                compliance[standard] = self._check_compliance(
                    standard, integrated_lufs, loudness_range, true_peak, targets
                )

        return compliance

    def _check_compliance(self, standard: str, lufs: float, lra: float,
                         peak: float, targets: Dict[str, Any]) -> Dict[str, Any]:
        """Check compliance with standard using target values"""
        target_lufs = targets.get('target_lufs')
        tolerance = targets.get('tolerance', 0.0)
        max_peak = targets.get('max_true_peak', -1.0)

        # Check LUFS compliance
        lufs_compliant = abs(lufs - target_lufs) <= tolerance if target_lufs else False

        # Check peak compliance
        peak_compliant = peak <= max_peak

        # Check LRA if present
        lra_compliant = True
        if 'max_lra' in targets:
            lra_compliant = lra <= targets['max_lra']

        compliant = lufs_compliant and peak_compliant and lra_compliant

        return {
            'compliant': compliant,
            'target_lufs': float(target_lufs) if target_lufs else None,
            'tolerance_lufs': float(tolerance),
            'max_true_peak': float(max_peak),
            'current_lufs': float(lufs),
            'current_peak': float(peak),
            'notes': f'{standard.upper()} standard'
        }

# -*- coding: utf-8 -*-

"""
Dynamic Range Assessment
~~~~~~~~~~~~~~~~~~~~~~~~

Assess audio dynamic range quality

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Dict
from auralis.analysis.quality_assessors.base_assessor import BaseAssessor
from auralis.analysis.quality_assessors.utilities.scoring_ops import ScoringOperations
from auralis.analysis.quality_assessors.utilities.assessment_constants import AssessmentConstants


class DynamicRangeAssessor(BaseAssessor):
    """Assess dynamic range quality"""

    def assess(self, dynamic_result: Dict[str, Any]) -> float:
        """
        Assess dynamic range quality (0-100)

        Args:
            dynamic_result: Dictionary with 'dr_value' and 'crest_factor_db'

        Returns:
            Quality score (0-100, higher is better)
        """
        dr_value = dynamic_result['dr_value']
        crest_factor = dynamic_result['crest_factor_db']

        # DR value scoring using band score
        dr_score = ScoringOperations.band_score(dr_value, [
            (0.0, 0.0),
            (4.0, 20.0),
            (7.0, 40.0),
            (10.0, 60.0),
            (14.0, 80.0),
            (20.0, 100.0)
        ])

        # Crest factor scoring
        cf_score = ScoringOperations.band_score(crest_factor, [
            (0.0, 0.0),
            (6.0, 40.0),
            (10.0, 70.0),
            (15.0, 100.0)
        ])

        # Combined score (weighted average)
        total_score = ScoringOperations.weighted_score([
            (dr_score, 0.7),
            (cf_score, 0.3)
        ])

        return float(total_score)

    def detailed_analysis(self, dynamic_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform detailed dynamic range analysis

        Args:
            dynamic_result: Dictionary with dynamic range metrics

        Returns:
            Dictionary with detailed dynamic metrics
        """
        dr_value = dynamic_result['dr_value']
        crest_factor = dynamic_result['crest_factor_db']

        dr_score = ScoringOperations.band_score(dr_value, [
            (0.0, 0.0), (4.0, 20.0), (7.0, 40.0),
            (10.0, 60.0), (14.0, 80.0), (20.0, 100.0)
        ])

        cf_score = ScoringOperations.band_score(crest_factor, [
            (0.0, 0.0), (6.0, 40.0), (10.0, 70.0), (15.0, 100.0)
        ])

        return {
            'dr_value': float(dr_value),
            'crest_factor_db': float(crest_factor),
            'dr_score': dr_score,
            'crest_factor_score': cf_score
        }

    def categorize_dynamics(self, dr_value: float) -> Dict[str, Any]:
        """
        Categorize dynamic range characteristics

        Args:
            dr_value: DR value

        Returns:
            Dictionary with categorization
        """
        if dr_value >= 14:
            category = "Excellent"
            description = "Very dynamic, natural sound with wide dynamic range"
        elif dr_value >= 10:
            category = "Good"
            description = "Good dynamic range, suitable for most applications"
        elif dr_value >= 7:
            category = "Fair"
            description = "Moderate compression, acceptable dynamic range"
        elif dr_value >= 4:
            category = "Compressed"
            description = "Heavily compressed, limited dynamic range"
        else:
            category = "Over-compressed"
            description = "Extreme compression, very limited dynamics"

        return {
            'category': category,
            'description': description,
            'dr_value': float(dr_value),
            'is_over_compressed': dr_value < 7,
            'is_brickwalled': dr_value < 4
        }

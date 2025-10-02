# -*- coding: utf-8 -*-

"""
Dynamic Range Assessment
~~~~~~~~~~~~~~~~~~~~~~~~

Assess audio dynamic range quality

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Dict


class DynamicRangeAssessor:
    """Assess dynamic range quality"""

    def assess(self, dynamic_result: Dict) -> float:
        """
        Assess dynamic range quality (0-100)

        Args:
            dynamic_result: Dictionary with 'dr_value' and 'crest_factor_db'

        Returns:
            Quality score (0-100, higher is better)
        """
        dr_value = dynamic_result['dr_value']
        crest_factor = dynamic_result['crest_factor_db']

        # DR value scoring
        dr_score = self._score_dr_value(dr_value)

        # Crest factor scoring
        cf_score = self._score_crest_factor(crest_factor)

        # Combined score (weighted average)
        return float(dr_score * 0.7 + cf_score * 0.3)

    def _score_dr_value(self, dr_value: float) -> float:
        """
        Score DR (Dynamic Range) value

        Args:
            dr_value: DR value from EBU R128

        Returns:
            Score 0-100
        """
        if dr_value >= 20:
            return 100.0
        elif dr_value >= 14:
            return 80 + (dr_value - 14) * 20 / 6  # 80-100
        elif dr_value >= 10:
            return 60 + (dr_value - 10) * 20 / 4  # 60-80
        elif dr_value >= 7:
            return 40 + (dr_value - 7) * 20 / 3   # 40-60
        elif dr_value >= 4:
            return 20 + (dr_value - 4) * 20 / 3   # 20-40
        else:
            return dr_value * 20 / 4               # 0-20

    def _score_crest_factor(self, crest_factor: float) -> float:
        """
        Score crest factor (peak-to-RMS ratio)

        Args:
            crest_factor: Crest factor in dB

        Returns:
            Score 0-100
        """
        if crest_factor >= 15:
            return 100.0
        elif crest_factor >= 10:
            return 70 + (crest_factor - 10) * 30 / 5  # 70-100
        elif crest_factor >= 6:
            return 40 + (crest_factor - 6) * 30 / 4   # 40-70
        else:
            return crest_factor * 40 / 6              # 0-40

    def categorize_dynamics(self, dr_value: float) -> Dict:
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

# -*- coding: utf-8 -*-

"""
Distortion Assessment
~~~~~~~~~~~~~~~~~~~~

Assess audio distortion and noise levels

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
from typing import Dict
from auralis.analysis.quality_assessors.base_assessor import BaseAssessor
from auralis.analysis.quality_assessors.utilities.estimation_ops import EstimationOperations
from auralis.analysis.quality_assessors.utilities.scoring_ops import ScoringOperations
from auralis.analysis.quality_assessors.utilities.assessment_constants import AssessmentConstants


class DistortionAssessor(BaseAssessor):
    """Assess distortion and noise quality"""

    def assess(self, audio_data: np.ndarray) -> float:
        """
        Assess distortion levels (0-100)

        Args:
            audio_data: Audio data to analyze

        Returns:
            Quality score (0-100, higher is better)
        """
        # Estimate distortion metrics using utilities
        thd = EstimationOperations.estimate_thd(audio_data)
        clipping_factor = EstimationOperations.detect_clipping(audio_data)
        noise_floor = EstimationOperations.estimate_noise_floor(audio_data)

        # Score individual components
        thd_score = ScoringOperations.band_score(thd, [
            (0.0, 100.0),
            (0.001, 100.0),  # < 0.1%
            (0.01, 80.0),    # < 1%
            (0.05, 40.0),    # < 5%
            (0.1, 0.0)       # Critical
        ])

        clipping_score = ScoringOperations.exponential_penalty(
            clipping_factor, 0.0, steepness=1000.0
        )

        snr_db = -noise_floor
        noise_score = ScoringOperations.band_score(snr_db, [
            (0.0, 0.0),
            (60.0, 70.0),
            (90.0, 100.0)
        ])

        # Combined score (weighted average)
        total_score = ScoringOperations.weighted_score([
            (thd_score, 0.4),
            (clipping_score, 0.3),
            (noise_score, 0.3)
        ])

        return float(total_score)

    def detailed_analysis(self, audio_data: np.ndarray) -> Dict[str, Any]:
        """
        Perform detailed distortion analysis

        Args:
            audio_data: Audio data to analyze

        Returns:
            Dictionary with detailed distortion metrics
        """
        thd = EstimationOperations.estimate_thd(audio_data)
        clipping_factor = EstimationOperations.detect_clipping(audio_data)
        noise_floor = EstimationOperations.estimate_noise_floor(audio_data)

        return {
            'thd': float(thd),
            'thd_percent': float(thd * 100),
            'clipping_factor': float(clipping_factor),
            'clipping_percent': float(clipping_factor * 100),
            'noise_floor_db': float(noise_floor),
            'snr_db': float(-noise_floor),
            'has_clipping': clipping_factor > AssessmentConstants.ACCEPTABLE_CLIPPING_FACTOR,
            'excessive_distortion': thd > AssessmentConstants.ACCEPTABLE_THD,
            'high_noise': noise_floor > AssessmentConstants.ACCEPTABLE_NOISE_FLOOR
        }

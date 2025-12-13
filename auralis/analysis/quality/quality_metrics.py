# -*- coding: utf-8 -*-

"""
Quality Metrics Orchestrator
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Main quality assessment orchestrator using specialized assessors

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
from typing import Dict, Any, List
from dataclasses import dataclass

from ..spectrum_analyzer import SpectrumAnalyzer, SpectrumSettings
from ..loudness_meter import LoudnessMeter
from ..phase_correlation import PhaseCorrelationAnalyzer
from ..dynamic_range import DynamicRangeAnalyzer

from .frequency_assessment import FrequencyResponseAssessor
from .dynamic_assessment import DynamicRangeAssessor
from .stereo_assessment import StereoImagingAssessor
from .distortion_assessment import DistortionAssessor
from .loudness_assessment import LoudnessAssessor


@dataclass
class QualityScores:
    """Audio quality assessment scores"""
    overall_score: float  # 0-100 overall quality score

    # Sub-scores
    frequency_response_score: float
    dynamic_range_score: float
    stereo_imaging_score: float
    distortion_score: float
    loudness_score: float

    # Quality category
    quality_category: str  # Excellent, Very Good, Good, Fair, Poor

    # Detailed metrics
    detailed_metrics: Dict[str, Any]


class QualityMetrics:
    """Comprehensive audio quality assessment"""

    def __init__(self, sample_rate: int = 44100):
        """
        Initialize quality metrics system

        Args:
            sample_rate: Audio sample rate in Hz
        """
        self.sample_rate = sample_rate

        # Initialize analyzers
        self.spectrum_analyzer = SpectrumAnalyzer(
            SpectrumSettings(
                fft_size=8192,
                frequency_bands=128,
                sample_rate=sample_rate
            )
        )
        self.loudness_meter = LoudnessMeter(sample_rate)
        self.phase_analyzer = PhaseCorrelationAnalyzer(sample_rate)
        self.dynamic_range_analyzer = DynamicRangeAnalyzer(sample_rate)

        # Initialize assessors
        self.frequency_assessor = FrequencyResponseAssessor(
            self.spectrum_analyzer.frequency_bins
        )
        self.dynamic_assessor = DynamicRangeAssessor()
        self.stereo_assessor = StereoImagingAssessor()
        self.distortion_assessor = DistortionAssessor()
        self.loudness_assessor = LoudnessAssessor()

    def assess_quality(self, audio_data: np.ndarray) -> QualityScores:
        """
        Comprehensive quality assessment of audio

        Args:
            audio_data: Audio data (mono or stereo)

        Returns:
            QualityScores with comprehensive assessment
        """
        # Ensure stereo for full analysis
        if audio_data.ndim == 1:
            stereo_audio = np.column_stack([audio_data, audio_data])
        else:
            stereo_audio = audio_data

        # Perform all analyses
        spectrum_result = self.spectrum_analyzer.analyze_file(stereo_audio[:, 0])

        # Reset loudness meter for fresh measurement
        self.loudness_meter.reset()

        # Analyze in chunks for loudness
        chunk_size = int(0.4 * self.sample_rate)  # 400ms chunks
        for i in range(0, len(stereo_audio), chunk_size):
            chunk = stereo_audio[i:i + chunk_size]
            if len(chunk) >= chunk_size:
                self.loudness_meter.measure_chunk(chunk)

        loudness_result = self.loudness_meter.finalize_measurement()
        phase_result = self.phase_analyzer.analyze_correlation(stereo_audio)
        dynamic_result = self.dynamic_range_analyzer.analyze_dynamic_range(stereo_audio)

        # Calculate quality scores using specialized assessors
        freq_score = self.frequency_assessor.assess(spectrum_result)
        dynamic_score = self.dynamic_assessor.assess(dynamic_result)
        stereo_score = self.stereo_assessor.assess(phase_result)
        distortion_score = self.distortion_assessor.assess(audio_data)
        loudness_score = self.loudness_assessor.assess(loudness_result)

        # Calculate overall score (weighted average)
        weights = {
            'frequency': 0.25,
            'dynamic': 0.20,
            'stereo': 0.15,
            'distortion': 0.25,
            'loudness': 0.15
        }

        overall_score = (
            freq_score * weights['frequency'] +
            dynamic_score * weights['dynamic'] +
            stereo_score * weights['stereo'] +
            distortion_score * weights['distortion'] +
            loudness_score * weights['loudness']
        )

        # Determine quality category
        quality_category = self._categorize_quality(overall_score)

        # Compile detailed metrics
        detailed_metrics = {
            'spectrum_analysis': spectrum_result,
            'loudness_measurement': {
                'integrated_lufs': loudness_result.integrated_lufs,
                'loudness_range': loudness_result.loudness_range,
                'peak_level': loudness_result.peak_level_dbfs,
                'true_peak': loudness_result.true_peak_dbfs
            },
            'phase_correlation': phase_result,
            'dynamic_range': dynamic_result,
            'distortion_analysis': self.distortion_assessor.detailed_analysis(audio_data),
            'quality_issues': self._identify_quality_issues(
                freq_score, dynamic_score, stereo_score,
                distortion_score, loudness_score
            ),
            'frequency_issues': self.frequency_assessor.identify_frequency_issues(spectrum_result),
            'stereo_issues': self.stereo_assessor.identify_stereo_issues(phase_result),
            'dynamic_category': self.dynamic_assessor.categorize_dynamics(dynamic_result['dr_value']),
            'stereo_category': self.stereo_assessor.categorize_stereo_image(phase_result),
            'loudness_compliance': self.loudness_assessor.check_standards_compliance(loudness_result)
        }

        return QualityScores(
            overall_score=float(overall_score),
            frequency_response_score=float(freq_score),
            dynamic_range_score=float(dynamic_score),
            stereo_imaging_score=float(stereo_score),
            distortion_score=float(distortion_score),
            loudness_score=float(loudness_score),
            quality_category=quality_category,
            detailed_metrics=detailed_metrics
        )

    def _categorize_quality(self, overall_score: float) -> str:
        """Categorize overall quality score"""
        if overall_score >= 90:
            return "Excellent"
        elif overall_score >= 75:
            return "Very Good"
        elif overall_score >= 60:
            return "Good"
        elif overall_score >= 40:
            return "Fair"
        else:
            return "Poor"

    def _identify_quality_issues(self,
                                freq_score: float,
                                dynamic_score: float,
                                stereo_score: float,
                                distortion_score: float,
                                loudness_score: float) -> List[str]:
        """Identify specific quality issues based on sub-scores"""
        issues = []

        if freq_score < 60:
            issues.append("Frequency response issues detected")
        if dynamic_score < 60:
            issues.append("Limited dynamic range or over-compression")
        if stereo_score < 60:
            issues.append("Stereo imaging or phase issues detected")
        if distortion_score < 60:
            issues.append("Distortion or noise issues present")
        if loudness_score < 60:
            issues.append("Loudness levels not optimal")

        return issues

    def compare_quality(self, audio1: np.ndarray, audio2: np.ndarray) -> Dict[str, Any]:
        """
        Compare quality between two audio files

        Args:
            audio1: First audio sample
            audio2: Second audio sample

        Returns:
            Comparison dictionary with scores and differences
        """
        scores1 = self.assess_quality(audio1)
        scores2 = self.assess_quality(audio2)

        comparison = {
            'audio1_score': scores1.overall_score,
            'audio2_score': scores2.overall_score,
            'difference': scores2.overall_score - scores1.overall_score,
            'winner': 'audio2' if scores2.overall_score > scores1.overall_score else 'audio1',
            'sub_score_differences': {
                'frequency_response': scores2.frequency_response_score - scores1.frequency_response_score,
                'dynamic_range': scores2.dynamic_range_score - scores1.dynamic_range_score,
                'stereo_imaging': scores2.stereo_imaging_score - scores1.stereo_imaging_score,
                'distortion': scores2.distortion_score - scores1.distortion_score,
                'loudness': scores2.loudness_score - scores1.loudness_score
            },
            'quality_categories': {
                'audio1': scores1.quality_category,
                'audio2': scores2.quality_category
            }
        }

        return comparison

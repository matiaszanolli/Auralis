# -*- coding: utf-8 -*-

"""
Audio Quality Metrics
~~~~~~~~~~~~~~~~~~~~~

Comprehensive audio quality assessment using perceptual and objective metrics.
"""

import numpy as np
from scipy import signal
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

from .spectrum_analyzer import SpectrumAnalyzer, SpectrumSettings
from .loudness_meter import LoudnessMeter
from .phase_correlation import PhaseCorrelationAnalyzer
from .dynamic_range import DynamicRangeAnalyzer


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
    detailed_metrics: Dict


class QualityMetrics:
    """Comprehensive audio quality assessment"""

    def __init__(self, sample_rate: int = 44100):
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

        # Quality assessment parameters
        self.reference_curve = self._create_reference_curve()

    def _create_reference_curve(self) -> np.ndarray:
        """Create reference frequency response curve for quality assessment"""
        freqs = self.spectrum_analyzer.frequency_bins

        # Idealized "flat" response with slight high-frequency rolloff
        # This represents a high-quality audio system response
        reference = np.zeros_like(freqs)

        for i, freq in enumerate(freqs):
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
            # Convert mono to fake stereo
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

        # Calculate quality scores
        freq_score = self._assess_frequency_response(spectrum_result)
        dynamic_score = self._assess_dynamic_range(dynamic_result)
        stereo_score = self._assess_stereo_imaging(phase_result)
        distortion_score = self._assess_distortion(audio_data)
        loudness_score = self._assess_loudness(loudness_result)

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
            'distortion_analysis': self._detailed_distortion_analysis(audio_data),
            'quality_issues': self._identify_quality_issues(
                freq_score, dynamic_score, stereo_score,
                distortion_score, loudness_score
            )
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

    def _assess_frequency_response(self, spectrum_result: Dict) -> float:
        """Assess frequency response quality (0-100)"""
        spectrum = np.array(spectrum_result['spectrum'])

        # Compare to reference curve
        deviation = np.abs(spectrum - self.reference_curve)

        # Calculate weighted deviation (more weight to mid frequencies)
        freqs = np.array(spectrum_result['frequency_bins'])
        weights = np.ones_like(freqs)

        # Higher weight for critical frequency ranges
        for i, freq in enumerate(freqs):
            if 200 <= freq <= 5000:  # Critical vocal/instrument range
                weights[i] = 2.0
            elif 50 <= freq <= 200 or 5000 <= freq <= 16000:  # Important ranges
                weights[i] = 1.5

        weighted_deviation = np.average(deviation, weights=weights)

        # Convert to score (lower deviation = higher score)
        # Score decreases as deviation increases
        score = max(0, 100 - weighted_deviation * 2)

        return score

    def _assess_dynamic_range(self, dynamic_result: Dict) -> float:
        """Assess dynamic range quality (0-100)"""
        dr_value = dynamic_result['dr_value']
        crest_factor = dynamic_result['crest_factor_db']

        # DR value scoring
        if dr_value >= 20:
            dr_score = 100
        elif dr_value >= 14:
            dr_score = 80 + (dr_value - 14) * 20 / 6  # 80-100
        elif dr_value >= 10:
            dr_score = 60 + (dr_value - 10) * 20 / 4  # 60-80
        elif dr_value >= 7:
            dr_score = 40 + (dr_value - 7) * 20 / 3   # 40-60
        elif dr_value >= 4:
            dr_score = 20 + (dr_value - 4) * 20 / 3   # 20-40
        else:
            dr_score = dr_value * 20 / 4               # 0-20

        # Crest factor scoring
        if crest_factor >= 15:
            cf_score = 100
        elif crest_factor >= 10:
            cf_score = 70 + (crest_factor - 10) * 30 / 5  # 70-100
        elif crest_factor >= 6:
            cf_score = 40 + (crest_factor - 6) * 30 / 4   # 40-70
        else:
            cf_score = crest_factor * 40 / 6              # 0-40

        # Combined score (weighted average)
        return (dr_score * 0.7 + cf_score * 0.3)

    def _assess_stereo_imaging(self, phase_result: Dict) -> float:
        """Assess stereo imaging quality (0-100)"""
        correlation = phase_result['correlation']
        phase_correlation = phase_result['phase_correlation']
        stereo_width = phase_result['stereo_width']
        mono_compatibility = phase_result['mono_compatibility']

        # Correlation scoring (should be positive but not too high)
        if 0.3 <= correlation <= 0.8:
            corr_score = 100
        elif correlation > 0.8:
            corr_score = 100 - (correlation - 0.8) * 200  # Penalty for too high correlation
        elif correlation >= 0:
            corr_score = correlation * 100 / 0.3
        else:
            corr_score = 0  # Negative correlation is bad

        # Phase correlation scoring
        phase_score = phase_correlation * 100

        # Stereo width scoring (should be moderate)
        if 0.3 <= stereo_width <= 0.8:
            width_score = 100
        elif stereo_width < 0.3:
            width_score = stereo_width * 100 / 0.3
        else:
            width_score = 100 - (stereo_width - 0.8) * 100 / 0.2

        # Mono compatibility scoring
        mono_score = mono_compatibility * 100

        # Combined score
        return (corr_score * 0.3 + phase_score * 0.2 +
                width_score * 0.2 + mono_score * 0.3)

    def _assess_distortion(self, audio_data: np.ndarray) -> float:
        """Assess distortion levels (0-100)"""
        # Calculate THD+N estimation
        thd = self._estimate_thd(audio_data)

        # Calculate clipping detection
        clipping_factor = self._detect_clipping(audio_data)

        # Calculate noise floor
        noise_floor = self._estimate_noise_floor(audio_data)

        # THD scoring (lower is better)
        if thd < 0.001:  # < 0.1%
            thd_score = 100
        elif thd < 0.01:  # < 1%
            thd_score = 80 + (0.01 - thd) * 20 / 0.009
        elif thd < 0.05:  # < 5%
            thd_score = 40 + (0.05 - thd) * 40 / 0.04
        else:
            thd_score = max(0, 40 - thd * 40 / 0.05)

        # Clipping scoring
        clipping_score = max(0, 100 - clipping_factor * 1000)

        # Noise floor scoring (higher SNR is better)
        snr_db = -noise_floor
        if snr_db > 90:
            noise_score = 100
        elif snr_db > 60:
            noise_score = 70 + (snr_db - 60) * 30 / 30
        else:
            noise_score = snr_db * 70 / 60

        # Combined distortion score
        return (thd_score * 0.4 + clipping_score * 0.4 + noise_score * 0.2)

    def _assess_loudness(self, loudness_result) -> float:
        """Assess loudness quality (0-100)"""
        integrated_lufs = loudness_result.integrated_lufs
        loudness_range = loudness_result.loudness_range
        true_peak = loudness_result.true_peak_dbfs

        # Integrated LUFS scoring (closer to -23 LUFS is better for broadcast)
        # But we'll use a wider "good" range for general audio
        lufs_deviation = abs(integrated_lufs - (-18))  # Target -18 LUFS for general audio
        if lufs_deviation <= 5:
            lufs_score = 100
        elif lufs_deviation <= 15:
            lufs_score = 70 + (15 - lufs_deviation) * 30 / 10
        else:
            lufs_score = max(0, 70 - (lufs_deviation - 15) * 70 / 20)

        # Loudness range scoring (moderate range is good)
        if 5 <= loudness_range <= 15:
            lr_score = 100
        elif loudness_range < 5:
            lr_score = loudness_range * 100 / 5
        else:
            lr_score = max(0, 100 - (loudness_range - 15) * 50 / 10)

        # True peak scoring (should be below 0 dBFS)
        if true_peak <= -1:
            tp_score = 100
        elif true_peak <= 0:
            tp_score = 50 + (0 - true_peak) * 50
        else:
            tp_score = max(0, 50 - true_peak * 25)

        # Combined loudness score
        return (lufs_score * 0.4 + lr_score * 0.3 + tp_score * 0.3)

    def _estimate_thd(self, audio_data: np.ndarray) -> float:
        """Estimate Total Harmonic Distortion"""
        if audio_data.ndim == 2:
            audio_data = np.mean(audio_data, axis=1)

        # Use FFT to estimate THD
        fft = np.fft.rfft(audio_data)
        magnitude = np.abs(fft)

        # Find fundamental frequency (largest peak)
        fundamental_idx = np.argmax(magnitude[1:]) + 1  # Skip DC

        # Estimate harmonics (2nd, 3rd, 4th, 5th)
        harmonic_power = 0
        fundamental_power = magnitude[fundamental_idx]**2

        for harmonic in [2, 3, 4, 5]:
            harmonic_idx = fundamental_idx * harmonic
            if harmonic_idx < len(magnitude):
                harmonic_power += magnitude[harmonic_idx]**2

        # Calculate THD
        if fundamental_power > 0:
            thd = np.sqrt(harmonic_power / fundamental_power)
        else:
            thd = 0.0

        return thd

    def _detect_clipping(self, audio_data: np.ndarray) -> float:
        """Detect clipping artifacts"""
        # Count samples near full scale
        threshold = 0.99
        clipped_samples = np.sum(np.abs(audio_data) >= threshold)
        clipping_factor = clipped_samples / len(audio_data.flatten())

        return clipping_factor

    def _estimate_noise_floor(self, audio_data: np.ndarray) -> float:
        """Estimate noise floor level"""
        if audio_data.ndim == 2:
            audio_data = np.mean(audio_data, axis=1)

        # Use quiet sections to estimate noise floor
        rms_values = []
        window_size = int(0.1 * self.sample_rate)  # 100ms windows

        for i in range(0, len(audio_data) - window_size, window_size):
            window = audio_data[i:i + window_size]
            rms = np.sqrt(np.mean(window**2))
            rms_values.append(rms)

        # Use 10th percentile as noise floor estimate
        if rms_values:
            noise_rms = np.percentile(rms_values, 10)
            noise_floor_db = 20 * np.log10(noise_rms + 1e-10)
        else:
            noise_floor_db = -96  # Default very low noise floor

        return noise_floor_db

    def _detailed_distortion_analysis(self, audio_data: np.ndarray) -> Dict:
        """Detailed distortion analysis"""
        thd = self._estimate_thd(audio_data)
        clipping = self._detect_clipping(audio_data)
        noise_floor = self._estimate_noise_floor(audio_data)

        return {
            'thd_estimate': float(thd),
            'thd_percentage': float(thd * 100),
            'clipping_factor': float(clipping),
            'clipped_samples_percentage': float(clipping * 100),
            'noise_floor_db': float(noise_floor),
            'snr_estimate_db': float(-noise_floor)
        }

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

    def _identify_quality_issues(self, freq_score: float, dynamic_score: float,
                               stereo_score: float, distortion_score: float,
                               loudness_score: float) -> List[str]:
        """Identify specific quality issues"""
        issues = []

        if freq_score < 70:
            issues.append("Frequency response imbalance detected")
        if dynamic_score < 60:
            issues.append("Poor dynamic range - may be over-compressed")
        if stereo_score < 60:
            issues.append("Stereo imaging issues detected")
        if distortion_score < 70:
            issues.append("Distortion or clipping detected")
        if loudness_score < 60:
            issues.append("Loudness levels not optimal")

        if not issues:
            issues.append("No significant quality issues detected")

        return issues

    def compare_quality(self, audio1: np.ndarray, audio2: np.ndarray) -> Dict:
        """Compare quality between two audio files"""
        quality1 = self.assess_quality(audio1)
        quality2 = self.assess_quality(audio2)

        return {
            'audio1_quality': quality1,
            'audio2_quality': quality2,
            'comparison': {
                'overall_difference': quality2.overall_score - quality1.overall_score,
                'frequency_response_difference': quality2.frequency_response_score - quality1.frequency_response_score,
                'dynamic_range_difference': quality2.dynamic_range_score - quality1.dynamic_range_score,
                'stereo_imaging_difference': quality2.stereo_imaging_score - quality1.stereo_imaging_score,
                'distortion_difference': quality2.distortion_score - quality1.distortion_score,
                'loudness_difference': quality2.loudness_score - quality1.loudness_score,
                'winner': 'audio2' if quality2.overall_score > quality1.overall_score else
                         'audio1' if quality1.overall_score > quality2.overall_score else 'tie'
            }
        }
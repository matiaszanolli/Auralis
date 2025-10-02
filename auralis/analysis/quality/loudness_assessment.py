# -*- coding: utf-8 -*-

"""
Loudness Assessment
~~~~~~~~~~~~~~~~~~

Assess audio loudness quality and compliance

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Dict


class LoudnessAssessor:
    """Assess loudness quality and standards compliance"""

    def assess(self, loudness_result) -> float:
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

        # Integrated loudness scoring (target: -14 to -16 LUFS)
        lufs_score = self._score_integrated_lufs(integrated_lufs)

        # Loudness range scoring
        lra_score = self._score_loudness_range(loudness_range)

        # True peak scoring (should be below -1 dBFS)
        peak_score = self._score_true_peak(true_peak)

        # Combined score
        total_score = (lufs_score * 0.5 + lra_score * 0.3 + peak_score * 0.2)

        return float(total_score)

    def _score_integrated_lufs(self, lufs: float) -> float:
        """
        Score integrated loudness

        Target range is -14 to -16 LUFS (streaming standard)

        Args:
            lufs: Integrated LUFS value

        Returns:
            Score 0-100
        """
        # Optimal range: -14 to -16 LUFS
        if -16 <= lufs <= -14:
            return 100.0

        # Good range: -18 to -12 LUFS
        elif -18 <= lufs < -16:
            return 90 + (lufs + 16) * 10 / 2
        elif -14 < lufs <= -12:
            return 90 + (-14 - lufs) * 10 / 2

        # Acceptable range: -20 to -10 LUFS
        elif -20 <= lufs < -18:
            return 70 + (lufs + 18) * 20 / 2
        elif -12 < lufs <= -10:
            return 70 + (-12 - lufs) * 20 / 2

        # Below acceptable
        elif lufs < -20:
            return max(0, 70 + (lufs + 20) * 70 / 10)  # Penalty for too quiet
        else:
            return max(0, 70 - (lufs + 10) * 70 / 10)  # Penalty for too loud

    def _score_loudness_range(self, lra: float) -> float:
        """
        Score loudness range (LRA)

        Good dynamic range is typically 6-15 LU

        Args:
            lra: Loudness Range in LU

        Returns:
            Score 0-100
        """
        if 6 <= lra <= 15:
            return 100.0
        elif 4 <= lra < 6:
            return 70 + (lra - 4) * 30 / 2
        elif 15 < lra <= 20:
            return 70 + (20 - lra) * 30 / 5
        elif lra < 4:
            return max(0, lra * 70 / 4)  # Too compressed
        else:
            return max(0, 70 - (lra - 20) * 70 / 10)  # Too dynamic

    def _score_true_peak(self, true_peak: float) -> float:
        """
        Score true peak level

        Should be below -1 dBFS to prevent clipping in converters

        Args:
            true_peak: True peak level in dBFS

        Returns:
            Score 0-100
        """
        if true_peak <= -1:
            return 100.0
        elif true_peak <= 0:
            return 100 - (true_peak + 1) * 100  # Linear penalty
        else:
            return 0.0  # Over 0 dBFS = clipping

    def check_standards_compliance(self, loudness_result) -> Dict:
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

        compliance = {
            # Streaming platforms
            'spotify': self._check_spotify_compliance(integrated_lufs, true_peak),
            'apple_music': self._check_apple_music_compliance(integrated_lufs, true_peak),
            'youtube': self._check_youtube_compliance(integrated_lufs, true_peak),
            'tidal': self._check_tidal_compliance(integrated_lufs, true_peak),

            # Broadcast standards
            'ebu_r128': self._check_ebu_r128_compliance(integrated_lufs, loudness_range, true_peak),
            'atsc_a85': self._check_atsc_a85_compliance(integrated_lufs, true_peak),

            # General quality
            'mastering_quality': self._assess_mastering_quality(integrated_lufs, loudness_range, true_peak)
        }

        return compliance

    def _check_spotify_compliance(self, lufs: float, peak: float) -> Dict:
        """Check Spotify loudness recommendations"""
        compliant = (-16 <= lufs <= -14) and (peak <= -1)
        return {
            'compliant': compliant,
            'target_lufs': -14.0,
            'tolerance_lufs': 1.0,
            'max_true_peak': -1.0,
            'notes': 'Spotify normalizes to -14 LUFS'
        }

    def _check_apple_music_compliance(self, lufs: float, peak: float) -> Dict:
        """Check Apple Music loudness recommendations"""
        compliant = (-17 <= lufs <= -15) and (peak <= -1)
        return {
            'compliant': compliant,
            'target_lufs': -16.0,
            'tolerance_lufs': 1.0,
            'max_true_peak': -1.0,
            'notes': 'Apple Music normalizes to -16 LUFS'
        }

    def _check_youtube_compliance(self, lufs: float, peak: float) -> Dict:
        """Check YouTube loudness recommendations"""
        compliant = (-15 <= lufs <= -13) and (peak <= -1)
        return {
            'compliant': compliant,
            'target_lufs': -14.0,
            'tolerance_lufs': 1.0,
            'max_true_peak': -1.0,
            'notes': 'YouTube normalizes to -14 LUFS'
        }

    def _check_tidal_compliance(self, lufs: float, peak: float) -> Dict:
        """Check TIDAL loudness recommendations"""
        compliant = (-15 <= lufs <= -13) and (peak <= -1)
        return {
            'compliant': compliant,
            'target_lufs': -14.0,
            'tolerance_lufs': 1.0,
            'max_true_peak': -1.0,
            'notes': 'TIDAL normalizes to -14 LUFS'
        }

    def _check_ebu_r128_compliance(self, lufs: float, lra: float, peak: float) -> Dict:
        """Check EBU R128 broadcast standard compliance"""
        compliant = (-24 <= lufs <= -22) and (lra <= 15) and (peak <= -1)
        return {
            'compliant': compliant,
            'target_lufs': -23.0,
            'tolerance_lufs': 1.0,
            'max_lra': 15.0,
            'max_true_peak': -1.0,
            'notes': 'EBU R128 broadcast standard'
        }

    def _check_atsc_a85_compliance(self, lufs: float, peak: float) -> Dict:
        """Check ATSC A/85 broadcast standard compliance (US)"""
        compliant = (-25 <= lufs <= -23) and (peak <= -2)
        return {
            'compliant': compliant,
            'target_lufs': -24.0,
            'tolerance_lufs': 1.0,
            'max_true_peak': -2.0,
            'notes': 'ATSC A/85 US broadcast standard'
        }

    def _assess_mastering_quality(self, lufs: float, lra: float, peak: float) -> Dict:
        """Assess general mastering quality"""
        # High quality mastering typically has:
        # - Integrated LUFS: -12 to -16
        # - Loudness Range: 6-15 LU
        # - True Peak: < -1 dBFS

        quality_issues = []

        if lufs > -10:
            quality_issues.append("Too loud - may cause distortion")
        elif lufs < -18:
            quality_issues.append("Too quiet - may lack presence")

        if lra < 4:
            quality_issues.append("Over-compressed - limited dynamics")
        elif lra > 20:
            quality_issues.append("Excessive dynamic range - may need compression")

        if peak > -0.5:
            quality_issues.append("Peak level too high - risk of clipping")

        compliant = len(quality_issues) == 0

        return {
            'compliant': compliant,
            'quality_issues': quality_issues,
            'recommended_lufs_range': (-16, -12),
            'recommended_lra_range': (6, 15),
            'recommended_peak_max': -1.0
        }

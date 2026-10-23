"""
Assessment Constants
~~~~~~~~~~~~~~~~~~~

Target values and ranges for quality assessments.

Defines standards and thresholds used across all quality assessors
for consistent evaluation against industry standards.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

from typing import Any


class AssessmentConstants:
    """Target values and ranges for quality assessments"""

    # ========== LOUDNESS TARGETS ==========
    # ITU-R BS.1770-4 Loudness Descriptors

    TARGET_LOUDNESS_RANGE_LU = (7.0, 20.0)  # dB
    ACCEPTABLE_LOUDNESS_RANGE_LU = (4.0, 22.0)

    # Streaming platform standards
    SPOTIFY_TARGET_LUFS = -14.0
    SPOTIFY_TOLERANCE_LUFS = 1.0
    SPOTIFY_MAX_TRUE_PEAK = -1.0

    APPLE_MUSIC_TARGET_LUFS = -16.0
    APPLE_MUSIC_TOLERANCE_LUFS = 1.0
    APPLE_MUSIC_MAX_TRUE_PEAK = -1.0

    YOUTUBE_TARGET_LUFS = -14.0
    YOUTUBE_TOLERANCE_LUFS = 1.0
    YOUTUBE_MAX_TRUE_PEAK = -1.0

    TIDAL_TARGET_LUFS = -14.0
    TIDAL_TOLERANCE_LUFS = 1.0
    TIDAL_MAX_TRUE_PEAK = -1.0

    # Broadcast standards
    EBU_R128_TARGET_LUFS = -23.0
    EBU_R128_TOLERANCE_LUFS = 1.0
    EBU_R128_MAX_LOUDNESS_RANGE = 15.0
    EBU_R128_MAX_TRUE_PEAK = -1.0

    ATSC_A85_TARGET_LUFS = -24.0
    ATSC_A85_TOLERANCE_LUFS = 1.0
    ATSC_A85_MAX_TRUE_PEAK = -2.0

    # ========== DISTORTION LIMITS ==========

    ACCEPTABLE_THD = 0.05  # 5%
    ACCEPTABLE_CLIPPING_FACTOR = 0.0001  # 0.01% of samples

    # ========== NOISE LEVELS ==========

    ACCEPTABLE_NOISE_FLOOR = -60

    # ========== UTILITY METHODS ==========

    @classmethod
    def get_standard_compliance_targets(cls, standard: str) -> dict[str, Any]:
        """Get target values for a specific standard"""
        standards = {
            'spotify': {
                'target_lufs': cls.SPOTIFY_TARGET_LUFS,
                'tolerance': cls.SPOTIFY_TOLERANCE_LUFS,
                'max_true_peak': cls.SPOTIFY_MAX_TRUE_PEAK,
            },
            'apple_music': {
                'target_lufs': cls.APPLE_MUSIC_TARGET_LUFS,
                'tolerance': cls.APPLE_MUSIC_TOLERANCE_LUFS,
                'max_true_peak': cls.APPLE_MUSIC_MAX_TRUE_PEAK,
            },
            'youtube': {
                'target_lufs': cls.YOUTUBE_TARGET_LUFS,
                'tolerance': cls.YOUTUBE_TOLERANCE_LUFS,
                'max_true_peak': cls.YOUTUBE_MAX_TRUE_PEAK,
            },
            'tidal': {
                'target_lufs': cls.TIDAL_TARGET_LUFS,
                'tolerance': cls.TIDAL_TOLERANCE_LUFS,
                'max_true_peak': cls.TIDAL_MAX_TRUE_PEAK,
            },
            'ebu_r128': {
                'target_lufs': cls.EBU_R128_TARGET_LUFS,
                'tolerance': cls.EBU_R128_TOLERANCE_LUFS,
                'max_lra': cls.EBU_R128_MAX_LOUDNESS_RANGE,
                'max_true_peak': cls.EBU_R128_MAX_TRUE_PEAK,
            },
            'atsc_a85': {
                'target_lufs': cls.ATSC_A85_TARGET_LUFS,
                'tolerance': cls.ATSC_A85_TOLERANCE_LUFS,
                'max_true_peak': cls.ATSC_A85_MAX_TRUE_PEAK,
            },
        }
        return standards.get(standard.lower(), {})

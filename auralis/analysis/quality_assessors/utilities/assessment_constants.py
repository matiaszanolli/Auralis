# -*- coding: utf-8 -*-

"""
Assessment Constants
~~~~~~~~~~~~~~~~~~~

Target values and ranges for quality assessments.

Defines standards and thresholds used across all quality assessors
for consistent evaluation against industry standards.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Any, Dict


class AssessmentConstants:
    """Target values and ranges for quality assessments"""

    # ========== LOUDNESS TARGETS ==========
    # ITU-R BS.1770-4 Loudness Descriptors

    # Streaming platform targets
    TARGET_INTEGRATED_LUFS = -14.0
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

    # General mastering quality targets
    MASTERING_TARGET_LUFS_RANGE = (-16.0, -12.0)
    MASTERING_TARGET_LRA_RANGE = (6.0, 15.0)
    MASTERING_TARGET_PEAK_MAX = -1.0

    # ========== DYNAMIC RANGE TARGETS ==========

    TARGET_DR_VALUE = 14  # dB
    MINIMUM_DR_VALUE = 6
    EXCELLENT_DR_VALUE = 18
    MAXIMUM_ACCEPTABLE_DR = 25

    # ========== STEREO CORRELATION TARGETS ==========

    TARGET_CORRELATION = 0.7
    EXCELLENT_CORRELATION = 0.85
    ACCEPTABLE_CORRELATION = 0.5
    MINIMUM_CORRELATION = -0.3  # Severe phase issues below this

    # Stereo width targets
    TARGET_STEREO_WIDTH = 0.5
    EXCELLENT_STEREO_WIDTH = (0.3, 0.8)
    MINIMUM_STEREO_WIDTH = 0.2
    MAXIMUM_STEREO_WIDTH = 0.9

    # Mono compatibility
    TARGET_MONO_COMPATIBILITY = 0.95
    ACCEPTABLE_MONO_COMPATIBILITY = 0.8
    POOR_MONO_COMPATIBILITY = 0.5

    # ========== FREQUENCY RESPONSE TARGETS ==========

    # Frequency balance targets (dB)
    ACCEPTABLE_FREQUENCY_BALANCE = (-3.0, 3.0)
    EXCELLENT_FREQUENCY_BALANCE = (-1.0, 1.0)

    # Critical bands for frequency assessment
    BASS_BAND_RANGE = (20, 250)  # Hz
    MIDS_BAND_RANGE = (250, 2000)  # Hz
    TREBLE_BAND_RANGE = (2000, 20000)  # Hz

    # Bass/Treble threshold
    EXCESSIVE_BASS_THRESHOLD = 6.0  # dB above reference
    EXCESSIVE_TREBLE_THRESHOLD = 6.0  # dB above reference

    # ========== DISTORTION LIMITS ==========

    ACCEPTABLE_THD = 0.05  # 5%
    EXCELLENT_THD = 0.01  # 1%
    CRITICAL_THD = 0.10  # 10% (severe)

    CLIPPING_THRESHOLD = 0.98  # Normalized amplitude
    ACCEPTABLE_CLIPPING_FACTOR = 0.0001  # 0.01% of samples
    CRITICAL_CLIPPING_FACTOR = 0.001  # 0.1% of samples

    # ========== NOISE LEVELS ==========

    EXCELLENT_SNR_DB = 90
    GOOD_SNR_DB = 70
    ACCEPTABLE_SNR_DB = 60
    POOR_SNR_DB = 40

    EXCELLENT_NOISE_FLOOR = -90
    ACCEPTABLE_NOISE_FLOOR = -60
    POOR_NOISE_FLOOR = -40

    # ========== ANALYSIS PARAMETERS ==========

    # Frame-based analysis
    DEFAULT_FRAME_DURATION = 0.05  # 50 ms
    DEFAULT_HOP_DURATION = 0.025  # 25 ms (50% overlap)

    # FFT parameters
    DEFAULT_FFT_SIZE = 2048
    DEFAULT_FFT_WINDOW = 'hann'

    # Frequency band resolution
    DEFAULT_NUM_BANDS = 10  # Number of frequency bands for analysis
    MIN_FREQUENCY = 20  # Hz
    MAX_FREQUENCY = 20000  # Hz

    # ========== WEIGHTING CURVES ==========

    # A-weighting curve (ISO 61672-1)
    # Simulated at key frequencies
    A_WEIGHTING_FREQUENCIES = [
        31.5, 63, 125, 250, 500, 1000, 2000, 4000, 8000, 16000
    ]
    A_WEIGHTING_DB = [
        -39.4, -26.2, -16.1, -8.6, -3.2, 0.0, 1.2, 1.0, -1.1, -6.6
    ]

    # C-weighting curve (ISO 61672-1)
    C_WEIGHTING_FREQUENCIES = [
        31.5, 63, 125, 250, 500, 1000, 2000, 4000, 8000, 16000
    ]
    C_WEIGHTING_DB = [
        -3.0, -0.8, 0.0, 0.0, 0.0, 0.0, -0.2, -0.8, -3.4, -8.5
    ]

    # ========== UTILITY METHODS ==========

    @classmethod
    def get_standard_compliance_targets(cls, standard: str) -> Dict[str, Any]:
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

    @classmethod
    def is_compliant_with_standard(cls, standard: str, **kwargs: Any) -> bool:
        """Check if values meet standard compliance"""
        targets = cls.get_standard_compliance_targets(standard)
        if not targets:
            return False

        # Default check: required keys present
        return all(key in targets for key in kwargs.keys())

"""
Realtime EQ Settings
~~~~~~~~~~~~~~~~~~~~

Configuration for real-time adaptive EQ processing

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from dataclasses import dataclass


@dataclass
class RealtimeEQSettings:
    """
    Configuration for real-time adaptive EQ processing

    Attributes:
        sample_rate: Audio sample rate in Hz
        buffer_size: Processing buffer size in samples
        adaptation_rate: Speed of adaptation (0.0-1.0, higher = faster)
        target_latency_ms: Target processing latency in milliseconds
        enable_look_ahead: Enable look-ahead processing for better quality
        min_analysis_frames: Minimum frames for reliable analysis
        smoothing_time_constant: Time constant for gain smoothing (seconds)
    """
    sample_rate: int = 44100
    buffer_size: int = 1024
    adaptation_rate: float = 0.1
    target_latency_ms: float = 20.0
    enable_look_ahead: bool = True
    min_analysis_frames: int = 4
    smoothing_time_constant: float = 0.05

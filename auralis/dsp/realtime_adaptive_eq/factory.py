# -*- coding: utf-8 -*-

"""
Realtime EQ Factory
~~~~~~~~~~~~~~~~~~~

Factory function for creating real-time adaptive EQ instances

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from .realtime_eq import RealtimeAdaptiveEQ
from .settings import RealtimeEQSettings


def create_realtime_adaptive_eq(
    sample_rate: int = 44100,
    buffer_size: int = 1024,
    target_latency_ms: float = 20.0,
    adaptation_rate: float = 0.1
) -> RealtimeAdaptiveEQ:
    """
    Factory function to create real-time adaptive EQ

    Args:
        sample_rate: Audio sample rate
        buffer_size: Processing buffer size
        target_latency_ms: Target processing latency
        adaptation_rate: Rate of EQ adaptation

    Returns:
        Configured RealtimeAdaptiveEQ instance
    """

    settings = RealtimeEQSettings(
        sample_rate=sample_rate,
        buffer_size=buffer_size,
        target_latency_ms=target_latency_ms,
        adaptation_rate=adaptation_rate
    )

    return RealtimeAdaptiveEQ(settings)

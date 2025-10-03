# -*- coding: utf-8 -*-

"""
Real-time EQ Manager
~~~~~~~~~~~~~~~~~~~

Manages real-time adaptive EQ parameters and state

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from typing import Dict, Any
from ...dsp.realtime_adaptive_eq import RealtimeAdaptiveEQ
from ...utils.logging import info


class RealtimeEQManager:
    """Manages real-time EQ operations for HybridProcessor"""

    def __init__(self, realtime_eq: RealtimeAdaptiveEQ):
        self.realtime_eq = realtime_eq

    def get_info(self) -> Dict[str, Any]:
        """Get real-time EQ status and performance information"""
        eq_curve = self.realtime_eq.get_current_eq_curve()
        performance = self.realtime_eq.get_performance_stats()

        return {
            "eq_curve": eq_curve,
            "performance": performance,
            "buffer_size": self.realtime_eq.settings.buffer_size,
            "target_latency_ms": self.realtime_eq.settings.target_latency_ms,
            "actual_latency_ms": performance.get("total_latency_ms", 0),
            "adaptation_rate": self.realtime_eq.settings.adaptation_rate
        }

    def set_parameters(self, **kwargs):
        """Update real-time EQ parameters dynamically"""
        self.realtime_eq.set_adaptation_parameters(**kwargs)
        info(f"Updated real-time EQ parameters: {kwargs}")

    def reset(self):
        """Reset real-time EQ state"""
        self.realtime_eq.reset()
        info("Real-time EQ state reset")

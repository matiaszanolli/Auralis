# -*- coding: utf-8 -*-

"""
Performance Monitor
~~~~~~~~~~~~~~~~~~

Monitors processing performance and adapts quality

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
from typing import Dict, Any
from ...utils.logging import warning, info


class PerformanceMonitor:
    """Monitors processing performance and adapts quality"""

    def __init__(self, max_cpu_usage: float = 0.8):
        self.max_cpu_usage = max_cpu_usage
        self.processing_times = []
        self.max_history = 100
        self.performance_mode = False
        self.consecutive_overruns = 0
        self.chunks_processed = 0

    def record_processing_time(self, processing_time: float, chunk_duration: float) -> None:
        """Record processing time for a chunk"""
        self.chunks_processed += 1
        cpu_usage = processing_time / chunk_duration if chunk_duration > 0 else 0.0
        self.processing_times.append(cpu_usage)

        if len(self.processing_times) > self.max_history:
            self.processing_times.pop(0)

        # Check for performance issues
        if cpu_usage > self.max_cpu_usage:
            self.consecutive_overruns += 1
        else:
            self.consecutive_overruns = max(0, self.consecutive_overruns - 1)

        # Enter performance mode if we have sustained overruns
        if self.consecutive_overruns >= 5:
            if not self.performance_mode:
                self.performance_mode = True
                warning("Entering performance mode due to high CPU usage")
        elif self.consecutive_overruns == 0 and self.performance_mode:
            recent_avg = np.mean(self.processing_times[-20:]) if len(self.processing_times) >= 20 else cpu_usage
            if recent_avg < self.max_cpu_usage * 0.6:
                self.performance_mode = False
                info("Exiting performance mode - CPU usage stable")

    def get_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        if not self.processing_times:
            return {
                'cpu_usage': 0.0,
                'performance_mode': False,
                'status': 'initializing',
                'chunks_processed': self.chunks_processed
            }

        recent_usage = np.mean(self.processing_times[-10:]) if len(self.processing_times) >= 10 else 0.0

        # Determine status
        status = 'optimal'
        if recent_usage > self.max_cpu_usage * 0.8:
            status = 'high_load'
        elif self.performance_mode:
            status = 'performance_mode'
        elif recent_usage > self.max_cpu_usage * 0.6:
            status = 'moderate_load'

        return {
            'cpu_usage': recent_usage,
            'avg_cpu_usage': np.mean(self.processing_times),
            'max_cpu_usage': np.max(self.processing_times),
            'performance_mode': self.performance_mode,
            'consecutive_overruns': self.consecutive_overruns,
            'chunks_processed': self.chunks_processed,
            'status': status,
        }

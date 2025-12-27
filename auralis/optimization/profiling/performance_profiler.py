# -*- coding: utf-8 -*-

"""
Performance Profiler
~~~~~~~~~~~~~~~~~~~~

Performance profiling and monitoring for audio processing.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import threading
import time
from collections import defaultdict, deque
from functools import wraps
from typing import Any, Callable, Dict, List

import numpy as np


class PerformanceProfiler:
    """Performance profiling and monitoring"""

    def __init__(self) -> None:
        self.timings: Dict[str, List[float]] = defaultdict(list)
        self.counters: Dict[str, int] = defaultdict(int)
        self.memory_usage: deque[float] = deque(maxlen=1000)
        self.lock = threading.RLock()

    def time_function(self, func_name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Decorator for timing function execution"""
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            @wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                start_time = time.perf_counter()
                try:
                    result = func(*args, **kwargs)
                    return result
                finally:
                    end_time = time.perf_counter()
                    execution_time = (end_time - start_time) * 1000  # ms

                    with self.lock:
                        self.timings[func_name].append(execution_time)
                        self.counters[f"{func_name}_calls"] += 1

                        # Keep only recent timings
                        if len(self.timings[func_name]) > 1000:
                            self.timings[func_name] = self.timings[func_name][-500:]

            return wrapper
        return decorator

    def get_performance_report(self) -> Dict[str, Any]:
        """Generate performance report"""
        with self.lock:
            report = {}

            for func_name, times in self.timings.items():
                if times:
                    report[func_name] = {
                        'avg_time_ms': np.mean(times),
                        'min_time_ms': np.min(times),
                        'max_time_ms': np.max(times),
                        'std_time_ms': np.std(times),
                        'total_calls': len(times),
                        'total_time_ms': np.sum(times)
                    }

            return report

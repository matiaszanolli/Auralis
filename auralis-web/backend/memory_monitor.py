"""
Memory Pressure Monitoring and Degradation Management
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Monitors system memory and adjusts cache sizes for graceful degradation.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import psutil
import logging
import time
from typing import Tuple, Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class MemoryStatus:
    """Current memory status."""
    total_mb: float
    available_mb: float
    used_mb: float
    used_percent: float
    status: str  # "normal", "warning", "critical"
    timestamp: float


class MemoryPressureMonitor:
    """
    Monitors system memory and determines appropriate cache sizing.

    Uses psutil to track memory usage and recommends cache sizes
    based on available memory.
    """

    def __init__(
        self,
        warning_threshold: float = 0.75,
        critical_threshold: float = 0.85
    ):
        """
        Initialize memory monitor.

        Args:
            warning_threshold: Memory usage % to trigger warning (0.0-1.0)
            critical_threshold: Memory usage % to trigger critical (0.0-1.0)
        """
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold

        # Cache sizes for each status level (in MB)
        self.cache_sizes = {
            "normal": (18.0, 36.0, 45.0),    # Full caching (99MB)
            "warning": (12.0, 18.0, 0.0),    # Reduced caching (30MB)
            "critical": (9.0, 0.0, 0.0)       # Minimal caching (9MB)
        }

        # Track memory status history
        self.status_history = []
        self.last_check_time = 0.0

        logger.info(
            f"Memory monitor initialized: "
            f"warning={warning_threshold:.0%}, critical={critical_threshold:.0%}"
        )

    def get_memory_status(self) -> MemoryStatus:
        """Get current memory status."""
        memory = psutil.virtual_memory()

        total_mb = memory.total / (1024 * 1024)
        available_mb = memory.available / (1024 * 1024)
        used_mb = memory.used / (1024 * 1024)
        used_percent = memory.percent / 100.0

        # Determine status
        if used_percent >= self.critical_threshold:
            status = "critical"
        elif used_percent >= self.warning_threshold:
            status = "warning"
        else:
            status = "normal"

        return MemoryStatus(
            total_mb=total_mb,
            available_mb=available_mb,
            used_mb=used_mb,
            used_percent=used_percent,
            status=status,
            timestamp=time.time()
        )

    def get_recommended_cache_sizes(self) -> Tuple[float, float, float]:
        """
        Get recommended cache sizes based on current memory status.

        Returns:
            Tuple of (L1_size_mb, L2_size_mb, L3_size_mb)
        """
        status = self.get_memory_status()

        sizes = self.cache_sizes[status.status]

        # Log if status changed
        if not self.status_history or self.status_history[-1].status != status.status:
            logger.info(
                f"Memory status changed to {status.status}: "
                f"{status.used_percent:.1%} used, "
                f"cache sizes: L1={sizes[0]}MB, L2={sizes[1]}MB, L3={sizes[2]}MB"
            )

        # Record status
        self.status_history.append(status)
        if len(self.status_history) > 100:
            self.status_history.pop(0)

        self.last_check_time = time.time()

        return sizes

    def should_check_memory(self, check_interval: float = 30.0) -> bool:
        """
        Determine if it's time to check memory again.

        Args:
            check_interval: Minimum seconds between checks

        Returns:
            True if enough time has passed since last check
        """
        return (time.time() - self.last_check_time) >= check_interval

    def get_statistics(self) -> Dict:
        """Get memory monitoring statistics."""
        if not self.status_history:
            current = self.get_memory_status()
            return {
                "current_status": current.status,
                "used_percent": current.used_percent,
                "available_mb": current.available_mb,
                "history_count": 0
            }

        recent = self.status_history[-1]
        return {
            "current_status": recent.status,
            "used_percent": recent.used_percent,
            "available_mb": recent.available_mb,
            "total_mb": recent.total_mb,
            "history_count": len(self.status_history),
            "status_distribution": {
                "normal": sum(1 for s in self.status_history if s.status == "normal"),
                "warning": sum(1 for s in self.status_history if s.status == "warning"),
                "critical": sum(1 for s in self.status_history if s.status == "critical")
            }
        }


class DegradationManager:
    """
    Manages graceful degradation of buffer system under resource constraints.

    Implements 4 degradation levels:
    - Level 0 (Normal): Full caching (L1+L2+L3)
    - Level 1 (Warning): Reduced caching (L1+L2)
    - Level 2 (Critical): Minimal caching (L1 only)
    - Level 3 (Emergency): Disable background worker
    """

    def __init__(self, memory_monitor: MemoryPressureMonitor):
        """
        Initialize degradation manager.

        Args:
            memory_monitor: MemoryPressureMonitor instance
        """
        self.memory_monitor = memory_monitor
        self.current_level = 0
        self.degradation_history = []

        # Track if worker is causing latency
        self.worker_latency_samples = []
        self.latency_threshold_ms = 100.0  # 100ms threshold

        logger.info("Degradation manager initialized at level 0 (normal)")

    def get_degradation_level(self) -> int:
        """
        Determine appropriate degradation level (0-3).

        Returns:
            Degradation level (0=normal, 1=warning, 2=critical, 3=emergency)
        """
        status = self.memory_monitor.get_memory_status()

        if status.status == "critical":
            # Check if worker is causing latency issues
            if self._is_worker_causing_latency():
                return 3  # Emergency: disable worker
            else:
                return 2  # Critical: L1 only

        elif status.status == "warning":
            return 1  # Warning: L1+L2

        else:
            return 0  # Normal: full caching

    def _is_worker_causing_latency(self) -> bool:
        """Check if worker is causing playback latency issues."""
        if len(self.worker_latency_samples) < 10:
            return False  # Need more data

        # Check if average latency exceeds threshold
        avg_latency = sum(self.worker_latency_samples[-10:]) / 10
        return avg_latency > self.latency_threshold_ms

    def record_worker_latency(self, latency_ms: float):
        """Record worker processing latency."""
        self.worker_latency_samples.append(latency_ms)
        if len(self.worker_latency_samples) > 100:
            self.worker_latency_samples.pop(0)

    async def apply_degradation(self, level: int, buffer_manager, worker):
        """
        Apply degradation strategy to buffer system.

        Args:
            level: Degradation level (0-3)
            buffer_manager: MultiTierBufferManager instance
            worker: MultiTierBufferWorker instance
        """
        if level == self.current_level:
            return  # No change needed

        logger.info(f"Applying degradation level {level} (was {self.current_level})")

        old_level = self.current_level
        self.current_level = level

        # Record degradation event
        self.degradation_history.append({
            "timestamp": time.time(),
            "old_level": old_level,
            "new_level": level,
            "memory_status": self.memory_monitor.get_memory_status()
        })

        if level == 0:
            # Normal operation: full caching
            await worker.resume()
            buffer_manager.l1_cache.max_size_mb = 18.0
            buffer_manager.l2_cache.max_size_mb = 36.0
            buffer_manager.l3_cache.max_size_mb = 45.0
            logger.info("Degradation level 0: Full caching enabled")

        elif level == 1:
            # Warning: reduced caching (L1+L2)
            await worker.resume()
            buffer_manager.l1_cache.max_size_mb = 12.0
            buffer_manager.l2_cache.max_size_mb = 18.0
            buffer_manager.l3_cache.max_size_mb = 0.0
            await buffer_manager.l3_cache.clear()
            logger.info("Degradation level 1: Reduced caching (L1+L2)")

        elif level == 2:
            # Critical: minimal caching (L1 only)
            await worker.resume()
            buffer_manager.l1_cache.max_size_mb = 9.0
            buffer_manager.l2_cache.max_size_mb = 0.0
            buffer_manager.l3_cache.max_size_mb = 0.0
            await buffer_manager.l2_cache.clear()
            await buffer_manager.l3_cache.clear()
            logger.info("Degradation level 2: Minimal caching (L1 only)")

        elif level == 3:
            # Emergency: disable worker
            await worker.pause()
            buffer_manager.l1_cache.max_size_mb = 6.0
            buffer_manager.l2_cache.max_size_mb = 0.0
            buffer_manager.l3_cache.max_size_mb = 0.0
            await buffer_manager.l2_cache.clear()
            await buffer_manager.l3_cache.clear()
            logger.warning("Degradation level 3: Worker paused due to latency")

    def get_statistics(self) -> Dict:
        """Get degradation statistics."""
        return {
            "current_level": self.current_level,
            "level_name": [
                "Normal (L1+L2+L3)",
                "Warning (L1+L2)",
                "Critical (L1 only)",
                "Emergency (worker paused)"
            ][self.current_level],
            "degradation_event_count": len(self.degradation_history),
            "recent_events": self.degradation_history[-5:],  # Last 5 events
            "worker_latency_avg_ms": (
                sum(self.worker_latency_samples[-10:]) / len(self.worker_latency_samples[-10:])
                if self.worker_latency_samples
                else 0.0
            )
        }


# Singleton instances
_memory_monitor_instance: Optional[MemoryPressureMonitor] = None
_degradation_manager_instance: Optional[DegradationManager] = None


def get_memory_monitor() -> MemoryPressureMonitor:
    """Get global memory monitor instance."""
    global _memory_monitor_instance
    if _memory_monitor_instance is None:
        _memory_monitor_instance = MemoryPressureMonitor()
    return _memory_monitor_instance


def get_degradation_manager() -> DegradationManager:
    """Get global degradation manager instance."""
    global _degradation_manager_instance
    if _degradation_manager_instance is None:
        _degradation_manager_instance = DegradationManager(get_memory_monitor())
    return _degradation_manager_instance

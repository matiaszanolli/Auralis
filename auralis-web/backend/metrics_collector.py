"""
Performance Metrics Collection and Health Monitoring
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Collects and aggregates performance metrics for the multi-tier buffer system.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import time
import logging
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Deque
from collections import deque

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Snapshot of system performance metrics."""

    # Timestamp
    timestamp: float

    # Cache metrics
    l1_hit_rate: float
    l2_hit_rate: float
    l3_hit_rate: float
    overall_hit_rate: float
    l1_size_mb: float
    l2_size_mb: float
    l3_size_mb: float

    # Prediction metrics
    prediction_accuracy: float
    user_only_accuracy: float
    audio_enhanced_accuracy: float
    total_predictions: int

    # Memory metrics
    memory_usage_mb: float
    memory_usage_percent: float
    degradation_level: int

    # Performance metrics
    avg_switch_latency_ms: float
    instant_switches_percent: float

    # Worker metrics
    worker_queue_size: int
    worker_processing_rate: float
    worker_idle_percent: float
    worker_is_running: bool

    # Weights
    current_user_weight: float
    current_audio_weight: float


class MetricsCollector:
    """
    Collects and aggregates performance metrics from the multi-tier buffer system.

    Maintains a rolling window of metrics for historical analysis.
    """

    def __init__(self, history_size: int = 1000):
        """
        Initialize metrics collector.

        Args:
            history_size: Number of metrics snapshots to keep in history
        """
        self.metrics_history: Deque[PerformanceMetrics] = deque(maxlen=history_size)
        self.collection_count = 0

        # References to system components (set externally)
        self.buffer_manager = None
        self.worker = None
        self.learning_system = None
        self.weight_tuner = None
        self.memory_monitor = None
        self.degradation_manager = None

        logger.info(f"Metrics collector initialized (history_size={history_size})")

    def set_components(
        self,
        buffer_manager,
        worker,
        learning_system,
        weight_tuner,
        memory_monitor,
        degradation_manager
    ):
        """Set references to system components."""
        self.buffer_manager = buffer_manager
        self.worker = worker
        self.learning_system = learning_system
        self.weight_tuner = weight_tuner
        self.memory_monitor = memory_monitor
        self.degradation_manager = degradation_manager

    def collect_current_metrics(self) -> PerformanceMetrics:
        """
        Collect current performance metrics from all system components.

        Returns:
            PerformanceMetrics snapshot
        """
        if not self.buffer_manager:
            raise RuntimeError("Components not set. Call set_components() first.")

        # Get cache statistics
        cache_stats = self.buffer_manager.get_cache_stats()

        # Calculate hit rates
        l1_hit_rate = self._calculate_hit_rate(cache_stats['l1'])
        l2_hit_rate = self._calculate_hit_rate(cache_stats['l2'])
        l3_hit_rate = self._calculate_hit_rate(cache_stats['l3'])
        overall_hit_rate = self._calculate_overall_hit_rate(cache_stats)

        # Get learning statistics
        learning_stats = self.learning_system.get_statistics()

        # Get weight tuner weights
        user_weight, audio_weight = self.weight_tuner.get_weights()

        # Get memory status
        memory_status = self.memory_monitor.get_memory_status()

        # Get degradation level
        degradation_level = self.degradation_manager.current_level

        # Get worker stats
        worker_stats = self._get_worker_stats()

        # Create metrics snapshot
        metrics = PerformanceMetrics(
            timestamp=time.time(),

            # Cache metrics
            l1_hit_rate=l1_hit_rate,
            l2_hit_rate=l2_hit_rate,
            l3_hit_rate=l3_hit_rate,
            overall_hit_rate=overall_hit_rate,
            l1_size_mb=cache_stats['l1']['size_mb'],
            l2_size_mb=cache_stats['l2']['size_mb'],
            l3_size_mb=cache_stats['l3']['size_mb'],

            # Prediction metrics
            prediction_accuracy=learning_stats['overall_accuracy'],
            user_only_accuracy=learning_stats['user_only_accuracy'],
            audio_enhanced_accuracy=learning_stats['audio_enhanced_accuracy'],
            total_predictions=learning_stats['total_predictions'],

            # Memory metrics
            memory_usage_mb=memory_status.used_mb,
            memory_usage_percent=memory_status.used_percent,
            degradation_level=degradation_level,

            # Performance metrics
            avg_switch_latency_ms=self._estimate_avg_switch_latency(l1_hit_rate, l2_hit_rate, l3_hit_rate),
            instant_switches_percent=l1_hit_rate,

            # Worker metrics
            worker_queue_size=worker_stats['queue_size'],
            worker_processing_rate=worker_stats['processing_rate'],
            worker_idle_percent=worker_stats['idle_percent'],
            worker_is_running=worker_stats['is_running'],

            # Weights
            current_user_weight=user_weight,
            current_audio_weight=audio_weight
        )

        # Add to history
        self.metrics_history.append(metrics)
        self.collection_count += 1

        return metrics

    def _calculate_hit_rate(self, cache_stats: Dict) -> float:
        """Calculate hit rate for a cache tier."""
        hits = cache_stats.get('hits', 0)
        misses = cache_stats.get('misses', 0)
        total = hits + misses

        if total == 0:
            return 0.0

        return hits / total

    def _calculate_overall_hit_rate(self, cache_stats: Dict) -> float:
        """Calculate overall hit rate across all tiers."""
        total_hits = sum(
            cache_stats[tier].get('hits', 0)
            for tier in ['l1', 'l2', 'l3']
        )
        total_requests = sum(
            cache_stats[tier].get('hits', 0) + cache_stats[tier].get('misses', 0)
            for tier in ['l1', 'l2', 'l3']
        )

        if total_requests == 0:
            return 0.0

        return total_hits / total_requests

    def _estimate_avg_switch_latency(
        self,
        l1_hit_rate: float,
        l2_hit_rate: float,
        l3_hit_rate: float
    ) -> float:
        """
        Estimate average switch latency based on hit rates.

        Assumptions:
        - L1 hit: 0ms (instant)
        - L2 hit: 5ms (load from cache)
        - L3 hit: 10ms (load from disk)
        - Miss: 2000ms (full processing)
        """
        l1_latency = 0.0
        l2_latency = 5.0
        l3_latency = 10.0
        miss_latency = 2000.0

        # Calculate miss rate
        miss_rate = 1.0 - (l1_hit_rate + l2_hit_rate + l3_hit_rate)
        miss_rate = max(0.0, miss_rate)  # Clamp to 0

        # Weighted average
        avg_latency = (
            l1_hit_rate * l1_latency +
            l2_hit_rate * l2_latency +
            l3_hit_rate * l3_latency +
            miss_rate * miss_latency
        )

        return avg_latency

    def _get_worker_stats(self) -> Dict:
        """Get worker statistics.

        Collects metrics about cache building worker:
        - queue_size: Remaining chunks to process for current track
        - processing_rate: Estimated chunks per second
        - idle_percent: Percentage of time idle vs processing
        - is_running: Whether worker is actively running
        """
        if not self.worker:
            return {
                'queue_size': 0,
                'processing_rate': 0.0,
                'idle_percent': 0.0,
                'is_running': False
            }

        is_running = getattr(self.worker, 'running', False)

        if not is_running:
            return {
                'queue_size': 0,
                'processing_rate': 0.0,
                'idle_percent': 100.0,  # Fully idle when not running
                'is_running': False
            }

        # Calculate queue size and processing metrics
        queue_size = 0
        processing_rate = 0.5  # Default: conservative estimate
        idle_percent = 50.0    # Default: assume partial idle time

        try:
            # Get current track being processed from worker state
            building_track_id = getattr(self.worker, '_building_track_id', None)
            cache_manager = getattr(self.worker, 'cache_manager', None)

            if building_track_id and cache_manager:
                # Try to get track cache status from cache manager
                track_status = getattr(cache_manager, 'track_status', {}).get(building_track_id)

                if track_status:
                    # Calculate remaining chunks to process
                    # Queue size = total chunks - chunks already cached (processed)
                    total_chunks = track_status.total_chunks
                    cached_chunks = len(track_status.cached_chunks_processed)
                    queue_size = max(0, total_chunks - cached_chunks)

                    # Estimate processing rate based on queue
                    # Worker processes ~1 chunk per iteration with 1s check interval
                    # Actual processing varies: 2-10s per chunk depending on tier
                    # Conservative estimate: 0.5 chunks/second
                    processing_rate = 0.5

                    # Idle percentage based on queue
                    # If significant queue, worker is actively processing (0% idle)
                    # If queue is empty, worker is waiting for next task (higher idle)
                    if queue_size > 5:
                        idle_percent = 0.0   # Heavy backlog, fully active
                    elif queue_size > 0:
                        idle_percent = 25.0  # Some queue, mostly active
                    else:
                        idle_percent = 75.0  # Queue empty, mostly idle

        except (AttributeError, TypeError, KeyError) as e:
            # Use defaults if cache manager structure is different
            logger.debug(f"Could not access worker cache metrics: {e}")

        return {
            'queue_size': queue_size,
            'processing_rate': processing_rate,
            'idle_percent': idle_percent,
            'is_running': is_running
        }

    def get_recent_metrics(self, count: int = 100) -> List[Dict]:
        """Get N most recent metrics snapshots as dicts."""
        recent = list(self.metrics_history)[-count:]
        return [asdict(m) for m in recent]

    def get_summary_statistics(self) -> Dict:
        """Get summary statistics across all collected metrics."""
        if not self.metrics_history:
            return {"error": "No metrics collected yet"}

        recent = list(self.metrics_history)[-100:]  # Last 100 samples

        return {
            "collection_count": self.collection_count,
            "history_size": len(self.metrics_history),

            # Average metrics
            "avg_l1_hit_rate": sum(m.l1_hit_rate for m in recent) / len(recent),
            "avg_l2_hit_rate": sum(m.l2_hit_rate for m in recent) / len(recent),
            "avg_l3_hit_rate": sum(m.l3_hit_rate for m in recent) / len(recent),
            "avg_overall_hit_rate": sum(m.overall_hit_rate for m in recent) / len(recent),

            "avg_prediction_accuracy": sum(m.prediction_accuracy for m in recent) / len(recent),
            "avg_user_only_accuracy": sum(m.user_only_accuracy for m in recent) / len(recent),
            "avg_audio_enhanced_accuracy": sum(m.audio_enhanced_accuracy for m in recent) / len(recent),

            "avg_memory_usage_percent": sum(m.memory_usage_percent for m in recent) / len(recent),
            "avg_switch_latency_ms": sum(m.avg_switch_latency_ms for m in recent) / len(recent),

            # Current values
            "current_user_weight": recent[-1].current_user_weight,
            "current_audio_weight": recent[-1].current_audio_weight,
            "current_degradation_level": recent[-1].degradation_level,

            # Totals
            "total_predictions": recent[-1].total_predictions
        }


class HealthChecker:
    """
    Performs health checks on the multi-tier buffer system.

    Checks cache health, prediction health, memory health, and worker health.
    """

    def __init__(
        self,
        buffer_manager,
        learning_system,
        memory_monitor,
        degradation_manager,
        worker=None
    ):
        """
        Initialize health checker.

        Args:
            buffer_manager: MultiTierBufferManager instance
            learning_system: LearningSystem instance
            memory_monitor: MemoryPressureMonitor instance
            degradation_manager: DegradationManager instance
            worker: MultiTierBufferWorker instance (optional)
        """
        self.buffer_manager = buffer_manager
        self.learning_system = learning_system
        self.memory_monitor = memory_monitor
        self.degradation_manager = degradation_manager
        self.worker = worker

    def check_health(self) -> Dict:
        """
        Perform comprehensive health check.

        Returns:
            Dict with overall status and individual check results
        """
        checks = {
            "cache_health": self._check_cache_health(),
            "prediction_health": self._check_prediction_health(),
            "memory_health": self._check_memory_health(),
            "worker_health": self._check_worker_health()
        }

        # Determine overall status
        overall_status = "healthy"
        if any(check["status"] == "critical" for check in checks.values()):
            overall_status = "critical"
        elif any(check["status"] == "warning" for check in checks.values()):
            overall_status = "warning"

        return {
            "overall_status": overall_status,
            "checks": checks,
            "timestamp": time.time()
        }

    def _check_cache_health(self) -> Dict:
        """Check cache system health."""
        cache_stats = self.buffer_manager.get_cache_stats()

        # Calculate L1 hit rate
        l1_hits = cache_stats['l1'].get('hits', 0)
        l1_misses = cache_stats['l1'].get('misses', 0)
        l1_total = l1_hits + l1_misses

        if l1_total == 0:
            l1_hit_rate = 0.0
        else:
            l1_hit_rate = l1_hits / l1_total

        # Determine status based on L1 hit rate
        if l1_hit_rate < 0.5:  # Below 50%
            return {
                "status": "critical",
                "message": f"L1 hit rate critical: {l1_hit_rate:.1%}",
                "l1_hit_rate": l1_hit_rate,
                "l1_size_mb": cache_stats['l1']['size_mb'],
                "l1_entries": cache_stats['l1']['entries']
            }
        elif l1_hit_rate < 0.7:  # Below 70%
            return {
                "status": "warning",
                "message": f"L1 hit rate low: {l1_hit_rate:.1%}",
                "l1_hit_rate": l1_hit_rate,
                "l1_size_mb": cache_stats['l1']['size_mb'],
                "l1_entries": cache_stats['l1']['entries']
            }
        else:
            return {
                "status": "healthy",
                "message": f"L1 hit rate: {l1_hit_rate:.1%}",
                "l1_hit_rate": l1_hit_rate,
                "l1_size_mb": cache_stats['l1']['size_mb'],
                "l1_entries": cache_stats['l1']['entries']
            }

    def _check_prediction_health(self) -> Dict:
        """Check prediction system health."""
        stats = self.learning_system.get_statistics()
        accuracy = stats['overall_accuracy']

        if stats['total_predictions'] < 10:
            return {
                "status": "healthy",
                "message": "Insufficient predictions for health check",
                "total_predictions": stats['total_predictions']
            }

        if accuracy < 0.3:  # Below 30%
            return {
                "status": "critical",
                "message": f"Prediction accuracy critical: {accuracy:.1%}",
                "accuracy": accuracy,
                "total_predictions": stats['total_predictions']
            }
        elif accuracy < 0.5:  # Below 50%
            return {
                "status": "warning",
                "message": f"Prediction accuracy low: {accuracy:.1%}",
                "accuracy": accuracy,
                "total_predictions": stats['total_predictions']
            }
        else:
            return {
                "status": "healthy",
                "message": f"Prediction accuracy: {accuracy:.1%}",
                "accuracy": accuracy,
                "total_predictions": stats['total_predictions']
            }

    def _check_memory_health(self) -> Dict:
        """Check memory system health."""
        memory_status = self.memory_monitor.get_memory_status()

        if memory_status.status == "critical":
            return {
                "status": "critical",
                "message": f"Memory usage critical: {memory_status.used_percent:.1%}",
                "used_percent": memory_status.used_percent,
                "available_mb": memory_status.available_mb,
                "degradation_level": self.degradation_manager.current_level
            }
        elif memory_status.status == "warning":
            return {
                "status": "warning",
                "message": f"Memory usage high: {memory_status.used_percent:.1%}",
                "used_percent": memory_status.used_percent,
                "available_mb": memory_status.available_mb,
                "degradation_level": self.degradation_manager.current_level
            }
        else:
            return {
                "status": "healthy",
                "message": f"Memory usage: {memory_status.used_percent:.1%}",
                "used_percent": memory_status.used_percent,
                "available_mb": memory_status.available_mb,
                "degradation_level": self.degradation_manager.current_level
            }

    def _check_worker_health(self) -> Dict:
        """Check worker health."""
        if not self.worker:
            return {
                "status": "healthy",
                "message": "Worker not configured"
            }

        # Check if worker is running
        is_running = getattr(self.worker, 'is_running', True)

        if not is_running:
            return {
                "status": "warning",
                "message": "Worker is paused (degradation level 3)",
                "is_running": False
            }
        else:
            return {
                "status": "healthy",
                "message": "Worker is running",
                "is_running": True
            }


# Singleton instances
_metrics_collector_instance: Optional[MetricsCollector] = None
_health_checker_instance: Optional[HealthChecker] = None


def get_metrics_collector() -> MetricsCollector:
    """Get global metrics collector instance."""
    global _metrics_collector_instance
    if _metrics_collector_instance is None:
        _metrics_collector_instance = MetricsCollector()
    return _metrics_collector_instance


def create_health_checker(
    buffer_manager,
    learning_system,
    memory_monitor,
    degradation_manager,
    worker=None
) -> HealthChecker:
    """Create health checker instance."""
    return HealthChecker(
        buffer_manager,
        learning_system,
        memory_monitor,
        degradation_manager,
        worker
    )

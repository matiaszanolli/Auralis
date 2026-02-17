"""
Cache Monitoring and Analytics
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Real-time monitoring, alerting, and analytics for Phase 7.5 cache system.

Phase B.2: Cache Integration and Monitoring

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    """Cache health status."""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class CacheAlert:
    """Cache system alert."""
    level: str  # "warning" or "critical"
    title: str
    description: str
    metric: str
    current_value: float
    threshold: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def is_active(self) -> bool:
        """Check if alert is still active (within last 5 minutes)."""
        elapsed = datetime.now(timezone.utc) - self.timestamp
        return elapsed < timedelta(minutes=5)


@dataclass
class CacheMetrics:
    """Point-in-time cache metrics."""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    tier1_hit_rate: float = 0.0
    tier2_hit_rate: float = 0.0
    overall_hit_rate: float = 0.0
    tier1_size_mb: float = 0.0
    tier2_size_mb: float = 0.0
    total_size_mb: float = 0.0
    tier1_chunks: int = 0
    tier2_chunks: int = 0
    tracks_cached: int = 0
    total_requests: int = 0


class CacheMonitor:
    """
    Monitor and analyze cache system health and performance.

    Features:
    - Real-time hit rate tracking
    - Memory usage monitoring
    - Alert generation for thresholds
    - Metrics history and trends
    - Health status calculation
    """

    def __init__(self, cache_manager: Any) -> None:
        """
        Initialize cache monitor.

        Args:
            cache_manager: StreamlinedCacheManager instance
        """
        self.cache_manager: Any = cache_manager

        # Configuration thresholds
        self.tier1_size_limit_mb: int = 15
        self.tier2_size_limit_mb: int = 250
        self.total_size_limit_mb: int = 260

        self.min_hit_rate_warning: float = 0.70
        self.min_hit_rate_critical: float = 0.50

        self.tier1_memory_warning_percent: float = 0.80
        self.tier1_memory_critical_percent: float = 0.95

        # Metrics history (keep last 100 measurements)
        self.metrics_history: list[CacheMetrics] = []
        self.max_history: int = 100

        # Alerts
        self.active_alerts: dict[str, CacheAlert] = {}

        logger.info("CacheMonitor initialized with default thresholds")

    def update_metrics(self) -> CacheMetrics:
        """
        Capture current cache metrics.

        Returns:
            CacheMetrics object with current state
        """
        stats: dict[str, Any] = self.cache_manager.get_stats()

        metrics: CacheMetrics = CacheMetrics(
            tier1_hit_rate=stats["tier1"].get("hit_rate", 0.0),
            tier2_hit_rate=stats["tier2"].get("hit_rate", 0.0),
            overall_hit_rate=stats["overall"].get("overall_hit_rate", 0.0),
            tier1_size_mb=stats["tier1"].get("size_mb", 0.0),
            tier2_size_mb=stats["tier2"].get("size_mb", 0.0),
            total_size_mb=stats["overall"].get("total_size_mb", 0.0),
            tier1_chunks=stats["tier1"].get("chunks", 0),
            tier2_chunks=stats["tier2"].get("chunks", 0),
            tracks_cached=stats["tier2"].get("tracks_cached", 0),
            total_requests=stats["overall"].get("total_hits", 0) + stats["overall"].get("total_misses", 0)
        )

        # Add to history
        self.metrics_history.append(metrics)
        if len(self.metrics_history) > self.max_history:
            self.metrics_history.pop(0)

        # Check thresholds and generate alerts
        self._check_thresholds(metrics)

        return metrics

    def _check_thresholds(self, metrics: CacheMetrics) -> None:
        """
        Check metrics against thresholds and generate alerts.

        Args:
            metrics: Current cache metrics
        """
        # Check Tier 1 size
        if metrics.tier1_size_mb > self.tier1_size_limit_mb:
            self._add_alert(
                "tier1_size_exceeded",
                "critical",
                "Tier 1 Cache Size Exceeded",
                f"Tier 1 using {metrics.tier1_size_mb:.1f}MB (limit: {self.tier1_size_limit_mb}MB)",
                "tier1_size_mb",
                metrics.tier1_size_mb,
                self.tier1_size_limit_mb
            )
        else:
            self.active_alerts.pop("tier1_size_exceeded", None)

        # Check Tier 2 size
        if metrics.tier2_size_mb > self.tier2_size_limit_mb:
            self._add_alert(
                "tier2_size_exceeded",
                "critical",
                "Tier 2 Cache Size Exceeded",
                f"Tier 2 using {metrics.tier2_size_mb:.1f}MB (limit: {self.tier2_size_limit_mb}MB)",
                "tier2_size_mb",
                metrics.tier2_size_mb,
                self.tier2_size_limit_mb
            )
        else:
            self.active_alerts.pop("tier2_size_exceeded", None)

        # Check overall size
        if metrics.total_size_mb > self.total_size_limit_mb:
            self._add_alert(
                "total_size_exceeded",
                "critical",
                "Total Cache Size Exceeded",
                f"Total cache using {metrics.total_size_mb:.1f}MB (limit: {self.total_size_limit_mb}MB)",
                "total_size_mb",
                metrics.total_size_mb,
                self.total_size_limit_mb
            )
        else:
            self.active_alerts.pop("total_size_exceeded", None)

        # Check hit rate (only if enough requests)
        if metrics.total_requests >= 100:
            if metrics.overall_hit_rate < self.min_hit_rate_critical:
                self._add_alert(
                    "hit_rate_critical",
                    "critical",
                    "Cache Hit Rate Critical",
                    f"Overall hit rate {metrics.overall_hit_rate:.1%} below critical threshold {self.min_hit_rate_critical:.0%}",
                    "overall_hit_rate",
                    metrics.overall_hit_rate,
                    self.min_hit_rate_critical
                )
            elif metrics.overall_hit_rate < self.min_hit_rate_warning:
                self._add_alert(
                    "hit_rate_warning",
                    "warning",
                    "Cache Hit Rate Low",
                    f"Overall hit rate {metrics.overall_hit_rate:.1%} below warning threshold {self.min_hit_rate_warning:.0%}",
                    "overall_hit_rate",
                    metrics.overall_hit_rate,
                    self.min_hit_rate_warning
                )
            else:
                self.active_alerts.pop("hit_rate_warning", None)
                self.active_alerts.pop("hit_rate_critical", None)

    def _add_alert(
        self,
        alert_id: str,
        level: str,
        title: str,
        description: str,
        metric: str,
        current_value: float,
        threshold: float
    ) -> None:
        """Create or update an alert."""
        if alert_id not in self.active_alerts:
            alert = CacheAlert(
                level=level,
                title=title,
                description=description,
                metric=metric,
                current_value=current_value,
                threshold=threshold
            )
            self.active_alerts[alert_id] = alert
            logger.warning(f"🚨 {title}: {description}")
        else:
            # Update existing alert
            self.active_alerts[alert_id].current_value = current_value
            self.active_alerts[alert_id].timestamp = datetime.now(timezone.utc)

    def get_health_status(self) -> tuple[HealthStatus, list[CacheAlert]]:
        """
        Get overall cache health status.

        Returns:
            (health_status, active_alerts)
        """
        # Clean up expired alerts
        active_alerts = [
            alert for alert in self.active_alerts.values()
            if alert.is_active()
        ]

        if not active_alerts:
            return HealthStatus.HEALTHY, []

        critical_alerts = [a for a in active_alerts if a.level == "critical"]

        if critical_alerts:
            return HealthStatus.CRITICAL, active_alerts

        return HealthStatus.WARNING, active_alerts

    def get_trend(self, metric_name: str, window: int = 10) -> dict[str, Any]:
        """
        Get trend for a metric over the last N measurements.

        Args:
            metric_name: Name of metric ('hit_rate', 'size_mb', 'chunks', etc.)
            window: Number of recent measurements (default 10)

        Returns:
            Dictionary with trend information
        """
        if not self.metrics_history:
            return {"value": 0, "trend": "none", "change": 0}

        recent: list[CacheMetrics] = self.metrics_history[-window:]

        if len(recent) < 2:
            return {"value": getattr(recent[0], metric_name, 0), "trend": "none", "change": 0}

        current: float = getattr(recent[-1], metric_name, 0)
        previous: float = getattr(recent[0], metric_name, 0)

        change: float = current - previous
        change_percent: float = (change / previous * 100) if previous != 0 else 0

        trend: str
        if change > 0:
            trend = "up"
        elif change < 0:
            trend = "down"
        else:
            trend = "stable"

        return {
            "value": current,
            "previous": previous,
            "trend": trend,
            "change": round(change, 2),
            "change_percent": round(change_percent, 1),
            "window": len(recent)
        }

    def get_summary(self) -> dict[str, Any]:
        """
        Get comprehensive cache system summary.

        Returns:
            Dictionary with system summary
        """
        if not self.metrics_history:
            return {"status": "no_data"}

        latest: CacheMetrics = self.metrics_history[-1]
        health_status: HealthStatus
        alerts: list[CacheAlert]
        health_status, alerts = self.get_health_status()

        return {
            "timestamp": latest.timestamp.isoformat(),
            "health_status": health_status.value,
            "tier1": {
                "size_mb": round(latest.tier1_size_mb, 2),
                "chunks": latest.tier1_chunks,
                "hit_rate": round(latest.tier1_hit_rate, 3),
                "trend": self.get_trend("tier1_size_mb", 10)
            },
            "tier2": {
                "size_mb": round(latest.tier2_size_mb, 2),
                "chunks": latest.tier2_chunks,
                "hit_rate": round(latest.tier2_hit_rate, 3),
                "trend": self.get_trend("tier2_size_mb", 10),
                "tracks_cached": latest.tracks_cached
            },
            "overall": {
                "size_mb": round(latest.total_size_mb, 2),
                "hit_rate": round(latest.overall_hit_rate, 3),
                "total_requests": latest.total_requests,
                "trend": self.get_trend("overall_hit_rate", 10)
            },
            "alerts": [
                {
                    "id": alert_id,
                    "level": alert.level,
                    "title": alert.title,
                    "description": alert.description,
                    "metric": alert.metric,
                    "current_value": round(alert.current_value, 2),
                    "threshold": round(alert.threshold, 2),
                    "timestamp": alert.timestamp.isoformat()
                }
                for alert_id, alert in self.active_alerts.items()
                if alert.is_active()
            ]
        }

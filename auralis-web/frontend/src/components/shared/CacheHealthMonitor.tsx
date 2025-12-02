/**
 * Cache Health Monitor Component
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Real-time monitoring of cache system health with status indicators,
 * alerts, and recommended actions.
 *
 * Phase C.1: Frontend Integration
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import React, { useEffect } from 'react';
import { tokens } from '@/design-system';
import { useCacheHealth } from '@/hooks/useStandardizedAPI';
import { CacheHealth } from '@/services/api/standardizedAPIClient';

interface CacheHealthMonitorProps {
  /**
   * Refresh interval in milliseconds (default 10000ms)
   */
  refreshInterval?: number;
  /**
   * Callback when health status changes
   */
  onHealthStatusChange?: (healthy: boolean) => void;
}

/**
 * Health status indicator with color and text
 */
function HealthStatusIndicator({ healthy, isHealthy }: { healthy: boolean; isHealthy?: boolean }) {
  const actualHealthy = isHealthy !== undefined ? isHealthy : healthy;
  const statusColor = actualHealthy ? tokens.colors.semantic.success : tokens.colors.semantic.error;
  const statusText = actualHealthy ? 'Healthy' : 'Unhealthy';

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: tokens.spacing.sm }}>
      <div
        style={{
          width: '12px',
          height: '12px',
          borderRadius: '50%',
          background: statusColor,
          boxShadow: `0 0 8px ${statusColor}`,
          animation: actualHealthy ? 'none' : 'pulse 1s infinite',
        }}
      />
      <span
        style={{
          color: statusColor,
          fontWeight: tokens.typography.fontWeight.semibold,
          fontSize: tokens.typography.fontSize.sm,
        }}
      >
        {statusText}
      </span>
    </div>
  );
}

/**
 * Health metric card showing a single metric
 */
function HealthMetricCard({
  label,
  value,
  unit,
  status,
  icon,
}: {
  label: string;
  value: number;
  unit: string;
  status: 'healthy' | 'warning' | 'critical';
  icon: React.ReactNode;
}) {
  const statusColor =
    status === 'healthy'
      ? tokens.colors.semantic.success
      : status === 'warning'
        ? tokens.colors.semantic.warning
        : tokens.colors.semantic.error;

  return (
    <div
      style={{
        padding: tokens.spacing.lg,
        background: tokens.colors.bg.tertiary,
        borderRadius: '8px',
        border: `1px solid ${tokens.colors.border.light}`,
        display: 'flex',
        alignItems: 'center',
        gap: tokens.spacing.md,
      }}
    >
      <div
        style={{
          width: '40px',
          height: '40px',
          borderRadius: '50%',
          background: `${statusColor}20`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: statusColor,
          fontSize: tokens.typography.fontSize.lg,
        }}
      >
        {icon}
      </div>

      <div style={{ flex: 1 }}>
        <div
          style={{
            fontSize: tokens.typography.fontSize.xs,
            color: tokens.colors.text.tertiary,
            marginBottom: tokens.spacing.xs,
          }}
        >
          {label}
        </div>
        <div
          style={{
            fontSize: tokens.typography.fontSize.lg,
            fontWeight: tokens.typography.fontWeight.semibold,
            color: tokens.colors.text.primary,
          }}
        >
          {value.toFixed(1)} {unit}
        </div>
      </div>

      <div
        style={{
          width: '4px',
          height: '40px',
          borderRadius: '2px',
          background: statusColor,
        }}
      />
    </div>
  );
}

/**
 * Determines health status based on thresholds
 */
function getHealthStatus(health: CacheHealth): 'healthy' | 'warning' | 'critical' {
  if (!health.memory_healthy || !health.tier1_healthy || !health.tier2_healthy) {
    return 'critical';
  }
  if (health.overall_hit_rate < 0.7 || health.tier1_hit_rate < 0.7) {
    return 'warning';
  }
  return 'healthy';
}

/**
 * Cache Health Monitor Component
 */
export function CacheHealthMonitor({
  refreshInterval = 10000,
  onHealthStatusChange,
}: CacheHealthMonitorProps) {
  const { data: cacheHealth, loading, error, isHealthy, refetch } = useCacheHealth();

  // Set up auto-refresh
  useEffect(() => {
    const interval = setInterval(() => {
      refetch();
    }, refreshInterval);

    return () => clearInterval(interval);
  }, [refreshInterval, refetch]);

  // Notify about health status changes
  useEffect(() => {
    if (cacheHealth && onHealthStatusChange) {
      onHealthStatusChange(isHealthy ?? cacheHealth.healthy);
    }
  }, [cacheHealth, isHealthy, onHealthStatusChange]);

  if (loading && !cacheHealth) {
    return (
      <div
        style={{
          padding: tokens.spacing.lg,
          color: tokens.colors.text.secondary,
          textAlign: 'center',
        }}
      >
        Loading cache health...
      </div>
    );
  }

  if (error) {
    return (
      <div
        style={{
          padding: tokens.spacing.lg,
          background: 'rgba(239, 68, 68, 0.1)',
          borderRadius: '8px',
          color: tokens.colors.semantic.error,
          fontSize: tokens.typography.fontSize.sm,
        }}
      >
        Failed to load cache health: {error}
      </div>
    );
  }

  if (!cacheHealth) {
    return null;
  }

  const healthStatus = getHealthStatus(cacheHealth);

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: tokens.spacing.lg,
      }}
    >
      {/* Header with overall status */}
      <div
        style={{
          padding: tokens.spacing.lg,
          background:
            healthStatus === 'critical'
              ? 'rgba(239, 68, 68, 0.1)'
              : healthStatus === 'warning'
                ? 'rgba(245, 158, 11, 0.1)'
                : 'rgba(0, 212, 170, 0.1)',
          borderRadius: '8px',
          border: `1px solid ${
            healthStatus === 'critical'
              ? tokens.colors.semantic.error
              : healthStatus === 'warning'
                ? tokens.colors.semantic.warning
                : tokens.colors.semantic.success
          }`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <div>
          <div
            style={{
              fontSize: tokens.typography.fontSize.md,
              fontWeight: tokens.typography.fontWeight.semibold,
              color: tokens.colors.text.primary,
              marginBottom: tokens.spacing.sm,
            }}
          >
            Cache System Status
          </div>
          <div
            style={{
              fontSize: tokens.typography.fontSize.sm,
              color: tokens.colors.text.secondary,
            }}
          >
            Last updated: {new Date(cacheHealth.timestamp).toLocaleTimeString()}
          </div>
        </div>

        <HealthStatusIndicator healthy={isHealthy ?? cacheHealth.healthy} />
      </div>

      {/* Health Metrics */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
          gap: tokens.spacing.lg,
        }}
      >
        <HealthMetricCard
          label="Tier 1 Size"
          value={cacheHealth.tier1_size_mb}
          unit="MB"
          status={cacheHealth.tier1_healthy ? 'healthy' : 'critical'}
          icon="🔥"
        />
        <HealthMetricCard
          label="Tier 2 Size"
          value={cacheHealth.tier2_size_mb}
          unit="MB"
          status={cacheHealth.tier2_healthy ? 'healthy' : 'critical'}
          icon="🧊"
        />
        <HealthMetricCard
          label="Total Size"
          value={cacheHealth.total_size_mb}
          unit="MB"
          status={cacheHealth.memory_healthy ? 'healthy' : 'critical'}
          icon="💾"
        />
      </div>

      {/* Hit Rate Metrics */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
          gap: tokens.spacing.lg,
        }}
      >
        <HealthMetricCard
          label="Tier 1 Hit Rate"
          value={cacheHealth.tier1_hit_rate * 100}
          unit="%"
          status={
            cacheHealth.tier1_hit_rate >= 0.7
              ? 'healthy'
              : cacheHealth.tier1_hit_rate >= 0.5
                ? 'warning'
                : 'critical'
          }
          icon="🎯"
        />
        <HealthMetricCard
          label="Overall Hit Rate"
          value={cacheHealth.overall_hit_rate * 100}
          unit="%"
          status={
            cacheHealth.overall_hit_rate >= 0.7
              ? 'healthy'
              : cacheHealth.overall_hit_rate >= 0.5
                ? 'warning'
                : 'critical'
          }
          icon="📊"
        />
      </div>

      {/* Recommendations */}
      {healthStatus !== 'healthy' && (
        <div
          style={{
            padding: tokens.spacing.lg,
            background: tokens.colors.bg.tertiary,
            borderRadius: '8px',
            border: `1px solid ${tokens.colors.border.light}`,
          }}
        >
          <div
            style={{
              fontSize: tokens.typography.fontSize.md,
              fontWeight: tokens.typography.fontWeight.semibold,
              color:
                healthStatus === 'critical'
                  ? tokens.colors.semantic.error
                  : tokens.colors.semantic.warning,
              marginBottom: tokens.spacing.md,
            }}
          >
            {healthStatus === 'critical' ? '⚠️ Critical Issues' : '⚡ Warnings'}
          </div>

          <ul
            style={{
              margin: 0,
              paddingLeft: tokens.spacing.lg,
              fontSize: tokens.typography.fontSize.sm,
              color: tokens.colors.text.secondary,
              lineHeight: tokens.typography.lineHeight.relaxed,
            }}
          >
            {!cacheHealth.tier1_healthy && (
              <li>Tier 1 cache size exceeds safe limits - consider clearing old cache</li>
            )}
            {!cacheHealth.tier2_healthy && (
              <li>Tier 2 cache size exceeds safe limits - consider clearing old cache</li>
            )}
            {!cacheHealth.memory_healthy && (
              <li>Total memory usage exceeds safe limits - system performance may degrade</li>
            )}
            {cacheHealth.tier1_hit_rate < 0.7 && (
              <li>Tier 1 hit rate below optimal - cache may not be effective</li>
            )}
            {cacheHealth.overall_hit_rate < 0.7 && (
              <li>Overall hit rate below optimal - consider expanding cache size</li>
            )}
          </ul>
        </div>
      )}

      {/* Auto-refresh indicator */}
      <div
        style={{
          fontSize: tokens.typography.fontSize.xs,
          color: tokens.colors.text.tertiary,
          textAlign: 'center',
        }}
      >
        Auto-refreshing every {refreshInterval / 1000}s
      </div>
    </div>
  );
}

export default CacheHealthMonitor;

/**
 * Cache Health Widget Component
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Compact cache health indicator with:
 * - Health status at a glance
 * - Quick alerts
 * - Trend indicators
 * - Expandable for full monitoring
 *
 * Phase C.2: Advanced UI Components
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import React, { useState } from 'react';
import { tokens } from '@/design-system';
import { useCacheHealth } from '@/hooks/shared/useStandardizedAPI';
import CacheHealthMonitor from './CacheHealthMonitor';
import { getHealthStatus } from './HealthStatusIndicator';

type Size = 'small' | 'medium' | 'large';

interface CacheHealthWidgetProps {
  /**
   * Widget size
   */
  size?: Size;
  /**
   * Allow expansion to full monitor
   */
  interactive?: boolean;
}

/**
 * Get dimensions based on size
 */
function getSizeStyles(size: Size) {
  switch (size) {
    case 'small':
      return {
        width: '120px',
        height: '120px',
        padding: tokens.spacing.md,
        iconSize: '40px',
        textSize: tokens.typography.fontSize.xs,
      };
    case 'large':
      return {
        width: '180px',
        height: '180px',
        padding: tokens.spacing.lg,
        iconSize: '60px',
        textSize: tokens.typography.fontSize.sm,
      };
    default:
      return {
        width: '150px',
        height: '150px',
        padding: tokens.spacing.lg,
        iconSize: '48px',
        textSize: tokens.typography.fontSize.sm,
      };
  }
}

/**
 * Cache Health Widget Component
 */
export function CacheHealthWidget({
  size = 'medium',
  interactive = true,
}: CacheHealthWidgetProps) {
  const { data: cacheHealth, loading, error, isHealthy, refetch } = useCacheHealth();
  const [showExpandedMonitor, setShowExpandedMonitor] = useState(false);
  const sizeStyles = getSizeStyles(size);

  if (loading && !cacheHealth) {
    return (
      <div
        data-testid="health-skeleton"
        style={{
          width: sizeStyles.width,
          height: sizeStyles.height,
          padding: sizeStyles.padding,
          background: tokens.colors.bg.tertiary,
          borderRadius: '12px',
          border: `1px solid ${tokens.colors.border.light}`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: tokens.typography.fontSize.xs,
          color: tokens.colors.text.tertiary,
        }}
      >
        Loading...
      </div>
    );
  }

  if (error || !cacheHealth) {
    return (
      <div
        style={{
          width: sizeStyles.width,
          height: sizeStyles.height,
          padding: sizeStyles.padding,
          background: 'rgba(239, 68, 68, 0.1)',
          borderRadius: '12px',
          border: `1px solid ${tokens.colors.semantic.error}`,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: tokens.spacing.md,
          fontSize: tokens.typography.fontSize.xs,
          color: tokens.colors.semantic.error,
          textAlign: 'center',
        }}
      >
        <div>Error</div>
        <button
          onClick={() => refetch()}
          style={{
            padding: `${tokens.spacing.sm} ${tokens.spacing.md}`,
            background: tokens.colors.semantic.error,
            color: tokens.colors.text.primary,
            border: 'none',
            borderRadius: '6px',
            fontSize: tokens.typography.fontSize.xs,
            cursor: 'pointer',
            fontWeight: tokens.typography.fontWeight.medium,
          }}
        >
          Retry
        </button>
      </div>
    );
  }

  const isActuallyHealthy = isHealthy ?? cacheHealth.healthy;
  const { statusColor, statusText } = getHealthStatus(isActuallyHealthy);
  const statusEmoji = isActuallyHealthy ? '✅' : '⚠️';

  // Calculate alert count
  const alertCount =
    (!cacheHealth.tier1_healthy ? 1 : 0) +
    (!cacheHealth.tier2_healthy ? 1 : 0) +
    (!cacheHealth.memory_healthy ? 1 : 0) +
    (cacheHealth.overall_hit_rate < 0.7 ? 1 : 0);

  // Determine trend
  const trend =
    cacheHealth.overall_hit_rate > 0.8
      ? '📈'
      : cacheHealth.overall_hit_rate > 0.6
        ? '➡️'
        : '📉';

  return (
    <>
      <div
        data-testid="cache-health-widget"
        tabIndex={interactive ? 0 : undefined}
        onClick={() => interactive && setShowExpandedMonitor(true)}
        style={{
          width: sizeStyles.width,
          height: sizeStyles.height,
          padding: sizeStyles.padding,
          background: `${statusColor}10`,
          borderRadius: '12px',
          border: `2px solid ${statusColor}`,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'space-between',
          cursor: interactive ? 'pointer' : 'default',
          transition: 'all 0.2s',
          position: 'relative',
        }}
        onMouseOver={(e) => {
          if (interactive) {
            (e.currentTarget as HTMLElement).style.transform = 'scale(1.05)';
            (e.currentTarget as HTMLElement).style.boxShadow = `0 0 20px ${statusColor}40`;
          }
        }}
        onMouseOut={(e) => {
          if (interactive) {
            (e.currentTarget as HTMLElement).style.transform = 'scale(1)';
            (e.currentTarget as HTMLElement).style.boxShadow = 'none';
          }
        }}
      >
        {/* Status Indicator */}
        <div style={{ fontSize: sizeStyles.iconSize }}>{statusEmoji}</div>

        {/* Status Text */}
        <div
          aria-label={`Cache status: ${statusText}`}
          aria-live="polite"
          style={{
            fontSize: sizeStyles.textSize,
            fontWeight: tokens.typography.fontWeight.semibold,
            color: tokens.colors.text.primary,
            textAlign: 'center',
          }}
        >
          {statusText}
        </div>

        {/* Health Percentage */}
        <div
          data-testid="percentage"
          style={{
            fontSize: tokens.typography.fontSize.xs,
            color: tokens.colors.text.secondary,
          }}
        >
          {cacheHealth.overall_hit_rate >= 0
            ? `${(cacheHealth.overall_hit_rate * 100).toFixed(0)}%`
            : 'N/A'}
        </div>

        {/* Alert Badge */}
        {alertCount > 0 && (
          <div
            data-testid="alert-badge"
            style={{
              position: 'absolute',
              top: tokens.spacing.sm,
              right: tokens.spacing.sm,
              width: '24px',
              height: '24px',
              borderRadius: '50%',
              background: tokens.colors.semantic.error,
              color: tokens.colors.text.primary,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: tokens.typography.fontSize.xs,
              fontWeight: tokens.typography.fontWeight.bold,
            }}
          >
            {alertCount}
          </div>
        )}

        {/* Trend Indicator */}
        <div style={{ fontSize: '18px' }}>{trend}</div>

        {/* Expand Hint */}
        {interactive && (
          <div
            style={{
              fontSize: tokens.typography.fontSize.xs,
              color: tokens.colors.text.tertiary,
              marginTop: tokens.spacing.xs,
            }}
          >
            Click to expand
          </div>
        )}
      </div>

      {/* Expanded Monitor Modal */}
      {showExpandedMonitor && interactive && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0, 0, 0, 0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: tokens.spacing.lg,
          }}
          onClick={() => setShowExpandedMonitor(false)}
        >
          <div
            style={{
              background: tokens.colors.bg.secondary,
              borderRadius: '12px',
              border: `1px solid ${tokens.colors.border.medium}`,
              padding: tokens.spacing.lg,
              maxWidth: '800px',
              maxHeight: '90vh',
              overflowY: 'auto',
              width: '100%',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: tokens.spacing.lg,
              }}
            >
              <h2
                style={{
                  margin: 0,
                  fontSize: tokens.typography.fontSize.lg,
                  fontWeight: tokens.typography.fontWeight.semibold,
                  color: tokens.colors.text.primary,
                }}
              >
                Cache Health Monitoring
              </h2>
              <button
                onClick={() => setShowExpandedMonitor(false)}
                style={{
                  border: 'none',
                  background: tokens.colors.bg.tertiary,
                  borderRadius: '6px',
                  width: '32px',
                  height: '32px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  cursor: 'pointer',
                  fontSize: tokens.typography.fontSize.lg,
                  color: tokens.colors.text.secondary,
                }}
              >
                ✕
              </button>
            </div>

            <CacheHealthMonitor />
          </div>
        </div>
      )}
    </>
  );
}

export default CacheHealthWidget;

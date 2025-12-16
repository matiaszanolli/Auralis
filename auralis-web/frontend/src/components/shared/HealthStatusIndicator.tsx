/**
 * Health Status Indicator Component
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Reusable component for displaying health status with color and text.
 * Extracted from cache components to eliminate duplication (DRY principle).
 *
 * Used by:
 * - CacheHealthMonitor
 * - CacheHealthWidget
 * - CacheStatsDashboard
 *
 * @module components/shared/HealthStatusIndicator
 */

import { tokens } from '@/design-system';

/**
 * Get status values for health indicator
 *
 * Centralized logic for determining status color and text based on health state.
 * Use this utility when you need the status values but not the full component.
 *
 * @param isHealthy - Whether the system is healthy
 * @param labels - Optional custom labels
 * @returns Object with statusColor and statusText
 *
 * @example
 * ```tsx
 * const { statusColor, statusText } = getHealthStatus(isHealthy);
 * <div style={{ color: statusColor }}>{statusText}</div>
 * ```
 */
export function getHealthStatus(
  isHealthy: boolean,
  labels = { healthy: 'Healthy', unhealthy: 'Unhealthy' }
): { statusColor: string; statusText: string } {
  return {
    statusColor: isHealthy
      ? tokens.colors.semantic.success
      : tokens.colors.semantic.error,
    statusText: isHealthy ? labels.healthy : labels.unhealthy,
  };
}

export interface HealthStatusIndicatorProps {
  /**
   * Whether the system is healthy
   */
  isHealthy: boolean;

  /**
   * Optional custom labels
   * @default { healthy: 'Healthy', unhealthy: 'Unhealthy' }
   */
  labels?: {
    healthy: string;
    unhealthy: string;
  };

  /**
   * Size variant
   * @default 'medium'
   */
  size?: 'small' | 'medium' | 'large';

  /**
   * Show pulsing animation for unhealthy state
   * @default true
   */
  animate?: boolean;

  /**
   * Show status dot indicator
   * @default true
   */
  showDot?: boolean;
}

/**
 * Health status indicator with color-coded dot and text.
 *
 * Provides consistent visual feedback for system health status across
 * all cache-related UI components.
 *
 * @example
 * ```tsx
 * <HealthStatusIndicator isHealthy={true} />
 * <HealthStatusIndicator
 *   isHealthy={false}
 *   labels={{ healthy: 'OK', unhealthy: 'Error' }}
 *   size="large"
 * />
 * ```
 */
export function HealthStatusIndicator({
  isHealthy,
  labels = { healthy: 'Healthy', unhealthy: 'Unhealthy' },
  size = 'medium',
  animate = true,
  showDot = true,
}: HealthStatusIndicatorProps) {
  const { statusColor, statusText } = getHealthStatus(isHealthy, labels);

  // Size configurations
  const sizeConfig = {
    small: { dotSize: '8px', fontSize: tokens.typography.fontSize.xs, gap: '6px' },
    medium: { dotSize: '12px', fontSize: tokens.typography.fontSize.sm, gap: '8px' },
    large: { dotSize: '16px', fontSize: tokens.typography.fontSize.base, gap: '10px' },
  }[size];

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: sizeConfig.gap,
      }}
      role="status"
      aria-live="polite"
      aria-label={`Status: ${statusText}`}
    >
      {showDot && (
        <div
          style={{
            width: sizeConfig.dotSize,
            height: sizeConfig.dotSize,
            borderRadius: '50%',
            background: statusColor,
            boxShadow: `0 0 8px ${statusColor}`,
            animation: animate && !isHealthy ? 'pulse 1s infinite' : 'none',
          }}
          aria-hidden="true"
        />
      )}
      <span
        style={{
          color: statusColor,
          fontWeight: tokens.typography.fontWeight.semibold,
          fontSize: sizeConfig.fontSize,
        }}
      >
        {statusText}
      </span>
    </div>
  );
}

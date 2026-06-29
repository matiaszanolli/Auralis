/**
 * Connection Status Indicator Component
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Real-time connection status display with:
 * - WebSocket connection status
 * - API connection status
 * - Latency measurement
 * - Reconnection information
 * - Auto-hide when connected
 *
 * Phase C.2: Advanced UI Components
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import { useState } from 'react';
import { tokens } from '@/design-system';
import { useWebSocketContext } from '@/contexts/WebSocketContext';
import { useConnectionState } from '@/hooks/shared/useReduxState';
import { useAPIHealthPoll } from '@/hooks/shared/useAPIHealthPoll';
import { useAutoHide } from '@/hooks/shared/useAutoHide';
import { ConnectionDetailsPanel } from './ConnectionDetailsPanel';

type Position = 'top-left' | 'top-right' | 'bottom-left' | 'bottom-right';

interface ConnectionStatusIndicatorProps {
  /**
   * Position on screen
   */
  position?: Position;
  /**
   * Compact layout
   */
  compact?: boolean;
}

/**
 * Get position styles
 */
function getPositionStyles(position: Position) {
  const baseStyles = {
    position: 'fixed' as const,
    zIndex: tokens.zIndex.fixed,
    margin: tokens.spacing.lg,
  };

  switch (position) {
    case 'top-left':
      return { ...baseStyles, top: 0, left: 0 };
    case 'top-right':
      return { ...baseStyles, top: 0, right: 0 };
    case 'bottom-left':
      return { ...baseStyles, bottom: 0, left: 0 };
    case 'bottom-right':
      return { ...baseStyles, bottom: 0, right: 0 };
    default:
      return { ...baseStyles, bottom: 0, right: 0 };
  }
}

/**
 * Connection Status Indicator Component
 *
 * Reads connection state from Redux (single source of truth) and
 * dispatches API health-poll results back to the store (#3380).
 */
export function ConnectionStatusIndicator({
  position = 'bottom-right',
  compact = false,
}: ConnectionStatusIndicatorProps) {
  const { connect } = useWebSocketContext();
  const status = useConnectionState();
  const [showDetails, setShowDetails] = useState(false);

  // API latency heartbeats (results dispatched to the store) + auto-hide of the
  // details panel when the connection is restored — extracted to hooks (#4186).
  useAPIHealthPoll();
  useAutoHide(status.wsConnected && showDetails, () => setShowDetails(false));

  // Don't show if everything is connected and compact mode
  if (compact && status.wsConnected && status.apiConnected && !showDetails) {
    return null;
  }

  const isHealthy = status.wsConnected && status.apiConnected;
  const isReconnecting = status.lastError !== null && !status.wsConnected;
  const statusColor = isHealthy
    ? tokens.colors.semantic.success
    : isReconnecting
      ? tokens.colors.semantic.warning
      : tokens.colors.semantic.error;

  const statusText = isHealthy
    ? 'Connected'
    : isReconnecting
      ? 'Reconnecting...'
      : 'Disconnected';

  const positionStyles = getPositionStyles(position);

  return (
    <div
      data-testid="connection-indicator"
      data-status={isHealthy ? 'connected' : isReconnecting ? 'reconnecting' : 'disconnected'}
      style={positionStyles}
      onMouseEnter={() => setShowDetails(true)}
      onMouseLeave={() => setShowDetails(false)}
    >
      {/* Compact Indicator */}
      <button
        onClick={() => setShowDetails(!showDetails)}
        onKeyDown={(e) => {
          if (e.key === 'Escape' && showDetails) {
            setShowDetails(false);
            e.stopPropagation();
          }
        }}
        style={{
          padding: tokens.spacing.sm,
          background: tokens.colors.bg.secondary,
          border: `2px solid ${statusColor}`,
          borderRadius: '50%',
          width: '40px',
          height: '40px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          cursor: 'pointer',
          transition: tokens.transitions.hover_out,
          boxShadow: isHealthy
            ? 'none'
            : `0 0 10px ${statusColor}, inset 0 0 10px ${statusColor}20`,
          // Status colour fed to the static connection-status-pulse keyframes via
          // CSS vars (#4188) — no per-status <style> re-injection. Cast because
          // React.CSSProperties doesn't type custom properties.
          ['--pulse-shadow-start' as string]: `${statusColor}80`,
          ['--pulse-shadow-end' as string]: `${statusColor}00`,
          animation: isReconnecting ? 'connection-status-pulse 1s infinite' : 'none',
        } as React.CSSProperties}
        aria-label={statusText}
        aria-live="assertive"
        role="status"
        aria-expanded={showDetails}
      >
        <div
          style={{
            width: '12px',
            height: '12px',
            borderRadius: '50%',
            background: statusColor,
            boxShadow: `0 0 6px ${statusColor}`,
          }}
        />
      </button>

      {/* Expanded Details */}
      {showDetails && (
        <ConnectionDetailsPanel
          wsConnected={status.wsConnected}
          apiConnected={status.apiConnected}
          latency={status.latency}
          lastError={status.lastError}
          statusColor={statusColor}
          statusText={statusText}
          isReconnecting={isReconnecting}
          onReconnect={connect}
        />
      )}
    </div>
  );
}

export default ConnectionStatusIndicator;

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

import React, { useState, useEffect } from 'react';
import { tokens } from '@/design-system';
import { useWebSocketProtocol } from '@/hooks/useWebSocketProtocol';

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

interface ConnectionStatus {
  wsConnected: boolean;
  apiConnected: boolean;
  latency: number;
  isReconnecting: boolean;
  lastError: Error | null;
}

/**
 * Get position styles
 */
function getPositionStyles(position: Position) {
  const baseStyles = {
    position: 'fixed' as const,
    zIndex: 100,
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
 */
export function ConnectionStatusIndicator({
  position = 'bottom-right',
  compact = false,
}: ConnectionStatusIndicatorProps) {
  const { connected: wsConnected, error: wsError } = useWebSocketProtocol();
  const [status, setStatus] = useState<ConnectionStatus>({
    wsConnected: false,
    apiConnected: true,
    latency: 0,
    isReconnecting: false,
    lastError: null,
  });

  const [showDetails, setShowDetails] = useState(false);
  const [autoHideTimer, setAutoHideTimer] = useState<NodeJS.Timeout | null>(null);

  // Update connection status
  useEffect(() => {
    setStatus((prev) => ({
      ...prev,
      wsConnected,
      isReconnecting: wsError !== undefined && !wsConnected,
      lastError: wsError,
    }));

    // Auto-hide when connected
    if (wsConnected && !showDetails) {
      const timer = setTimeout(() => {
        // Keep hidden if connected
      }, 2000);
      setAutoHideTimer(timer);
    }

    return () => {
      if (autoHideTimer) {
        clearTimeout(autoHideTimer);
      }
    };
  }, [wsConnected, wsError, showDetails]);

  // Measure latency with heartbeats
  useEffect(() => {
    const interval = setInterval(async () => {
      const start = performance.now();
      try {
        // Make a quick API call to measure latency
        const response = await fetch('/api/health', { method: 'GET' });
        const latency = Math.round(performance.now() - start);
        if (response.ok) {
          setStatus((prev) => ({
            ...prev,
            apiConnected: true,
            latency,
          }));
        }
      } catch {
        setStatus((prev) => ({
          ...prev,
          apiConnected: false,
          latency: 0,
        }));
      }
    }, 5000);

    return () => clearInterval(interval);
  }, []);

  // Don't show if everything is connected and compact mode
  if (compact && status.wsConnected && status.apiConnected && !showDetails) {
    return null;
  }

  const isHealthy = status.wsConnected && status.apiConnected;
  const statusColor = isHealthy
    ? tokens.colors.semantic.success
    : status.isReconnecting
      ? tokens.colors.semantic.warning
      : tokens.colors.semantic.error;

  const statusText = isHealthy
    ? 'Connected'
    : status.isReconnecting
      ? 'Reconnecting...'
      : 'Disconnected';

  const positionStyles = getPositionStyles(position);

  return (
    <div
      style={positionStyles}
      onMouseEnter={() => setShowDetails(true)}
      onMouseLeave={() => setShowDetails(false)}
    >
      {/* Compact Indicator */}
      <div
        onClick={() => setShowDetails(!showDetails)}
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
          transition: 'all 0.2s',
          boxShadow: isHealthy
            ? 'none'
            : `0 0 10px ${statusColor}, inset 0 0 10px ${statusColor}20`,
          animation: status.isReconnecting ? 'pulse 1s infinite' : 'none',
        }}
        title={statusText}
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
      </div>

      {/* Expanded Details */}
      {showDetails && (
        <div
          style={{
            marginTop: tokens.spacing.sm,
            padding: tokens.spacing.lg,
            background: tokens.colors.bg.secondary,
            border: `1px solid ${tokens.colors.border.medium}`,
            borderRadius: '8px',
            minWidth: '280px',
            boxShadow: '0 4px 20px rgba(0, 0, 0, 0.4)',
          }}
          onClick={(e) => e.stopPropagation()}
        >
          {/* Status Header */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: tokens.spacing.sm,
              marginBottom: tokens.spacing.md,
              paddingBottom: tokens.spacing.md,
              borderBottom: `1px solid ${tokens.colors.border.light}`,
            }}
          >
            <div
              style={{
                width: '12px',
                height: '12px',
                borderRadius: '50%',
                background: statusColor,
                boxShadow: `0 0 6px ${statusColor}`,
                animation: status.isReconnecting ? 'pulse 1s infinite' : 'none',
              }}
            />
            <div
              style={{
                fontSize: tokens.typography.fontSize.sm,
                fontWeight: tokens.typography.fontWeight.semibold,
                color: statusColor,
              }}
            >
              {statusText}
            </div>
          </div>

          {/* WebSocket Status */}
          <div
            style={{
              marginBottom: tokens.spacing.md,
              paddingBottom: tokens.spacing.md,
              borderBottom: `1px solid ${tokens.colors.border.light}`,
            }}
          >
            <div
              style={{
                fontSize: tokens.typography.fontSize.xs,
                color: tokens.colors.text.tertiary,
                marginBottom: tokens.spacing.xs,
              }}
            >
              WebSocket
            </div>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: tokens.spacing.sm,
              }}
            >
              <div
                style={{
                  width: '8px',
                  height: '8px',
                  borderRadius: '50%',
                  background: status.wsConnected
                    ? tokens.colors.semantic.success
                    : tokens.colors.semantic.error,
                }}
              />
              <span
                style={{
                  fontSize: tokens.typography.fontSize.sm,
                  color: tokens.colors.text.secondary,
                }}
              >
                {status.wsConnected ? 'Connected' : 'Disconnected'}
              </span>
            </div>
          </div>

          {/* API Status */}
          <div
            style={{
              marginBottom: tokens.spacing.md,
              paddingBottom: tokens.spacing.md,
              borderBottom: `1px solid ${tokens.colors.border.light}`,
            }}
          >
            <div
              style={{
                fontSize: tokens.typography.fontSize.xs,
                color: tokens.colors.text.tertiary,
                marginBottom: tokens.spacing.xs,
              }}
            >
              API Connection
            </div>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: tokens.spacing.sm,
              }}
            >
              <div
                style={{
                  width: '8px',
                  height: '8px',
                  borderRadius: '50%',
                  background: status.apiConnected
                    ? tokens.colors.semantic.success
                    : tokens.colors.semantic.error,
                }}
              />
              <span
                style={{
                  fontSize: tokens.typography.fontSize.sm,
                  color: tokens.colors.text.secondary,
                }}
              >
                {status.apiConnected ? 'Connected' : 'Disconnected'}
              </span>
            </div>
          </div>

          {/* Latency */}
          {status.latency > 0 && (
            <div
              style={{
                marginBottom: tokens.spacing.md,
                paddingBottom: tokens.spacing.md,
                borderBottom: `1px solid ${tokens.colors.border.light}`,
              }}
            >
              <div
                style={{
                  fontSize: tokens.typography.fontSize.xs,
                  color: tokens.colors.text.tertiary,
                  marginBottom: tokens.spacing.xs,
                }}
              >
                Latency
              </div>
              <div
                style={{
                  fontSize: tokens.typography.fontSize.md,
                  fontWeight: tokens.typography.fontWeight.semibold,
                  color:
                    status.latency < 50
                      ? tokens.colors.semantic.success
                      : status.latency < 100
                        ? tokens.colors.semantic.warning
                        : tokens.colors.semantic.error,
                }}
              >
                {status.latency} ms
              </div>
            </div>
          )}

          {/* Error Message */}
          {status.lastError && (
            <div
              style={{
                marginBottom: tokens.spacing.md,
                padding: tokens.spacing.sm,
                background: 'rgba(239, 68, 68, 0.1)',
                borderRadius: '4px',
                border: `1px solid ${tokens.colors.semantic.error}20`,
              }}
            >
              <div
                style={{
                  fontSize: tokens.typography.fontSize.xs,
                  color: tokens.colors.semantic.error,
                  wordBreak: 'break-word',
                }}
              >
                {status.lastError.message}
              </div>
            </div>
          )}

          {/* Reconnect Button */}
          {status.isReconnecting && (
            <button
              onClick={() => {
                // Trigger manual reconnection
                window.location.reload();
              }}
              style={{
                width: '100%',
                padding: tokens.spacing.sm,
                background: tokens.colors.accent.primary,
                border: 'none',
                borderRadius: '6px',
                color: tokens.colors.text.primary,
                fontSize: tokens.typography.fontSize.sm,
                fontWeight: tokens.typography.fontWeight.semibold,
                cursor: 'pointer',
                opacity: 0.9,
                transition: 'all 0.2s',
              }}
              onMouseOver={(e) => {
                (e.target as HTMLButtonElement).style.opacity = '1';
              }}
              onMouseOut={(e) => {
                (e.target as HTMLButtonElement).style.opacity = '0.9';
              }}
            >
              Reconnect
            </button>
          )}
        </div>
      )}

      <style>{`
        @keyframes pulse {
          0% {
            box-shadow: 0 0 0 0 ${statusColor}80;
          }
          70% {
            box-shadow: 0 0 0 10px ${statusColor}00;
          }
          100% {
            box-shadow: 0 0 0 0 ${statusColor}00;
          }
        }
      `}</style>
    </div>
  );
}

export default ConnectionStatusIndicator;

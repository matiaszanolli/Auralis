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

import { useState, useEffect, useRef } from 'react';
import Box from '@mui/material/Box';
import { tokens } from '@/design-system';
import { useWebSocketContext } from '@/contexts/WebSocketContext';
import { useConnectionState } from '@/hooks/shared/useReduxState';
import { useDispatch } from 'react-redux';
import { setAPIConnected, setLatency } from '@/store/slices/connectionSlice';

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
  const dispatch = useDispatch();
  const { connect } = useWebSocketContext();
  const status = useConnectionState();

  const [showDetails, setShowDetails] = useState(false);
  // Use ref for timer so cleanup always reads the current ID (fixes #2767).
  const autoHideTimerRef = useRef<NodeJS.Timeout | null>(null);
  // Guard against dispatch after unmount.
  const mountedRef = useRef(true);
  useEffect(() => () => { mountedRef.current = false; }, []);

  // Auto-hide details panel when connection is restored
  useEffect(() => {
    if (status.wsConnected && showDetails) {
      const timer = setTimeout(() => {
        if (mountedRef.current) {
          setShowDetails(false);
        }
      }, 2000);
      autoHideTimerRef.current = timer;
    }

    return () => {
      if (autoHideTimerRef.current) {
        clearTimeout(autoHideTimerRef.current);
        autoHideTimerRef.current = null;
      }
    };
  }, [status.wsConnected, showDetails]);

  // Measure latency with heartbeats — pauses when tab is hidden (#3257)
  // Results dispatched to Redux so all consumers see the same values (#3380)
  useEffect(() => {
    let interval: ReturnType<typeof setInterval> | null = null;

    const pollHealth = async () => {
      const start = performance.now();
      try {
        const response = await fetch('/api/health', { method: 'GET' });
        if (!mountedRef.current) return;
        const latency = Math.round(performance.now() - start);
        if (response.ok) {
          dispatch(setAPIConnected(true));
          dispatch(setLatency(latency));
        }
      } catch {
        if (!mountedRef.current) return;
        dispatch(setAPIConnected(false));
        dispatch(setLatency(0));
      }
    };

    const startPolling = () => {
      if (!interval) {
        interval = setInterval(pollHealth, 5000);
      }
    };

    const stopPolling = () => {
      if (interval) {
        clearInterval(interval);
        interval = null;
      }
    };

    const handleVisibility = () => {
      if (document.hidden) {
        stopPolling();
      } else {
        pollHealth(); // Immediate check on return
        startPolling();
      }
    };

    startPolling();
    document.addEventListener('visibilitychange', handleVisibility);

    return () => {
      stopPolling();
      document.removeEventListener('visibilitychange', handleVisibility);
    };
  }, [dispatch]);

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
          transition: 'all 0.2s',
          boxShadow: isHealthy
            ? 'none'
            : `0 0 10px ${statusColor}, inset 0 0 10px ${statusColor}20`,
          animation: isReconnecting ? 'pulse 1s infinite' : 'none',
        }}
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
        <div
          role="region"
          aria-label="Connection status details"
          style={{
            marginTop: tokens.spacing.sm,
            padding: tokens.spacing.lg,
            background: tokens.colors.bg.secondary,
            border: `1px solid ${tokens.colors.border.medium}`,
            borderRadius: '8px',
            minWidth: '280px',
            boxShadow: `0 4px 20px ${tokens.colors.opacityScale.dark.veryStrong}`,
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
                animation: isReconnecting ? 'pulse 1s infinite' : 'none',
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
                background: tokens.colors.utility.errorBg,
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
                {status.lastError}
              </div>
            </div>
          )}

          {/* Reconnect Button */}
          {isReconnecting && (
            <Box
              component="button"
              onClick={() => {
                // Trigger manual WebSocket reconnection without full page reload
                connect();
              }}
              sx={{
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
                '&:hover': {
                  opacity: 1,
                },
              }}
            >
              Reconnect
            </Box>
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

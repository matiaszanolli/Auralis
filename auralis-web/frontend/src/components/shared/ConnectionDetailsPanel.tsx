/**
 * ConnectionDetailsPanel
 * ~~~~~~~~~~~~~~~~~~~~~~~
 *
 * The expanded details panel of ConnectionStatusIndicator (WebSocket/API status,
 * latency, error, reconnect button). Extracted to keep the indicator under the
 * 300-line rule (#4186); purely presentational.
 */

import Box from '@mui/material/Box';
import { tokens } from '@/design-system';

interface ConnectionDetailsPanelProps {
  wsConnected: boolean;
  apiConnected: boolean;
  latency: number;
  lastError: string | null;
  statusColor: string;
  statusText: string;
  isReconnecting: boolean;
  onReconnect: () => void;
}

export function ConnectionDetailsPanel({
  wsConnected,
  apiConnected,
  latency,
  lastError,
  statusColor,
  statusText,
  isReconnecting,
  onReconnect,
}: ConnectionDetailsPanelProps) {
  return (
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
              background: wsConnected
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
            {wsConnected ? 'Connected' : 'Disconnected'}
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
              background: apiConnected
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
            {apiConnected ? 'Connected' : 'Disconnected'}
          </span>
        </div>
      </div>

      {/* Latency */}
      {latency > 0 && (
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
                latency < 50
                  ? tokens.colors.semantic.success
                  : latency < 100
                    ? tokens.colors.semantic.warning
                    : tokens.colors.semantic.error,
            }}
          >
            {latency} ms
          </div>
        </div>
      )}

      {/* Error Message */}
      {lastError && (
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
            {lastError}
          </div>
        </div>
      )}

      {/* Reconnect Button */}
      {isReconnecting && (
        <Box
          component="button"
          onClick={() => {
            // Trigger manual WebSocket reconnection without full page reload
            onReconnect();
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
            transition: tokens.transitions.hover_out,
            '&:hover': {
              opacity: 1,
            },
          }}
        >
          Reconnect
        </Box>
      )}
    </div>
  );
}

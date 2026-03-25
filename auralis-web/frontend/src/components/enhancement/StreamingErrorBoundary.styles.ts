/**
 * Styles, types, and helpers for StreamingErrorBoundary / StreamingErrorDisplay
 */

import type React from 'react';
import { tokens } from '@/design-system';

export enum StreamingErrorType {
  NETWORK = 'network_error',
  BUFFER_UNDERRUN = 'buffer_underrun',
  INVALID_MESSAGE = 'invalid_message',
  AUDIO_CONTEXT = 'audio_context_error',
  SERVER = 'server_error',
  UNKNOWN = 'unknown_error',
}

export enum ErrorSeverity {
  WARNING = 'warning',
  ERROR = 'error',
  CRITICAL = 'critical',
}

export interface StreamingError {
  type: StreamingErrorType;
  message: string;
  severity: ErrorSeverity;
  timestamp: number;
  retryable: boolean;
  details?: string;
}

export const getErrorInfo = (
  error: string,
  errorType?: StreamingErrorType
): { title: string; description: string; icon: string; severity: ErrorSeverity } => {
  switch (errorType) {
    case StreamingErrorType.NETWORK:
      return {
        title: 'Connection Error',
        description: 'Network connection lost or unstable. Check your internet and try again.',
        icon: '📡',
        severity: ErrorSeverity.ERROR,
      };
    case StreamingErrorType.BUFFER_UNDERRUN:
      return {
        title: 'Buffering Issue',
        description: 'Not enough audio data buffered. This usually resolves automatically.',
        icon: '⏳',
        severity: ErrorSeverity.WARNING,
      };
    case StreamingErrorType.INVALID_MESSAGE:
      return {
        title: 'Data Format Error',
        description: 'Received invalid audio data format. Try again.',
        icon: '⚠️',
        severity: ErrorSeverity.ERROR,
      };
    case StreamingErrorType.AUDIO_CONTEXT:
      return {
        title: 'Audio System Error',
        description: 'Web Audio API error. Falling back to regular playback.',
        icon: '🔊',
        severity: ErrorSeverity.ERROR,
      };
    case StreamingErrorType.SERVER:
      return {
        title: 'Server Error',
        description: 'The audio processing server encountered an error.',
        icon: '🖥️',
        severity: ErrorSeverity.ERROR,
      };
    default:
      return {
        title: 'Unknown Error',
        description: error || 'An unexpected error occurred. Try again.',
        icon: '❌',
        severity: ErrorSeverity.ERROR,
      };
  }
};

export const getSeverityColor = (severity: ErrorSeverity): string => {
  switch (severity) {
    case ErrorSeverity.WARNING:
      return tokens.colors.semantic.warning;
    case ErrorSeverity.CRITICAL:
      return tokens.colors.semantic.error;
    case ErrorSeverity.ERROR:
    default:
      return tokens.colors.semantic.error;
  }
};

export const styles: Record<string, React.CSSProperties> = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacing.md,
    padding: tokens.spacing.md,
    backgroundColor: `${tokens.colors.semantic.error}08`,
    border: `1px solid ${tokens.colors.semantic.error}`,
    borderLeftWidth: '4px',
    borderRadius: tokens.borderRadius.sm,
    fontSize: tokens.typography.fontSize.sm,
    animation: 'slideInDown 300ms ease-out',
  },

  content: {
    display: 'flex',
    gap: tokens.spacing.md,
    alignItems: 'flex-start',
  },

  iconSection: {
    minWidth: '40px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },

  icon: {
    fontSize: tokens.typography.fontSize.xl,
  },

  textSection: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacing.xs,
  },

  title: {
    fontWeight: tokens.typography.fontWeight.semibold,
    fontSize: tokens.typography.fontSize.base,
    color: tokens.colors.text.primary,
  },

  description: {
    fontSize: tokens.typography.fontSize.xs,
    color: tokens.colors.text.secondary,
    lineHeight: tokens.typography.lineHeight.normal,
  },

  details: {
    fontSize: tokens.typography.fontSize.xs,
    color: tokens.colors.text.secondary,
    padding: `${tokens.spacing.xs} ${tokens.spacing.sm}`,
    backgroundColor: tokens.colors.bg.level2,
    borderRadius: tokens.borderRadius.sm,
    fontFamily: tokens.typography.fontFamily.mono,
    maxHeight: '60px',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
  },

  retryIndicator: {
    fontSize: tokens.typography.fontSize.xs,
    color: tokens.colors.semantic.warning,
    fontWeight: tokens.typography.fontWeight.medium,
  },

  actions: {
    display: 'flex',
    gap: tokens.spacing.sm,
    minWidth: 'fit-content',
  },

  retryButton: {
    padding: `${tokens.spacing.xs} ${tokens.spacing.sm}`,
    backgroundColor: tokens.colors.semantic.warning,
    color: tokens.colors.text.inverse,
    border: 'none',
    borderRadius: tokens.borderRadius.sm,
    cursor: 'pointer',
    fontSize: tokens.typography.fontSize.xs,
    fontWeight: tokens.typography.fontWeight.semibold,
    transition: 'all 150ms ease-in-out',
    whiteSpace: 'nowrap',
  },

  fallbackButton: {
    padding: `${tokens.spacing.xs} ${tokens.spacing.sm}`,
    backgroundColor: tokens.colors.bg.level2,
    color: tokens.colors.text.primary,
    border: `1px solid ${tokens.colors.border.medium}`,
    borderRadius: tokens.borderRadius.sm,
    cursor: 'pointer',
    fontSize: tokens.typography.fontSize.xs,
    fontWeight: tokens.typography.fontWeight.semibold,
    transition: 'all 150ms ease-in-out',
    whiteSpace: 'nowrap',
  },

  dismissButton: {
    padding: `${tokens.spacing.xs} 6px`,
    backgroundColor: 'transparent',
    color: tokens.colors.semantic.error,
    border: 'none',
    cursor: 'pointer',
    fontSize: tokens.typography.fontSize.md,
    minWidth: '24px',
    transition: 'opacity 150ms ease-in-out',
  },

  historySection: {
    paddingTop: tokens.spacing.md,
    borderTop: `1px solid ${tokens.colors.border.medium}`,
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacing.xs,
  },

  historyTitle: {
    fontSize: tokens.typography.fontSize.xs,
    fontWeight: tokens.typography.fontWeight.semibold,
    color: tokens.colors.text.secondary,
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
  },

  historyList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
  },

  historyItem: {
    display: 'flex',
    gap: tokens.spacing.sm,
    fontSize: '10px',
    color: tokens.colors.text.secondary,
    padding: '4px 0',
  },

  historyTime: {
    fontFamily: tokens.typography.fontFamily.mono,
    color: tokens.colors.text.secondary,
    minWidth: '60px',
  },

  historyError: {
    flex: 1,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  },

  recoveryHint: {
    fontSize: tokens.typography.fontSize.xs,
    color: tokens.colors.semantic.warning,
    padding: `${tokens.spacing.xs} ${tokens.spacing.sm}`,
    backgroundColor: tokens.colors.semantic.warning + '10',
    borderRadius: tokens.borderRadius.sm,
    borderLeft: `2px solid ${tokens.colors.semantic.warning}`,
  },
};

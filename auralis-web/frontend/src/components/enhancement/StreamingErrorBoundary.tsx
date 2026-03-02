/**
 * Streaming Error Boundary Component
 *
 * Catches and displays streaming errors gracefully with recovery options.
 * Provides user-friendly error messages, retry logic, and fallback to regular playback.
 *
 * Features:
 * - Error message display with categorization
 * - Automatic retry with exponential backoff
 * - Fallback to regular playback option
 * - Auto-dismiss after configurable timeout
 * - Error history for debugging
 * - Severity-based styling (warning, error, critical)
 */

import React, { useState, useCallback, useEffect } from 'react';
import { tokens } from '@/design-system';

/**
 * Supported error types during streaming
 */
export enum StreamingErrorType {
  NETWORK = 'network_error',
  BUFFER_UNDERRUN = 'buffer_underrun',
  INVALID_MESSAGE = 'invalid_message',
  AUDIO_CONTEXT = 'audio_context_error',
  SERVER = 'server_error',
  UNKNOWN = 'unknown_error',
}

/**
 * Error severity levels
 */
export enum ErrorSeverity {
  WARNING = 'warning',
  ERROR = 'error',
  CRITICAL = 'critical',
}

/**
 * Detailed error information
 */
interface StreamingError {
  type: StreamingErrorType;
  message: string;
  severity: ErrorSeverity;
  timestamp: number;
  retryable: boolean;
  details?: string;
}

/**
 * Props for StreamingErrorBoundary component
 */
export interface StreamingErrorBoundaryProps {
  /** Error message to display */
  error: string | null;

  /** Error type for categorization */
  errorType?: StreamingErrorType;

  /** Callback when user clicks retry */
  onRetry?: () => void;

  /** Callback when user chooses to use regular playback */
  onFallback?: () => void;

  /** Auto-dismiss after ms (0 = no auto-dismiss) */
  autoDismissMs?: number;

  /** Allow retry button */
  allowRetry?: boolean;

  /** Allow fallback option */
  allowFallback?: boolean;

  /** Track ID for context */
  trackId?: number;

  /** Show error history */
  showHistory?: boolean;
}

/**
 * Format error message based on type
 */
const getErrorInfo = (
  error: string,
  errorType?: StreamingErrorType
): { title: string; description: string; icon: string; severity: ErrorSeverity } => {
  switch (errorType) {
    case StreamingErrorType.NETWORK:
      return {
        title: 'Connection Error',
        description:
          'Network connection lost or unstable. Check your internet and try again.',
        icon: '📡',
        severity: ErrorSeverity.ERROR,
      };

    case StreamingErrorType.BUFFER_UNDERRUN:
      return {
        title: 'Buffering Issue',
        description:
          'Not enough audio data buffered. This usually resolves automatically.',
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

/**
 * Get color based on severity
 */
const getSeverityColor = (severity: ErrorSeverity): string => {
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

/**
 * StreamingErrorBoundary Component
 *
 * Displays streaming errors with recovery options and auto-dismiss behavior.
 */
export const StreamingErrorBoundary: React.FC<StreamingErrorBoundaryProps> = ({
  error,
  errorType = StreamingErrorType.UNKNOWN,
  onRetry,
  onFallback,
  autoDismissMs = 10000,
  allowRetry = true,
  allowFallback = true,
  trackId: _trackId,
  showHistory = false,
}) => {
  const [isVisible, setIsVisible] = useState(!!error);
  const [retryCount, setRetryCount] = useState(0);
  const [errorHistory, setErrorHistory] = useState<StreamingError[]>([]);
  const [isDismissing, setIsDismissing] = useState(false);

  /**
   * Get error info for display
   */
  const errorInfo = getErrorInfo(error || '', errorType);
  const severityColor = getSeverityColor(errorInfo.severity);

  /**
   * Handle retry with exponential backoff
   */
  const handleRetry = useCallback(() => {
    if (!onRetry) return;

    const newCount = retryCount + 1;
    setRetryCount(newCount);

    // Add to history
    setErrorHistory((prev) => [
      ...prev,
      {
        type: errorType,
        message: error || 'Unknown error',
        severity: errorInfo.severity,
        timestamp: Date.now(),
        retryable: true,
      },
    ]);

    // Exponential backoff: 1s, 2s, 4s, 8s
    const backoffMs = Math.min(1000 * Math.pow(2, newCount - 1), 8000);
    setTimeout(() => {
      onRetry();
    }, backoffMs);
  }, [retryCount, onRetry, error, errorType, errorInfo.severity]);

  /**
   * Handle fallback to regular playback
   */
  const handleFallback = useCallback(() => {
    onFallback?.();
    setIsVisible(false);
  }, [onFallback]);

  /**
   * Handle dismiss
   */
  const handleDismiss = useCallback(() => {
    setIsDismissing(true);
    setTimeout(() => {
      setIsVisible(false);
      setIsDismissing(false);
    }, 150);
  }, []);

  /**
   * Auto-dismiss after timeout
   */
  useEffect(() => {
    if (!error || autoDismissMs <= 0) return;

    const timer = setTimeout(() => {
      handleDismiss();
    }, autoDismissMs);

    return () => clearTimeout(timer);
  }, [error, autoDismissMs, handleDismiss]);

  /**
   * Update visibility when error changes
   */
  useEffect(() => {
    if (error) {
      setIsVisible(true);
      setRetryCount(0);
    }
  }, [error]);

  if (!isVisible) return null;

  return (
    <div
      style={{
        ...styles.container,
        opacity: isDismissing ? 0 : 1,
        transition: 'opacity 150ms ease-out',
        borderLeftColor: severityColor,
      }}
    >
      {/* Main Error Content */}
      <div style={styles.content}>
        <div style={styles.iconSection}>
          <span style={styles.icon}>{errorInfo.icon}</span>
        </div>

        <div style={styles.textSection}>
          <div style={styles.title}>{errorInfo.title}</div>
          <div style={styles.description}>{errorInfo.description}</div>

          {/* Additional error details if available */}
          {error && error !== errorInfo.description && (
            <div style={styles.details}>{error}</div>
          )}

          {/* Retry count indicator */}
          {retryCount > 0 && (
            <div style={styles.retryIndicator}>
              Retry attempt {retryCount}
              {retryCount > 3 && ' (consider falling back)'}
            </div>
          )}
        </div>

        {/* Action Buttons */}
        <div style={styles.actions}>
          {allowRetry && (
            <button
              style={{
                ...styles.retryButton,
                opacity: retryCount > 5 ? 0.5 : 1,
              }}
              onClick={handleRetry}
              disabled={retryCount > 5}
              title="Retry enhanced playback"
            >
              🔄 Retry
            </button>
          )}

          {allowFallback && (
            <button
              style={styles.fallbackButton}
              onClick={handleFallback}
              title="Use regular playback instead"
            >
              ▶ Regular
            </button>
          )}

          <button
            style={styles.dismissButton}
            onClick={handleDismiss}
            title="Dismiss this error"
          >
            ✕
          </button>
        </div>
      </div>

      {/* Error History */}
      {showHistory && errorHistory.length > 0 && (
        <div style={styles.historySection}>
          <div style={styles.historyTitle}>Recent Errors ({errorHistory.length})</div>
          <div style={styles.historyList}>
            {errorHistory.slice(-3).map((err, idx) => (
              <div key={idx} style={styles.historyItem}>
                <span style={styles.historyTime}>
                  {new Date(err.timestamp).toLocaleTimeString()}
                </span>
                <span style={styles.historyError}>{err.message}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Buffer underrun recovery hint */}
      {errorType === StreamingErrorType.BUFFER_UNDERRUN && (
        <div style={styles.recoveryHint}>
          💡 Waiting for more data to buffer. Playback will resume automatically.
        </div>
      )}
    </div>
  );
};

/**
 * Styles for StreamingErrorBoundary
 */
const styles: Record<string, React.CSSProperties> = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacing.md,
    padding: tokens.spacing.md,
    backgroundColor: `${tokens.colors.semantic.error}08`,
    border: `1px solid ${tokens.colors.semantic.error}`,
    borderLeftWidth: '4px',
    borderRadius: '6px',
    fontSize: '13px',
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
    fontSize: '24px',
  },

  textSection: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacing.xs,
  },

  title: {
    fontWeight: 600,
    fontSize: '14px',
    color: tokens.colors.text.primary,
  },

  description: {
    fontSize: '12px',
    color: tokens.colors.text.secondary,
    lineHeight: 1.4,
  },

  details: {
    fontSize: '11px',
    color: tokens.colors.text.secondary,
    padding: `${tokens.spacing.xs} ${tokens.spacing.sm}`,
    backgroundColor: tokens.colors.bg.level2,
    borderRadius: '3px',
    fontFamily: 'monospace',
    maxHeight: '60px',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
  },

  retryIndicator: {
    fontSize: '11px',
    color: tokens.colors.semantic.warning,
    fontWeight: 500,
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
    borderRadius: '4px',
    cursor: 'pointer',
    fontSize: '11px',
    fontWeight: 600,
    transition: 'all 150ms ease-in-out',
    whiteSpace: 'nowrap',
  },

  fallbackButton: {
    padding: `${tokens.spacing.xs} ${tokens.spacing.sm}`,
    backgroundColor: tokens.colors.bg.level2,
    color: tokens.colors.text.primary,
    border: `1px solid ${tokens.colors.border.medium}`,
    borderRadius: '4px',
    cursor: 'pointer',
    fontSize: '11px',
    fontWeight: 600,
    transition: 'all 150ms ease-in-out',
    whiteSpace: 'nowrap',
  },

  dismissButton: {
    padding: `${tokens.spacing.xs} 6px`,
    backgroundColor: 'transparent',
    color: tokens.colors.semantic.error,
    border: 'none',
    cursor: 'pointer',
    fontSize: '16px',
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
    fontSize: '11px',
    fontWeight: 600,
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
    fontFamily: 'monospace',
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
    fontSize: '12px',
    color: tokens.colors.semantic.warning,
    padding: `${tokens.spacing.xs} ${tokens.spacing.sm}`,
    backgroundColor: tokens.colors.semantic.warning + '10',
    borderRadius: '4px',
    borderLeft: `2px solid ${tokens.colors.semantic.warning}`,
  },
};

export default StreamingErrorBoundary;

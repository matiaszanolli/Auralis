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

import React, { useState, useCallback, useEffect, useRef } from 'react';
import {
  styles, getErrorInfo, getSeverityColor,
  StreamingErrorType, ErrorSeverity, type StreamingError,
} from './StreamingErrorBoundary.styles';

// Canonical imports: always import these from this file (or the barrel index.ts),
// not directly from StreamingErrorBoundary.styles.ts.
export { StreamingErrorType, ErrorSeverity };

export interface StreamingErrorDisplayProps {
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
 * StreamingErrorDisplay Component
 *
 * Displays streaming errors with recovery options and auto-dismiss behavior.
 */
export const StreamingErrorDisplay = ({
  error,
  errorType = StreamingErrorType.UNKNOWN,
  onRetry,
  onFallback,
  autoDismissMs = 10000,
  allowRetry = true,
  allowFallback = true,
  trackId: _trackId,
  showHistory = false,
}: StreamingErrorDisplayProps) => {
  const [isVisible, setIsVisible] = useState(!!error);
  const [retryCount, setRetryCount] = useState(0);
  const [errorHistory, setErrorHistory] = useState<StreamingError[]>([]);
  const [isDismissing, setIsDismissing] = useState(false);
  const retryTimerRef = useRef<ReturnType<typeof setTimeout>>();
  const dismissTimerRef = useRef<ReturnType<typeof setTimeout>>();

  // Clean up timers on unmount (#2981, #3074)
  useEffect(() => {
    return () => {
      if (retryTimerRef.current) clearTimeout(retryTimerRef.current);
      if (dismissTimerRef.current) clearTimeout(dismissTimerRef.current);
    };
  }, []);

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
    retryTimerRef.current = setTimeout(() => {
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
    if (dismissTimerRef.current) clearTimeout(dismissTimerRef.current);
    setIsDismissing(true);
    dismissTimerRef.current = setTimeout(() => {
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
      role="alert"
      aria-live="assertive"
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
 * StreamingErrorBoundaryWrapper — real React error boundary (class component).
 *
 * Catches render-time exceptions from children and displays the
 * StreamingErrorDisplay UI as a fallback. Supports retry via
 * state reset (#2960).
 */

interface ErrorBoundaryWrapperProps {
  children: React.ReactNode;
  onFallback?: () => void;
}

interface ErrorBoundaryWrapperState {
  hasError: boolean;
  error: string | null;
}

export class StreamingErrorBoundaryWrapper extends React.Component<
  ErrorBoundaryWrapperProps,
  ErrorBoundaryWrapperState
> {
  constructor(props: ErrorBoundaryWrapperProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryWrapperState {
    return { hasError: true, error: error.message };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo): void {
    console.error('[StreamingErrorDisplay] Caught render error:', error, info);
  }

  handleRetry = (): void => {
    this.setState({ hasError: false, error: null });
  };

  render(): React.ReactNode {
    if (this.state.hasError) {
      return (
        <StreamingErrorDisplay
          error={this.state.error}
          errorType={StreamingErrorType.UNKNOWN}
          onRetry={this.handleRetry}
          onFallback={this.props.onFallback}
          autoDismissMs={0}
          allowRetry={true}
          allowFallback={!!this.props.onFallback}
        />
      );
    }
    return this.props.children;
  }
}

export default StreamingErrorDisplay;

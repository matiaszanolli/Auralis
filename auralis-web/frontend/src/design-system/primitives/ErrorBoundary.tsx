import React from 'react';
import { tokens } from '@/design-system';

interface ErrorBoundaryProps {
  children: React.ReactNode;
  fallback?: (error: Error, retry: () => void) => React.ReactNode;
  onError?: (error: Error, errorInfo: React.ErrorInfo) => void;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

/**
 * Error boundary component for catching React errors.
 */
export class ErrorBoundary extends React.Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    this.props.onError?.(error, errorInfo);
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError && this.state.error) {
      if (this.props.fallback) {
        return this.props.fallback(this.state.error, this.handleRetry);
      }

      const containerStyles: React.CSSProperties = {
        padding: tokens.spacing.lg,
        backgroundColor: tokens.colors.semantic.error + '15',
        border: `1px solid ${tokens.colors.semantic.error}`,
        borderRadius: tokens.borderRadius.md,
        margin: tokens.spacing.lg,
      };

      const titleStyles: React.CSSProperties = {
        color: tokens.colors.semantic.error,
        fontSize: tokens.typography.fontSize.lg,
        fontWeight: tokens.typography.fontWeight.semibold,
        marginBottom: tokens.spacing.md,
      };

      const messageStyles: React.CSSProperties = {
        color: tokens.colors.text.secondary,
        fontSize: tokens.typography.fontSize.sm,
        marginBottom: tokens.spacing.md,
        fontFamily: tokens.typography.fontFamily.mono,
        overflow: 'auto',
        maxHeight: '200px',
      };

      const buttonStyles: React.CSSProperties = {
        padding: `${tokens.spacing.sm} ${tokens.spacing.md}`,
        backgroundColor: tokens.colors.accent.primary,
        color: tokens.colors.text.primary,
        border: 'none',
        borderRadius: tokens.borderRadius.md,
        cursor: 'pointer',
        fontSize: tokens.typography.fontSize.sm,
        fontWeight: tokens.typography.fontWeight.medium,
      };

      return (
        <div style={containerStyles}>
          <h3 style={titleStyles}>Something went wrong</h3>
          <pre style={messageStyles}>{this.state.error.toString()}</pre>
          <button style={buttonStyles} onClick={this.handleRetry}>
            Try again
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

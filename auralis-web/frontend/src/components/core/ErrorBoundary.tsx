/**
 * React Error Boundary
 *
 * Catches rendering errors in the component tree and displays a recovery UI
 * instead of crashing the entire application (#2088).
 *
 * Must be a class component — React does not support error boundaries via hooks.
 */

import { Component, ErrorInfo, ReactNode } from 'react';
import { tokens } from '@/design-system/tokens';
import { themeVars } from '@/theme/semanticTheme';

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

interface ErrorBoundaryProps {
  children: ReactNode;
  /** Optional fallback to render instead of the default error UI */
  fallback?: ReactNode;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error('[ErrorBoundary] Uncaught rendering error:', error, info.componentStack);
  }

  private handleRetry = (): void => {
    this.setState({ hasError: false, error: null });
  };

  render(): ReactNode {
    if (!this.state.hasError) {
      return this.props.children;
    }

    if (this.props.fallback) {
      return this.props.fallback;
    }

    const msg = this.state.error?.message ?? 'Unknown error';

    return (
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          height: '100vh',
          background: themeVars.canvas,
          color: themeVars.textPrimary,
          fontFamily: tokens.typography.fontFamily.primary,
        }}
      >
        <div style={{ textAlign: 'center', maxWidth: 500, padding: 40 }}>
          <h1 style={{ color: themeVars.error, fontSize: tokens.typography.fontSize.xl, marginBottom: 16 }}>
            Something went wrong
          </h1>
          <p style={{ color: themeVars.textSecondary, fontSize: tokens.typography.fontSize.base, marginBottom: 24 }}>
            {msg}
          </p>
          <button
            onClick={this.handleRetry}
            style={{
              padding: '10px 24px',
              borderRadius: tokens.borderRadius.md,
              border: 'none',
              background: themeVars.accent,
              color: themeVars.onAccent,
              fontSize: tokens.typography.fontSize.base,
              cursor: 'pointer',
            }}
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }
}

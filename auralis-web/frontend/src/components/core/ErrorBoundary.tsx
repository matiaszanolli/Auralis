/**
 * React Error Boundary
 *
 * Catches rendering errors in the component tree and displays a recovery UI
 * instead of crashing the entire application (#2088).
 *
 * Must be a class component — React does not support error boundaries via hooks.
 */

import React from 'react';
import { tokens } from '@/design-system';

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

interface ErrorBoundaryProps {
  children: React.ReactNode;
  /** Optional fallback to render instead of the default error UI */
  fallback?: React.ReactNode;
}

export class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo): void {
    console.error('[ErrorBoundary] Uncaught rendering error:', error, info.componentStack);
  }

  private handleRetry = (): void => {
    this.setState({ hasError: false, error: null });
  };

  render(): React.ReactNode {
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
          background: tokens.colors.bg.level0,
          color: tokens.colors.text.primary,
          fontFamily: tokens.typography.fontFamily.primary,
        }}
      >
        <div style={{ textAlign: 'center', maxWidth: 500, padding: 40 }}>
          <h1 style={{ color: tokens.colors.semantic.error, fontSize: tokens.typography.fontSize.xl, marginBottom: 16 }}>
            Something went wrong
          </h1>
          <p style={{ color: tokens.colors.text.secondary, fontSize: tokens.typography.fontSize.base, marginBottom: 24 }}>
            {msg}
          </p>
          <button
            onClick={this.handleRetry}
            style={{
              padding: '10px 24px',
              borderRadius: tokens.borderRadius.md,
              border: 'none',
              background: tokens.colors.accent.primary,
              color: '#fff',
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

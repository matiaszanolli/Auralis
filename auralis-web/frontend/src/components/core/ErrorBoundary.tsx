/**
 * React Error Boundary
 *
 * Catches rendering errors in the component tree and displays a recovery UI
 * instead of crashing the entire application (#2088).
 *
 * Must be a class component — React does not support error boundaries via hooks.
 *
 * Fallback contract (#5627): a fallback may be a plain node (rendered as-is)
 * or a function `(error, retry) => node` — the retry callback clears the
 * error state and re-renders the children, which is the only recovery path
 * for the region fallbacks in ComfortableApp (their old static "Refresh the
 * page" copy made the built-in retry unreachable). `resetKeys` additionally
 * clears the error state whenever any key changes, so e.g. switching views
 * recovers the library boundary without a click.
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
  /**
   * Static node, or `(error, retry)` for fallbacks with a working recovery
   * action. A plain node still renders, but only the function form — or the
   * default UI — offers a retry path.
   */
  fallback?: ReactNode | ((error: Error, retry: () => void) => ReactNode);
  /**
   * When any value changes while an error is shown, the boundary resets
   * (children re-render). Use the region's identity, e.g. `[currentView]`.
   */
  resetKeys?: unknown[];
  /** Observability hook; the default UI never surfaces errorInfo anywhere. */
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
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
    this.props.onError?.(error, info);
  }

  componentDidUpdate(prevProps: ErrorBoundaryProps): void {
    if (
      !this.state.hasError ||
      !this.props.resetKeys ||
      prevProps.resetKeys === this.props.resetKeys
    ) {
      return;
    }
    const changed = this.props.resetKeys.some(
      (key, i) => !Object.is(key, prevProps.resetKeys?.[i])
    );
    if (changed) {
      this.handleRetry();
    }
  }

  private handleRetry = (): void => {
    this.setState({ hasError: false, error: null });
  };

  render(): ReactNode {
    if (!this.state.hasError) {
      return this.props.children;
    }

    if (typeof this.props.fallback === 'function') {
      return this.props.fallback(this.state.error ?? new Error('Unknown error'), this.handleRetry);
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
              // 10px/24px are both off the spacing scale (sm=6, md=12,
              // lg=20, xl=28). Kept literal rather than snapped, so this
              // button's size does not shift (#4663).
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

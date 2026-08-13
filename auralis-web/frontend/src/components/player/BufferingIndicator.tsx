/**
 * BufferingIndicator - Buffering progress and status indicator
 *
 * Displays buffered content percentage and buffering/error states with animations.
 * Provides visual feedback on download progress and playback readiness.
 *
 * @component
 * @example
 * <BufferingIndicator
 *   bufferedPercentage={75}
 *   isBuffering={false}
 *   isError={false}
 * />
 */

import { useMemo, memo } from 'react';
import { tokens } from '@/design-system/tokens';
import { themeVars } from '@/theme/semanticTheme';

export interface BufferingIndicatorProps {
  /**
   * Percentage of audio that has been buffered (0-100)
   */
  bufferedPercentage: number;

  /**
   * Whether currently buffering
   * Default: false
   */
  isBuffering?: boolean;

  /**
   * Whether in error state
   * Default: false
   */
  isError?: boolean;

  /**
   * Error message to display (optional)
   */
  errorMessage?: string;

  /**
   * Additional CSS class names
   */
  className?: string;

  /**
   * Custom aria label (optional)
   */
  ariaLabel?: string;
}

/**
 * BufferingIndicator Component
 *
 * Shows buffering progress and status with appropriate animations and messaging.
 */
const BufferingIndicatorComponent = ({
  bufferedPercentage,
  isBuffering = false,
  isError = false,
  errorMessage,
  className = '',
  ariaLabel,
}: BufferingIndicatorProps) => {
  // Clamp percentage to 0-100
  const clampedPercentage = useMemo(() => {
    // Handle NaN and non-numeric values
    if (Number.isNaN(bufferedPercentage)) {
      return 0;
    }
    return Math.min(Math.max(bufferedPercentage, 0), 100);
  }, [bufferedPercentage]);

  // Format percentage string
  const percentageStr = useMemo(() => {
    return `${Math.round(clampedPercentage)}%`;
  }, [clampedPercentage]);

  // Determine status text
  const statusText = useMemo(() => {
    if (isError) {
      return errorMessage || 'Playback error';
    }

    if (isBuffering) {
      return 'Buffering...';
    }

    return `Buffered: ${percentageStr}`;
  }, [isError, isBuffering, errorMessage, percentageStr]);

  // Aria label
  const finalAriaLabel = useMemo(() => {
    if (ariaLabel) {
      return ariaLabel;
    }

    if (isError) {
      return errorMessage || 'Playback error';
    }

    if (isBuffering) {
      return 'Buffering content, please wait';
    }

    return `${percentageStr} of content buffered`;
  }, [ariaLabel, isError, isBuffering, errorMessage, percentageStr]);

  return (
    <div
      className={className}
      data-testid="buffering-indicator"
      role="status"
      aria-label={finalAriaLabel}
      aria-live="polite"
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: tokens.spacing.xs,
      }}
    >
      {/* Buffered content bar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: tokens.spacing.xs,
        }}
      >
        <div
          style={{
            flex: 1,
            height: '4px',
            backgroundColor: themeVars.surfaceRaised,
            borderRadius: '2px',
            overflow: 'hidden',
            position: 'relative',
          }}
        >
          <div
            style={{
              height: '100%',
              width: `${clampedPercentage}%`,
              backgroundColor: themeVars.accent,
              transition: `width ${tokens.transitions.hover}`,
            }}
            data-testid="buffered-bar"
          />
        </div>

        {/* Percentage label */}
        <span
          style={{
            minWidth: '35px',
            textAlign: 'right',
            fontSize: tokens.typography.fontSize.xs,
            color: themeVars.textMuted,
            fontFamily: tokens.typography.fontFamily.mono,
          }}
          data-testid="buffered-percentage"
        >
          {percentageStr}
        </span>
      </div>

      {/* Buffering spinner or error message */}
      {(isBuffering || isError) && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: tokens.spacing.xs,
            fontSize: tokens.typography.fontSize.xs,
            color: isError ? themeVars.error : themeVars.textSecondary,
          }}
          data-testid="buffering-status"
        >
          {isBuffering && !isError && (
            <div
              style={{
                width: '12px',
                height: '12px',
                borderRadius: '50%',
                border: `2px solid ${themeVars.accent}`,
                borderTopColor: themeVars.accentHover,
                animation: 'spin 1s linear infinite',
              }}
              data-testid="buffering-spinner"
            />
          )}

          <span>{statusText}</span>
        </div>
      )}
    </div>
  );
};

/**
 * Memoized (#4632): `Player` re-renders 10x/second while a track is playing —
 * it subscribes to the 10Hz position tick via `usePlaybackProgress()` because it
 * renders the progress bar. This component's props do not change on that tick,
 * so without `memo` its whole body re-executed 10x/second for the entire
 * duration of every playback session, on a machine that is simultaneously
 * running the Python DSP engine.
 *
 * This only holds while every prop stays referentially stable: an inline arrow
 * or object literal at the call site defeats it silently. See Player.tsx, where
 * the handlers are `useCallback`-wrapped for exactly this reason.
 */
export const BufferingIndicator = memo(BufferingIndicatorComponent);

BufferingIndicator.displayName = 'BufferingIndicator';

export default BufferingIndicator;

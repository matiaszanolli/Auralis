/**
 * TimeDisplay - Player time information display component
 *
 * Displays current time, duration, and remaining time with appropriate formatting.
 * Supports both time-based display and live content indicator.
 *
 * @component
 * @example
 * <TimeDisplay
 *   currentTime={90}
 *   duration={225}
 *   showRemaining={false}
 * />
 */

import React, { useMemo } from 'react';
import { formatSecondToTime } from '@/hooks/player/usePlayerDisplay';
import { tokens } from '@/design-system';

export interface TimeDisplayProps {
  /**
   * Current playback position in seconds
   */
  currentTime: number;

  /**
   * Total track duration in seconds
   */
  duration: number;

  /**
   * Whether to show remaining time instead of total duration
   * Default: false (shows total duration)
   */
  showRemaining?: boolean;

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
 * TimeDisplay Component
 *
 * Provides formatted time information for the player UI.
 * Handles live content detection and appropriate display.
 */
export const TimeDisplay: React.FC<TimeDisplayProps> = ({
  currentTime,
  duration,
  showRemaining = false,
  className = '',
  ariaLabel,
}) => {
  // Determine if this is live content (no duration or infinity)
  const isLiveContent = useMemo(() => {
    return !Number.isFinite(duration) || duration === 0;
  }, [duration]);

  // Format current time
  const currentTimeStr = useMemo(() => {
    return formatSecondToTime(currentTime, duration >= 3600);
  }, [currentTime, duration]);

  // Calculate and format duration or remaining time
  const secondaryTimeStr = useMemo(() => {
    if (isLiveContent) {
      return '';
    }

    if (showRemaining) {
      const remaining = Math.max(0, duration - currentTime);
      return `-${formatSecondToTime(remaining, duration >= 3600)}`;
    }

    return formatSecondToTime(duration, duration >= 3600);
  }, [duration, currentTime, showRemaining, isLiveContent]);

  // Full display string
  const displayString = useMemo(() => {
    if (isLiveContent) {
      return 'LIVE';
    }

    if (showRemaining) {
      return `${currentTimeStr} / ${secondaryTimeStr}`;
    }

    return `${currentTimeStr} / ${secondaryTimeStr}`;
  }, [currentTimeStr, secondaryTimeStr, isLiveContent, showRemaining]);

  // Aria label for accessibility
  const finalAriaLabel = useMemo(() => {
    if (ariaLabel) {
      return ariaLabel;
    }

    if (isLiveContent) {
      return 'Live stream';
    }

    if (showRemaining) {
      return `Time remaining: ${secondaryTimeStr}`;
    }

    return `Duration: ${secondaryTimeStr}`;
  }, [ariaLabel, isLiveContent, showRemaining, secondaryTimeStr]);

  return (
    <time
      className={className}
      aria-label={finalAriaLabel}
      style={{
        fontFamily: tokens.typography.fontFamily.mono,
        fontSize: tokens.typography.fontSize.sm,
        color: tokens.colors.text.secondary,
        userSelect: 'none',
      }}
      data-testid="time-display"
      title={displayString}
    >
      {displayString}
    </time>
  );
};

export default TimeDisplay;

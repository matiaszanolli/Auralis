/**
 * ProgressBar Component
 * ~~~~~~~~~~~~~~~~~~~~~
 *
 * Shows current playback position and duration with seek slider.
 * Interactive scrubbing for track seeking.
 *
 * Usage:
 * ```typescript
 * <ProgressBar />
 * ```
 *
 * Props: None required (uses hooks internally)
 *
 * @module components/player/ProgressBar
 */

import React, { useCallback, useState } from 'react';
import { tokens } from '@/design-system/tokens';
import { usePlaybackState, usePlaybackPosition } from '@/hooks/player/usePlaybackState';
import { useSeekControl } from '@/hooks/player/usePlaybackControl';
import { formatDuration } from '@/types/domain';

/**
 * ProgressBar component
 *
 * Displays seekable progress slider with time display.
 * Shows current position and total duration.
 * Handles user seeking with optimistic UI updates.
 */
export const ProgressBar: React.FC = () => {
  const { position, duration } = usePlaybackPosition();
  const { seek, isLoading } = useSeekControl();
  const [isDragging, setIsDragging] = useState(false);
  const [dragPosition, setDragPosition] = useState(position);

  /**
   * Calculate percentage for progress display
   */
  const percentage = duration > 0 ? (position / duration) * 100 : 0;
  const dragPercentage = duration > 0 ? (dragPosition / duration) * 100 : 0;

  /**
   * Handle slider input change (dragging)
   */
  const handleSliderChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      setIsDragging(true);
      const newPosition = parseFloat(e.target.value);
      setDragPosition(newPosition);
    },
    []
  );

  /**
   * Handle slider release (stop dragging, commit seek)
   */
  const handleSliderRelease = useCallback(async () => {
    setIsDragging(false);

    try {
      await seek(dragPosition);
    } catch (err) {
      console.error('Failed to seek:', err);
      // Reset to current position on error
      setDragPosition(position);
    }
  }, [dragPosition, position, seek]);

  /**
   * Handle mouse down to start tracking drag
   */
  const handleMouseDown = useCallback(() => {
    setIsDragging(true);
  }, []);

  return (
    <div style={styles.container}>
      {/* Time display (current / total) */}
      <div style={styles.timeDisplay}>
        <span style={styles.time}>{formatDuration(isDragging ? dragPosition : position)}</span>
        <span style={styles.separator}>/</span>
        <span style={styles.time}>{formatDuration(duration)}</span>
      </div>

      {/* Progress slider */}
      <div style={styles.sliderContainer}>
        <input
          type="range"
          min="0"
          max={Math.ceil(duration) || 0}
          value={isDragging ? dragPosition : position}
          onChange={handleSliderChange}
          onMouseDown={handleMouseDown}
          onMouseUp={handleSliderRelease}
          onTouchStart={handleMouseDown}
          onTouchEnd={handleSliderRelease}
          disabled={duration === 0 || isLoading}
          style={{
            ...styles.slider,
            background: `linear-gradient(to right, ${tokens.colors.accent.primary} 0%, ${tokens.colors.accent.primary} ${isDragging ? dragPercentage : percentage}%, ${tokens.colors.bg.tertiary} ${isDragging ? dragPercentage : percentage}%, ${tokens.colors.bg.tertiary} 100%)`,
          }}
          aria-label="Seek slider"
          title={`${isDragging ? dragPercentage.toFixed(1) : percentage.toFixed(1)}%`}
        />
      </div>

      {/* Optional: Buffered progress indicator */}
      {false && (
        <div style={styles.bufferedIndicator}>
          <div style={styles.bufferedBar} />
        </div>
      )}
    </div>
  );
};

/**
 * Component styles using design tokens
 */
const styles = {
  container: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: tokens.spacing.sm,
    padding: `${tokens.spacing.sm} 0`,
    width: '100%',
  },

  timeDisplay: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    fontSize: tokens.typography.fontSize.xs,
    color: tokens.colors.text.secondary,
    paddingX: tokens.spacing.sm,
  },

  time: {
    fontFamily: tokens.typography.fontFamily.monospace,
    fontWeight: tokens.typography.fontWeight.bold,
  },

  separator: {
    margin: `0 ${tokens.spacing.xs}`,
  },

  sliderContainer: {
    display: 'flex',
    alignItems: 'center',
    width: '100%',
    paddingX: tokens.spacing.xs,
  },

  slider: {
    width: '100%',
    height: '6px',
    cursor: 'pointer',
    appearance: 'none' as const,
    WebkitAppearance: 'none' as const,
    borderRadius: tokens.borderRadius.full,
    border: 'none',
    outline: 'none',
    WebkitSliderThumb: {
      appearance: 'none' as const,
      WebkitAppearance: 'none' as const,
      width: '14px',
      height: '14px',
      borderRadius: tokens.borderRadius.full,
      backgroundColor: tokens.colors.accent.primary,
      cursor: 'pointer',
      boxShadow: `0 0 4px ${tokens.colors.shadow.md}`,
    },
  },

  bufferedIndicator: {
    display: 'flex',
    alignItems: 'center',
    width: '100%',
    height: '2px',
    backgroundColor: tokens.colors.bg.tertiary,
    borderRadius: tokens.borderRadius.full,
  },

  bufferedBar: {
    height: '100%',
    backgroundColor: tokens.colors.text.secondary,
    borderRadius: tokens.borderRadius.full,
    width: '0%', // Will be set dynamically
  },
};

export default ProgressBar;

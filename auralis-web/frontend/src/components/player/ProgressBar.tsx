/**
 * ProgressBar - Interactive progress timeline with seeking capability
 *
 * Provides draggable/clickable progress indicator with buffered range visualization
 * and hover time tooltip. Core component for track position control.
 *
 * @component
 * @example
 * <ProgressBar
 *   currentTime={90}
 *   duration={225}
 *   bufferedPercentage={75}
 *   onSeek={(position) => console.log(`Seek to ${position}s`)}
 * />
 */

import React, { useRef, useCallback, useState, useMemo } from 'react';
import { formatSecondToTime } from '@/hooks/usePlayerDisplay';
import { tokens } from '@/design-system';

export interface ProgressBarProps {
  /**
   * Current playback position in seconds
   */
  currentTime: number;

  /**
   * Total track duration in seconds
   */
  duration: number;

  /**
   * Percentage of audio that has been buffered (0-100)
   * Default: 0
   */
  bufferedPercentage?: number;

  /**
   * Callback when user seeks to a position (in seconds)
   */
  onSeek: (position: number) => void;

  /**
   * Disable interaction and seeking
   * Default: false
   */
  disabled?: boolean;

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
 * ProgressBar Component
 *
 * Renders an interactive timeline with seeking capability, buffered range,
 * and hover time preview.
 */
export const ProgressBar: React.FC<ProgressBarProps> = ({
  currentTime,
  duration,
  bufferedPercentage = 0,
  onSeek,
  disabled = false,
  className = '',
  ariaLabel,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [isHovering, setIsHovering] = useState(false);
  const [hoverPosition, setHoverPosition] = useState(0);
  const [isDragging, setIsDragging] = useState(false);

  // Calculate progress percentage
  const progressPercentage = useMemo(() => {
    if (!Number.isFinite(duration) || duration <= 0) {
      return 0;
    }
    const percentage = (currentTime / duration) * 100;
    return Math.min(Math.max(percentage, 0), 100);
  }, [currentTime, duration]);

  // Clamp buffered percentage
  const clampedBufferedPercentage = useMemo(() => {
    return Math.min(Math.max(bufferedPercentage, 0), 100);
  }, [bufferedPercentage]);

  // Format hover time
  const hoverTimeStr = useMemo(() => {
    return formatSecondToTime(hoverPosition, duration >= 3600);
  }, [hoverPosition, duration]);

  // Handle mouse position calculation
  const getPositionFromEvent = useCallback(
    (event: React.MouseEvent | MouseEvent) => {
      if (!containerRef.current) return currentTime;

      const rect = containerRef.current.getBoundingClientRect();
      const x = ('clientX' in event ? event.clientX : event.pageX) - rect.left;
      const percentage = Math.max(0, Math.min(1, x / rect.width));
      return percentage * duration;
    },
    [duration, currentTime]
  );

  // Handle click to seek
  const handleClick = useCallback(
    (event: React.MouseEvent<HTMLDivElement>) => {
      if (disabled || !Number.isFinite(duration) || duration <= 0) {
        return;
      }

      const position = getPositionFromEvent(event);
      onSeek(position);
    },
    [disabled, duration, getPositionFromEvent, onSeek]
  );

  // Handle mouse move for hover preview
  const handleMouseMove = useCallback(
    (event: React.MouseEvent<HTMLDivElement>) => {
      if (disabled || !containerRef.current) {
        return;
      }

      const position = getPositionFromEvent(event);
      setHoverPosition(position);
    },
    [disabled, getPositionFromEvent]
  );

  // Handle drag start
  const handleMouseDown = useCallback(
    (event: React.MouseEvent<HTMLDivElement>) => {
      if (disabled || !Number.isFinite(duration) || duration <= 0) {
        return;
      }

      setIsDragging(true);
      const position = getPositionFromEvent(event);
      onSeek(position);
    },
    [disabled, duration, getPositionFromEvent, onSeek]
  );

  // Handle drag during mouse move
  const handleGlobalMouseMove = useCallback(
    (event: MouseEvent) => {
      if (!isDragging || !containerRef.current) {
        return;
      }

      const position = getPositionFromEvent(event);
      onSeek(position);
    },
    [isDragging, getPositionFromEvent, onSeek]
  );

  // Handle drag end
  const handleGlobalMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  // Set up global event listeners during drag
  React.useEffect(() => {
    if (!isDragging) {
      return;
    }

    document.addEventListener('mousemove', handleGlobalMouseMove);
    document.addEventListener('mouseup', handleGlobalMouseUp);

    return () => {
      document.removeEventListener('mousemove', handleGlobalMouseMove);
      document.removeEventListener('mouseup', handleGlobalMouseUp);
    };
  }, [isDragging, handleGlobalMouseMove, handleGlobalMouseUp]);

  // Aria label
  const finalAriaLabel = useMemo(() => {
    if (ariaLabel) {
      return ariaLabel;
    }
    return `Progress: ${formatSecondToTime(currentTime, duration >= 3600)} of ${formatSecondToTime(duration, duration >= 3600)}`;
  }, [ariaLabel, currentTime, duration]);

  return (
    <div
      className={className}
      data-testid="progress-bar"
      style={{
        position: 'relative',
        width: '100%',
      }}
    >
      {/* Main progress bar container */}
      <div
        ref={containerRef}
        role="slider"
        aria-label={finalAriaLabel}
        aria-valuemin={0}
        aria-valuemax={Math.round(duration)}
        aria-valuenow={Math.round(currentTime)}
        aria-disabled={disabled}
        onMouseEnter={() => setIsHovering(true)}
        onMouseLeave={() => setIsHovering(false)}
        onMouseMove={handleMouseMove}
        onClick={handleClick}
        onMouseDown={handleMouseDown}
        style={{
          position: 'relative',
          height: '24px',
          cursor: disabled ? 'default' : 'pointer',
          padding: '8px 0',
          userSelect: 'none',
        }}
        data-testid="progress-bar-container"
      >
        {/* Background/track */}
        <div
          style={{
            position: 'absolute',
            top: '50%',
            transform: 'translateY(-50%)',
            width: '100%',
            height: '4px',
            backgroundColor: tokens.colors.bg.tertiary,
            borderRadius: '2px',
            overflow: 'hidden',
          }}
          data-testid="progress-bar-track"
        >
          {/* Buffered range */}
          <div
            style={{
              position: 'absolute',
              height: '100%',
              width: `${clampedBufferedPercentage}%`,
              backgroundColor: tokens.colors.accent.secondary,
              transition: isDragging ? 'none' : 'width 0.1s ease-out',
            }}
            data-testid="progress-bar-buffered"
          />

          {/* Played range */}
          <div
            style={{
              position: 'absolute',
              height: '100%',
              width: `${progressPercentage}%`,
              backgroundColor: tokens.colors.accent.primary,
              transition: isDragging ? 'none' : 'width 0.1s ease-out',
            }}
            data-testid="progress-bar-played"
          />
        </div>

        {/* Draggable thumb */}
        <div
          style={{
            position: 'absolute',
            top: '50%',
            left: `${progressPercentage}%`,
            transform: 'translate(-50%, -50%)',
            width: isDragging ? '14px' : '10px',
            height: isDragging ? '14px' : '10px',
            backgroundColor: tokens.colors.accent.primary,
            borderRadius: '50%',
            boxShadow: isDragging ? `0 0 8px ${tokens.colors.accent.primary}` : 'none',
            transition: 'all 0.1s ease-out',
            pointerEvents: 'none',
          }}
          data-testid="progress-bar-thumb"
        />

        {/* Hover time tooltip */}
        {isHovering && !disabled && (
          <div
            style={{
              position: 'absolute',
              top: '-30px',
              left: `${Math.min(Math.max((hoverPosition / duration) * 100, 0), 100)}%`,
              transform: 'translateX(-50%)',
              backgroundColor: tokens.colors.bg.secondary,
              color: tokens.colors.text.primary,
              padding: `${tokens.spacing.xs} ${tokens.spacing.sm}`,
              borderRadius: '4px',
              fontSize: tokens.typography.fontSize.xs,
              fontFamily: tokens.typography.fontFamilyMono,
              whiteSpace: 'nowrap',
              pointerEvents: 'none',
              border: `1px solid ${tokens.colors.border.medium}`,
              zIndex: 1000,
            }}
            data-testid="progress-bar-tooltip"
          >
            {hoverTimeStr}
          </div>
        )}
      </div>
    </div>
  );
};

export default ProgressBar;

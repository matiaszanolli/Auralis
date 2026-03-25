/**
 * ProgressBar - Interactive progress timeline with seeking, buffered range, and hover tooltip.
 */

import React, { useRef, useCallback, useState, useMemo } from 'react';
import { formatSecondToTime } from '@/hooks/player/usePlayerDisplay';
import { progressBarStyles as pbs } from './ProgressBar.styles';

export interface ProgressBarProps {
  currentTime: number;
  duration: number;
  bufferedPercentage?: number;
  onSeek: (position: number) => void;
  disabled?: boolean;
  className?: string;
  ariaLabel?: string;
}
export const ProgressBar = ({
  currentTime,
  duration,
  bufferedPercentage = 0,
  onSeek,
  disabled = false,
  className = '',
  ariaLabel,
}: ProgressBarProps) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [isHovering, setIsHovering] = useState(false);
  const [hoverPosition, setHoverPosition] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  const [isFocused, setIsFocused] = useState(false);
  // Live position during drag — throttled to ~4Hz for ARIA announcements (fixes #2538)
  const [liveSeekTime, setLiveSeekTime] = useState<number | null>(null);
  const lastAriaAnnounceRef = useRef<number>(0);

  // Stable refs for values used in drag handlers to avoid recreating
  // callbacks on every playback tick (#3103)
  const durationRef = useRef(duration);
  durationRef.current = duration;
  const currentTimeRef = useRef(currentTime);
  currentTimeRef.current = currentTime;
  const onSeekRef = useRef(onSeek);
  onSeekRef.current = onSeek;

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

  // Handle mouse position calculation (stable — reads from refs)
  const getPositionFromEvent = useCallback(
    (event: React.MouseEvent | MouseEvent) => {
      if (!containerRef.current) return currentTimeRef.current;

      const rect = containerRef.current.getBoundingClientRect();
      const x = ('clientX' in event ? event.clientX : (event as MouseEvent).pageX) - rect.left;
      const percentage = Math.max(0, Math.min(1, x / rect.width));
      return percentage * durationRef.current;
    },
    []
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

  // Handle drag during mouse move (stable — reads from refs)
  const handleGlobalMouseMove = useCallback(
    (event: MouseEvent) => {
      if (!containerRef.current) return;

      const position = getPositionFromEvent(event);
      onSeekRef.current(position);

      // Throttle ARIA live region updates to ~4Hz during drag (fixes #2538)
      const now = Date.now();
      if (now - lastAriaAnnounceRef.current >= 250) {
        lastAriaAnnounceRef.current = now;
        setLiveSeekTime(position);
      }
    },
    [getPositionFromEvent]
  );

  // Handle drag end
  const handleGlobalMouseUp = useCallback(() => {
    setIsDragging(false);
    setLiveSeekTime(null);
  }, []);

  // Handle keyboard navigation
  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLDivElement>) => {
      if (disabled || !Number.isFinite(duration) || duration <= 0) {
        return;
      }

      const STEP = 1; // 1 second per arrow key
      let newPosition: number | null = null;

      switch (event.key) {
        case 'ArrowLeft':
        case 'ArrowDown':
          event.preventDefault();
          newPosition = Math.max(0, currentTime - STEP);
          break;
        case 'ArrowRight':
        case 'ArrowUp':
          event.preventDefault();
          newPosition = Math.min(duration, currentTime + STEP);
          break;
        case 'Home':
          event.preventDefault();
          newPosition = 0;
          break;
        case 'End':
          event.preventDefault();
          newPosition = duration;
          break;
        default:
          return;
      }

      if (newPosition !== null) {
        onSeek(newPosition);
      }
    },
    [disabled, duration, currentTime, onSeek]
  );

  // Handle touch start
  const handleTouchStart = useCallback(
    (event: React.TouchEvent<HTMLDivElement>) => {
      if (disabled || !Number.isFinite(duration) || duration <= 0) {
        return;
      }

      setIsDragging(true);
      const touch = event.touches[0];
      if (!touch || !containerRef.current) return;

      const rect = containerRef.current.getBoundingClientRect();
      const x = touch.clientX - rect.left;
      const percentage = Math.max(0, Math.min(1, x / rect.width));
      const position = percentage * duration;
      onSeek(position);
    },
    [disabled, duration, onSeek]
  );

  // Handle touch move
  const handleTouchMove = useCallback(
    (event: React.TouchEvent<HTMLDivElement>) => {
      if (!isDragging || !containerRef.current) {
        return;
      }

      event.preventDefault();
      const touch = event.touches[0];
      if (!touch) return;

      const rect = containerRef.current.getBoundingClientRect();
      const x = touch.clientX - rect.left;
      const percentage = Math.max(0, Math.min(1, x / rect.width));
      const position = percentage * duration;
      onSeek(position);

      // Throttle ARIA live region updates to ~4Hz during touch drag (fixes #2538)
      const now = Date.now();
      if (now - lastAriaAnnounceRef.current >= 250) {
        lastAriaAnnounceRef.current = now;
        setLiveSeekTime(position);
      }
    },
    [isDragging, duration, onSeek]
  );

  // Handle touch end
  const handleTouchEnd = useCallback(() => {
    setIsDragging(false);
    setLiveSeekTime(null);
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
  }, [isDragging, handleGlobalMouseMove, handleGlobalMouseUp]); // handlers are stable (empty/minimal deps)

  // Aria labels and values
  const finalAriaLabel = useMemo(() => {
    if (ariaLabel) {
      return ariaLabel;
    }
    return `Track progress slider. Use arrow keys to seek.`;
  }, [ariaLabel]);

  const ariaValueText = useMemo(() => {
    return `${formatSecondToTime(currentTime, duration >= 3600)} of ${formatSecondToTime(duration, duration >= 3600)}`;
  }, [currentTime, duration]);

  return (
    <div className={className} data-testid="progress-bar" style={pbs.wrapper}>
      {/* Screen-reader live region — announces position during drag/touch (fixes #2538) */}
      <div aria-live="assertive" aria-atomic="true" style={pbs.srOnly}>
        {liveSeekTime !== null
          ? `Seeking to ${formatSecondToTime(liveSeekTime, duration >= 3600)}`
          : ''}
      </div>

      {/* Main progress bar container */}
      <div
        ref={containerRef}
        role="slider"
        tabIndex={disabled ? -1 : 0}
        aria-label={finalAriaLabel}
        aria-valuemin={0}
        aria-valuemax={Math.round(duration)}
        aria-valuenow={Math.round(currentTime)}
        aria-valuetext={ariaValueText}
        aria-disabled={disabled}
        onMouseEnter={() => setIsHovering(true)}
        onMouseLeave={() => setIsHovering(false)}
        onMouseMove={handleMouseMove}
        onClick={handleClick}
        onMouseDown={handleMouseDown}
        onTouchStart={handleTouchStart}
        onTouchMove={handleTouchMove}
        onTouchEnd={handleTouchEnd}
        onKeyDown={handleKeyDown}
        onFocus={() => setIsFocused(true)}
        onBlur={() => setIsFocused(false)}
        style={pbs.container(disabled, isFocused)}
        data-testid="progress-bar-container"
      >
        {/* Background/track */}
        <div style={pbs.track} data-testid="progress-bar-track">
          {/* Buffered range */}
          <div
            style={pbs.bufferedRange(clampedBufferedPercentage, isDragging)}
            data-testid="progress-bar-buffered"
          />
          {/* Played range */}
          <div
            style={pbs.playedRange(progressPercentage, isDragging)}
            data-testid="progress-bar-played"
          />
        </div>

        {/* Draggable thumb */}
        <div
          style={pbs.thumb(progressPercentage, isDragging)}
          data-testid="progress-bar-thumb"
        />

        {/* Hover time tooltip */}
        {isHovering && !disabled && (
          <div
            style={pbs.tooltip((hoverPosition / duration) * 100)}
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

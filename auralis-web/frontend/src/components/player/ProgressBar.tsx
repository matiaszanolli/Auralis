/**
 * ProgressBar - Interactive progress timeline with seeking, buffered range, and hover tooltip.
 */

import { useMemo } from 'react';
import { formatSecondToTime } from '@/hooks/player/usePlayerDisplay';
import { progressBarStyles as pbs } from './ProgressBar.styles';
import { useProgressBarInteraction } from './useProgressBarInteraction';

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
  const {
    containerRef,
    isHovering,
    setIsHovering,
    hoverPosition,
    isDragging,
    isFocused,
    setIsFocused,
    liveSeekTime,
    progressPercentage,
    handleClick,
    handleMouseMove,
    handleMouseDown,
    handleKeyDown,
    handleTouchStart,
    handleTouchMove,
    handleTouchEnd,
  } = useProgressBarInteraction({ currentTime, duration, onSeek, disabled });

  // Clamp buffered percentage
  const clampedBufferedPercentage = useMemo(() => {
    return Math.min(Math.max(bufferedPercentage, 0), 100);
  }, [bufferedPercentage]);

  // Format hover time
  const hoverTimeStr = useMemo(() => {
    return formatSecondToTime(hoverPosition, duration >= 3600);
  }, [hoverPosition, duration]);

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
      {/* Screen-reader live region — announces position during drag/touch (fixes #2538).
          #3651: changed from aria-live="assertive" to "polite" — seeking is not an
          urgent interruption; assertive should be reserved for errors. */}
      <div aria-live="polite" aria-atomic="true" style={pbs.srOnly}>
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

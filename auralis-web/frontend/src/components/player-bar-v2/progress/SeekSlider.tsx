/**
 * SeekSlider - Interactive seeking slider with preview
 *
 * Responsibility: Handle seeking interaction and display slider UI
 *
 * Extracted from ProgressBar to:
 * - Make seeking logic testable in isolation
 * - Enable seeking behavior customization
 * - Separate interaction from visualization
 * - Allow smooth seeking without affecting other progress bar components
 */

import React from 'react';
import { formatTime } from '@/utils/timeFormat';
import { SliderContainer, StyledSlider } from './SeekSlider.styles';
import useSeekControls from './useSeekControls';

interface SeekSliderProps {
  currentTime: number;
  duration: number;
  onSeek: (time: number) => void;
  children?: React.ReactNode; // For overlaid CrossfadeVisualization
}

/**
 * SeekSlider - Interactive slider for seeking through track
 *
 * Features:
 * - Smooth dragging with preview
 * - Accessible with proper ARIA labels
 * - Visual feedback on hover/focus
 * - Value label showing seek time
 *
 * @example
 * <SeekSlider
 *   currentTime={45.32}
 *   duration={295}
 *   onSeek={(time) => player.seek(time)}
 * />
 */
export const SeekSlider: React.FC<SeekSliderProps> = React.memo(({ currentTime, duration, onSeek, children }) => {
  const { handleSeekStart, handleSeekChange, handleSeekEnd, seekPreview } = useSeekControls({
    onSeek,
  });

  // Display time (preview during seek, current otherwise)
  const displayTime = seekPreview !== null ? seekPreview : currentTime;

  return (
    <SliderContainer>
      {/* Optional overlay for crossfade visualization */}
      {children}

      {/* Progress slider */}
      <StyledSlider
        value={displayTime}
        min={0}
        max={duration || 100}
        step={0.1}
        onMouseDown={handleSeekStart}
        onChange={handleSeekChange}
        onChangeCommitted={handleSeekEnd}
        valueLabelDisplay="auto"
        valueLabelFormat={formatTime}
        aria-label="Seek"
        aria-valuetext={`${formatTime(displayTime)} of ${formatTime(duration)}`}
      />
    </SliderContainer>
  );
});

SeekSlider.displayName = 'SeekSlider';

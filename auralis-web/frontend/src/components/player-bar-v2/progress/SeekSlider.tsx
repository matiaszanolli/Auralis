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

import React, { useState, useCallback } from 'react';
import { Box, Slider, styled } from '@mui/material';
import { tokens } from '@/design-system/tokens';
import { formatTime } from '@/utils/timeFormat';

const SliderContainer = styled(Box)({
  flex: 1,
  position: 'relative'
});

const StyledSlider = styled(Slider)({
  color: tokens.colors.accent.primary,
  height: 6,
  padding: '8px 0',

  '& .MuiSlider-track': {
    border: 'none',
    background: tokens.gradients.aurora,
    height: 6
  },

  '& .MuiSlider-rail': {
    backgroundColor: tokens.colors.bg.elevated,
    opacity: 1,
    height: 6
  },

  '& .MuiSlider-thumb': {
    height: 16,
    width: 16,
    backgroundColor: tokens.colors.text.primary,
    border: `2px solid ${tokens.colors.accent.primary}`,
    boxShadow: tokens.shadows.glow,
    transition: tokens.transitions.all,

    '&:hover, &.Mui-focusVisible': {
      boxShadow: tokens.shadows.glowStrong,
      transform: 'scale(1.2)'
    },

    '&.Mui-active': {
      boxShadow: tokens.shadows.glowStrong
    }
  },

  '& .MuiSlider-valueLabel': {
    fontFamily: tokens.typography.fontFamily.mono,
    fontSize: tokens.typography.fontSize.xs,
    background: tokens.colors.bg.secondary,
    borderRadius: tokens.borderRadius.sm,
    padding: `${tokens.spacing.xs} ${tokens.spacing.sm}`
  }
});

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
export const SeekSlider: React.FC<SeekSliderProps> = ({ currentTime, duration, onSeek, children }) => {
  const [isSeeking, setIsSeeking] = useState(false);
  const [seekPreview, setSeekPreview] = useState<number | null>(null);

  // Handle seek start
  const handleSeekStart = useCallback(() => {
    setIsSeeking(true);
  }, []);

  // Handle seek change (preview while dragging)
  const handleSeekChange = useCallback((event: Event, value: number | number[]) => {
    const time = Array.isArray(value) ? value[0] : value;
    setSeekPreview(time);
  }, []);

  // Handle seek end (commit the seek)
  const handleSeekEnd = useCallback((event: Event | React.SyntheticEvent, value: number | number[]) => {
    const time = Array.isArray(value) ? value[0] : value;
    setIsSeeking(false);
    setSeekPreview(null);
    onSeek(time);
  }, [onSeek]);

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
};

SeekSlider.displayName = 'SeekSlider';

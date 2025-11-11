/**
 * ProgressBar - Seek bar with crossfade visualization
 *
 * Features:
 * - Visual indicators for 5-second crossfade regions
 * - Smooth seeking that accounts for chunk overlap
 * - Time display (current / duration)
 * - Hover preview
 * - Design token styling
 */

import React, { useState, useCallback, useMemo } from 'react';
import { Box, Slider, Typography, styled } from '@mui/material';
import { tokens } from '@/design-system/tokens';

interface ProgressBarProps {
  currentTime: number;
  duration: number;
  onSeek: (time: number) => void;
  chunkDuration: number;  // 15s
  chunkInterval: number;  // 10s
}

const ProgressContainer = styled(Box)({
  display: 'flex',
  alignItems: 'center',
  gap: tokens.spacing.sm,
  width: '100%',
});

const TimeDisplay = styled(Typography)({
  fontFamily: tokens.typography.fontFamily.mono,
  fontSize: tokens.typography.fontSize.sm,
  color: tokens.colors.text.secondary,
  minWidth: '45px',
  textAlign: 'right',
});

const SliderContainer = styled(Box)({
  flex: 1,
  position: 'relative',
});

const CrossfadeIndicators = styled(Box)({
  position: 'absolute',
  top: 0,
  left: 0,
  right: 0,
  bottom: 0,
  pointerEvents: 'none',
  display: 'flex',
});

const CrossfadeRegion = styled(Box)({
  position: 'absolute',
  height: '100%',
  background: `linear-gradient(90deg,
    ${tokens.colors.accent.primary}20,
    ${tokens.colors.accent.tertiary}30,
    ${tokens.colors.accent.primary}20
  )`,
  borderLeft: `1px solid ${tokens.colors.accent.primary}40`,
  borderRight: `1px solid ${tokens.colors.accent.primary}40`,
  opacity: 0.6,
  transition: tokens.transitions.opacity,
  '&:hover': {
    opacity: 0.9,
  },
});

const StyledSlider = styled(Slider)({
  color: tokens.colors.accent.primary,
  height: 6,
  padding: '8px 0',

  '& .MuiSlider-track': {
    border: 'none',
    background: tokens.gradients.aurora,
    height: 6,
  },

  '& .MuiSlider-rail': {
    backgroundColor: tokens.colors.bg.elevated,
    opacity: 1,
    height: 6,
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
      transform: 'scale(1.2)',
    },

    '&.Mui-active': {
      boxShadow: tokens.shadows.glowStrong,
    },
  },

  '& .MuiSlider-valueLabel': {
    fontFamily: tokens.typography.fontFamily.mono,
    fontSize: tokens.typography.fontSize.xs,
    background: tokens.colors.bg.secondary,
    borderRadius: tokens.borderRadius.sm,
    padding: `${tokens.spacing.xs} ${tokens.spacing.sm}`,
  },
});

/**
 * Format time in MM:SS format
 */
function formatTime(seconds: number): string {
  if (!isFinite(seconds) || seconds < 0) return '0:00';

  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

/**
 * Calculate crossfade regions for visualization
 *
 * With 15s chunks every 10s:
 * - Chunk 0: [0-15s]
 * - Chunk 1: [10-25s] (crossfade: 10-15s)
 * - Chunk 2: [20-35s] (crossfade: 20-25s)
 * - etc.
 */
function getCrossfadeRegions(
  duration: number,
  chunkInterval: number,
  chunkDuration: number
): Array<{ start: number; end: number }> {
  const overlapDuration = chunkDuration - chunkInterval; // 5s
  const regions: Array<{ start: number; end: number }> = [];

  let chunkStart = chunkInterval; // First overlap starts at 10s

  while (chunkStart < duration) {
    const overlapStart = chunkStart;
    const overlapEnd = Math.min(chunkStart + overlapDuration, duration);

    regions.push({
      start: overlapStart,
      end: overlapEnd,
    });

    chunkStart += chunkInterval;
  }

  return regions;
}

export const ProgressBar: React.FC<ProgressBarProps> = React.memo(({
  currentTime,
  duration,
  onSeek,
  chunkDuration,
  chunkInterval,
}) => {
  const [isSeeking, setIsSeeking] = useState(false);
  const [seekPreview, setSeekPreview] = useState<number | null>(null);

  // Calculate crossfade regions
  const crossfadeRegions = useMemo(() => {
    return getCrossfadeRegions(duration, chunkInterval, chunkDuration);
  }, [duration, chunkInterval, chunkDuration]);

  // Handle seek start
  const handleSeekStart = useCallback(() => {
    setIsSeeking(true);
  }, []);

  // Handle seek change
  const handleSeekChange = useCallback((event: Event, value: number | number[]) => {
    const time = Array.isArray(value) ? value[0] : value;
    setSeekPreview(time);
  }, []);

  // Handle seek end
  const handleSeekEnd = useCallback((event: Event | React.SyntheticEvent, value: number | number[]) => {
    const time = Array.isArray(value) ? value[0] : value;
    setIsSeeking(false);
    setSeekPreview(null);
    onSeek(time);
  }, [onSeek]);

  // Display time (preview during seek, current otherwise)
  const displayTime = seekPreview !== null ? seekPreview : currentTime;

  return (
    <ProgressContainer>
      <TimeDisplay>{formatTime(displayTime)}</TimeDisplay>

      <SliderContainer>
        {/* Crossfade region indicators */}
        <CrossfadeIndicators>
          {crossfadeRegions.map((region, index) => {
            const leftPercent = (region.start / duration) * 100;
            const widthPercent = ((region.end - region.start) / duration) * 100;

            return (
              <CrossfadeRegion
                key={index}
                sx={{
                  left: `${leftPercent}%`,
                  width: `${widthPercent}%`,
                }}
                title={`Crossfade region ${formatTime(region.start)} - ${formatTime(region.end)}`}
              />
            );
          })}
        </CrossfadeIndicators>

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

      <TimeDisplay>{formatTime(duration)}</TimeDisplay>
    </ProgressContainer>
  );
});

ProgressBar.displayName = 'ProgressBar';

/**
 * CrossfadeVisualization - Visual indicators for chunk crossfade regions
 *
 * Responsibility: Render visual indicators showing where 5-second crossfade regions occur
 *
 * Extracted from ProgressBar to:
 * - Make crossfade logic testable in isolation
 * - Allow customization of crossfade styling
 * - Separate visualization from seeking logic
 * - Enable future enhancements (e.g., interactive crossfade adjustment)
 */

import React, { useMemo } from 'react';
import { Box, styled } from '@mui/material';
import { tokens } from '@/design-system/tokens';
import { formatTime } from '../../utils/timeFormat';

const CrossfadeIndicators = styled(Box)({
  position: 'absolute',
  top: 0,
  left: 0,
  right: 0,
  bottom: 0,
  pointerEvents: 'none',
  display: 'flex'
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
    opacity: 0.9
  }
});

interface CrossfadeRegionData {
  start: number;
  end: number;
}

interface CrossfadeVisualizationProps {
  duration: number;
  chunkDuration: number; // 15s
  chunkInterval: number; // 10s
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
): CrossfadeRegionData[] {
  const overlapDuration = chunkDuration - chunkInterval; // 5s
  const regions: CrossfadeRegionData[] = [];

  let chunkStart = chunkInterval; // First overlap starts at 10s

  while (chunkStart < duration) {
    const overlapStart = chunkStart;
    const overlapEnd = Math.min(chunkStart + overlapDuration, duration);

    regions.push({
      start: overlapStart,
      end: overlapEnd
    });

    chunkStart += chunkInterval;
  }

  return regions;
}

/**
 * CrossfadeVisualization - Renders visual regions showing chunk crossfades
 *
 * @example
 * <CrossfadeVisualization duration={295} chunkDuration={15} chunkInterval={10} />
 * // Renders regions at: 10-15s, 20-25s, 30-35s, ... indicating overlap areas
 */
export const CrossfadeVisualization: React.FC<CrossfadeVisualizationProps> = ({
  duration,
  chunkDuration,
  chunkInterval
}) => {
  const crossfadeRegions = useMemo(() => {
    return getCrossfadeRegions(duration, chunkInterval, chunkDuration);
  }, [duration, chunkInterval, chunkDuration]);

  return (
    <CrossfadeIndicators>
      {crossfadeRegions.map((region, index) => {
        const leftPercent = (region.start / duration) * 100;
        const widthPercent = ((region.end - region.start) / duration) * 100;

        return (
          <CrossfadeRegion
            key={index}
            sx={{
              left: `${leftPercent}%`,
              width: `${widthPercent}%`
            }}
            title={`Crossfade region ${formatTime(region.start)} - ${formatTime(region.end)}`}
          />
        );
      })}
    </CrossfadeIndicators>
  );
};

CrossfadeVisualization.displayName = 'CrossfadeVisualization';

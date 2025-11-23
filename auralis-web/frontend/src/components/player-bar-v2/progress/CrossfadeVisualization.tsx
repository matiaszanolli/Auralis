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
 *
 * @example
 * <CrossfadeVisualization duration={295} chunkDuration={15} chunkInterval={10} />
 * // Renders regions at: 10-15s, 20-25s, 30-35s, ... indicating overlap areas
 */

import React from 'react';
import { CrossfadeIndicators } from './CrossfadeVisualization.styles';
import { useCrossfadeRegions } from './useCrossfadeRegions';
import { CrossfadeRegionItem } from './CrossfadeRegionItem';

interface CrossfadeVisualizationProps {
  duration: number;
  chunkDuration: number; // 15s
  chunkInterval: number; // 10s
}

export const CrossfadeVisualization: React.FC<CrossfadeVisualizationProps> = ({
  duration,
  chunkDuration,
  chunkInterval
}) => {
  const crossfadeRegions = useCrossfadeRegions({
    duration,
    chunkDuration,
    chunkInterval,
  });

  return (
    <CrossfadeIndicators>
      {crossfadeRegions.map((region, index) => (
        <CrossfadeRegionItem
          key={index}
          region={region}
          duration={duration}
          index={index}
        />
      ))}
    </CrossfadeIndicators>
  );
};

CrossfadeVisualization.displayName = 'CrossfadeVisualization';

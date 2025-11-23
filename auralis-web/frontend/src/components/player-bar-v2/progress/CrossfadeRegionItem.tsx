import React from 'react';
import { CrossfadeRegion } from './CrossfadeVisualization.styles';
import { formatTime } from '@/utils/timeFormat';
import { CrossfadeRegionData } from './useCrossfadeRegions';

interface CrossfadeRegionItemProps {
  region: CrossfadeRegionData;
  duration: number;
  index: number;
}

/**
 * CrossfadeRegionItem - Single crossfade region visualization
 *
 * Displays:
 * - Styled region box positioned at correct percentage
 * - Tooltip showing time range of crossfade
 */
export const CrossfadeRegionItem: React.FC<CrossfadeRegionItemProps> = ({
  region,
  duration,
  index,
}) => {
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
};

export default CrossfadeRegionItem;

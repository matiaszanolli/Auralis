import { useMemo } from 'react';

export interface CrossfadeRegionData {
  start: number;
  end: number;
}

interface UseCrossfadeRegionsProps {
  duration: number;
  chunkDuration: number;
  chunkInterval: number;
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
 * useCrossfadeRegions - Calculate crossfade regions for audio chunks
 *
 * Memoizes crossfade region calculation to prevent unnecessary recalculations.
 */
export const useCrossfadeRegions = ({
  duration,
  chunkDuration,
  chunkInterval,
}: UseCrossfadeRegionsProps): CrossfadeRegionData[] => {
  return useMemo(() => {
    return getCrossfadeRegions(duration, chunkInterval, chunkDuration);
  }, [duration, chunkInterval, chunkDuration]);
};

import React from 'react';
import { Box } from '@mui/material';
import { TrackRowSkeleton } from './TrackRowSkeleton';

interface TrackListSkeletonProps {
  count?: number;
}

/**
 * TrackListSkeleton - Loading skeleton for track list
 *
 * Displays:
 * - Multiple track row skeletons in vertical list
 * - Configurable number of rows to display
 */
export const TrackListSkeleton: React.FC<TrackListSkeletonProps> = ({
  count = 8,
}) => {
  return (
    <Box>
      {Array.from({ length: count }).map((_, index) => (
        <TrackRowSkeleton key={index} />
      ))}
    </Box>
  );
};

export default TrackListSkeleton;

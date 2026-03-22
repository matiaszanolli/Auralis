import React from 'react';
import Grid2 from '@mui/material/Unstable_Grid2';
import { AlbumCardSkeleton } from './AlbumCardSkeleton';

interface LibraryGridSkeletonProps {
  count?: number;
}

/**
 * LibraryGridSkeleton - Loading skeleton for library grid
 *
 * Displays:
 * - Multiple album card skeletons in responsive grid layout
 * - Configurable number of cards to display
 */
export const LibraryGridSkeleton = ({
  count = 12,
}: LibraryGridSkeletonProps) => {
  return (
    <Grid2 container spacing={3}>
      {Array.from({ length: count }).map((_, index) => (
        <Grid2 xs={12} sm={6} md={4} lg={3} key={index}>
          <AlbumCardSkeleton />
        </Grid2>
      ))}
    </Grid2>
  );
};

export default LibraryGridSkeleton;

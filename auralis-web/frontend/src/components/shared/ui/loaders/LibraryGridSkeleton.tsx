import React from 'react';
import { Grid } from '@mui/material';
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
export const LibraryGridSkeleton: React.FC<LibraryGridSkeletonProps> = ({
  count = 12,
}) => {
  return (
    <Grid container spacing={3}>
      {Array.from({ length: count }).map((_, index) => (
        <Grid item xs={12} sm={6} md={4} lg={3} key={index}>
          <AlbumCardSkeleton />
        </Grid>
      ))}
    </Grid>
  );
};

export default LibraryGridSkeleton;

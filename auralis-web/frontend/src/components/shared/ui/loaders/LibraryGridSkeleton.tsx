
import Grid from '@mui/material/Grid';
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
    <Grid container spacing={3} aria-busy="true">
      {Array.from({ length: count }).map((_, index) => (
        <Grid
          key={index}
          size={{
            xs: 12,
            sm: 6,
            md: 4,
            lg: 3
          }}>
          <AlbumCardSkeleton />
        </Grid>
      ))}
    </Grid>
  );
};

export default LibraryGridSkeleton;

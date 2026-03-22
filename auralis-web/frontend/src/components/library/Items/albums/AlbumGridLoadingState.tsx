/**
 * AlbumGridLoadingState Component
 *
 * Displays loading skeletons while albums are being fetched
 */

import React from 'react';
import { Box, Skeleton } from '@mui/material';
import Grid2 from '@mui/material/Unstable_Grid2';

export const AlbumGridLoadingState = () => {
  return (
    <Box sx={{ p: 3 }}>
      <Grid2 container spacing={3}>
        {[...Array(12)].map((_, index) => (
          <Grid2 xs={12} sm={6} md={4} lg={3} key={index}>
            <Box>
              <Skeleton
                variant="rectangular"
                width="100%"
                height={200}
                sx={{ borderRadius: '8px', marginBottom: '12px' }}
              />
              <Skeleton variant="text" width="80%" />
              <Skeleton variant="text" width="60%" />
              <Skeleton variant="text" width="40%" />
            </Box>
          </Grid2>
        ))}
      </Grid2>
    </Box>
  );
};

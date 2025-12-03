/**
 * AlbumGridLoadingState Component
 *
 * Displays loading skeletons while albums are being fetched
 */

import React from 'react';
import { Box, Grid, Skeleton } from '@mui/material';

export const AlbumGridLoadingState: React.FC = () => {
  return (
    <Box sx={{ p: 3 }}>
      <Grid container spacing={3}>
        {[...Array(12)].map((_, index) => (
          <Grid item xs={12} sm={6} md={4} lg={3} key={index}>
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
          </Grid>
        ))}
      </Grid>
    </Box>
  );
};

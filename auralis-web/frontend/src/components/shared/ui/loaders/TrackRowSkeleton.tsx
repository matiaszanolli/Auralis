import React from 'react';
import { Box } from '@mui/material';
import { SkeletonBox } from '../../../library/Styles/Skeleton.styles';

/**
 * TrackRowSkeleton - Loading skeleton for track row
 *
 * Displays:
 * - Track number placeholder
 * - Track title placeholder
 * - Duration placeholder
 */
export const TrackRowSkeleton: React.FC = () => {
  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: 2,
        p: 1.5,
        borderRadius: '6px',
      }}
    >
      <SkeletonBox
        sx={{
          width: '32px',
          height: '16px',
          borderRadius: '4px',
        }}
      />
      <SkeletonBox
        sx={{
          width: '60%',
          height: '16px',
          borderRadius: '4px',
        }}
      />
      <Box sx={{ flex: 1 }} />
      <SkeletonBox
        sx={{
          width: '50px',
          height: '16px',
          borderRadius: '4px',
        }}
      />
    </Box>
  );
};

export default TrackRowSkeleton;

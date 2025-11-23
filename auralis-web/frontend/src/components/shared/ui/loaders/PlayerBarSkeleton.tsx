import React from 'react';
import { Box } from '@mui/material';
import { SkeletonBox } from '../library/Skeleton.styles';

/**
 * PlayerBarSkeleton - Loading skeleton for player bar
 *
 * Displays:
 * - Album artwork placeholder
 * - Track info (title, artist) placeholders
 * - Control buttons placeholders
 * - Volume slider placeholder
 */
export const PlayerBarSkeleton: React.FC = () => {
  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: 3,
        p: 2,
      }}
    >
      {/* Album art */}
      <SkeletonBox
        sx={{
          width: '64px',
          height: '64px',
          borderRadius: '6px',
        }}
      />

      {/* Track info */}
      <Box sx={{ flex: 1 }}>
        <SkeletonBox
          sx={{
            width: '200px',
            height: '18px',
            mb: 1,
            borderRadius: '4px',
          }}
        />
        <SkeletonBox
          sx={{
            width: '150px',
            height: '14px',
            borderRadius: '4px',
          }}
        />
      </Box>

      {/* Controls */}
      <Box sx={{ display: 'flex', gap: 2 }}>
        <SkeletonBox
          sx={{
            width: '48px',
            height: '48px',
            borderRadius: '50%',
          }}
        />
      </Box>

      {/* Volume */}
      <SkeletonBox
        sx={{
          width: '100px',
          height: '6px',
          borderRadius: '3px',
        }}
      />
    </Box>
  );
};

export default PlayerBarSkeleton;

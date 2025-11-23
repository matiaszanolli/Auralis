import React from 'react';
import { Box } from '@mui/material';
import { SkeletonBox } from '../../../library/Styles/Skeleton.styles';

/**
 * SidebarItemSkeleton - Loading skeleton for sidebar item
 *
 * Displays:
 * - Icon placeholder
 * - Item label placeholder
 */
export const SidebarItemSkeleton: React.FC = () => {
  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: 2,
        p: 1,
        mb: 1,
      }}
    >
      <SkeletonBox
        sx={{
          width: '24px',
          height: '24px',
          borderRadius: '6px',
        }}
      />
      <SkeletonBox
        sx={{
          width: '70%',
          height: '16px',
          borderRadius: '4px',
        }}
      />
    </Box>
  );
};

export default SidebarItemSkeleton;

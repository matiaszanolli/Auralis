import React from 'react';
import { Box, Grid } from '@mui/material';
import { SkeletonBox } from '../library/Skeleton.styles';

// Album Card Skeleton
export const AlbumCardSkeleton: React.FC = () => {
  return (
    <Box>
      <SkeletonBox
        sx={{
          width: '100%',
          paddingTop: '100%', // 1:1 aspect ratio
          borderRadius: '8px',
        }}
      />
      <SkeletonBox
        sx={{
          width: '80%',
          height: '20px',
          mt: 2,
          borderRadius: '4px',
        }}
      />
      <SkeletonBox
        sx={{
          width: '60%',
          height: '16px',
          mt: 1,
          borderRadius: '4px',
        }}
      />
    </Box>
  );
};

// Track Row Skeleton
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

// Library Grid Skeleton
interface LibraryGridSkeletonProps {
  count?: number;
}

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

// Track List Skeleton
interface TrackListSkeletonProps {
  count?: number;
}

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

// Sidebar Item Skeleton
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

// Player Bar Skeleton
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

// Generic Skeleton Component
interface SkeletonProps {
  width?: string | number;
  height?: string | number;
  borderRadius?: string | number;
  variant?: 'text' | 'rectangular' | 'circular';
}

export const Skeleton: React.FC<SkeletonProps> = ({
  width = '100%',
  height = '20px',
  borderRadius = '4px',
  variant = 'rectangular',
}) => {
  const getBorderRadius = () => {
    if (variant === 'circular') return '50%';
    if (variant === 'text') return '4px';
    return borderRadius;
  };

  return (
    <SkeletonBox
      sx={{
        width,
        height,
        borderRadius: getBorderRadius(),
      }}
    />
  );
};

export default Skeleton;

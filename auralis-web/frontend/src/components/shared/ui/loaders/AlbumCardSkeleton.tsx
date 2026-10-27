
import { Box } from '@mui/material';
import { SkeletonBox } from '@/components/library/Styles/Skeleton.styles';
import { tokens } from '@/design-system';

/**
 * AlbumCardSkeleton - Loading skeleton for album card
 *
 * Displays:
 * - Square aspect ratio placeholder
 * - Album title skeleton
 * - Artist name skeleton
 */
export const AlbumCardSkeleton = () => {
  return (
    <Box>
      <SkeletonBox
        sx={{
          width: '100%',
          paddingTop: '100%', // 1:1 aspect ratio
          borderRadius: tokens.borderRadius.sm,
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

export default AlbumCardSkeleton;

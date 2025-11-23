import React from 'react';
import { SkeletonBox } from '../library/Skeleton.styles';

interface SkeletonProps {
  width?: string | number;
  height?: string | number;
  borderRadius?: string | number;
  variant?: 'text' | 'rectangular' | 'circular';
}

/**
 * Skeleton - Generic loading skeleton with configurable variant
 *
 * Variants:
 * - text: Renders with 4px border radius for text lines
 * - rectangular: Standard rectangular skeleton with custom border radius
 * - circular: Renders with 50% border radius for avatar/icon placeholders
 *
 * @example
 * <Skeleton width="100%" height="20px" variant="text" />
 * <Skeleton width="64px" height="64px" variant="circular" />
 */
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

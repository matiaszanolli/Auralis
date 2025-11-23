/**
 * Skeleton Styles - Reusable skeleton loader and loading state styling
 *
 * Consolidates skeleton component styling and shimmer/pulse animations
 * used for loading states across image components, progressive loaders,
 * and other loading placeholders.
 *
 * Border radius values are imported from BorderRadius.styles.ts.
 *
 * Variants:
 * - SkeletonBox: Base shimmer animation for skeleton elements
 * - PulsingBox: Opacity pulse animation for icon/text loaders
 */

import { Box, styled } from '@mui/material';
import { tokens } from '@/design-system/tokens';
import { shimmer, pulse } from './Animation.styles';
import { radiusMedium } from './BorderRadius.styles';

/**
 * SkeletonBox - Base skeleton element with shimmer animation
 * Used for all skeleton loaders (album cards, track rows, etc.)
 * Features: gradient shimmer, configurable border radius
 */
export const SkeletonBox = styled(Box)({
  background: `linear-gradient(
    90deg,
    ${tokens.colors.bg.surface} 0%,
    ${tokens.colors.bg.hover} 50%,
    ${tokens.colors.bg.surface} 100%
  )`,
  backgroundSize: '1000px 100%',
  animation: `${shimmer} 2s infinite linear`,
  borderRadius: radiusMedium,
});

/**
 * PulsingBox - Box with opacity pulse animation
 * Used for loading state icons and text indicators
 * Features: fades in/out smoothly over 2 seconds
 */
export const PulsingBox = styled(Box)({
  animation: `${pulse} 2s ease-in-out infinite`,
});

/**
 * SkeletonContainer - Container for skeleton elements (image load state)
 * Positioned absolutely to overlay loading state
 */
export const SkeletonContainer = styled(Box)({
  position: 'absolute',
  top: 0,
  left: 0,
  width: '100%',
  height: '100%',
});

/**
 * ImageLoadingContainer - Container for image loading state
 * Used by ProgressiveImage component
 */
export const ImageLoadingContainer = styled(Box)({
  position: 'relative',
  overflow: 'hidden',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  flexShrink: 0,
});

/**
 * LoadingIconContainer - Container for loading state icon
 * Used by enhancement pane and processing feedback
 * Features: centered flex layout for icons
 */
export const LoadingIconContainer = styled(Box)({
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  gap: '16px',
});

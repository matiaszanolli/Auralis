/**
 * Skeleton Styles - Reusable skeleton loader and loading state styling
 *
 * Consolidates skeleton component styling and the shimmer animation
 * used for loading states across image components, progressive loaders,
 * and other loading placeholders.
 *
 * Border radius values are imported from BorderRadius.styles.ts.
 *
 * Variants:
 * - SkeletonBox: Base shimmer animation for skeleton elements
 */

import { Box, styled } from '@mui/material';
import { themeVars } from '@/theme/semanticTheme';
import { shimmer } from './Animation.styles';
import { radiusMedium } from './BorderRadius.styles';

/**
 * SkeletonBox - Base skeleton element with shimmer animation
 * Used for all skeleton loaders (album cards, track rows, etc.)
 * Features: gradient shimmer, configurable border radius
 */
export const SkeletonBox = styled(Box)({
  background: `linear-gradient(
    90deg,
    ${themeVars.surfaceSecondary} 0%,
    ${themeVars.surfaceOverlay} 50%,
    ${themeVars.surfaceSecondary} 100%
  )`,
  backgroundSize: '1000px 100%',
  animation: `${shimmer} 2s infinite linear`,
  borderRadius: radiusMedium,
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

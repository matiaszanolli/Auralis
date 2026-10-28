/**
 * Spinner Styles - Reusable loading spinner styling
 *
 * Consolidates CSS-based spinner styling used across multiple components.
 * Provides consistent loading state UI with animation.
 */

import { Box, styled } from '@mui/material';

/**
 * SpinnerBox - CSS-animated loading spinner
 * Used as a lightweight alternative to CircularProgress
 * Can be wrapped with optional text label
 */
export const SpinnerBox = styled(Box)({
  width: 20,
  height: 20,
  border: '2px solid',
  borderColor: 'primary.main',
  borderRightColor: 'transparent',
  borderRadius: '50%',
  animation: 'spin 1s linear infinite', // keyframes: styles/globalKeyframes.ts (#6022)
});

export default SpinnerBox;

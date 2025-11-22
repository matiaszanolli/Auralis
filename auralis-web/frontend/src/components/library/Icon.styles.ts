/**
 * Icon Styles - Reusable icon and icon button styling
 *
 * Consolidates icon sizing patterns and icon button variants used across
 * player controls, action buttons, and decorative icons.
 *
 * Icon Button Sizes:
 * - SmallIconButton: 32px (secondary actions, compact)
 * - MediumIconButton: 40px (standard list actions)
 * - LargeIconButton: 56px (primary player controls)
 *
 * Icon Sizes (for use with sx prop):
 * - xs: 16px (dense UI)
 * - sm: 20px (standard)
 * - md: 24px (medium)
 * - lg: 32px (large)
 * - xl: 48px (extra large)
 * - xxl: 64px (huge)
 */

import { Box, IconButton, styled } from '@mui/material';

/**
 * SmallIconButton - Compact icon button (32px)
 * Used for secondary actions in track rows, compact menus
 */
export const SmallIconButton = styled(IconButton)({
  width: '32px',
  height: '32px',
  minWidth: '32px',
  minHeight: '32px',
  padding: '4px',
  flexShrink: 0,

  '& .MuiSvgIcon-root': {
    fontSize: '20px',
  },
});

/**
 * MediumIconButton - Standard icon button (40px)
 * Used for standard actions in lists, tables, album art
 */
export const MediumIconButton = styled(IconButton)({
  width: '40px',
  height: '40px',
  minWidth: '40px',
  minHeight: '40px',
  padding: '6px',
  flexShrink: 0,

  '& .MuiSvgIcon-root': {
    fontSize: '24px',
  },
});

/**
 * LargeIconButton - Primary action button (56px)
 * Used for main player controls (play/pause)
 */
export const LargeIconButton = styled(IconButton)({
  width: '56px',
  height: '56px',
  minWidth: '56px',
  minHeight: '56px',
  padding: '8px',
  flexShrink: 0,

  '& .MuiSvgIcon-root': {
    fontSize: '32px',
  },
});

/**
 * IconBox - Container for decorative icons with sizing variants
 * Used for empty states, loading indicators, etc.
 * Apply icon size using fontSize prop: 16, 20, 24, 32, 48, 64
 */
export const IconBox = styled(Box)({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  flexShrink: 0,
});

/**
 * Icon Size Presets (use with sx prop)
 * Example: <MyIcon sx={iconSizes.lg} />
 */
export const iconSizes = {
  xs: { fontSize: '16px' },
  sm: { fontSize: '20px' },
  md: { fontSize: '24px' },
  lg: { fontSize: '32px' },
  xl: { fontSize: '48px' },
  xxl: { fontSize: '64px' },
} as const;

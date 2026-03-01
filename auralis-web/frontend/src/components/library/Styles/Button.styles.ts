/**
 * Button Styles - Reusable button styles for library components
 *
 * Consolidates gradient buttons and other styled buttons used across detail views.
 * Shadow effects are imported from Shadow.styles.ts for consistency.
 * Border radius values are imported from BorderRadius.styles.ts.
 * Color tokens are sourced from '@/design-system' for consistency.
 */

import { buttonShadows } from './Shadow.styles';
import { radiusMedium } from './BorderRadius.styles';
import { Button } from '@/design-system';
import { styled } from '@mui/material';
import { tokens } from '@/design-system';

/**
 * GradientButton - Primary action button with aurora gradient (Design Language v1.2.0)
 * Used in CreatePlaylistDialog, EditPlaylistDialog, SettingsDialog
 * Glass effect on hover for elevated aesthetic
 */
export const GradientButton = styled(Button)({
  background: tokens.gradients.aurora,
  color: tokens.colors.text.primary,
  textTransform: 'none',
  fontWeight: tokens.typography.fontWeight.semibold,
  padding: `${tokens.spacing.xs} ${tokens.spacing.lg}`,  // 4px vertical, 20px horizontal
  borderRadius: tokens.borderRadius.md,                   // 12px - softer, more organic
  boxShadow: buttonShadows.primary,                       // Initial depth

  '&:hover': {
    background: tokens.gradients.aurora,
    transform: 'scale(1.02)',                             // Subtle scale for organic feel
    boxShadow: '0 12px 32px rgba(115, 102, 240, 0.4), 0 0 0 1px rgba(255, 255, 255, 0.12)', // Enhanced glow
  },

  '&:active': {
    transform: 'scale(0.98)',                             // Press feedback
  },

  '&:disabled': {
    background: tokens.colors.opacityScale.accent.strong,
    color: 'rgba(255, 255, 255, 0.5)',
  },

  transition: `${tokens.transitions.all}, backdrop-filter ${tokens.transitions.base}`,
});

/**
 * CancelButton - Secondary button with glass hover effect (Design Language v1.2.0)
 * Used in dialog action bars
 */
export const CancelButton = styled(Button)(({ theme }) => ({
  color: tokens.colors.text.secondary,
  textTransform: 'none',
  borderRadius: tokens.borderRadius.md,                   // 12px - softer, more organic
  padding: `${tokens.spacing.xs} ${tokens.spacing.lg}`,  // 4px vertical, 20px horizontal

  '&:hover': {
    backgroundColor: tokens.glass.subtle.background,      // Glass effect on hover
    backdropFilter: tokens.glass.subtle.backdropFilter,   // 20px blur for glossy feel
    color: tokens.colors.text.primary,
  },

  transition: `${tokens.transitions.all}, backdrop-filter ${tokens.transitions.base}`,
}));

/**
 * SaveButton - Primary action button with aurora gradient (Design Language v1.2.0)
 * Used in dialogs and forms for saving/submitting data
 * Glass effect on hover for elevated aesthetic
 */
export const SaveButton = styled(Button)(({ theme }) => ({
  background: tokens.gradients.aurora,
  color: tokens.colors.text.primary,
  textTransform: 'none',
  fontWeight: tokens.typography.fontWeight.semibold,
  padding: `${tokens.spacing.xs} ${tokens.spacing.lg}`,  // 4px vertical, 20px horizontal
  borderRadius: tokens.borderRadius.md,                   // 12px - softer, more organic
  boxShadow: buttonShadows.primary,                       // Initial depth

  '&:hover': {
    background: tokens.gradients.aurora,
    transform: 'scale(1.02)',                             // Subtle scale for organic feel
    boxShadow: '0 12px 32px rgba(115, 102, 240, 0.4), 0 0 0 1px rgba(255, 255, 255, 0.12)', // Enhanced glow
  },

  '&:active': {
    transform: 'scale(0.98)',                             // Press feedback
  },

  '&:disabled': {
    background: tokens.colors.opacityScale.accent.strong,
    color: 'rgba(255, 255, 255, 0.5)',
  },

  transition: `${tokens.transitions.all}, backdrop-filter ${tokens.transitions.base}`,
}));

/**
 * CancelButtonForDialog - Cancel button with secondary styling
 * Alias for CancelButton, used in EditMetadataDialog and other dialogs
 */
export const CancelButtonForDialog = CancelButton;

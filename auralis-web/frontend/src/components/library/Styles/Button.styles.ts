/**
 * Button Styles - Reusable button styles for library components
 *
 * Consolidates gradient buttons and other styled buttons used across detail views.
 * Shadow effects are imported from Shadow.styles.ts for consistency.
 * Border radius values are imported from BorderRadius.styles.ts.
 * Color presets are imported from Color.styles.ts for consistency.
 */

import { Button, styled } from '@mui/material';
import { gradients, auroraOpacity } from './Color.styles';
import { buttonShadows } from './Shadow.styles';
import { radiusMedium } from './BorderRadius.styles';

/**
 * GradientButton - Primary action button with aurora gradient (135deg variant)
 * Used in CreatePlaylistDialog, EditPlaylistDialog, SettingsDialog
 */
export const GradientButton = styled(Button)({
  background: gradients.aurora,
  color: '#ffffff',
  textTransform: 'none',
  fontWeight: 600,
  padding: '10px 24px',
  borderRadius: radiusMedium,
  '&:hover': {
    background: gradients.auroraHover,
    transform: 'translateY(-1px)',
    boxShadow: buttonShadows.primary,
  },
  '&:disabled': {
    background: auroraOpacity.strong,
    color: 'rgba(255, 255, 255, 0.5)',
  },
  transition: 'all 0.2s ease',
});

/**
 * CancelButton - Secondary button with text styling
 * Used in dialog action bars
 */
export const CancelButton = styled(Button)(({ theme }) => ({
  color: theme.palette.text.secondary,
  textTransform: 'none',
  '&:hover': {
    backgroundColor: auroraOpacity.veryLight,
    color: theme.palette.text.primary,
  },
  transition: 'all 0.2s ease',
}));

/**
 * SaveButton - Primary action button with aurora gradient
 * Used in dialogs and forms for saving/submitting data
 */
export const SaveButton = styled(Button)(({ theme }) => ({
  background: gradients.aurora,
  color: '#ffffff',
  textTransform: 'none',
  fontWeight: 600,
  '&:hover': {
    background: gradients.auroraHover,
    transform: 'translateY(-1px)',
    boxShadow: buttonShadows.primary,
  },
  '&:disabled': {
    background: auroraOpacity.strong,
    color: 'rgba(255, 255, 255, 0.5)',
  },
  transition: 'all 0.2s ease',
}));

/**
 * CancelButtonForDialog - Cancel button with secondary styling
 * Alias for CancelButton, used in EditMetadataDialog and other dialogs
 */
export const CancelButtonForDialog = CancelButton;

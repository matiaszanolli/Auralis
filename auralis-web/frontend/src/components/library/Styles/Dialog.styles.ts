/**
 * Dialog Styles - Reusable dialog component styling
 *
 * Consolidates dialog styling patterns used across SettingsDialog,
 * CreatePlaylistDialog, EditPlaylistDialog, and KeyboardShortcutsHelp.
 *
 * Tab components (StyledTabs, DialogTabs) are imported from Tabs.styles.ts
 */

import { Dialog, DialogTitle, DialogActions, Box, styled } from '@mui/material';
import { tokens } from '@/design-system';
import { themeVars } from '@/theme/semanticTheme';
export { DialogTabs as StyledTabs, DetailViewTabs } from './Tabs.styles';
export { SaveButton, CancelButtonForDialog } from './Button.styles';
export { SectionLabel, SectionDescription } from './Typography.styles';

/**
 * StyledDialog - Base dialog with glass effect (Design Language v1.2.0 §4.2)
 * Used by: SettingsDialog, CreatePlaylistDialog, EditPlaylistDialog, KeyboardShortcutsHelp
 */
export const StyledDialog = styled(Dialog)({
  '& .MuiDialog-paper': {
    background: themeVars.surfaceRaised,
    border: `1px solid ${themeVars.borderDefault}`,
    boxShadow: themeVars.shadowOverlay,
    borderRadius: tokens.borderRadius.lg,
  }
});

/**
 * StyledDialogTitle - Dialog header with aurora gradient background
 */
export const StyledDialogTitle = styled(DialogTitle)({
  background: themeVars.surfaceRaised,
  color: themeVars.textPrimary,
  borderBottom: `1px solid ${themeVars.borderSubtle}`,
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  padding: `${tokens.spacing.sm} ${tokens.spacing.md}`,
});

/**
 * SectionContainer - Reusable section styling for dialog content
 */
export const SectionContainer = styled(Box)({
  marginBottom: tokens.spacing.md,
});

/**
 * MetadataDialogActions - Dialog actions bar for EditMetadataDialog
 * Features border-top separator and padding
 */
export const MetadataDialogActions = styled(DialogActions)({
  borderTop: `1px solid ${themeVars.borderSubtle}`,
  padding: tokens.spacing.sm,
});

/**
 * DialogPaperProps - Standard PaperProps for EditMetadataDialog
 * Provides gradient background styling
 */
export const DialogPaperProps = {
  sx: {
    bgcolor: themeVars.surfaceRaised,
    backgroundImage: 'none',
  },
};

export default StyledDialog;

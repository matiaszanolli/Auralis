/**
 * Dialog Styles - Reusable dialog component styling
 *
 * Consolidates dialog styling patterns used across SettingsDialog,
 * CreatePlaylistDialog, EditPlaylistDialog, and KeyboardShortcutsHelp.
 *
 * Tab components (StyledTabs, DialogTabs) are imported from Tabs.styles.ts
 */

import { gradients } from './Color.styles';
import { Button } from '@/design-system';
import { Dialog, DialogTitle, DialogActions, Box, styled } from '@mui/material';
import { tokens } from '@/design-system';
export { DialogTabs as StyledTabs, DetailViewTabs } from './Tabs.styles';
export { SaveButton, CancelButtonForDialog } from './Button.styles';
export { SectionLabel, SectionDescription } from './Typography.styles';

/**
 * StyledDialog - Base dialog with glass effect (Design Language v1.2.0 §4.2)
 * Used by: SettingsDialog, CreatePlaylistDialog, EditPlaylistDialog, KeyboardShortcutsHelp
 */
export const StyledDialog = styled(Dialog)(({ theme }) => ({
  '& .MuiDialog-paper': {
    // Glass effect for elevated dialog (upgraded to strong for maximum prominence)
    background: tokens.glass.strong.background,
    backdropFilter: tokens.glass.strong.backdropFilter,   // 40px blur for dramatic modal presence
    border: tokens.glass.strong.border,                   // 22% white opacity for light-catching borders
    boxShadow: tokens.glass.strong.boxShadow,             // Deep shadow + strong inner glow
    borderRadius: tokens.borderRadius.md,                 // 12px - softer, more organic
  }
}));

/**
 * StyledDialogTitle - Dialog header with aurora gradient background
 */
export const StyledDialogTitle = styled(DialogTitle)(({ theme }) => ({
  background: gradients.aurora,
  color: tokens.colors.text.primary,
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  padding: theme.spacing(2, 3)
}));

/**
 * SectionContainer - Reusable section styling for dialog content
 */
export const SectionContainer = styled(Box)(({ theme }) => ({
  marginBottom: theme.spacing(3)
}));

/**
 * MetadataDialogActions - Dialog actions bar for EditMetadataDialog
 * Features border-top separator and padding
 */
export const MetadataDialogActions = styled(DialogActions)(({ theme }) => ({
  borderTop: `1px solid ${tokens.colors.border.light}`,
  padding: theme.spacing(2)
}));

/**
 * DialogPaperProps - Standard PaperProps for EditMetadataDialog
 * Provides gradient background styling
 */
export const DialogPaperProps = {
  sx: {
    bgcolor: tokens.colors.bg.level3,
    backgroundImage: tokens.gradients.darkSubtle,
  },
};

export default StyledDialog;

/**
 * Dialog Styles - Reusable dialog component styling
 *
 * Consolidates dialog styling patterns used across SettingsDialog,
 * CreatePlaylistDialog, EditPlaylistDialog, and KeyboardShortcutsHelp.
 *
 * Tab components (StyledTabs, DialogTabs) are imported from Tabs.styles.ts
 */

import { Dialog, DialogTitle, DialogActions, Button, Box, styled } from '@mui/material';
import { gradients } from './Color.styles';
export { DialogTabs as StyledTabs, DetailViewTabs } from './Tabs.styles';
export { SaveButton, CancelButtonForDialog } from './Button.styles';
export { SectionLabel, SectionDescription } from './Typography.styles';

/**
 * StyledDialog - Base dialog with dark theme, blur background, and aurora border
 * Used by: SettingsDialog, CreatePlaylistDialog, EditPlaylistDialog, KeyboardShortcutsHelp
 */
export const StyledDialog = styled(Dialog)(({ theme }) => ({
  '& .MuiDialog-paper': {
    background: 'rgba(26, 31, 58, 0.98)',
    backdropFilter: 'blur(20px)',
    border: '1px solid rgba(255,255,255,0.1)',
    borderRadius: theme.spacing(2),
  }
}));

/**
 * StyledDialogTitle - Dialog header with aurora gradient background
 */
export const StyledDialogTitle = styled(DialogTitle)(({ theme }) => ({
  background: gradients.aurora,
  color: 'white',
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
  borderTop: '1px solid rgba(255,255,255,0.1)',
  padding: theme.spacing(2)
}));

export default StyledDialog;

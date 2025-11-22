/**
 * Dialog Styles - Reusable dialog component styling
 *
 * Consolidates dialog styling patterns used across SettingsDialog,
 * CreatePlaylistDialog, EditPlaylistDialog, and KeyboardShortcutsHelp.
 */

import { Dialog, DialogTitle, DialogActions, Button, Box, Tabs, Typography, styled } from '@mui/material';
import { gradients } from '../../theme/auralisTheme';

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
 * StyledTabs - Tab navigation with aurora indicator
 */
export const StyledTabs = styled(Tabs)(({ theme }) => ({
  borderBottom: '1px solid rgba(255,255,255,0.1)',
  minHeight: 48,
  '& .MuiTab-root': {
    textTransform: 'none',
    fontSize: '0.95rem',
    minHeight: 48,
    color: theme.palette.text.secondary,
    '&.Mui-selected': {
      color: '#667eea'
    }
  },
  '& .MuiTabs-indicator': {
    backgroundColor: '#667eea'
  }
}));

/**
 * SectionContainer - Reusable section styling for dialog content
 */
export const SectionContainer = styled(Box)(({ theme }) => ({
  marginBottom: theme.spacing(3)
}));

/**
 * SectionLabel - Section header typography
 */
export const SectionLabel = styled(Typography)(({ theme }) => ({
  fontSize: '0.875rem',
  fontWeight: 600,
  color: theme.palette.text.primary,
  marginBottom: theme.spacing(1)
}));

/**
 * SectionDescription - Secondary text for section labels
 */
export const SectionDescription = styled(Typography)(({ theme }) => ({
  fontSize: '0.75rem',
  color: theme.palette.text.secondary,
  marginTop: theme.spacing(0.5)
}));

/**
 * MetadataDialogActions - Dialog actions bar for EditMetadataDialog
 * Features border-top separator and padding
 */
export const MetadataDialogActions = styled(DialogActions)(({ theme }) => ({
  borderTop: '1px solid rgba(255,255,255,0.1)',
  padding: theme.spacing(2)
}));

/**
 * SaveButton - Primary action button with aurora gradient
 * Used in EditMetadataDialog for saving metadata
 */
export const SaveButton = styled(Button)(({ theme }) => ({
  background: gradients.aurora,
  color: '#ffffff',
  '&:hover': {
    background: gradients.auroraHover,
    transform: 'translateY(-1px)',
    boxShadow: '0 4px 12px rgba(102, 126, 234, 0.4)',
  },
  '&:disabled': {
    background: 'rgba(102, 126, 234, 0.3)',
    color: 'rgba(255, 255, 255, 0.5)',
  },
  transition: 'all 0.2s ease',
}));

/**
 * CancelButtonForDialog - Cancel button with secondary styling
 * Used in EditMetadataDialog
 */
export const CancelButtonForDialog = styled(Button)(({ theme }) => ({
  color: 'rgba(255,255,255,0.7)',
  '&:hover': {
    backgroundColor: 'rgba(255,255,255,0.1)'
  },
  transition: 'all 0.2s ease',
}));

export default StyledDialog;

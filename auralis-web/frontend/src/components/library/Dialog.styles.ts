/**
 * Dialog Styles - Reusable dialog component styling
 *
 * Consolidates dialog styling patterns used across SettingsDialog,
 * CreatePlaylistDialog, EditPlaylistDialog, and KeyboardShortcutsHelp.
 */

import { Dialog, DialogTitle, Box, Tabs, Typography, styled } from '@mui/material';

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
  background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
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

export default StyledDialog;

/**
 * Button Styles - Reusable button styles for library components
 *
 * Consolidates gradient buttons and other styled buttons used across detail views.
 */

import { Button, styled } from '@mui/material';
import { gradients } from '../../theme/auralisTheme';

/**
 * PlayButton - Gradient action button for playing tracks/albums
 * Used in AlbumDetailView and ArtistDetailView
 */
export const PlayButton = styled(Button)(({ theme }) => ({
  background: gradients.aurora45,
  color: 'white',
  padding: '12px 32px',
  fontSize: '1rem',
  fontWeight: 'bold',
  borderRadius: 24,
  textTransform: 'none',
  '&:hover': {
    background: gradients.aurora45Hover,
    transform: 'translateY(-2px)',
    boxShadow: '0 4px 12px rgba(102, 126, 234, 0.4)'
  },
  transition: 'all 0.2s ease'
}));

/**
 * ShuffleButton - Outlined button for shuffle/secondary actions
 * Used in ArtistDetailView
 */
export const ShuffleButton = styled(Button)(({ theme }) => ({
  borderColor: theme.palette.text.secondary,
  color: theme.palette.text.secondary,
  padding: '12px 24px',
  borderRadius: 24,
  textTransform: 'none',
  '&:hover': {
    borderColor: theme.palette.primary.main,
    color: theme.palette.primary.main,
    backgroundColor: 'rgba(102, 126, 234, 0.1)'
  }
}));

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
  borderRadius: '8px',
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
});

/**
 * CancelButton - Secondary button with text styling
 * Used in dialog action bars
 */
export const CancelButton = styled(Button)(({ theme }) => ({
  color: theme.palette.text.secondary,
  textTransform: 'none',
  '&:hover': {
    backgroundColor: 'rgba(102, 126, 234, 0.1)',
    color: theme.palette.text.primary,
  },
  transition: 'all 0.2s ease',
}));

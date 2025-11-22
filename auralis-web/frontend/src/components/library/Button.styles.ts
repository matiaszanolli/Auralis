/**
 * Button Styles - Reusable button styles for library components
 *
 * Consolidates gradient buttons and other styled buttons used across detail views.
 */

import { Button, styled } from '@mui/material';

/**
 * PlayButton - Gradient action button for playing tracks/albums
 * Used in AlbumDetailView and ArtistDetailView
 */
export const PlayButton = styled(Button)(({ theme }) => ({
  background: 'linear-gradient(45deg, #667eea, #764ba2)',
  color: 'white',
  padding: '12px 32px',
  fontSize: '1rem',
  fontWeight: 'bold',
  borderRadius: 24,
  textTransform: 'none',
  '&:hover': {
    background: 'linear-gradient(45deg, #5568d3, #6a3f8f)',
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

/**
 * ArtistDetail Styles - Reusable artist detail component styling
 *
 * Consolidates styled components from ArtistDetailView for better organization
 * and reusability across artist-related components.
 *
 * Avatar components (ArtistAvatarCircle) are imported from Avatar.styles.ts
 * Tab components (StyledTabs, DetailViewTabs) are imported from Tabs.styles.ts
 */

import { Typography, TableContainer, Paper, styled } from '@mui/material';
import { auroraOpacity } from './Color.styles';
import { tokens } from '@/design-system';
export { ArtistAvatarCircle } from './Avatar.styles';
export { DetailViewTabs as StyledTabs } from './Tabs.styles';

/**
 * AlbumCard - Card container for album displays in artist view
 * Features hover elevation and color transition on album title
 */
export const AlbumCard = styled(Paper)(({ theme }) => ({
  background: auroraOpacity.ultraLight,
  borderRadius: theme.spacing(2),
  overflow: 'hidden',
  cursor: 'pointer',
  transition: tokens.transitions.all,
  border: `1px solid ${auroraOpacity.ultraLight}`,
  '&:hover': {
    transform: 'translateY(-4px)',
    boxShadow: tokens.shadows.lg,
    '& .album-title': {
      color: tokens.colors.accent.primary
    }
  }
}));

/**
 * AlbumTitle - Title typography for album cards
 */
export const AlbumTitle = styled(Typography)(({ theme }) => ({
  fontSize: tokens.typography.fontSize.md,
  fontWeight: tokens.typography.fontWeight.semibold,
  color: tokens.colors.text.primary,
  marginBottom: 4,
  transition: tokens.transitions.color
}));

/**
 * AlbumInfo - Secondary information typography for album cards (year, track count)
 */
export const AlbumInfo = styled(Typography)(({ theme }) => ({
  fontSize: tokens.typography.fontSize.sm,
  color: tokens.colors.text.secondary
}));

/**
 * TracksTableContainer - Container for the tracks table with styling
 */
export const TracksTableContainer = styled(TableContainer)(({ theme }) => ({
  background: auroraOpacity.ultraLight,
  borderRadius: theme.spacing(2),
  backdropFilter: 'blur(10px)'
}));

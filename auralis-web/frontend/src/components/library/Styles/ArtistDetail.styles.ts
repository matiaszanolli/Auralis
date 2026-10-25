/**
 * ArtistDetail Styles - Reusable artist detail component styling
 *
 * Consolidates styled components from ArtistDetailView for better organization
 * and reusability across artist-related components.
 *
 * Avatar components (ArtistAvatarCircle) are imported from Avatar.styles.ts
 * Tab components are imported from Tabs.styles.ts
 */

import { TableContainer, styled } from '@mui/material';
import { tokens } from '@/design-system';
export { ArtistAvatarCircle } from './Avatar.styles';

/*
 * Album cards: use the unified `components/album/AlbumCard` (-> MediaCard). A
 * local card with only `onClick` is keyboard-unreachable.
 */

/**
 * TracksTableContainer - Container for the tracks table with styling
 */
export const TracksTableContainer = styled(TableContainer)({
  background: tokens.colors.opacityScale.accent.ultraLight,
  borderRadius: tokens.spacing.sm,
  backdropFilter: 'blur(10px)'
});

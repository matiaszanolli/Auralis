/**
 * ArtistDetail Styles - Reusable artist detail component styling
 *
 * Consolidates styled components from ArtistDetailView for better organization
 * and reusability across artist-related components.
 *
 * Avatar components (ArtistAvatarCircle) are imported from Avatar.styles.ts
 * Tab components (StyledTabs, DetailViewTabs) are imported from Tabs.styles.ts
 */

import { TableContainer, styled } from '@mui/material';
import { tokens } from '@/design-system';
export { ArtistAvatarCircle } from './Avatar.styles';
export { DetailViewTabs as StyledTabs } from './Tabs.styles';

/*
 * AlbumCard / AlbumTitle / AlbumInfo were removed in #4537.
 *
 * They existed only for AlbumsTab, which now renders the unified
 * `components/album/AlbumCard` (-> MediaCard). The local card set `onClick` and
 * `cursor: pointer` but never `role`, `tabIndex` or `onKeyDown`, so the artist
 * page's album grid was keyboard-unreachable while the identical main-library
 * grid — already on MediaCard — was fine. Re-adding a local clickable card here
 * reintroduces that gap; use the unified card instead.
 */

/**
 * TracksTableContainer - Container for the tracks table with styling
 */
export const TracksTableContainer = styled(TableContainer)({
  background: tokens.colors.opacityScale.accent.ultraLight,
  borderRadius: tokens.spacing.sm,
  backdropFilter: 'blur(10px)'
});

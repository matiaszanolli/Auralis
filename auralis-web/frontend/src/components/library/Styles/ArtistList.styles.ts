/**
 * Artist List Styles - Reusable artist list component styling
 *
 * Consolidates styled components from CozyArtistList
 * to improve modularity and maintainability.
 */

import { Avatar, Box, ListItem, ListItemButton, Typography, styled } from '@mui/material';
import { tokens } from '@/design-system';

/**
 * ListContainer - Main container for artist list
 */
export const ListContainer = styled(Box)({
  padding: '24px',
  width: '100%',
});

/**
 * StyledListItem - Wrapper for artist list items
 */
export const StyledListItem = styled(ListItem)({
  padding: 0,
  marginBottom: '8px',
});

/**
 * StyledListItemButton - Clickable artist list item with glass hover effects
 * Typography-driven design with increased breathing room
 * Glass effect on hover for starfield visibility
 */
export const StyledListItemButton = styled(ListItemButton)({
  borderRadius: tokens.borderRadius.md,
  padding: '20px 24px',
  minHeight: '72px',
  transition: 'all 0.2s ease, backdrop-filter 0.2s ease',
  background: 'transparent',
  border: 'none',

  '&:hover': {
    // Glass effect on hover
    background: 'rgba(21, 29, 47, 0.35)',
    backdropFilter: 'blur(6px) saturate(1.05)',
    // Glass bevel: subtle highlight + shadow
    boxShadow: '0 4px 12px rgba(0, 0, 0, 0.12), inset 0 1px 0 rgba(255, 255, 255, 0.06), inset 0 -1px 0 rgba(0, 0, 0, 0.10)',
    transform: 'translateX(2px)',

    '& .artist-name': {
      color: tokens.colors.accent.primary,
    },
  },
});

/**
 * ArtistAvatar - Avatar display for artist with gradient background
 */
export const ArtistAvatar = styled(Avatar)({
  width: 56,
  height: 56,
  marginRight: '20px',
  background: `linear-gradient(135deg, ${tokens.colors.accent.primary} 0%, ${tokens.colors.accent.secondary} 100%)`,
  fontSize: '24px',
});

/**
 * ArtistName - Artist name typography (primary identity)
 */
export const ArtistName = styled(Typography)({
  fontSize: '17px',
  fontWeight: 500,
  color: tokens.colors.text.primary,
  letterSpacing: '0.01em',
  transition: 'color 0.2s ease',
});

/**
 * ArtistInfo - Secondary information (album/track counts)
 */
export const ArtistInfo = styled(Typography)({
  fontSize: '13px',
  fontWeight: 400,
  color: tokens.colors.text.tertiary,
  marginTop: '6px',
  letterSpacing: '0.005em',
});

/**
 * SectionHeader - Header for artist sections
 * Glass bevel instead of hard border
 */
export const SectionHeader = styled(Box)({
  marginBottom: '24px',
  paddingBottom: '16px',
  // Glass bevel: bottom shadow instead of hard border
  boxShadow: 'inset 0 -1px 0 rgba(255, 255, 255, 0.05)',
});

/**
 * AlphabetDivider - Alphabetical section divider
 * Quiet index header that organizes without dominating
 */
export const AlphabetDivider = styled(Typography)({
  fontSize: '12px',
  fontWeight: 600,
  color: tokens.colors.text.tertiary,
  textTransform: 'uppercase',
  letterSpacing: '0.08em',
  marginTop: '40px',
  marginBottom: '16px',
  paddingLeft: '24px',
  opacity: 0.7,
});

export default ListContainer;

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
 * StyledListItemButton - Clickable artist list item with hover effects
 * Typography-driven design with increased breathing room
 */
export const StyledListItemButton = styled(ListItemButton)({
  borderRadius: '8px',
  padding: '20px 24px',
  minHeight: '72px',
  transition: 'all 0.2s ease',
  border: '1px solid transparent',

  '&:hover': {
    backgroundColor: `${tokens.colors.accent.primary}0a`,
    border: `1px solid ${tokens.colors.accent.primary}33`,
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
 */
export const SectionHeader = styled(Box)({
  marginBottom: '24px',
  paddingBottom: '16px',
  borderBottom: `1px solid ${tokens.colors.border.light}`,
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

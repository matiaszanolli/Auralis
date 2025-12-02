/**
 * Artist List Styles - Reusable artist list component styling
 *
 * Consolidates styled components from CozyArtistList
 * to improve modularity and maintainability.
 */

import { Avatar, Box, ListItem, ListItemButton, Typography, styled } from '@mui/material';
import { tokens } from '@/design-system/tokens';

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
 */
export const StyledListItemButton = styled(ListItemButton)({
  borderRadius: '12px',
  padding: '16px 20px',
  transition: 'all 0.3s ease',
  border: '1px solid transparent',

  '&:hover': {
    backgroundColor: `${tokens.colors.accent.primary}14`,
    border: `1px solid ${tokens.colors.accent.primary}4d`,
    transform: 'translateX(4px)',

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
 * ArtistName - Artist name typography
 */
export const ArtistName = styled(Typography)({
  fontSize: '18px',
  fontWeight: 600,
  color: tokens.colors.text.primary,
  transition: 'color 0.2s ease',
});

/**
 * ArtistInfo - Secondary information (album/track counts)
 */
export const ArtistInfo = styled(Typography)({
  fontSize: '14px',
  color: tokens.colors.text.secondary,
  marginTop: '4px',
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
 */
export const AlphabetDivider = styled(Typography)({
  fontSize: '14px',
  fontWeight: 700,
  color: tokens.colors.accent.primary,
  textTransform: 'uppercase',
  letterSpacing: '1px',
  marginTop: '32px',
  marginBottom: '12px',
  paddingLeft: '8px',
});

export default ListContainer;

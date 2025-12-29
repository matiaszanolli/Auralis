/**
 * Artist List Styles - Glass card-based artist display
 *
 * Uses glass cards instead of list items for starfield visibility.
 * Each artist is displayed as a discrete glass card.
 */

import { Avatar, Box, ButtonBase, Typography, styled } from '@mui/material';
import { tokens } from '@/design-system';

/**
 * ListContainer - Main container for artist cards
 */
export const ListContainer = styled(Box)({
  padding: '24px',
  width: '100%',
});

/**
 * StyledListItem - Wrapper for artist card (renamed for backwards compat)
 */
export const StyledListItem = styled(Box)({
  marginBottom: tokens.spacing.md,
});

/**
 * StyledListItemButton - Glass card for artist
 * Transparent by default, glass effect on hover
 * Uses ButtonBase for clean clickable without MUI ListItem background
 */
export const StyledListItemButton = styled(ButtonBase)({
  display: 'flex',
  alignItems: 'center',
  width: '100%',
  textAlign: 'left',
  borderRadius: tokens.borderRadius.md,
  padding: '16px 20px',
  minHeight: '64px',
  transition: 'all 0.2s ease, backdrop-filter 0.2s ease',

  // Glass card: subtle background for visibility without blocking starfield
  background: 'rgba(21, 29, 47, 0.25)',
  backdropFilter: 'blur(4px) saturate(1.02)',
  // Glass bevel
  boxShadow: 'inset 0 1px 0 rgba(255, 255, 255, 0.04), inset 0 -1px 0 rgba(0, 0, 0, 0.08)',

  '&:hover': {
    // Enhanced glass on hover
    background: 'rgba(21, 29, 47, 0.40)',
    backdropFilter: 'blur(8px) saturate(1.05)',
    // Stronger glass bevel
    boxShadow: '0 4px 16px rgba(0, 0, 0, 0.15), inset 0 1px 0 rgba(255, 255, 255, 0.08), inset 0 -1px 0 rgba(0, 0, 0, 0.12)',
    transform: 'translateY(-1px)',

    '& .artist-name': {
      color: tokens.colors.accent.primary,
    },
  },

  '&:active': {
    transform: 'translateY(0)',
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

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
  padding: tokens.spacing.lg, // #3947: was 24px → token scale (20px)
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
  padding: `${tokens.spacing.md} ${tokens.spacing.lg}`, // #3947: was 16px 20px → token scale
  minHeight: '64px', // card dimension (not a spacing-scale value) — left as-is
  transition: `${tokens.transitions.hover_out}, backdrop-filter ${tokens.transitions.hover}`,

  // Glass card: subtle background for visibility without blocking starfield
  background: tokens.glass.starfield.faint, // #3950: unified starfield glass
  backdropFilter: 'blur(4px) saturate(1.02)',
  // Glass bevel
  boxShadow: `inset 0 1px 0 ${tokens.colors.opacityScale.white.micro}, inset 0 -1px 0 ${tokens.colors.opacityScale.dark.light}`,

  '&:hover': {
    // Enhanced glass on hover
    background: tokens.glass.starfield.subtle, // #3950: unified starfield glass
    backdropFilter: 'blur(8px) saturate(1.05)',
    // Stronger glass bevel
    boxShadow: `0 4px 16px ${tokens.colors.opacityScale.dark.lighter}, inset 0 1px 0 ${tokens.colors.opacityScale.white.subtle}, inset 0 -1px 0 ${tokens.colors.opacityScale.dark.lighter}`,
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
  marginRight: tokens.spacing.lg, // #3947: was 20px → token scale (20px)
  background: `linear-gradient(135deg, ${tokens.colors.accent.primary} 0%, ${tokens.colors.accent.secondary} 100%)`,
  fontSize: tokens.typography.fontSize.xl,
});

/**
 * ArtistName - Artist name typography (primary identity)
 */
export const ArtistName = styled(Typography)({
  // #3639: align with the body-text scale (md = 16px). Was a one-off 17px
  // between base (14px) and md (16px).
  fontSize: tokens.typography.fontSize.md,
  fontWeight: tokens.typography.fontWeight.medium,
  color: tokens.colors.text.primary,
  letterSpacing: '0.01em',
  transition: tokens.transitions.color,
});

/**
 * ArtistInfo - Secondary information (album/track counts)
 */
export const ArtistInfo = styled(Typography)({
  fontSize: tokens.typography.fontSize.sm,
  fontWeight: tokens.typography.fontWeight.normal,
  color: tokens.colors.text.tertiary,
  marginTop: tokens.spacing.sm, // #3947: was 6px → token scale (6px)
  letterSpacing: '0.005em',
});

/**
 * SectionHeader - Header for artist sections
 * Glass bevel instead of hard border
 */
export const SectionHeader = styled(Box)({
  marginBottom: tokens.spacing.lg, // #3947: was 24px → token scale (20px)
  paddingBottom: tokens.spacing.md, // #3947: was 16px → token scale (12px)
  // Glass bevel: bottom shadow instead of hard border
  boxShadow: `inset 0 -1px 0 ${tokens.colors.opacityScale.white.veryLight}`,
});

/**
 * AlphabetDivider - Alphabetical section divider
 * Quiet index header that organizes without dominating
 */
export const AlphabetDivider = styled(Typography)({
  fontSize: tokens.typography.fontSize.xs,
  fontWeight: tokens.typography.fontWeight.semibold,
  color: tokens.colors.text.tertiary,
  textTransform: 'uppercase',
  letterSpacing: '0.08em',
  marginTop: tokens.spacing.xxl, // #3947: was 40px → token scale (40px)
  marginBottom: tokens.spacing.md, // #3947: was 16px → token scale (12px)
  paddingLeft: tokens.spacing.lg, // #3947: was 24px → token scale (20px)
  opacity: 0.7,
});

export default ListContainer;

/**
 * PlaylistList Styles - Reusable playlist list component styling
 *
 * Consolidates styled components from PlaylistList for better organization
 * and reusability across playlist-related components.
 * Color presets are imported from Color.styles.ts for consistency.
 */

import { auroraOpacity, colorAuroraPrimary } from '../library/Styles/Color.styles';
import { tokens } from '@/design-system';
import { IconButton } from '@/design-system';
import { Box, ListItem, ListItemButton, Typography, styled } from '@mui/material';

/**
 * PlaylistSection - Root container for the playlists section
 */
export const PlaylistSection = styled(Box)({
  marginTop: '16px',
});

/**
 * SectionHeader - Header bar for playlists section with expand/collapse toggle
 */
export const SectionHeader = styled(Box)({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  padding: '8px 16px',
  cursor: 'pointer',
  '&:hover': {
    background: auroraOpacity.minimal,
  },
  transition: 'background 0.2s ease',
});

/**
 * SectionTitle - Title typography for playlists section header
 */
export const SectionTitle = styled(Typography)({
  fontSize: '14px',
  fontWeight: 600,
  color: tokens.colors.text.secondary,
  textTransform: 'uppercase',
  letterSpacing: '0.5px',
  display: 'flex',
  alignItems: 'center',
  gap: '8px',
});

/**
 * StyledListItem - List item container for playlists
 */
export const StyledListItem = styled(ListItem)({
  padding: 0,
});

/**
 * StyledListItemButton - Interactive button for playlist selection (Design Language §4.3)
 * Calm by default (§1.3), subtle selected state (muscle memory UI).
 * No hard borders - depth via subtle background only.
 */
export const StyledListItemButton = styled(ListItemButton)<{ selected?: boolean }>(
  ({ selected }) => ({
    paddingLeft: '32px',
    paddingRight: '8px',
    height: '40px',
    borderRadius: tokens.borderRadius.md,  // 8px (subtle)
    margin: '2px 8px',
    transition: tokens.transitions.all,    // Design Language §5 timing
    background: selected ? 'rgba(115, 102, 240, 0.06)' : 'transparent',  // Calm by default
    borderLeft: 'none',                    // No borders - surfaces not cards (§4.1)
    position: 'relative',

    ...(selected && {
      '&::before': {
        content: '""',
        position: 'absolute',
        left: 0,
        top: 0,
        bottom: 0,
        width: '2px',                      // Subtle indicator only
        background: tokens.colors.accent.primary,
        borderRadius: '0 1px 1px 0',
      },
    }),

    '&:hover': {
      background: selected
        ? 'rgba(115, 102, 240, 0.10)'      // Subtle increase
        : 'rgba(21, 29, 47, 0.30)',        // Lower contrast
      transform: 'translateX(2px)',        // Reduced from 4px
      backdropFilter: 'blur(6px)',         // Subtle blur

      '& .playlist-actions': {
        opacity: 1,
      },
    },

    '& .MuiListItemText-primary': {
      fontSize: tokens.typography.fontSize.sm,  // 12px
      color: selected ? tokens.colors.text.primary : tokens.colors.text.secondary,
      fontWeight: selected ? 500 : 400,    // Reduced from 600 - typography disappears (§3)
    },
  })
);

/**
 * PlaylistActions - Container for action buttons that appear on hover
 */
export const PlaylistActions = styled(Box)({
  display: 'flex',
  gap: '4px',
  opacity: 0,
  transition: 'opacity 0.2s ease',
});

/**
 * ActionButton - Icon button for playlist edit/delete actions
 */
export const ActionButton = styled(IconButton)({
  width: '28px',
  height: '28px',
  color: tokens.colors.text.secondary,
  '&:hover': {
    color: colorAuroraPrimary,
    background: auroraOpacity.veryLight,
  },
  '& .MuiSvgIcon-root': {
    fontSize: '18px',
  },
});

/**
 * AddButton - Icon button for creating new playlists
 */
export const AddButton = styled(IconButton)({
  width: '28px',
  height: '28px',
  color: tokens.colors.text.secondary,
  '&:hover': {
    color: colorAuroraPrimary,
    background: auroraOpacity.veryLight,
  },
  '& .MuiSvgIcon-root': {
    fontSize: '20px',
  },
});

/**
 * EmptyState - Message displayed when playlists list is empty or loading
 */
export const EmptyState = styled(Box)({
  padding: '16px 32px',
  textAlign: 'center',
  color: tokens.colors.text.disabled,
  fontSize: '13px',
});

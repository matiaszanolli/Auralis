/**
 * PlaylistList Styles - Reusable playlist list component styling
 *
 * Consolidates styled components from PlaylistList for better organization
 * and reusability across playlist-related components.
 * Color presets are imported from Color.styles.ts for consistency.
 */

import { Box, ListItem, ListItemButton, IconButton, Typography, styled } from '@mui/material';
import { auroraOpacity, colorAuroraPrimary } from '../library/Color.styles';
import { tokens } from '@/design-system/tokens';

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
 * StyledListItemButton - Interactive button for playlist selection
 * Supports selected state with aurora highlight
 */
export const StyledListItemButton = styled(ListItemButton)<{ selected?: boolean }>(
  ({ selected }) => ({
    paddingLeft: '32px',
    paddingRight: '8px',
    height: '40px',
    borderRadius: '6px',
    margin: '2px 8px',
    transition: 'all 0.2s ease',
    background: selected ? auroraOpacity.lighter : 'transparent',
    borderLeft: selected ? `3px solid ${colorAuroraPrimary}` : '3px solid transparent',

    '&:hover': {
      background: selected
        ? auroraOpacity.standard
        : auroraOpacity.ultraLight,
      transform: 'translateX(2px)',

      '& .playlist-actions': {
        opacity: 1,
      },
    },

    '& .MuiListItemText-primary': {
      fontSize: '14px',
      color: selected ? tokens.colors.text.primary : tokens.colors.text.secondary,
      fontWeight: selected ? 600 : 400,
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

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
 * PlaylistSection - Root container for the playlists section (Design Language v1.2.0)
 * Organic group spacing for natural rhythm
 */
export const PlaylistSection = styled(Box)({
  marginTop: tokens.spacing.group,                        // 16px - organic group spacing
});

/**
 * SectionHeader - Header bar for playlists section with expand/collapse toggle
 * Organic spacing with glass hover effect
 */
export const SectionHeader = styled(Box)({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  padding: `${tokens.spacing.cluster} ${tokens.spacing.group}`, // 8px vertical, 16px horizontal
  cursor: 'pointer',
  '&:hover': {
    background: tokens.glass.subtle.background,           // Glass effect on hover
    backdropFilter: 'blur(12px)',                         // Light blur
  },
  transition: `background ${tokens.transitions.base}, backdrop-filter ${tokens.transitions.base}`,
});

/**
 * SectionTitle - Title typography for playlists section header (Design Language v1.2.0)
 * Section labels fade into background (§4.3)
 */
export const SectionTitle = styled(Typography)({
  fontSize: tokens.typography.fontSize.sm,                // 11px - small section label
  fontWeight: tokens.typography.fontWeight.semibold,
  color: tokens.colors.text.secondary,
  textTransform: 'uppercase',
  letterSpacing: '0.5px',
  display: 'flex',
  alignItems: 'center',
  gap: tokens.spacing.cluster,                            // 8px - tight cluster
  opacity: 0.7,                                           // Fade labels - infrastructure, not content
});

/**
 * StyledListItem - List item container for playlists
 */
export const StyledListItem = styled(ListItem)({
  padding: 0,
});

/**
 * StyledListItemButton - Interactive button for playlist selection (Design Language v1.2.0 §4.3)
 * Calm by default (§1.3), subtle selected state (muscle memory UI).
 * No hard borders - depth via subtle glass effect only.
 */
export const StyledListItemButton = styled(ListItemButton)<{ selected?: boolean }>(
  ({ selected }) => ({
    paddingLeft: tokens.spacing.section,                  // 32px - organic section spacing
    paddingRight: tokens.spacing.cluster,                 // 8px - tight cluster
    height: '40px',
    borderRadius: tokens.borderRadius.md,                 // 12px - softer, more organic
    margin: `${tokens.spacing.xs} ${tokens.spacing.cluster}`, // 4px vertical, 8px horizontal
    transition: `${tokens.transitions.all}, backdrop-filter ${tokens.transitions.base}`,
    background: selected ? 'rgba(115, 102, 240, 0.06)' : 'transparent', // Calm by default
    borderLeft: 'none',                                   // No borders - surfaces not cards (§4.1)
    position: 'relative',

    ...(selected && {
      '&::before': {
        content: '""',
        position: 'absolute',
        left: 0,
        top: 0,
        bottom: 0,
        width: '2px',                                     // Subtle indicator only
        background: tokens.colors.accent.primary,
        borderRadius: '0 2px 2px 0',                      // Softer curve
      },
    }),

    '&:hover': {
      background: selected
        ? 'rgba(115, 102, 240, 0.10)'                     // Subtle increase
        : tokens.glass.subtle.background,                 // Glass effect on hover
      transform: 'translateX(2px)',                       // Subtle movement
      backdropFilter: tokens.glass.subtle.backdropFilter, // 20px blur for glossy feel

      '& .playlist-actions': {
        opacity: 1,
      },
    },

    '& .MuiListItemText-primary': {
      fontSize: tokens.typography.fontSize.sm,            // 11px
      color: selected ? tokens.colors.text.primary : tokens.colors.text.secondary,
      fontWeight: selected ? tokens.typography.fontWeight.medium : tokens.typography.fontWeight.normal,
    },
  })
);

/**
 * PlaylistActions - Container for action buttons that appear on hover
 * Organic cluster spacing for tight grouping
 */
export const PlaylistActions = styled(Box)({
  display: 'flex',
  gap: tokens.spacing.xs,                                 // 4px - very tight cluster
  opacity: 0,
  transition: `opacity ${tokens.transitions.base}`,
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
 * Organic spacing and typography
 */
export const EmptyState = styled(Box)({
  padding: `${tokens.spacing.group} ${tokens.spacing.section}`, // 16px vertical, 32px horizontal
  textAlign: 'center',
  color: tokens.colors.text.disabled,
  fontSize: tokens.typography.fontSize.base,              // 13px - standard base size
});

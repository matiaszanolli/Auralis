/**
 * TrackInfo Styled Components
 *
 * Centralized styling for TrackInfo component including layout,
 * typography, and button animations.
 */

import { Box, Typography, IconButton, styled } from '@mui/material';
import { tokens } from '@/design-system/tokens';

export const TrackInfoContainer = styled(Box)({
  display: 'flex',
  alignItems: 'center',
  gap: tokens.spacing.md,
  minWidth: 0,
  maxWidth: '400px',
});

export const TrackDetails = styled(Box)({
  minWidth: 0,
  flex: 1,
});

export const TitleContainer = styled(Box)({
  display: 'flex',
  alignItems: 'center',
  gap: tokens.spacing.sm,
  minWidth: 0,
});

export const ActionButtonsContainer = styled(Box)({
  display: 'flex',
  alignItems: 'center',
  gap: tokens.spacing.xs,
  flexShrink: 0,
});

export const ActionButton = styled(IconButton)({
  color: tokens.colors.text.secondary,
  padding: 0,
  minWidth: '24px',
  width: '24px',
  height: '24px',
  flexShrink: 0,
  transition: tokens.transitions.all,

  '&:hover': {
    color: tokens.colors.accent.error,
    transform: 'scale(1.2)',
  },

  '& .MuiSvgIcon-root': {
    fontSize: '20px',
  },
});

export const TrackTitle = styled(Typography)({
  fontSize: tokens.typography.fontSize.base,
  fontWeight: tokens.typography.fontWeight.semibold,
  color: tokens.colors.text.primary,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
  lineHeight: tokens.typography.lineHeight.tight,
  marginBottom: tokens.spacing.xs,
});

export const TrackArtist = styled(Typography)({
  fontSize: tokens.typography.fontSize.sm,
  color: tokens.colors.text.secondary,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
  lineHeight: tokens.typography.lineHeight.tight,
  transition: tokens.transitions.color,

  '&:hover': {
    color: tokens.colors.text.primary,
  },
});

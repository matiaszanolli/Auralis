import { Box, Typography, IconButton, styled } from '@mui/material';
import { colors, gradients, spacing, borderRadius, transitions } from '../../theme/auralisTheme';
import { SmallIconButton } from './Icon.styles';
import { auroraOpacity } from './Color.styles';
import { tokens } from '@/design-system/tokens';

export const RowContainer = styled(Box)<{ iscurrent?: string }>(({ iscurrent }) => ({
  display: 'flex',
  alignItems: 'center',
  height: '48px',
  padding: `0 ${spacing.md}px`,
  borderRadius: `${borderRadius.xs}px`,
  cursor: 'pointer',
  transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)', // Smooth easing
  background: iscurrent === 'true' ? auroraOpacity.light : 'transparent',
  border: iscurrent === 'true' ? `1px solid ${auroraOpacity.standard}` : '1px solid transparent',
  position: 'relative',
  marginBottom: `${spacing.xs / 2}px`,
  boxShadow: iscurrent === 'true' ? `0 0 0 1px ${auroraOpacity.veryLight}` : 'none',

  '&:hover': {
    background: iscurrent === 'true'
      ? auroraOpacity.lighter
      : auroraOpacity.ultraLight,
    transform: 'translateX(4px) scale(1.005)', // Subtle scale for depth
    boxShadow: '0 2px 8px rgba(0, 0, 0, 0.15)',

    '& .track-number': {
      opacity: 0,
      transform: 'scale(0.8)',
    },

    '& .play-button': {
      opacity: 1,
      transform: 'scale(1)',
    },

    '& .more-button': {
      opacity: 1,
    },

    '& .track-title': {
      color: tokens.colors.accent.purple,
    },

    '& .album-art': {
      transform: 'scale(1.05)',
      boxShadow: `0 4px 12px ${auroraOpacity.strong}`,
    },
  },

  '&:active': {
    transform: 'translateX(2px) scale(0.995)',
  },
}));

export const ActiveIndicator = styled(Box)({
  position: 'absolute',
  left: 0,
  top: 0,
  bottom: 0,
  width: '3px',
  background: gradients.aurora,
  borderRadius: `0 ${spacing.xs / 2}px ${spacing.xs / 2}px 0`,
});

export const TrackNumberBox = styled(Box)({
  minWidth: '40px',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  position: 'relative',
});

export const TrackNumber = styled(Typography)<{ iscurrent?: string }>(({ iscurrent }) => ({
  fontSize: '14px',
  fontWeight: 500,
  color: iscurrent === 'true' ? tokens.colors.accent.purple : colors.text.secondary,
  transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
}));

/**
 * PlayButton - Small icon button with play/pause state styling
 * Extends SmallIconButton with track-specific positioning and animations
 */
export const PlayButton = styled(SmallIconButton)({
  position: 'absolute',
  opacity: 0,
  transform: 'scale(0.8)',
  transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
  color: tokens.colors.accent.purple,

  '&:hover': {
    background: auroraOpacity.lighter,
    transform: 'scale(1.1)',
  },
});

export const AlbumArtThumbnail = styled(Box)({
  width: '40px',
  height: '40px',
  marginRight: `${spacing.md / 1.33}px`, // 12px
  borderRadius: `${borderRadius.xs}px`,
  overflow: 'hidden',
  flexShrink: 0,
  background: gradients.aurora,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',

  '& img': {
    width: '100%',
    height: '100%',
    objectFit: 'cover',
    transition: 'transform 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
  },
});

export const TrackInfo = styled(Box)({
  flex: 1,
  minWidth: 0,
  display: 'flex',
  flexDirection: 'column',
  justifyContent: 'center',
});

export const TrackTitle = styled(Typography)<{ iscurrent?: string }>(({ iscurrent }) => ({
  fontSize: '14px',
  fontWeight: iscurrent === 'true' ? 600 : 500,
  color: colors.text.primary,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
  lineHeight: 1.4,
  transition: 'color 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
}));

export const TrackArtist = styled(Typography)({
  fontSize: '13px',
  fontWeight: 400,
  color: colors.text.secondary,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
  lineHeight: 1.4,
});

export const TrackAlbum = styled(Typography)({
  fontSize: '13px',
  fontWeight: 400,
  color: colors.text.secondary,
  minWidth: '200px',
  maxWidth: '300px',
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
  marginRight: `${spacing.md}px`,
  display: { xs: 'none', md: 'block' },
});

export const TrackDuration = styled(Typography)({
  fontSize: '13px',
  fontWeight: 400,
  color: colors.text.disabled,
  minWidth: '50px',
  textAlign: 'right',
  marginRight: `${spacing.sm}px`,
});

/**
 * MoreButton - Small icon button for track menu actions
 * Extends SmallIconButton with track-specific styling
 */
export const MoreButton = styled(SmallIconButton)({
  opacity: 0,
  transition: `opacity ${transitions.fast}`,
  color: colors.text.secondary,

  '&:hover': {
    background: auroraOpacity.light,
    color: tokens.colors.accent.purple,
  },
});

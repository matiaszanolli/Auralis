
import { tokens } from '@/design-system';
import { auroraOpacity, gradients } from '../../Styles/Color.styles';
import { IconButton } from '@/design-system';
import { Box, Typography, styled } from '@mui/material';

export const RowContainer = styled(Box)<{ iscurrent?: string; isanyplaying?: string }>(
  ({ iscurrent, isanyplaying }) => ({
    display: 'flex',
    alignItems: 'center',
    height: '44px',                                      // Phase 2: Tighter vertical rhythm (was 48px)
    padding: `0 ${tokens.spacing.md}`,
    borderRadius: tokens.borderRadius.sm,
    cursor: 'pointer',
    transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)', // Smooth easing
    position: 'relative',
    marginBottom: tokens.spacing.xs,                     // Phase 2: Tighter spacing (was sm)

    // Playback Dominance (Phase 1): Dim non-playing rows when any track is playing
    opacity: isanyplaying === 'true' && iscurrent === 'false' ? 0.6 : 1,

    // Current track: Enhanced presence with glow and gradient (Phase 1)
    ...(iscurrent === 'true' && {
      background: `linear-gradient(90deg, ${auroraOpacity.light} 0%, transparent 100%)`,
      border: `1px solid ${auroraOpacity.standard}`,
      boxShadow: `
        0 4px 16px rgba(115, 102, 240, 0.15),
        0 0 0 1px ${auroraOpacity.veryLight},
        inset 0 0 20px ${auroraOpacity.ultraLight}
      `,
      // Slow shimmer animation (Phase 1) - "the room lights dim when music starts"
      animation: 'playbackShimmer 4s ease-in-out infinite',
      '@keyframes playbackShimmer': {
        '0%, 100%': { transform: 'scale(1)' },
        '50%': { transform: 'scale(1.005)' },
      },
    }),

    // Non-current row: Transparent background
    ...(iscurrent === 'false' && {
      background: 'transparent',
      border: '1px solid transparent',
      boxShadow: 'none',
    }),

    '&:hover': {
      background: iscurrent === 'true'
        ? `linear-gradient(90deg, ${auroraOpacity.lighter} 0%, ${auroraOpacity.ultraLight} 100%)`
        : auroraOpacity.ultraLight,
      transform: 'translateX(4px) scale(1.005)', // Subtle scale for depth
      boxShadow: iscurrent === 'true'
        ? `0 6px 20px rgba(115, 102, 240, 0.2), 0 0 0 1px ${auroraOpacity.veryLight}`
        : '0 2px 8px rgba(0, 0, 0, 0.15)',
      opacity: 1, // Full opacity on hover even when dimmed

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
        color: tokens.colors.accent.primary,
      },

      '& .album-art': {
        transform: 'scale(1.05)',
        boxShadow: `0 4px 12px ${auroraOpacity.strong}`,
      },
    },

    '&:active': {
      transform: 'translateX(2px) scale(0.995)',
    },
  })
);

export const ActiveIndicator = styled(Box)({
  position: 'absolute',
  left: 0,
  top: 0,
  bottom: 0,
  width: '3px',
  background: gradients.aurora,
  borderRadius: `0 ${tokens.borderRadius.sm} ${tokens.borderRadius.sm} 0`,
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
  color: iscurrent === 'true' ? tokens.colors.accent.primary : tokens.colors.text.secondary,
  transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
}));

/**
 * PlayButton - Small icon button with play/pause state styling
 * 32px compact icon button with track-specific positioning and animations
 */
export const PlayButton = styled(IconButton)({
  width: '32px',
  height: '32px',
  minWidth: '32px',
  minHeight: '32px',
  padding: '4px',
  flexShrink: 0,
  position: 'absolute',
  opacity: 0,
  transform: 'scale(0.8)',
  transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
  color: tokens.colors.accent.primary,

  '& .MuiSvgIcon-root': {
    fontSize: '20px',
  },

  '&:hover': {
    background: auroraOpacity.lighter,
    transform: 'scale(1.1)',
  },
});

export const AlbumArtThumbnail = styled(Box)({
  width: '40px',
  height: '40px',
  marginRight: '12px',
  borderRadius: tokens.borderRadius.sm,
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
  color: tokens.colors.text.primary,
  opacity: iscurrent === 'true' ? 1 : 0.9,           // Phase 2: Subtle reduction for non-current (sheet music, not stage)
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
  lineHeight: 1.4,
  transition: 'color 0.2s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
}));

export const TrackArtist = styled(Typography)({
  fontSize: '13px',
  fontWeight: 400,
  color: tokens.colors.text.secondary,
  opacity: 0.7,                                      // Phase 2: Muted metadata (second-level hierarchy)
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
  lineHeight: 1.4,
});

export const TrackAlbum = styled(Typography)(
  {
    fontSize: '13px',
    fontWeight: 400,
    color: tokens.colors.text.secondary,
    opacity: 0.7,                                    // Phase 2: Muted metadata (second-level hierarchy)
    minWidth: '200px',
    maxWidth: '300px',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
    marginRight: tokens.spacing.md,
  },
  {
    '@media (max-width: 960px)': {
      display: 'none',
    },
  }
);

export const TrackDuration = styled(Typography)({
  fontSize: '13px',
  fontWeight: 400,
  color: tokens.colors.text.disabled,
  opacity: 0.5,                                      // Phase 2: Ghosted duration (third-level hierarchy)
  minWidth: '50px',
  textAlign: 'right',
  marginRight: tokens.spacing.sm,
});

/**
 * MoreButton - Small icon button for track menu actions
 * 32px compact icon button with track-specific styling
 */
export const MoreButton = styled(IconButton)({
  width: '32px',
  height: '32px',
  minWidth: '32px',
  minHeight: '32px',
  padding: '4px',
  flexShrink: 0,
  opacity: 0,
  transition: `opacity ${tokens.transitions.fast}`,
  color: tokens.colors.text.secondary,

  '& .MuiSvgIcon-root': {
    fontSize: '20px',
  },

  '&:hover': {
    background: auroraOpacity.light,
    color: tokens.colors.accent.primary,
  },
});

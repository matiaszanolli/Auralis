/**
 * TrackCard Styled Components
 *
 * Reusable styled components for TrackCard layout
 */

import { tokens } from '@/design-system';
import { Card } from '@/design-system';
import { Box, CardContent, styled } from '@mui/material';

export const StyledTrackCard = styled(Card, {
  shouldForwardProp: (prop) => prop !== 'isPlaying',
})<{ isPlaying?: boolean }>(({ isPlaying }) => ({
  position: 'relative',
  borderRadius: 12,
  overflow: 'hidden',
  cursor: 'pointer',
  transition: tokens.transitions.state_inOut,
  background: isPlaying ? tokens.colors.bg.level4 : tokens.colors.bg.tertiary,
  // Visual anchor for currently playing track - stronger elevation
  boxShadow: isPlaying
    ? `0 4px 16px ${tokens.colors.opacityScale.dark.strong}, 0 0 0 1px ${tokens.colors.accent.primary}40` // Elevated + subtle accent glow
    : `0 2px 8px ${tokens.colors.opacityScale.dark.lighter}`, // Normal resting shadow
  transform: isPlaying ? 'translateY(-2px)' : 'none', // Slight lift for playing track
  '&:hover': {
    transform: 'translateY(-4px)',
    boxShadow: isPlaying
      ? `0 8px 28px ${tokens.colors.opacityScale.dark.strong}, 0 0 0 1px ${tokens.colors.accent.primary}60` // Enhanced glow on hover
      : `0 8px 24px ${tokens.colors.opacityScale.dark.strong}`,
    background: tokens.colors.bg.level4,
  },
}));

export const ArtworkContainer = styled(Box)({
  position: 'relative',
  width: '100%',
  paddingTop: '100%', // 1:1 aspect ratio
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  overflow: 'hidden',
  // Subtle shimmer animation for placeholders (defined below)
  '&:hover .shimmer-overlay': {
    animation: 'shimmer 3s ease-in-out infinite',
  },
  '@keyframes shimmer': {
    '0%': {
      transform: 'translateX(-100%)',
    },
    '100%': {
      transform: 'translateX(100%)',
    },
  },
});

export const PlayOverlay = styled(Box)(() => ({
  position: 'absolute',
  inset: 0,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  transition: tokens.transitions.state_inOut,
}));

export const DurationBadge = styled(Box)({
  position: 'absolute',
  bottom: 8,
  right: 8,
  paddingLeft: 8,
  paddingRight: 8,
  paddingTop: 4,
  paddingBottom: 4,
  borderRadius: 6, // Slightly larger for softer feel
  // Reduced contrast - low-contrast gray, semi-transparent (contextual, not constant)
  background: tokens.glass.starfield.medium, // #3950: unified starfield glass
  backdropFilter: 'blur(10px)',
  transition: tokens.transitions.hover_out,
});

export const TrackCardContent = styled(CardContent)({
  padding: 16,
});

export const NoArtworkIcon = styled(Box)({
  position: 'absolute',
  inset: 0,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
});

export const ShimmerOverlay = styled(Box)({
  position: 'absolute',
  top: 0,
  left: '-100%',
  width: '100%',
  height: '100%',
  background: tokens.gradients.shimmerSweep,
  pointerEvents: 'none',
});

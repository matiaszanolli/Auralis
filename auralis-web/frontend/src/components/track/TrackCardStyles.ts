/**
 * TrackCard Styled Components
 *
 * Reusable styled components for TrackCard layout
 */

import { tokens } from '@/design-system';
import { Box, CardContent, styled } from '@mui/material';
import { themeVars } from '@/theme/semanticTheme';

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
  // #5641: theme-aware fill (fixed starfield alpha was unreadable in light mode).
  background: themeVars.glassFill,
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

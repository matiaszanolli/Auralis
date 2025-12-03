/**
 * TrackCard Styled Components
 *
 * Reusable styled components for TrackCard layout
 */

import { auroraOpacity, gradients } from '../library/Styles/Color.styles';
import { tokens } from '@/design-system';
import { Card } from '@/design-system';
import { Box, CardContent, styled } from '@mui/material';

export const StyledTrackCard = styled(Card)(({ theme }) => ({
  position: 'relative',
  borderRadius: 8,
  overflow: 'hidden',
  cursor: 'pointer',
  transition: 'all 0.3s ease',
  background: tokens.colors.bg.tertiary,
  border: `1px solid ${tokens.colors.bg.elevated}`,
  '&:hover': {
    transform: 'translateY(-4px)',
    boxShadow: `0 8px 24px ${auroraOpacity.standard}`,
    border: `1px solid ${auroraOpacity.strong}`,
  },
}));

export const ArtworkContainer = styled(Box)({
  position: 'relative',
  width: '100%',
  paddingTop: '100%', // 1:1 aspect ratio
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
});

export const PlayOverlay = styled(Box)(({ theme }) => ({
  position: 'absolute',
  inset: 0,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  transition: 'all 0.3s ease',
}));

export const DurationBadge = styled(Box)({
  position: 'absolute',
  bottom: 8,
  right: 8,
  paddingLeft: 8,
  paddingRight: 8,
  paddingTop: 4,
  paddingBottom: 4,
  borderRadius: 4,
  background: 'rgba(0, 0, 0, 0.7)',
  backdropFilter: 'blur(10px)',
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

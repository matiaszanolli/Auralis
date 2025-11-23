import { Box, styled } from '@mui/material';
import { tokens } from '@/design-system/tokens';

export const CrossfadeIndicators = styled(Box)({
  position: 'absolute',
  top: 0,
  left: 0,
  right: 0,
  bottom: 0,
  pointerEvents: 'none',
  display: 'flex'
});

export const CrossfadeRegion = styled(Box)({
  position: 'absolute',
  height: '100%',
  background: `linear-gradient(90deg,
    ${tokens.colors.accent.primary}20,
    ${tokens.colors.accent.tertiary}30,
    ${tokens.colors.accent.primary}20
  )`,
  borderLeft: `1px solid ${tokens.colors.accent.primary}40`,
  borderRight: `1px solid ${tokens.colors.accent.primary}40`,
  opacity: 0.6,
  transition: tokens.transitions.opacity,
  '&:hover': {
    opacity: 0.9
  }
});

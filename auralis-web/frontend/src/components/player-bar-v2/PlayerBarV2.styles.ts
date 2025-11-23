/**
 * PlayerBarV2 Styled Components
 *
 * Layout-focused styling for the player bar container and grid sections.
 */

import { Box, styled } from '@mui/material';
import { tokens } from '@/design-system/tokens';

export const PlayerContainer = styled(Box)({
  position: 'fixed',
  bottom: 0,
  left: 0,
  right: 0,
  width: '100vw',
  height: tokens.components.playerBar.height,
  margin: 0,
  background: tokens.components.playerBar.background,
  backdropFilter: 'blur(20px)',
  borderTop: `1px solid ${tokens.colors.border.light}`,
  boxShadow: tokens.shadows.xl,
  zIndex: tokens.components.playerBar.zIndex,
  display: 'grid',
  gridTemplateColumns: '1fr auto 1fr',
  gridTemplateRows: '24px 1fr', // Progress bar (24px) + controls (remaining space)
  padding: `${tokens.spacing.sm} ${tokens.spacing.md} ${tokens.spacing.sm} ${tokens.spacing.md}`, // top right bottom left
  gap: tokens.spacing.xs,
  transition: tokens.transitions.all,
});

export const LeftSection = styled(Box)({
  gridColumn: '1',
  gridRow: '2',
  display: 'flex',
  alignItems: 'center',
  gap: tokens.spacing.md,
  minWidth: 0, // Enable text truncation
});

export const CenterSection = styled(Box)({
  gridColumn: '2',
  gridRow: '2',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
});

export const RightSection = styled(Box)({
  gridColumn: '3',
  gridRow: '2',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'flex-end',
  gap: tokens.spacing.md,
});

export const ProgressSection = styled(Box)({
  gridColumn: '1 / -1',
  gridRow: '1',
  display: 'flex',
  alignItems: 'center',
  gap: tokens.spacing.sm,
});

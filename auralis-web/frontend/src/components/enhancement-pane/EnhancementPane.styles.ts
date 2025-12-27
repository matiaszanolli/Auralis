import { styled } from '@mui/material/styles';
import { Box, Stack } from '@mui/material';
import { tokens } from '@/design-system';

export const CollapsedPaneContainer = styled(Box)({
  width: tokens.spacing.xxxl,
  height: '100%',
  background: tokens.colors.bg.secondary,
  borderLeft: `1px solid ${tokens.colors.border.light}`,
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  paddingTop: tokens.spacing.md,
  paddingBottom: tokens.spacing.md,
  transition: tokens.transitions.slow,
});

export const ExpandedPaneContainer = styled(Box)({
  width: tokens.components.rightPanel.width,
  height: '100%',
  background: tokens.colors.bg.secondary,
  // Removed border, using shadow for depth instead
  boxShadow: '-2px 0 16px rgba(0, 0, 0, 0.12)', // Subtle left shadow for separation
  display: 'flex',
  flexDirection: 'column',
  transition: tokens.transitions.slow,
  overflow: 'hidden',
});

export const PaneHeader = styled(Box)({
  padding: tokens.spacing.lg, // Increased from md for more breathing room
  paddingBottom: tokens.spacing.md, // Less bottom padding (asymmetric for cleaner look)
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  // Removed hard border, using subtle background difference instead
  background: tokens.colors.bg.level2, // Slightly darker than content for depth layering
});

export const PaneContent = styled(Box)({
  flex: 1,
  padding: tokens.spacing.xl, // Increased from lg (24px → 32px) for more breathing room
  paddingTop: tokens.spacing.lg, // Less top padding since header has padding
  overflowY: 'auto',
  background: tokens.colors.bg.secondary, // Explicit background for depth layering
});

export const CollapsedIconContainer = styled(Box)({
  marginTop: tokens.spacing.md,
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  gap: tokens.spacing.md,
});

export const DisabledStateContainer = styled(Box)({
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  textAlign: 'center',
  marginTop: tokens.spacing.xl,
});

export const ParametersStack = styled(Stack)({
  spacing: tokens.spacing.lg,
});

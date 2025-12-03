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
  borderLeft: `1px solid ${tokens.colors.border.light}`,
  display: 'flex',
  flexDirection: 'column',
  transition: tokens.transitions.slow,
  overflow: 'hidden',
});

export const PaneHeader = styled(Box)({
  padding: tokens.spacing.md,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  borderBottom: `1px solid ${tokens.colors.border.light}`,
});

export const PaneContent = styled(Box)({
  flex: 1,
  padding: tokens.spacing.lg,
  overflowY: 'auto',
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

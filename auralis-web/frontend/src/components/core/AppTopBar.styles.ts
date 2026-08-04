import { styled } from '@mui/material/styles';
import { Box } from '@mui/material';
import { tokens } from '@/design-system';
import { themeVars } from '@/theme/semanticTheme';

export const TopBarContainer = styled(Box)({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  padding: `${tokens.spacing.md} ${tokens.spacing.lg}`,
  background: themeVars.surfacePrimary,
  borderBottom: `1px solid ${themeVars.borderSubtle}`,
  height: 64,
  gap: tokens.spacing.md,
});

export const LeftSection = styled(Box)({
  display: 'flex',
  alignItems: 'center',
  gap: tokens.spacing.md,                               // 12px - organic spacing
});

export const RightSection = styled(Box)({
  display: 'flex',
  alignItems: 'center',
  gap: tokens.spacing.md,                               // 12px - organic spacing
  flex: 1,
  justifyContent: 'flex-end',
});

export const SearchContainer = styled(Box, {
  // Prevent 'focused' from being passed to the DOM
  shouldForwardProp: (prop) => prop !== 'focused',
})<{ focused: boolean }>(
  ({ focused }) => ({
    display: 'flex',
    alignItems: 'center',
    background: themeVars.surfaceSecondary,
    borderRadius: tokens.borderRadius.sm,
    border: `1px solid ${focused ? themeVars.accent : themeVars.borderDefault}`,
    boxShadow: focused ? `0 0 0 3px ${themeVars.focusRing}` : 'none',
    padding: `${tokens.spacing.cluster} ${tokens.spacing.md}`,
    gap: tokens.spacing.cluster,                        // 8px - tight cluster
    transition: tokens.transitions.hover_out,
  })
);

export const StatusIndicator = styled(Box)<{ color: string }>(({ color }) => ({
  width: tokens.spacing.md,                             // 12px - indicator size
  height: tokens.spacing.md,                            // 12px - indicator size
  borderRadius: tokens.borderRadius.full,               // 9999px - perfect circle
  background: color,
  boxShadow: `0 0 0 3px color-mix(in srgb, ${color} 18%, transparent)`,
  minWidth: tokens.spacing.md,
}));

export const TitleBox = styled('h1')({
  margin: 0,
  fontSize: tokens.typography.fontSize.xl,
  fontWeight: tokens.typography.fontWeight.semibold,
  color: themeVars.textPrimary,
  whiteSpace: 'nowrap',
});

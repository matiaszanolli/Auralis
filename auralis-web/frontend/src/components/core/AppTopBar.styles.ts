import { styled } from '@mui/material/styles';
import { Box } from '@mui/material';
import { tokens } from '@/design-system';

export const TopBarContainer = styled(Box)({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  padding: `${tokens.spacing.md} ${tokens.spacing.lg}`,
  // Semi-transparent to let starfield show through
  background: 'rgba(21, 29, 47, 0.55)',
  backdropFilter: 'blur(8px) saturate(1.05)',
  // Glass bevel: top highlight + bottom shadow (no hard borders)
  boxShadow: 'inset 0 1px 0 rgba(255, 255, 255, 0.08), inset 0 -1px 0 rgba(0, 0, 0, 0.20)',
  height: 70,
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

export const SearchContainer = styled(Box)<{ focused: boolean }>(
  ({ focused }) => ({
    display: 'flex',
    alignItems: 'center',
    background: 'transparent',
    borderRadius: 0,
    border: 'none',
    borderBottom: `1px solid ${focused ? tokens.colors.accent.primary : tokens.colors.border.light}`,
    padding: `${tokens.spacing.xs} ${tokens.spacing.md}`,
    gap: tokens.spacing.cluster,                        // 8px - tight cluster
    transition: tokens.transitions.fast,                // 150ms hover (close to 0.15s)
  })
);

export const StatusIndicator = styled(Box)<{ color: string }>(({ color }) => ({
  width: tokens.spacing.md,                             // 12px - indicator size
  height: tokens.spacing.md,                            // 12px - indicator size
  borderRadius: tokens.borderRadius.full,               // 9999px - perfect circle
  background: color,
  boxShadow: `0 0 8px ${color}80`,                     // 50% opacity glow
  minWidth: tokens.spacing.md,                          // 12px - prevent shrink
}));

export const TitleBox = styled(Box)({
  fontSize: tokens.typography.fontSize.xl,
  fontWeight: tokens.typography.fontWeight.semibold,
  color: tokens.colors.text.secondary,
  whiteSpace: 'nowrap',
});

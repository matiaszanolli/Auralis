import { styled } from '@mui/material/styles';
import { Box } from '@mui/material';
import { tokens } from '@/design-system';
import { auroraOpacity } from '../library/Styles/Color.styles';

export const TopBarContainer = styled(Box)({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  padding: `${tokens.spacing.md} ${tokens.spacing.lg}`,
  background: tokens.colors.bg.level2,
  borderBottom: `1px solid ${auroraOpacity.veryLight}`,
  height: 70,
  gap: tokens.spacing.md,
});

export const LeftSection = styled(Box)(({ theme }) => ({
  display: 'flex',
  alignItems: 'center',
  gap: 12,
}));

export const RightSection = styled(Box)({
  display: 'flex',
  alignItems: 'center',
  gap: 12,
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
    gap: 8,
    transition: 'border-color 0.15s ease',
  })
);

export const StatusIndicator = styled(Box)<{ color: string }>(({ color }) => ({
  width: 12,
  height: 12,
  borderRadius: '50%',
  background: color,
  boxShadow: `0 0 8px ${color}80`,
  minWidth: 12,
}));

export const TitleBox = styled(Box)({
  fontSize: tokens.typography.fontSize.xl,
  fontWeight: tokens.typography.fontWeight.semibold,
  color: tokens.colors.text.secondary,
  whiteSpace: 'nowrap',
});

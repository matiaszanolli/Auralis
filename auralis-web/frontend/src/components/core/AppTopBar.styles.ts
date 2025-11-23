import { styled } from '@mui/material/styles';
import { Box } from '@mui/material';
import { auroraOpacity } from '../library/Color.styles';

export const TopBarContainer = styled(Box)({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  padding: '16px 24px',
  background: 'var(--midnight-blue)',
  borderBottom: `1px solid ${auroraOpacity.veryLight}`,
  height: 70,
  gap: 16,
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
    background: auroraOpacity.minimal,
    borderRadius: '8px',
    border: `1px solid ${focused ? auroraOpacity.strong : auroraOpacity.veryLight}`,
    padding: '8px 12px',
    gap: 8,
    transition: 'all 0.2s ease',
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
  fontSize: '20px',
  fontWeight: 600,
  color: 'var(--silver)',
  whiteSpace: 'nowrap',
});

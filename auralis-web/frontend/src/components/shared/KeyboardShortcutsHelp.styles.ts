import { styled, Paper, Box, Typography } from '@mui/material';
import { auroraOpacity, colorAuroraPrimary } from '../library/Styles/Color.styles';
import { spacingSmall, spacingXSmall } from '../library/Styles/Spacing.styles';

export const CategorySection = styled(Paper)(({ theme }) => ({
  background: auroraOpacity.ultraLight,
  border: `1px solid ${auroraOpacity.veryLight}`,
  borderRadius: '12px',
  padding: spacingSmall,
  marginBottom: spacingSmall,
}));

export const ShortcutRow = styled(Box)(({ theme }) => ({
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  padding: `${spacingXSmall} 0`,
  borderBottom: `1px solid ${auroraOpacity.ultraLight}`,
  '&:last-child': {
    borderBottom: 'none',
  },
}));

export const ShortcutKey = styled(Box)(({ theme }) => ({
  background: auroraOpacity.standard,
  border: `1px solid ${auroraOpacity.veryStrong}`,
  borderRadius: '6px',
  padding: `${spacingXSmall} 12px`,
  fontFamily: 'monospace',
  fontSize: '14px',
  fontWeight: 'bold',
  color: colorAuroraPrimary,
  minWidth: '80px',
  textAlign: 'center',
  boxShadow: `0 2px 8px ${auroraOpacity.standard}`,
}));

export const ShortcutDescription = styled(Typography)(({ theme }) => ({
  color: auroraOpacity.veryStrong,
  fontSize: '14px',
}));

export const CategoryTitle = styled(Typography)(({ theme }) => ({
  color: colorAuroraPrimary,
  fontWeight: 'bold',
  fontSize: '16px',
  marginBottom: spacingXSmall,
  display: 'flex',
  alignItems: 'center',
  gap: spacingXSmall,
}));

export const EmptyStateBox = styled(Box)(({ theme }) => ({
  textAlign: 'center',
  padding: `40px ${spacingSmall}`,
  color: auroraOpacity.standard,
}));

export const DialogContentBoxStyles = {
  p: 3,
};

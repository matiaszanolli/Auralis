import { styled, Box } from '@mui/material';
import { auroraOpacity } from '../library/Color.styles';
import { tokens } from '@/design-system/tokens';

export const DialogContentBox = styled(Box)({
  pt: 2,
  display: 'flex',
  flexDirection: 'column',
  gap: 2,
});

export const TrackCountBox = styled(Box)({
  p: 2,
  background: auroraOpacity.veryLight,
  borderRadius: '8px',
  border: `1px solid ${auroraOpacity.standard}`,
});

export const TrackCountText = styled(Box)({
  color: tokens.colors.text.secondary,
  fontSize: '14px',
});

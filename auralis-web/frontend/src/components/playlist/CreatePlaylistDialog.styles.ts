import { styled, Box } from '@mui/material';
import { auroraOpacity } from '../library/Styles/Color.styles';
import { tokens } from '@/design-system/tokens';

export const DialogContentBox = styled(Box)({
  pt: 2,
  display: 'flex',
  flexDirection: 'column',
  gap: 2,
});

export const TrackCountInfoBox = styled(Box)({
  p: 2,
  background: auroraOpacity.veryLight,
  borderRadius: '8px',
  border: `1px solid ${auroraOpacity.standard}`,
});

export const TrackCountInfoText = styled(Box)({
  color: tokens.colors.text.secondary,
  fontSize: '14px',
});

import { styled, Box } from '@mui/material';
import { tokens } from '@/design-system';

export const DialogContentBox = styled(Box)({
  pt: 2,
  display: 'flex',
  flexDirection: 'column',
  gap: 2,
});

export const TrackCountInfoBox = styled(Box)({
  p: 2,
  background: tokens.colors.opacityScale.accent.veryLight,
  borderRadius: '8px',
  border: `1px solid ${tokens.colors.opacityScale.accent.standard}`,
});

export const TrackCountInfoText = styled(Box)({
  color: tokens.colors.text.secondary,
  fontSize: '14px',
});

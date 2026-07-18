import { styled } from '@mui/material/styles';
import { Paper, Box } from '@mui/material';
import { tokens } from '@/design-system';

export const ListViewContainer = styled(Paper)(({ theme }) => ({
  background: tokens.colors.opacityScale.white.veryLight,
  borderRadius: Number(theme.shape.borderRadius) * 3,
  overflow: 'hidden',
  padding: tokens.spacing.sm,
}));

export const TrackItemWrapper = styled(Box)({
  animation: 'fadeInLeft 0.5s ease-out forwards',
  '&:not(:last-child)': {
    marginBottom: 0,
  },
});

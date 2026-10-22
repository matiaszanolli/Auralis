import { styled } from '@mui/material/styles';
import { Paper } from '@mui/material';
import { tokens } from '@/design-system';

export const ListViewContainer = styled(Paper)(({ theme }) => ({
  background: tokens.colors.opacityScale.white.veryLight,
  borderRadius: Number(theme.shape.borderRadius) * 3,
  overflow: 'hidden',
  padding: tokens.spacing.sm,
}));


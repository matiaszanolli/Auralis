import { styled } from '@mui/material/styles';
import { Paper, Box } from '@mui/material';

export const ListViewContainer = styled(Paper)(({ theme }) => ({
  background: 'rgba(255,255,255,0.05)',
  borderRadius: theme.shape.borderRadius * 3,
  overflow: 'hidden',
  padding: theme.spacing(2),
}));

export const TrackItemWrapper = styled(Box)({
  animation: 'fadeInLeft 0.5s ease-out forwards',
  '&:not(:last-child)': {
    marginBottom: 0,
  },
});

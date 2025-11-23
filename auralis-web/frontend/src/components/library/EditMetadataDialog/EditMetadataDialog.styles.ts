import { styled, Box } from '@mui/material';
import { auroraOpacity } from '../Styles/Color.styles';
import { tokens } from '@/design-system/tokens';

export const DialogHeaderBox = styled(Box)({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
});

export const DialogTitleStyled = styled(Box)({
  color: tokens.colors.text.primary,
  borderBottom: `1px solid ${auroraOpacity.ultraLight}`,
});

export const DialogPaperProps = {
  sx: {
    bgcolor: '#1a1f3a',
    backgroundImage: 'linear-gradient(135deg, #1a1f3a 0%, #0f1228 100%)',
  },
};

export const AlertContainer = styled(Box)({
  mb: 2,
});

export const ContentBox = styled(Box)({
  mt: 2,
});

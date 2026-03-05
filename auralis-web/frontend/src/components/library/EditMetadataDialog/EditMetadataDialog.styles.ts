import { styled, Box } from '@mui/material';
import { tokens } from '@/design-system';

export const DialogHeaderBox = styled(Box)({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
});

export const DialogTitleStyled = styled(Box)({
  color: tokens.colors.text.primary,
  borderBottom: `1px solid ${tokens.colors.opacityScale.accent.ultraLight}`,
});

export const DialogPaperProps = {
  sx: {
    bgcolor: tokens.colors.bg.level3,
    backgroundImage: `linear-gradient(135deg, ${tokens.colors.bg.level3} 0%, ${tokens.colors.bg.level0} 100%)`,
  },
};

export const AlertContainer = styled(Box)({
  mb: 2,
});

export const ContentBox = styled(Box)({
  mt: 2,
});

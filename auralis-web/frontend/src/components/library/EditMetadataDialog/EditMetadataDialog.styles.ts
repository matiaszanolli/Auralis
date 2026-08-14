import { styled, Box } from '@mui/material';
import { tokens } from '@/design-system';
import { themeVars } from '@/theme/semanticTheme';

export const DialogHeaderBox = styled(Box)({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
});

export const DialogTitleStyled = styled(Box)({
  color: themeVars.textPrimary,
  borderBottom: `1px solid ${tokens.colors.opacityScale.accent.ultraLight}`,
});

export const DialogPaperProps = {
  sx: {
    bgcolor: themeVars.surfaceRaised,
    backgroundImage: `linear-gradient(135deg, ${themeVars.surfaceRaised} 0%, ${themeVars.canvas} 100%)`,
  },
};

export const AlertContainer = styled(Box)({
  mb: 2,
});

export const ContentBox = styled(Box)({
  mt: 2,
});

import { styled } from '@mui/material/styles';
import { DialogContent, DialogActions, Box } from '@mui/material';
import { tokens } from '@/design-system';
import { themeVars } from '@/theme/semanticTheme';

export const SettingsDialogContent = styled(DialogContent)({
  padding: tokens.spacing.lg,
  minHeight: 400,
});

export const SettingsDialogActions = styled(DialogActions)({
  padding: tokens.spacing.md,
  borderTop: `1px solid ${themeVars.borderSubtle}`,
});

export const SaveButtonGradient = {
  background: themeVars.accent,
  '&:hover': {
    background: themeVars.accentHover,
  },
};

export const FlexSpacer = styled(Box)({
  flex: 1,
});

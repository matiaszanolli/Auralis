import { styled } from '@mui/material/styles';
import { DialogContent, DialogActions, Box } from '@mui/material';
import { tokens } from '@/design-system';

export const SettingsDialogContent = styled(DialogContent)({
  padding: tokens.spacing.lg,
  minHeight: 400,
});

export const SettingsDialogActions = styled(DialogActions)({
  padding: tokens.spacing.md,
  borderTop: `1px solid ${tokens.colors.opacityScale.accent.ultraLight}`,
});

export const SaveButtonGradient = {
  background: `linear-gradient(45deg, ${tokens.colors.accent.primary}, ${tokens.colors.accent.secondary})`,
  '&:hover': {
    background: `linear-gradient(45deg, ${tokens.colors.accent.primary}, ${tokens.colors.accent.secondary})`,
  },
};

export const FlexSpacer = styled(Box)({
  flex: 1,
});

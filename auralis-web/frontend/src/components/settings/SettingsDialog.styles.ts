import { styled } from '@mui/material/styles';
import { DialogContent, DialogActions, Box } from '@mui/material';
import { auroraOpacity } from '../library/Color.styles';
import { tokens } from '@/design-system/tokens';

export const SettingsDialogContent = styled(DialogContent)({
  padding: tokens.spacing.lg,
  minHeight: 400,
});

export const SettingsDialogActions = styled(DialogActions)({
  padding: tokens.spacing.md,
  borderTop: `1px solid ${auroraOpacity.ultraLight}`,
});

export const SaveButtonGradient = {
  background: `linear-gradient(45deg, ${tokens.colors.accent.purple}, ${tokens.colors.accent.secondary})`,
  '&:hover': {
    background: `linear-gradient(45deg, ${tokens.colors.accent.purple}, ${tokens.colors.accent.secondary})`,
  },
};

export const FlexSpacer = styled(Box)({
  flex: 1,
});

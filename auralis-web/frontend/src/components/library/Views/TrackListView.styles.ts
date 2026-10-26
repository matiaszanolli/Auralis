import { styled } from '@mui/material/styles';
import { Paper } from '@mui/material';
import { tokens } from '@/design-system';
import { themeVars } from '@/theme/semanticTheme';

export const ListViewContainer = styled(Paper)(({ theme }) => ({
  background: themeVars.panelFill,
  borderRadius: Number(theme.shape.borderRadius) * 3,
  overflow: 'hidden',
  padding: tokens.spacing.sm,
}));


import { styled } from '@mui/material/styles';
import { Box } from '@mui/material';
import { tokens } from '@/design-system/tokens';

export const SimilarityContainer = styled(Box)({
  // Base styling handled by Box
});

export const SectionDivider = styled(Box)({
  borderBottom: `1px solid ${tokens.colors.border.light}`,
  padding: tokens.spacing.md,
});

export const DimensionRow = styled(Box)({
  marginBottom: tokens.spacing.lg,
});

export const ValueComparisonBox = styled(Box)({
  display: 'flex',
  justifyContent: 'space-between',
  marginTop: tokens.spacing.xs,
});

export const AccordionContainer = styled(Box)({
  backgroundColor: 'transparent',
  boxShadow: 'none',
  '&:before': { display: 'none' },
});

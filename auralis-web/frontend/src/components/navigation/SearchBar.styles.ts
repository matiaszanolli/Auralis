/**
 * SearchBar Styled Components
 */

import { IconButton, styled, Typography } from '@mui/material';
import { auroraOpacity } from '../library/Styles/Color.styles';
import { tokens } from '@/design-system/tokens';

export const ClearButton = styled(IconButton)({
  padding: '8px',
  color: tokens.colors.text.secondary,
  transition: 'all 0.2s ease',

  '&:hover': {
    color: tokens.colors.text.primary,
    background: auroraOpacity.ultraLight,
  },
});

export const ResultCount = styled(Typography)({
  fontSize: '12px',
  fontWeight: 500,
  color: tokens.colors.text.secondary,
  padding: '0 12px',
  whiteSpace: 'nowrap',
});

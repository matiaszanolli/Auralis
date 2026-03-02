/**
 * SelectableTrackRow Styled Components
 */

import { Box, Checkbox, styled } from '@mui/material';
import { tokens } from '@/design-system';

export const SelectableContainer = styled(Box, {
  shouldForwardProp: (prop) => prop !== 'isSelected',
})<{ isSelected: boolean }>(({ theme: _theme, isSelected }) => ({
  display: 'flex',
  alignItems: 'center',
  gap: '8px',
  padding: '4px 8px',
  borderRadius: '8px',
  backgroundColor: isSelected ? tokens.colors.opacityScale.accent.lighter : 'transparent',
  border: isSelected ? `1px solid ${tokens.colors.opacityScale.accent.strong}` : '1px solid transparent',
  transition: 'all 0.2s ease',
  cursor: 'pointer',
  '&:hover': {
    backgroundColor: isSelected ? tokens.colors.opacityScale.accent.standard : tokens.colors.opacityScale.accent.ultraLight,
    '& .selection-checkbox': {
      opacity: 1,
    },
  },
}));

export const StyledCheckbox = styled(Checkbox)(({ theme: _theme }) => ({
  color: tokens.colors.opacityScale.accent.lighter,
  opacity: 0,
  transition: 'opacity 0.2s ease',
  '&.Mui-checked': {
    color: tokens.colors.accent.primary,
    opacity: 1,
  },
  '&.visible': {
    opacity: 1,
  },
  '& .MuiSvgIcon-root': {
    fontSize: '20px',
  },
}));

export const TrackContainer = styled(Box)(({ theme: _theme }) => ({
  flex: 1,
  minWidth: 0, // Allow text truncation
}));

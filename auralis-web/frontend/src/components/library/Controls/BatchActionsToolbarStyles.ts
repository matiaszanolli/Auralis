/**
 * BatchActionsToolbar Styled Components
 */

import { cardShadows } from '../Styles/Shadow.styles';
import { spacingPresets } from '../Styles/Spacing.styles';
import { tokens } from '@/design-system';
import { IconButton } from '@/design-system';
import { Paper, Typography, styled } from '@mui/material';

export const ToolbarContainer = styled(Paper)(({ theme: _theme }) => ({
  position: 'fixed',
  top: '80px',
  left: '50%',
  transform: 'translateX(-50%)',
  zIndex: 1200,
  background: `linear-gradient(135deg, ${tokens.colors.opacityScale.accent.veryStrong} 0%, rgba(118, 75, 162, 0.95) 100%)`,
  backdropFilter: 'blur(20px)',
  border: `1px solid ${tokens.colors.opacityScale.accent.light}`,
  borderRadius: '16px',
  padding: spacingPresets.buttons.compact,
  display: 'flex',
  alignItems: 'center',
  gap: spacingPresets.gap.standard,
  boxShadow: cardShadows.dropdownDark,
  animation: 'slideDown 0.3s ease-out',
  '@keyframes slideDown': {
    from: {
      opacity: 0,
      transform: 'translate(-50%, -20px)',
    },
    to: {
      opacity: 1,
      transform: 'translate(-50%, 0)',
    },
  },
}));

export const SelectionCount = styled(Typography)(({ theme: _theme }) => ({
  color: tokens.colors.text.primary,
  fontWeight: 'bold',
  fontSize: '16px',
  minWidth: '140px',
}));

export const ActionButton = styled(IconButton)(({ theme: _theme }) => ({
  color: tokens.colors.text.primary,
  backgroundColor: tokens.colors.opacityScale.accent.light,
  '&:hover': {
    backgroundColor: tokens.colors.opacityScale.accent.standard,
  },
  transition: 'all 0.2s ease',
}));

export const CloseButton = styled(IconButton)(({ theme: _theme }) => ({
  color: tokens.colors.text.primary,
  marginLeft: 'auto',
  '&:hover': {
    backgroundColor: tokens.colors.opacityScale.accent.light,
  },
}));

/**
 * BatchActionsToolbar Styled Components
 */

import { cardShadows } from '@/components/library/Styles/Shadow.styles';
import { spacingPresets } from '@/components/library/Styles/Spacing.styles';
import { tokens, withOpacity } from '@/design-system';
import { IconButton } from '@/design-system';
import { Paper, Typography, styled } from '@mui/material';

export const ToolbarContainer = styled(Paper)(({ theme: _theme }) => ({
  position: 'fixed',
  top: '80px',
  left: '50%',
  transform: 'translateX(-50%)',
  zIndex: tokens.zIndex.fixed,
  // #3598: gradient now ramps from the brand violet accent to the harmonic
  // audioSemantic accent — previously the second stop was an inline
  // rgba(118, 75, 162, 0.95) that did not match any token.
  background: `linear-gradient(135deg, ${tokens.colors.opacityScale.accent.veryStrong} 0%, ${withOpacity(tokens.colors.audioSemantic.harmonic, 0.95)} 100%)`,
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
  fontWeight: tokens.typography.fontWeight.bold,
  fontSize: tokens.typography.fontSize.md,
  minWidth: '140px',
}));

export const ActionButton = styled(IconButton)(({ theme: _theme }) => ({
  color: tokens.colors.text.primary,
  backgroundColor: tokens.colors.opacityScale.accent.light,
  '&:hover': {
    backgroundColor: tokens.colors.opacityScale.accent.standard,
  },
  transition: tokens.transitions.hover_out,
}));

export const CloseButton = styled(IconButton)(({ theme: _theme }) => ({
  color: tokens.colors.text.primary,
  marginLeft: 'auto',
  '&:hover': {
    backgroundColor: tokens.colors.opacityScale.accent.light,
  },
}));

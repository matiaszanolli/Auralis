import { Box, IconButton, Paper, styled } from '@mui/material';
import { tokens } from '@/design-system';

/**
 * Styled components for EnhancementToggle variants
 * Exported for reuse in variant components
 */

export const ToggleButton = styled(IconButton, {
  shouldForwardProp: (prop) => prop !== '$isEnabled',
})<{ $isEnabled: boolean }>(({ $isEnabled }) => ({
  width: '40px',
  height: '40px',
  color: $isEnabled ? tokens.colors.accent.primary : tokens.colors.text.tertiary,
  background: $isEnabled ? `${tokens.colors.accent.primary}15` : 'transparent',
  border: `2px solid ${$isEnabled ? tokens.colors.accent.primary : tokens.colors.border.medium}`,
  boxShadow: $isEnabled ? tokens.shadows.glowSoft : 'none',
  transition: tokens.transitions.all,

  '&:hover': {
    transform: 'scale(1.1)',
    background: $isEnabled
      ? `${tokens.colors.accent.primary}25`
      : tokens.colors.bg.elevated,
    boxShadow: $isEnabled ? tokens.shadows.glowMd : tokens.shadows.md,
  },

  '&:active': {
    transform: 'scale(0.95)',
  },

  '& .MuiSvgIcon-root': {
    fontSize: '20px',
    transition: tokens.transitions.transform,
    transform: $isEnabled ? 'rotate(0deg)' : 'rotate(-180deg)',
  },
}));

export const EnhancementLabel = styled(Box, {
  shouldForwardProp: (prop) => prop !== '$isEnabled',
})<{ $isEnabled: boolean }>(({ $isEnabled }) => ({
  fontSize: tokens.typography.fontSize.xs,
  fontWeight: tokens.typography.fontWeight.medium,
  color: $isEnabled ? tokens.colors.accent.primary : tokens.colors.text.tertiary,
  textTransform: 'uppercase',
  letterSpacing: '0.5px',
  transition: tokens.transitions.color,
  marginTop: tokens.spacing.xs,
  textAlign: 'center',
}));

export const EnhancementContainer = styled(Box)({
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  gap: '2px',
});

export const SwitchPaper = styled(Paper, {
  shouldForwardProp: (prop) => prop !== '$isEnabled' && prop !== '$isProcessing',
})<{ $isEnabled: boolean; $isProcessing: boolean }>(
  ({ $isEnabled, $isProcessing }) => ({
    p: tokens.spacing.md,
    mb: tokens.spacing.lg,
    borderRadius: tokens.borderRadius.md,
    background: $isEnabled
      ? `${tokens.colors.accent.primary}1A` // ~10% opacity
      : tokens.colors.bg.tertiary,
    border: `1px solid ${
      $isEnabled
        ? `${tokens.colors.accent.primary}4D` // ~30% opacity
        : tokens.colors.border.light
    }`,
    transition: tokens.transitions.all,
    opacity: $isProcessing ? 0.7 : 1,
  })
);

import { Paper, styled, alpha } from '@mui/material';
import { tokens } from '@/design-system/tokens';
import { gradients } from '../../library/Styles/Color.styles';

/**
 * Styled components for DropZone
 */

export const DropZonePaper = styled(Paper, {
  shouldForwardProp: (prop) => prop !== '$isDragging' && prop !== '$disabled' && prop !== '$scanning',
})<{ $isDragging: boolean; $disabled: boolean; $scanning: boolean }>(
  ({ $isDragging, $disabled, $scanning }) => ({
    position: 'relative',
    padding: tokens.spacing.xxl,
    borderRadius: tokens.borderRadius.lg,
    border: `2px dashed ${
      $isDragging
        ? tokens.colors.accent.primary
        : $scanning
        ? alpha(tokens.colors.text.secondary, 0.3)
        : alpha(tokens.colors.text.disabled, 0.2)
    }`,
    background: $isDragging
      ? alpha(tokens.colors.accent.primary, 0.05)
      : $scanning
      ? alpha(tokens.colors.bg.elevated, 0.5)
      : 'transparent',
    cursor: $disabled || $scanning ? 'not-allowed' : 'pointer',
    transition: 'all 0.3s ease',
    textAlign: 'center',
    overflow: 'hidden',
    opacity: $disabled ? 0.5 : 1,

    ...((!$disabled && !$scanning) && {
      '&:hover': {
        borderColor: tokens.colors.accent.primary,
        background: alpha(tokens.colors.accent.primary, 0.02),
        transform: 'scale(1.01)',
      },
    }),

    ...($isDragging && {
      '&::before': {
        content: '""',
        position: 'absolute',
        inset: 0,
        background: gradients.aurora,
        opacity: 0.05,
        animation: 'pulse 2s ease-in-out infinite',
      },
    }),

    '@keyframes pulse': {
      '0%, 100%': { opacity: 0.05 },
      '50%': { opacity: 0.1 },
    },

    '@keyframes bounce': {
      '0%, 100%': {
        transform: 'translateY(0)',
      },
      '50%': {
        transform: 'translateY(-10px)',
      },
    },

    '@keyframes fadeIn': {
      from: {
        opacity: 0,
        transform: 'scale(0.8)',
      },
      to: {
        opacity: 1,
        transform: 'scale(1)',
      },
    },
  })
);

import { Alert, AlertColor, styled, keyframes } from '@mui/material';
import { tokens } from '@/design-system';
import { getToastBackgroundColor, getToastBorderColor } from './toastColors';

/**
 * Toast animation - slide in from right
 */
export const slideIn = keyframes`
  from {
    transform: translateX(100%);
    opacity: 0;
  }
  to {
    transform: translateX(0);
    opacity: 1;
  }
`;

/**
 * StyledAlert - Toast alert with severity-based colors and animations
 */
export const StyledAlert = styled(Alert)<{ severity: AlertColor }>(({ severity }) => {
  return {
    background: getToastBackgroundColor(severity),
    color: tokens.colors.text.primary,
    border: `1px solid ${getToastBorderColor(severity)}`,
    borderRadius: tokens.borderRadius.md,
    boxShadow: tokens.shadows.md,
    backdropFilter: 'blur(12px)',
    animation: `${slideIn} ${tokens.transitions.base}`,
    fontSize: tokens.typography.fontSize.base,
    fontWeight: tokens.typography.fontWeight.medium,

    '& .MuiAlert-icon': {
      color: getToastBorderColor(severity),
    },

    '& .MuiAlert-message': {
      padding: `${tokens.spacing.xs} 0`,
    },
  };
});

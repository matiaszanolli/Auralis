import { Alert, AlertColor, styled, keyframes } from '@mui/material';
import { tokens } from '@/design-system/tokens';
import { getToastBackgroundColor, getToastBorderColor } from './toastColors';
import { spacingXSmall } from '../../library/Spacing.styles';

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
    borderRadius: '8px',
    boxShadow: '0 4px 12px rgba(0, 0, 0, 0.19)',
    backdropFilter: 'blur(12px)',
    animation: `${slideIn} 0.3s ease-out`,
    fontSize: '14px',
    fontWeight: 500,

    '& .MuiAlert-icon': {
      color: getToastBorderColor(severity),
    },

    '& .MuiAlert-message': {
      padding: `${spacingXSmall} 0`,
    },
  };
});

import { AlertColor } from '@mui/material';
import { tokens, withOpacity } from '@/design-system';
import { themeVars } from '@/theme/semanticTheme';


/**
 * Get toast background color based on severity
 * @param severity - Alert severity type
 * @returns Background color string
 */
export const getToastBackgroundColor = (severity: AlertColor): string => {
  switch (severity) {
    case 'success':
      return withOpacity(tokens.colors.semantic.success, 0.15);
    case 'error':
      return withOpacity(tokens.colors.semantic.error, 0.15);
    case 'warning':
      return withOpacity(tokens.colors.semantic.warning, 0.15);
    case 'info':
      return tokens.colors.opacityScale.accent.veryLight; // replaces deprecated #667eea (fixes #2356)
    default:
      return themeVars.surfacePrimary;
  }
};

/**
 * Get toast border color based on severity
 * @param severity - Alert severity type
 * @returns Border color string
 */
export const getToastBorderColor = (severity: AlertColor): string => {
  switch (severity) {
    case 'success':
      return tokens.colors.semantic.success;
    case 'error':
      return tokens.colors.semantic.error;
    case 'warning':
      return tokens.colors.semantic.warning;
    case 'info':
      return tokens.colors.accent.primary; // replaces deprecated #667eea (fixes #2356)
    default:
      return themeVars.textDisabled;
  }
};

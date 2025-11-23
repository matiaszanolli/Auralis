import { AlertColor } from '@mui/material';
import { tokens } from '@/design-system/tokens';

/**
 * Convert hex color to RGBA string
 * @param hex - Hex color code (#RRGGBB)
 * @param alpha - Alpha value (0-1)
 * @returns RGBA color string
 */
const hexToRgba = (hex: string, alpha: number): string => {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
};

/**
 * Get toast background color based on severity
 * @param severity - Alert severity type
 * @returns Background color string
 */
export const getToastBackgroundColor = (severity: AlertColor): string => {
  switch (severity) {
    case 'success':
      return hexToRgba(tokens.colors.accent.success, 0.15);
    case 'error':
      return hexToRgba(tokens.colors.accent.error, 0.15);
    case 'warning':
      return hexToRgba(tokens.colors.accent.warning, 0.15);
    case 'info':
      return 'rgba(102, 126, 234, 0.1)';
    default:
      return tokens.colors.bg.secondary;
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
      return tokens.colors.accent.success;
    case 'error':
      return tokens.colors.accent.error;
    case 'warning':
      return tokens.colors.accent.warning;
    case 'info':
      return '#667eea';
    default:
      return tokens.colors.text.disabled;
  }
};

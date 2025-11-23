import React from 'react';
import { ThemeToggleLabel } from './ThemeToggle.styles';

interface ThemeToggleLabelComponentProps {
  isDark: boolean;
  color: string;
}

/**
 * ThemeToggleLabelComponent - Displays "Dark" or "Light" label
 *
 * Shows:
 * - Current theme mode as text label
 * - Only rendered when showLabel prop is true
 */
export const ThemeToggleLabelComponent: React.FC<ThemeToggleLabelComponentProps> = ({
  isDark,
  color,
}) => {
  return (
    <ThemeToggleLabel sx={{ color }}>
      {isDark ? 'Dark' : 'Light'}
    </ThemeToggleLabel>
  );
};

export default ThemeToggleLabelComponent;

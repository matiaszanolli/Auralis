import React from 'react';
import { LightMode, DarkMode } from '@mui/icons-material';
import { ThemeToggleIconContainer } from './ThemeToggle.styles';
import { colorAuroraPrimary, auroraOpacity } from '../../library/Styles/Color.styles';
import { tokens } from '@/design-system/tokens';

interface ThemeToggleIconProps {
  isDark: boolean;
  iconSize: number;
}

/**
 * ThemeToggleIcon - Animated icon that shows light/dark mode
 *
 * Features:
 * - Rotates between light and dark mode icons
 * - Glow effect for active mode
 * - Smooth transition animation
 */
export const ThemeToggleIcon: React.FC<ThemeToggleIconProps> = ({ isDark, iconSize }) => {
  return (
    <ThemeToggleIconContainer sx={{ transform: isDark ? 'rotate(0deg)' : 'rotate(180deg)' }}>
      {isDark ? (
        <DarkMode
          sx={{
            fontSize: iconSize,
            color: tokens.colors.semantic.warning,
            filter: `drop-shadow(0 0 8px ${tokens.colors.semantic.warning}99)`,
            transition: 'all 0.3s ease',
          }}
        />
      ) : (
        <LightMode
          sx={{
            fontSize: iconSize,
            color: colorAuroraPrimary,
            filter: `drop-shadow(0 0 8px ${auroraOpacity.veryStrong})`,
            transition: 'all 0.3s ease',
          }}
        />
      )}
    </ThemeToggleIconContainer>
  );
};

export default ThemeToggleIcon;

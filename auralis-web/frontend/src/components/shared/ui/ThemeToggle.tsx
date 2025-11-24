import React from 'react';
import { Tooltip } from '@mui/material';
import { useTheme } from '../../../contexts/ThemeContext';
import {
  ThemeToggleContainer,
  ThemeToggleButton,
  ThemeToggleBackground,
} from './ThemeToggle.styles';
import { useThemeToggleSize } from './useThemeToggleSize';
import { ThemeToggleIcon } from './ThemeToggleIcon';
import { ThemeToggleLabelComponent } from './ThemeToggleLabelComponent';

interface ThemeToggleProps {
  size?: 'small' | 'medium' | 'large';
  showLabel?: boolean;
}

/**
 * ThemeToggle - Light/Dark mode toggle button with animations
 *
 * Features:
 * - Smooth icon rotation between light and dark modes
 * - Animated background gradient on hover
 * - Configurable size (small, medium, large)
 * - Optional text label display
 * - Accessible tooltip with theme switch hint
 *
 * @example
 * <ThemeToggle size="medium" showLabel={false} />
 */
export const ThemeToggle: React.FC<ThemeToggleProps> = ({ size = 'medium', showLabel = false }) => {
  const { mode, toggleTheme, colors } = useTheme();
  const isDark = mode === 'dark';
  const { iconSize, buttonSize } = useThemeToggleSize(size);

  return (
    <Tooltip
      title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
      placement="bottom"
    >
      <ThemeToggleContainer>
        <ThemeToggleButton
          onClick={toggleTheme}
          buttonSize={buttonSize}
          isDark={isDark}
        >
          {/* Animated background gradient */}
          <ThemeToggleBackground sx={{
            '.MuiIconButton-root:hover &': {
              opacity: isDark ? 0.15 : 0.12,
            },
          }} />

          {/* Icon with rotation animation */}
          <ThemeToggleIcon isDark={isDark} iconSize={iconSize} />
        </ThemeToggleButton>

        {showLabel && (
          <ThemeToggleLabelComponent
            isDark={isDark}
            color={colors.text.secondary}
          />
        )}
      </ThemeToggleContainer>
    </Tooltip>
  );
};

export default ThemeToggle;

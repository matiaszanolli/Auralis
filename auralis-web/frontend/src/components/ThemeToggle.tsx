import React from 'react';
import { IconButton, Tooltip, Box } from '@mui/material';
import { LightMode, DarkMode } from '@mui/icons-material';
import { useTheme } from '../contexts/ThemeContext';
import { gradients } from '../theme/themeConfig';
import { auroraOpacity } from './library/Color.styles';

interface ThemeToggleProps {
  size?: 'small' | 'medium' | 'large';
  showLabel?: boolean;
}

const ThemeToggle: React.FC<ThemeToggleProps> = ({ size = 'medium', showLabel = false }) => {
  const { mode, toggleTheme, colors } = useTheme();
  const isDark = mode === 'dark';

  const iconSize = size === 'small' ? 20 : size === 'large' ? 28 : 24;
  const buttonSize = size === 'small' ? 36 : size === 'large' ? 52 : 44;

  return (
    <Tooltip
      title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
      placement="bottom"
    >
      <Box
        sx={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 1,
        }}
      >
        <IconButton
          onClick={toggleTheme}
          sx={{
            width: buttonSize,
            height: buttonSize,
            background: isDark
              ? 'rgba(255, 255, 255, 0.05)'
              : auroraOpacity.ultraLight,
            backdropFilter: 'blur(10px)',
            border: `1px solid ${
              isDark ? 'rgba(255, 255, 255, 0.1)' : auroraOpacity.lighter
            }`,
            transition: 'all 0.4s cubic-bezier(0.4, 0, 0.2, 1)',
            overflow: 'hidden',
            position: 'relative',
            '&:hover': {
              background: isDark
                ? 'rgba(255, 255, 255, 0.1)'
                : auroraOpacity.light,
              transform: 'scale(1.05) rotate(15deg)',
              boxShadow: isDark
                ? `0 4px 20px ${auroraOpacity.strong}`
                : `0 4px 20px ${auroraOpacity.standard}`,
            },
            '&:active': {
              transform: 'scale(0.95) rotate(0deg)',
            },
          }}
        >
          {/* Animated background gradient */}
          <Box
            sx={{
              position: 'absolute',
              inset: 0,
              background: gradients.aurora,
              opacity: 0,
              transition: 'opacity 0.4s ease',
              '.MuiIconButton-root:hover &': {
                opacity: isDark ? 0.15 : 0.12,
              },
            }}
          />

          {/* Icon with rotation animation */}
          <Box
            sx={{
              position: 'relative',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              transition: 'transform 0.5s cubic-bezier(0.4, 0, 0.2, 1)',
              transform: isDark ? 'rotate(0deg)' : 'rotate(180deg)',
            }}
          >
            {isDark ? (
              <DarkMode
                sx={{
                  fontSize: iconSize,
                  color: '#ffa502',
                  filter: 'drop-shadow(0 0 8px rgba(255, 165, 2, 0.6))',
                  transition: 'all 0.3s ease',
                }}
              />
            ) : (
              <LightMode
                sx={{
                  fontSize: iconSize,
                  color: '#667eea',
                  filter: `drop-shadow(0 0 8px ${auroraOpacity.veryStrong})`,
                  transition: 'all 0.3s ease',
                }}
              />
            )}
          </Box>
        </IconButton>

        {showLabel && (
          <Box
            sx={{
              fontSize: 12,
              fontWeight: 600,
              color: colors.text.secondary,
              textTransform: 'uppercase',
              letterSpacing: 1,
            }}
          >
            {isDark ? 'Dark' : 'Light'}
          </Box>
        )}
      </Box>
    </Tooltip>
  );
};

export default ThemeToggle;

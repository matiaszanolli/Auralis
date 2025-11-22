import React, { useState } from 'react';
import { Box, Typography, Tooltip } from '@mui/material';
import {
  AutoAwesome,
  WavesOutlined,
  WhatshotOutlined,
  FlareOutlined,
  BoltOutlined,
} from '@mui/icons-material';
import { colors, gradients } from '../theme/auralisTheme';
import { auroraOpacity, colorAuroraPrimary } from './library/Color.styles';

interface Preset {
  value: string;
  label: string;
  description: string;
  gradient: string;
  icon: React.ReactNode;
  angle: number; // Position on the circle (0-360 degrees)
}

interface RadialPresetSelectorProps {
  currentPreset: string;
  onPresetChange: (preset: string) => void;
  disabled?: boolean;
  size?: number; // Diameter of the circle
}

const RadialPresetSelector: React.FC<RadialPresetSelectorProps> = ({
  currentPreset,
  onPresetChange,
  disabled = false,
  size = 240,
}) => {
  const [hoveredPreset, setHoveredPreset] = useState<string | null>(null);

  // Define presets with unique colors and positions around the circle
  const presets: Preset[] = [
    {
      value: 'adaptive',
      label: 'Adaptive',
      description: 'Intelligent content-aware mastering',
      gradient: gradients.aurora,
      icon: <AutoAwesome />,
      angle: 0, // Top
    },
    {
      value: 'bright',
      label: 'Bright',
      description: 'Enhances clarity and presence',
      gradient: gradients.neonSunset,
      icon: <FlareOutlined />,
      angle: 72, // Top-right
    },
    {
      value: 'punchy',
      label: 'Punchy',
      description: 'Increases impact and dynamics',
      gradient: gradients.electricPurple,
      icon: <BoltOutlined />,
      angle: 144, // Bottom-right
    },
    {
      value: 'warm',
      label: 'Warm',
      description: 'Adds warmth and smoothness',
      gradient: gradients.neonSunset,
      icon: <WhatshotOutlined />,
      angle: 216, // Bottom-left
    },
    {
      value: 'gentle',
      label: 'Gentle',
      description: 'Subtle mastering with minimal processing',
      gradient: gradients.deepOcean,
      icon: <WavesOutlined />,
      angle: 288, // Top-left
    },
  ];

  // Calculate position on circle
  const getPosition = (angle: number, radius: number) => {
    const rad = ((angle - 90) * Math.PI) / 180; // -90 to start from top
    return {
      x: Math.cos(rad) * radius,
      y: Math.sin(rad) * radius,
    };
  };

  const radius = (size - 80) / 2; // Leave space for preset buttons
  const centerSize = size / 3;

  const currentPresetData = presets.find((p) => p.value === currentPreset) || presets[0];

  return (
    <Box
      sx={{
        position: 'relative',
        width: size,
        height: size,
        margin: '0 auto',
        opacity: disabled ? 0.4 : 1,
        pointerEvents: disabled ? 'none' : 'auto',
        transition: 'opacity 0.3s ease',
      }}
    >
      {/* Center hub - Current preset */}
      <Box
        sx={{
          position: 'absolute',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          width: centerSize,
          height: centerSize,
          borderRadius: '50%',
          background: currentPresetData.gradient,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          boxShadow: `0 0 40px ${currentPresetData.gradient.match(/#[0-9a-f]{6}/i)?.[0] || colorAuroraPrimary}66`,
          transition: 'all 0.5s cubic-bezier(0.4, 0, 0.2, 1)',
          border: '3px solid rgba(255, 255, 255, 0.2)',
          backdropFilter: 'blur(10px)',
        }}
      >
        <Box
          sx={{
            fontSize: 32,
            color: '#fff',
            mb: 0.5,
            filter: 'drop-shadow(0 2px 4px rgba(0,0,0,0.3))',
            animation: 'pulse 2s ease-in-out infinite',
            '@keyframes pulse': {
              '0%, 100%': { transform: 'scale(1)' },
              '50%': { transform: 'scale(1.1)' },
            },
          }}
        >
          {currentPresetData.icon}
        </Box>
        <Typography
          variant="caption"
          sx={{
            color: '#fff',
            fontWeight: 700,
            fontSize: 13,
            textTransform: 'uppercase',
            letterSpacing: 1.2,
            textShadow: '0 2px 4px rgba(0,0,0,0.3)',
          }}
        >
          {currentPresetData.label}
        </Typography>
      </Box>

      {/* Preset buttons around the circle */}
      {presets.map((preset) => {
        const pos = getPosition(preset.angle, radius);
        const isActive = preset.value === currentPreset;
        const isHovered = preset.value === hoveredPreset;
        const buttonSize = isActive ? 64 : isHovered ? 56 : 52;

        return (
          <Tooltip
            key={preset.value}
            title={
              <Box sx={{ textAlign: 'center', py: 0.5 }}>
                <Typography variant="body2" sx={{ fontWeight: 600, mb: 0.5 }}>
                  {preset.label}
                </Typography>
                <Typography variant="caption" sx={{ fontSize: 11, opacity: 0.9 }}>
                  {preset.description}
                </Typography>
              </Box>
            }
            placement="top"
            arrow
          >
            <Box
              onClick={() => !isActive && onPresetChange(preset.value)}
              onMouseEnter={() => setHoveredPreset(preset.value)}
              onMouseLeave={() => setHoveredPreset(null)}
              sx={{
                position: 'absolute',
                top: '50%',
                left: '50%',
                width: buttonSize,
                height: buttonSize,
                transform: `translate(calc(-50% + ${pos.x}px), calc(-50% + ${pos.y}px))`,
                borderRadius: '50%',
                background: isActive ? preset.gradient : colors.background.surface,
                border: isActive
                  ? '3px solid rgba(255, 255, 255, 0.4)'
                  : isHovered
                  ? `2px solid ${preset.gradient.match(/#[0-9a-f]{6}/i)?.[0] || colorAuroraPrimary}`
                  : '2px solid rgba(255, 255, 255, 0.1)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: isActive ? 'default' : 'pointer',
                transition: 'all 0.4s cubic-bezier(0.4, 0, 0.2, 1)',
                boxShadow: isActive
                  ? `0 0 30px ${preset.gradient.match(/#[0-9a-f]{6}/i)?.[0] || colorAuroraPrimary}99`
                  : isHovered
                  ? `0 0 20px ${preset.gradient.match(/#[0-9a-f]{6}/i)?.[0] || colorAuroraPrimary}66`
                  : '0 2px 8px rgba(0, 0, 0, 0.3)',
                zIndex: isActive ? 10 : isHovered ? 5 : 1,
                '&:hover': {
                  transform: `translate(calc(-50% + ${pos.x}px), calc(-50% + ${pos.y}px)) scale(1.05)`,
                },
                '&:active': {
                  transform: `translate(calc(-50% + ${pos.x}px), calc(-50% + ${pos.y}px)) scale(0.95)`,
                },
              }}
            >
              <Box
                sx={{
                  fontSize: isActive ? 28 : 24,
                  color: isActive ? '#fff' : isHovered ? '#fff' : colors.text.secondary,
                  transition: 'all 0.3s ease',
                  filter: isActive
                    ? 'drop-shadow(0 2px 4px rgba(0,0,0,0.3))'
                    : 'none',
                }}
              >
                {preset.icon}
              </Box>
            </Box>
          </Tooltip>
        );
      })}

      {/* Connecting lines (subtle) */}
      <svg
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          width: '100%',
          height: '100%',
          pointerEvents: 'none',
          opacity: 0.15,
        }}
      >
        {presets.map((preset) => {
          const pos = getPosition(preset.angle, radius);
          const centerX = size / 2;
          const centerY = size / 2;
          const isActive = preset.value === currentPreset;

          return (
            <line
              key={preset.value}
              x1={centerX}
              y1={centerY}
              x2={centerX + pos.x}
              y2={centerY + pos.y}
              stroke={isActive ? colorAuroraPrimary : '#ffffff'}
              strokeWidth={isActive ? 2 : 1}
              strokeDasharray={isActive ? '0' : '4 4'}
              style={{
                transition: 'all 0.3s ease',
              }}
            />
          );
        })}
      </svg>

      {/* Outer ring decoration */}
      <Box
        sx={{
          position: 'absolute',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          width: radius * 2 + 40,
          height: radius * 2 + 40,
          borderRadius: '50%',
          border: `1px solid ${auroraOpacity.standard}`,
          pointerEvents: 'none',
          '&::before': {
            content: '""',
            position: 'absolute',
            inset: -2,
            borderRadius: '50%',
            background: gradients.aurora,
            opacity: 0.05,
            animation: 'rotate 20s linear infinite',
          },
          '@keyframes rotate': {
            from: { transform: 'rotate(0deg)' },
            to: { transform: 'rotate(360deg)' },
          },
        }}
      />
    </Box>
  );
};

export default RadialPresetSelector;

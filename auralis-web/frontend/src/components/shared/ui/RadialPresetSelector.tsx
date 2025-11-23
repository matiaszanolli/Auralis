import React from 'react';
import { Box, Typography } from '@mui/material';
import { PRESETS, getCirclePosition, Preset } from './presetConfig';
import { PresetItem } from './PresetItem';
import { usePresetSelection } from './usePresetSelection';
import { auroraOpacity, colorAuroraPrimary, gradients } from '@/components/library/Styles/Color.styles';
import { tokens } from '@/design-system/tokens';

interface RadialPresetSelectorProps {
  currentPreset: string;
  onPresetChange: (preset: string) => void;
  disabled?: boolean;
  size?: number; // Diameter of the circle
}

/**
 * Circular preset selector UI component
 *
 * Displays 5 audio processing presets (Adaptive, Bright, Punchy, Warm, Gentle)
 * arranged in a circle with:
 * - Center hub showing current preset with animated icon
 * - Surrounding preset buttons with hover effects
 * - Connecting lines and decorative ring
 * - Full keyboard and mouse interaction support
 *
 * @example
 * ```tsx
 * <RadialPresetSelector
 *   currentPreset={preset}
 *   onPresetChange={setPreset}
 *   size={240}
 * />
 * ```
 */
const RadialPresetSelector: React.FC<RadialPresetSelectorProps> = ({
  currentPreset,
  onPresetChange,
  disabled = false,
  size = 240,
}) => {
  const { hoveredPreset, setHoveredPreset, getCirclePosition: calculatePosition } = usePresetSelection();

  const radius = (size - 80) / 2; // Leave space for preset buttons
  const centerSize = size / 3;

  const currentPresetData = PRESETS.find((p) => p.value === currentPreset) || PRESETS[0];

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
          border: `3px solid ${auroraOpacity.lighter}`,
          backdropFilter: 'blur(10px)',
        }}
      >
        <Box
          sx={{
            fontSize: 32,
            color: tokens.colors.text.primary,
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
            color: tokens.colors.text.primary,
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
      {PRESETS.map((preset) => {
        const pos = calculatePosition(preset.angle, radius);
        const isActive = preset.value === currentPreset;
        const isHovered = preset.value === hoveredPreset;

        return (
          <PresetItem
            key={preset.value}
            preset={preset}
            isActive={isActive}
            isHovered={isHovered}
            position={pos}
            size={size}
            onSelect={onPresetChange}
            onHover={setHoveredPreset}
          />
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
        {PRESETS.map((preset) => {
          const pos = getCirclePosition(preset.angle, radius);
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
              stroke={isActive ? colorAuroraPrimary : tokens.colors.text.primary}
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

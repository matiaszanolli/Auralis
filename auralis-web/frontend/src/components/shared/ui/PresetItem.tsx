import React from 'react';
import { Box, Tooltip, Typography } from '@mui/material';
import { auroraOpacity, colorAuroraPrimary } from '../../library/Styles/Color.styles';
import { tokens } from '@/design-system/tokens';
import { Preset } from './presetConfig';

interface PresetItemProps {
  preset: Preset;
  isActive: boolean;
  isHovered: boolean;
  position: { x: number; y: number };
  size: number;
  onSelect: (value: string) => void;
  onHover: (value: string | null) => void;
}

/**
 * Individual preset button in the RadialPresetSelector
 * Handles rendering, interaction, and visual feedback for a single preset
 */
export const PresetItem: React.FC<PresetItemProps> = ({
  preset,
  isActive,
  isHovered,
  position,
  size,
  onSelect,
  onHover,
}) => {
  const buttonSize = isActive ? 64 : isHovered ? 56 : 52;

  // Extract hex color from gradient for effects
  const extractHexColor = (gradient: string): string => {
    const match = gradient.match(/#[0-9a-f]{6}/i);
    return match?.[0] || colorAuroraPrimary;
  };

  const presetColor = extractHexColor(preset.gradient);

  return (
    <Tooltip
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
        onClick={() => !isActive && onSelect(preset.value)}
        onMouseEnter={() => onHover(preset.value)}
        onMouseLeave={() => onHover(null)}
        sx={{
          position: 'absolute',
          top: '50%',
          left: '50%',
          width: buttonSize,
          height: buttonSize,
          transform: `translate(calc(-50% + ${position.x}px), calc(-50% + ${position.y}px))`,
          borderRadius: '50%',
          background: isActive ? preset.gradient : tokens.colors.bg.tertiary,
          border: isActive
            ? `3px solid ${auroraOpacity.stronger}`
            : isHovered
            ? `2px solid ${presetColor}`
            : `2px solid ${auroraOpacity.ultraLight}`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          cursor: isActive ? 'default' : 'pointer',
          transition: 'all 0.4s cubic-bezier(0.4, 0, 0.2, 1)',
          boxShadow: isActive
            ? `0 0 30px ${presetColor}99`
            : isHovered
            ? `0 0 20px ${presetColor}66`
            : '0 2px 8px rgba(0, 0, 0, 0.19)',
          zIndex: isActive ? 10 : isHovered ? 5 : 1,
          '&:hover': {
            transform: `translate(calc(-50% + ${position.x}px), calc(-50% + ${position.y}px)) scale(1.05)`,
          },
          '&:active': {
            transform: `translate(calc(-50% + ${position.x}px), calc(-50% + ${position.y}px)) scale(0.95)`,
          },
        }}
      >
        <Box
          sx={{
            fontSize: isActive ? 28 : 24,
            color: isActive
              ? tokens.colors.text.primary
              : isHovered
              ? tokens.colors.text.primary
              : tokens.colors.text.secondary,
            transition: 'all 0.3s ease',
            filter: isActive ? 'drop-shadow(0 2px 4px rgba(0,0,0,0.3))' : 'none',
          }}
        >
          {preset.icon}
        </Box>
      </Box>
    </Tooltip>
  );
};

export default PresetItem;

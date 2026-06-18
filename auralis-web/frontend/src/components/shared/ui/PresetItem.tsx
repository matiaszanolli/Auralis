import { KeyboardEvent } from 'react';
import { Box, Typography } from '@mui/material';
import { Tooltip } from '@/design-system';
import { tokens } from '@/design-system';
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
export const PresetItem = ({
  preset,
  isActive,
  isHovered,
  position,
  size: _size,
  onSelect,
  onHover,
}: PresetItemProps) => {
  const buttonSize = isActive ? 64 : isHovered ? 56 : 52;

  // Extract hex color from gradient for effects
  const extractHexColor = (gradient: string): string => {
    const match = gradient.match(/#[0-9a-f]{6}/i);
    return match?.[0] || tokens.colors.accent.primary;
  };

  const presetColor = extractHexColor(preset.gradient);

  return (
    <Tooltip
      title={
        <Box sx={{ textAlign: 'center', py: 0.5 }}>
          <Typography variant="body2" sx={{ fontWeight: tokens.typography.fontWeight.semibold, mb: 0.5 }}>
            {preset.label}
          </Typography>
          <Typography variant="caption" sx={{ fontSize: tokens.typography.fontSize.xs, opacity: 0.9 }}>
            {preset.description}
          </Typography>
        </Box>
      }
      placement="top"
      arrow
    >
      <Box
        role="button"
        tabIndex={isActive ? -1 : 0}
        aria-pressed={isActive}
        aria-label={preset.label}
        onClick={() => !isActive && onSelect(preset.value)}
        onKeyDown={(e: KeyboardEvent) => {
          if (!isActive && (e.key === 'Enter' || e.key === ' ')) {
            e.preventDefault();
            onSelect(preset.value);
          }
        }}
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
            ? `3px solid ${tokens.colors.border.heavy}`
            : isHovered
            ? `2px solid ${presetColor}`
            : `2px solid ${tokens.colors.border.light}`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          cursor: isActive ? 'default' : 'pointer',
          transition: tokens.transitions.state_inOut,
          boxShadow: isActive
            ? `0 0 30px ${presetColor}99`
            : isHovered
            ? `0 0 20px ${presetColor}66`
            : `0 2px 8px ${tokens.colors.opacityScale.dark.standard}`,
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
            // 28 maps to the 2xl token; the inactive 24 is off-scale, so use
            // the nearest named step xl (22px) per #4204.
            fontSize: isActive ? tokens.typography.fontSize['2xl'] : tokens.typography.fontSize.xl,
            color: isActive
              ? tokens.colors.text.primary
              : isHovered
              ? tokens.colors.text.primary
              : tokens.colors.text.secondary,
            transition: tokens.transitions.state_inOut,
            filter: isActive ? `drop-shadow(0 2px 4px ${tokens.colors.opacityScale.dark.strong})` : 'none',
          }}
        >
          {preset.icon}
        </Box>
      </Box>
    </Tooltip>
  );
};

export default PresetItem;

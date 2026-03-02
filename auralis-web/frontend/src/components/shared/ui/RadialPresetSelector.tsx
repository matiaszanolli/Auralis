import React from 'react';
import { Box } from '@mui/material';
import { PRESETS } from './presetConfig';
import { PresetItem } from './PresetItem';
import { RadialCenterHub } from './RadialCenterHub';
import { RadialDecorations } from './RadialDecorations';
import { usePresetSelection } from './usePresetSelection';

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
export const RadialPresetSelector: React.FC<RadialPresetSelectorProps> = ({
  currentPreset,
  onPresetChange,
  disabled = false,
  size = 240,
}) => {
  const { hoveredPreset, setHoveredPreset, getCirclePosition: calculatePosition } = usePresetSelection();

  const radius = (size - 80) / 2; // Leave space for preset buttons
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
      <RadialCenterHub preset={currentPresetData} size={size} />

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

      {/* Connecting lines and decorations */}
      <RadialDecorations size={size} radius={radius} currentPreset={currentPreset} />
    </Box>
  );
};

export default RadialPresetSelector;

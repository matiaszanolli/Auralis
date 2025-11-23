/**
 * RadialDecorations - SVG connector lines and decorative ring
 *
 * Renders connecting lines from center to presets and rotating outer ring.
 */

import React from 'react';
import { Box } from '@mui/material';
import { PRESETS, getCirclePosition } from './presetConfig';
import { auroraOpacity, colorAuroraPrimary, gradients } from '../../library/Styles/Color.styles';
import { tokens } from '@/design-system/tokens';

interface RadialDecorationsProps {
  size: number; // Diameter of selector
  radius: number; // Radius to preset buttons
  currentPreset: string;
}

export const RadialDecorations: React.FC<RadialDecorationsProps> = ({
  size,
  radius,
  currentPreset,
}) => {
  return (
    <>
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
    </>
  );
};

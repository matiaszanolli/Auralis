/**
 * AuroraWaveIcon - Aurora wave SVG icon
 */

import React from 'react';
import { WaveIcon } from './AuroraLogo.styles';

interface AuroraWaveIconProps {
  size: number;
}

export const AuroraWaveIcon: React.FC<AuroraWaveIconProps> = ({ size }) => {
  return (
    <WaveIcon size={size} viewBox="0 0 24 24" fill="none">
      {/* Aurora wave pattern */}
      <path
        d="M2 12C2 12 4 8 8 8C12 8 12 16 16 16C20 16 22 12 22 12"
        stroke="white"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M2 16C2 16 4 12 8 12C12 12 12 20 16 20C20 20 22 16 22 16"
        stroke="white"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity="0.6"
      />
      <path
        d="M2 8C2 8 4 4 8 4C12 4 12 12 16 12C20 12 22 8 22 8"
        stroke="white"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity="0.4"
      />
    </WaveIcon>
  );
};

export default AuroraWaveIcon;

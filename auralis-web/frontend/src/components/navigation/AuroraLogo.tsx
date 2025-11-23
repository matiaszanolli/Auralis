import React from 'react';
import { LogoContainer, LogoIcon, LogoText } from './AuroraLogo.styles';
import AuroraWaveIcon from './AuroraWaveIcon';

interface AuroraLogoProps {
  size?: 'small' | 'medium' | 'large';
  showText?: boolean;
  animated?: boolean;
}

export const AuroraLogo: React.FC<AuroraLogoProps> = ({
  size = 'medium',
  showText = true,
  animated = false,
}) => {
  const iconSize = {
    small: 32,
    medium: 40,
    large: 56,
  }[size];

  return (
    <LogoContainer animated={animated}>
      <LogoIcon size={iconSize}>
        <AuroraWaveIcon size={iconSize} />
      </LogoIcon>

      {showText && (
        <LogoText size={size} animated={animated}>
          Auralis
        </LogoText>
      )}
    </LogoContainer>
  );
};

export default AuroraLogo;

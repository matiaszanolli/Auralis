import React from 'react';
import { Card, CardProps, styled, keyframes } from '@mui/material';
import { colors, gradients } from '../../theme/auralisTheme';

interface GlowCardProps extends CardProps {
  glowColor?: string;
  hoverGlow?: boolean;
}

const pulse = keyframes`
  0%, 100% {
    box-shadow: 0 0 20px rgba(102, 126, 234, 0.3);
  }
  50% {
    box-shadow: 0 0 40px rgba(102, 126, 234, 0.5);
  }
`;

const StyledGlowCard = styled(Card)<{ glowcolor?: string; hoverglow?: string }>(
  ({ glowcolor, hoverglow }) => ({
    background: colors.background.secondary,
    backgroundImage: 'none',
    borderRadius: '12px',
    border: `1px solid ${glowcolor || 'rgba(102, 126, 234, 0.2)'}`,
    transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
    position: 'relative',
    overflow: 'hidden',

    '&::before': {
      content: '""',
      position: 'absolute',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      background: gradients.aurora,
      opacity: 0,
      transition: 'opacity 0.3s ease',
      pointerEvents: 'none',
      zIndex: 0,
    },

    '& > *': {
      position: 'relative',
      zIndex: 1,
    },

    ...(hoverglow === 'true' && {
      '&:hover': {
        transform: 'translateY(-4px)',
        boxShadow: `0 12px 32px ${glowcolor || 'rgba(102, 126, 234, 0.4)'}`,
        border: `1px solid ${glowcolor || 'rgba(102, 126, 234, 0.5)'}`,

        '&::before': {
          opacity: 0.05,
        },
      },
    }),
  })
);

export const GlowCard: React.FC<GlowCardProps> = ({
  children,
  glowColor,
  hoverGlow = true,
  ...props
}) => {
  return (
    <StyledGlowCard
      glowcolor={glowColor}
      hoverglow={hoverGlow ? 'true' : 'false'}
      {...props}
    >
      {children}
    </StyledGlowCard>
  );
};

export default GlowCard;

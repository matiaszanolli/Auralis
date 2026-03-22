import { Box, Typography } from '@mui/material';
import { tokens } from '@/design-system';
import { arcPulse } from './animations';

interface GlowingArcProps {
  isAnimating: boolean;
  intensity: number;
  energyLevel: number;
}

export const GlowingArc = ({ isAnimating, intensity, energyLevel }: GlowingArcProps) => {
  const glowIntensity = Math.sqrt(intensity);

  // Arc spans based on energy level (more energy = wider arc)
  const arcDegrees = 120 + energyLevel * 60; // 120-180 degrees
  const startAngle = (180 - arcDegrees) / 2;

  return (
    <Box
      sx={{
        position: 'relative',
        width: '100%',
        height: '100px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        my: tokens.spacing.lg,
      }}
    >
      {/* Outer glow arc */}
      <Box
        sx={{
          position: 'absolute',
          width: '200px',
          height: '100px',
          borderRadius: '100px 100px 0 0',
          background: `conic-gradient(
            from ${startAngle}deg at 50% 100%,
            transparent 0deg,
            rgba(115, 102, 240, ${0.1 + glowIntensity * 0.3}) ${arcDegrees * 0.3}deg,
            rgba(0, 200, 220, ${0.2 + glowIntensity * 0.4}) ${arcDegrees * 0.5}deg,
            rgba(115, 102, 240, ${0.1 + glowIntensity * 0.3}) ${arcDegrees * 0.7}deg,
            transparent ${arcDegrees}deg
          )`,
          filter: `blur(${12 - glowIntensity * 4}px)`,
          opacity: 0.4 + glowIntensity * 0.4,
          animation: isAnimating
            ? `${arcPulse} 4s ease-in-out infinite`
            : 'none',
          transition: `all ${tokens.transitions.slow}`,
        }}
      />

      {/* Inner bright arc */}
      <Box
        sx={{
          position: 'absolute',
          width: '160px',
          height: '80px',
          borderRadius: '80px 80px 0 0',
          background: `conic-gradient(
            from ${startAngle + 10}deg at 50% 100%,
            transparent 0deg,
            rgba(180, 130, 255, ${0.3 + glowIntensity * 0.4}) ${arcDegrees * 0.4}deg,
            rgba(80, 220, 240, ${0.4 + glowIntensity * 0.5}) ${arcDegrees * 0.5}deg,
            rgba(180, 130, 255, ${0.3 + glowIntensity * 0.4}) ${arcDegrees * 0.6}deg,
            transparent ${arcDegrees - 20}deg
          )`,
          filter: `blur(${6 - glowIntensity * 2}px)`,
          opacity: 0.6 + glowIntensity * 0.3,
          animation: isAnimating
            ? `${arcPulse} 3s ease-in-out infinite 0.5s`
            : 'none',
          transition: `all ${tokens.transitions.slow}`,
        }}
      />

      {/* Center energy indicator */}
      <Box
        sx={{
          position: 'absolute',
          bottom: '0',
          width: '8px',
          height: '8px',
          borderRadius: '50%',
          background: `linear-gradient(135deg, rgba(115, 102, 240, 1), rgba(0, 200, 220, 1))`,
          boxShadow: `0 0 ${12 + glowIntensity * 8}px rgba(115, 102, 240, ${0.5 + glowIntensity * 0.3})`,
          transition: `all ${tokens.transitions.slow}`,
        }}
      />

      {/* "SPACE" label */}
      <Typography
        sx={{
          position: 'absolute',
          bottom: '-20px',
          fontSize: tokens.typography.fontSize.xs,
          fontWeight: tokens.typography.fontWeight.medium,
          color: tokens.colors.text.tertiary,
          letterSpacing: '0.15em',
          textTransform: 'uppercase',
          opacity: 0.6 + intensity * 0.3,
          transition: `opacity ${tokens.transitions.slow}`,
        }}
      >
        SPACE
      </Typography>
    </Box>
  );
};

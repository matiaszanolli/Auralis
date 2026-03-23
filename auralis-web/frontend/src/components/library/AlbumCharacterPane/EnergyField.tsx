import { Box, Typography } from '@mui/material';
import { tokens } from '@/design-system';
import { energyDrift } from './animations';

interface EnergyFieldProps {
  energy: number;
  isAnimating: boolean;
  intensity: number;
}

export const EnergyField = ({ energy, isAnimating, intensity }: EnergyFieldProps) => {
  // Map energy (0-1) to visual position
  const percentage = energy * 100;

  // Calculate hue shift based on energy (cool blue → warm orange/red)
  // Calm: 210 (blue), Aggressive: 15 (orange-red)
  const hue = 210 - energy * 195;

  // Glow lingers longer (use sqrt for slower fade)
  const glowIntensity = Math.sqrt(intensity);

  return (
    <Box sx={{ mt: tokens.spacing.lg }}>
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          mb: tokens.spacing.xs,
        }}
      >
        <Typography
          variant="caption"
          sx={{
            color: tokens.colors.text.tertiary,
            fontSize: tokens.typography.fontSize.xs,
            fontWeight: tokens.typography.fontWeight.medium,
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
            opacity: 0.7 + intensity * 0.3,
            transition: `opacity ${tokens.transitions.slow}`,
          }}
        >
          CALM
        </Typography>
        <Typography
          variant="caption"
          sx={{
            color: tokens.colors.text.tertiary,
            fontSize: tokens.typography.fontSize.xs,
            fontWeight: tokens.typography.fontWeight.medium,
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
            opacity: 0.7 + intensity * 0.3,
            transition: `opacity ${tokens.transitions.slow}`,
          }}
        >
          AGGRESSIVE
        </Typography>
      </Box>

      {/* Energy gradient field */}
      <Box
        role="meter"
        aria-label="Energy level"
        aria-valuenow={Math.round(percentage)}
        aria-valuemin={0}
        aria-valuemax={100}
        sx={{
          position: 'relative',
          height: '8px',
          borderRadius: tokens.borderRadius.full,
          // Gradient from cool (calm) to warm (aggressive)
          // Intensity modulates the alpha
          background: `linear-gradient(to right,
            hsla(210, 80%, 60%, ${0.25 + intensity * 0.15}) 0%,
            hsla(45, 90%, 55%, ${0.25 + intensity * 0.15}) 50%,
            hsla(15, 95%, 55%, ${0.25 + intensity * 0.15}) 100%)`,
          transition: `all ${tokens.transitions.slow}`,
          // Subtle inner glow - lingers longer via glowIntensity
          boxShadow: glowIntensity > 0.1
            ? `inset 0 0 8px hsla(${hue}, 70%, 50%, ${0.2 * glowIntensity})`
            : 'none',
        }}
      >
        {/* Floating energy node (not a slider thumb) */}
        <Box
          sx={{
            position: 'absolute',
            left: `${percentage}%`,
            top: '50%',
            transform: 'translate(-50%, -50%)',
            width: '16px',
            height: '16px',
            borderRadius: tokens.borderRadius.full,
            // Dynamic hue based on energy
            background: `hsla(${hue}, 75%, 55%, 1)`,
            border: `2px solid ${tokens.colors.bg.primary}`,
            // Glow radius and intensity fade during decay (but linger)
            boxShadow: `0 0 ${6 + glowIntensity * 6}px hsla(${hue}, 70%, 50%, ${0.3 + glowIntensity * 0.2})`,
            transition: `left ${tokens.transitions.slow}, box-shadow ${tokens.transitions.base}`,
            // Subtle drift animation when animating
            animation: isAnimating
              ? `${energyDrift} 4s cubic-bezier(0.25, 0.46, 0.45, 0.94) infinite`
              : 'none',
          }}
        />
      </Box>
    </Box>
  );
};

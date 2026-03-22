import { useMemo } from 'react';
import { Box } from '@mui/material';
import { tokens } from '@/design-system';
import { particleFloat } from './animations';

interface FloatingParticlesProps {
  isAnimating: boolean;
  intensity: number;
  count?: number;
}

export const FloatingParticles = ({
  isAnimating,
  intensity,
  count = 12,
}: FloatingParticlesProps) => {
  // Generate particles with varied properties
  const particles = useMemo(() =>
    Array.from({ length: count }, (_, i) => ({
      id: i,
      left: 10 + (i * 7) % 80, // Spread across width
      size: 2 + (i % 3) * 1.5, // Varied sizes (2-5px)
      duration: 6 + (i % 4) * 2, // 6-12s float duration
      delay: (i * 0.8) % 5, // Staggered starts
      hue: 240 + (i % 5) * 15, // Violet to cyan spectrum
    })),
  [count]);

  if (!isAnimating && intensity < 0.1) return null;

  return (
    <Box
      sx={{
        position: 'absolute',
        inset: 0,
        overflow: 'hidden',
        pointerEvents: 'none',
        opacity: intensity,
        transition: `opacity ${tokens.transitions.slow}`,
      }}
    >
      {particles.map((p) => (
        <Box
          key={p.id}
          sx={{
            position: 'absolute',
            left: `${p.left}%`,
            bottom: 0,
            width: `${p.size}px`,
            height: `${p.size}px`,
            borderRadius: '50%',
            background: `hsla(${p.hue}, 80%, 70%, 0.9)`,
            boxShadow: `0 0 ${p.size * 2}px hsla(${p.hue}, 80%, 60%, 0.6)`,
            animation: isAnimating
              ? `${particleFloat} ${p.duration}s ease-in-out infinite`
              : 'none',
            animationDelay: `${p.delay}s`,
          }}
        />
      ))}
    </Box>
  );
};

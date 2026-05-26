import { Box } from '@mui/material';
import { tokens, withOpacity } from '@/design-system';
import type { AudioFingerprint } from '@/utils/fingerprintToGradient';
import { breathePulse, barGlow } from './animations';

interface WaveformVisualizationProps {
  fingerprint: AudioFingerprint;
  isAnimating: boolean;
  intensity: number;
}

export const WaveformVisualization = ({
  fingerprint,
  isAnimating,
  intensity,
}: WaveformVisualizationProps) => {
  const frequencyBands = [
    fingerprint.sub_bass,
    fingerprint.bass,
    fingerprint.low_mid,
    fingerprint.mid,
    fingerprint.upper_mid,
    fingerprint.presence,
    fingerprint.air,
  ];

  const maxValue = Math.max(...frequencyBands, 0.01);
  const normalizedBands = frequencyBands.map((v) => v / maxValue);
  const glowIntensity = Math.sqrt(intensity);

  return (
    <Box
      sx={{
        position: 'relative',
        display: 'flex',
        alignItems: 'flex-end',
        justifyContent: 'space-around',
        height: '100px',
        gap: '6px',
        mt: tokens.spacing.xl,
        mb: tokens.spacing.lg,
        px: tokens.spacing.md,
        // Subtle backdrop glow behind waveform
        '&::before': {
          content: '""',
          position: 'absolute',
          inset: '-10px',
          background: `radial-gradient(ellipse at 50% 100%, ${withOpacity(tokens.colors.audioSemantic.identity, 0.08 + glowIntensity * 0.12)} 0%, transparent 70%)`,
          filter: 'blur(8px)',
          opacity: isAnimating ? 1 : 0.5,
          transition: `opacity ${tokens.transitions.slow}`,
          pointerEvents: 'none',
        },
      }}
    >
      {normalizedBands.map((value, index) => {
        // Hue shifts from violet (left/bass) to cyan (right/air)
        const hue = 260 - index * 8; // 260 (violet) to 204 (cyan)
        const barHeight = Math.max(value * 100, 12);

        return (
          <Box
            // #3615: bands are positionally stable but a frequency-derived
            // key clarifies intent and silences exhaustive-deps style lint.
            key={`band-${index}`}
            sx={{
              position: 'relative',
              flex: 1,
              height: `${barHeight}%`,
              minHeight: '12px',
              borderRadius: '4px',
              // Vibrant gradient with hue shift
              background: `linear-gradient(to top,
                hsla(${hue}, 70%, 50%, 0.9) 0%,
                hsla(${hue - 20}, 80%, 65%, 0.95) 50%,
                hsla(${hue - 40}, 90%, 75%, 1) 100%)`,
              // Glow effect intensifies with playback
              boxShadow: `
                0 0 ${4 + glowIntensity * 8}px hsla(${hue}, 80%, 55%, ${0.3 + glowIntensity * 0.4}),
                inset 0 1px 0 ${tokens.colors.opacityScale.white.strong}`,
              opacity: 0.7 + value * 0.2 + intensity * 0.1,
              transition: `all ${tokens.transitions.slow}`,
              // Breathing + glow animation when animating
              animation: isAnimating
                ? `${breathePulse} ${2.5 + index * 0.3}s cubic-bezier(0.25, 0.46, 0.45, 0.94) infinite,
                   ${barGlow} ${3 + index * 0.4}s ease-in-out infinite`
                : 'none',
              animationDelay: `${index * 0.15}s, ${index * 0.2}s`,
            }}
          />
        );
      })}
    </Box>
  );
};

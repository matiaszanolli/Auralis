import { Box, Chip } from '@mui/material';
import { tokens } from '@/design-system';
import { subtleGlow } from './animations';

interface CharacterTagsProps {
  tags: Array<{ label: string; category: string }>;
  isAnimating: boolean;
  intensity: number;
}

export const CharacterTags = ({ tags, isAnimating, intensity }: CharacterTagsProps) => {
  // Glow lingers longer (use sqrt for slower fade)
  const glowIntensity = Math.sqrt(intensity);

  return (
    <Box
      sx={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: tokens.spacing.sm,
        mb: tokens.spacing.lg,
      }}
    >
      {tags.map((tag, index) => {
        // Each tag gets a slightly different hue for variety
        const tagHue = 260 - (index * 12) % 60; // Violet to blue-cyan range

        return (
          <Chip
            key={`${tag.category}-${tag.label}`}
            label={tag.label}
            aria-label={`${tag.category}: ${tag.label}`}
            role="status"
            size="small"
            sx={{
              // Glass background
              background: `rgba(30, 40, 65, ${0.4 + glowIntensity * 0.15})`,
              backdropFilter: 'blur(4px)',
              color: tokens.colors.text.secondary,
              fontSize: tokens.typography.fontSize.xs,
              fontWeight: tokens.typography.fontWeight.medium,
              // Glass bevel instead of hard border
              border: 'none',
              transition: `all ${tokens.transitions.slow}`,
              // Multi-layer glow effect
              boxShadow: `
                inset 0 1px 0 rgba(255, 255, 255, ${0.08 + glowIntensity * 0.08}),
                inset 0 -1px 0 ${tokens.colors.opacityScale.dark.lighter},
                ${glowIntensity > 0.1
                  ? `0 0 ${8 + glowIntensity * 10}px hsla(${tagHue}, 70%, 55%, ${0.15 + glowIntensity * 0.25})`
                  : `0 2px 4px ${tokens.colors.opacityScale.dark.light}`}
              `,
              // Glow animation when animating
              animation: isAnimating
                ? `${subtleGlow} ${3 + index * 0.5}s cubic-bezier(0.25, 0.46, 0.45, 0.94) infinite`
                : 'none',
              animationDelay: `${index * 0.2}s`,
              '&:hover': {
                background: `rgba(40, 55, 85, ${0.5 + glowIntensity * 0.2})`,
                boxShadow: `
                  inset 0 1px 0 rgba(255, 255, 255, 0.12),
                  inset 0 -1px 0 ${tokens.colors.opacityScale.dark.standard},
                  0 0 16px hsla(${tagHue}, 70%, 55%, 0.35)
                `,
              },
            }}
          />
        );
      })}
    </Box>
  );
};

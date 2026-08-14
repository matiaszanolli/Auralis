import { memo } from 'react';
import { Box, Chip } from '@mui/material';
import { tokens } from '@/design-system';
import { subtleGlow } from './animations';
import { themeVars } from '@/theme/semanticTheme';

// #3598: surface lift derived from bg.level4 (closest token to the previous
// rgba(30, 40, 65, ...) inline literal). Glow halo backgrounds now share the
// brand blue-black ramp instead of inventing intermediate tints.
//
// #4877: now a CSS custom property rather than a hex literal, so it can NOT be
// passed to withOpacity() — that helper hex-parses its input and returns the
// string UNCHANGED when parsing fails, which would silently drop the alpha and
// render these halos fully opaque. Composed with color-mix() below instead.
const SURFACE_LIFT = themeVars.surfaceOverlay;

interface CharacterTagsProps {
  tags: Array<{ label: string; category: string }>;
  isAnimating: boolean;
  intensity: number;
}

export const CharacterTags = memo(({ tags, isAnimating, intensity }: CharacterTagsProps) => {
  // Glow lingers longer (use sqrt for slower fade)
  const glowIntensity = Math.sqrt(intensity);

  return (
    <Box
      role="list"
      aria-label="Character tags"
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
            role="listitem"
            size="small"
            sx={{
              // Glass background
              background: `color-mix(in srgb, ${SURFACE_LIFT} ${((0.4 + glowIntensity * 0.15) * 100).toFixed(2)}%, transparent)`,
              backdropFilter: 'blur(4px)',
              color: themeVars.textSecondary,
              fontSize: tokens.typography.fontSize.xs,
              fontWeight: tokens.typography.fontWeight.medium,
              // Glass bevel instead of hard border
              border: 'none',
              transition: `all ${tokens.transitions.slow}`,
              // Multi-layer glow effect
              boxShadow: `
                inset 0 1px 0 color-mix(in srgb, ${themeVars.textStrong} ${((0.08 + glowIntensity * 0.08) * 100).toFixed(2)}%, transparent),
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
                // Slightly stronger lift on hover — same bg.level4 token,
                // higher alpha to compensate for darker source.
                background: `color-mix(in srgb, ${SURFACE_LIFT} ${((0.6 + glowIntensity * 0.25) * 100).toFixed(2)}%, transparent)`,
                boxShadow: `
                  inset 0 1px 0 ${tokens.colors.opacityScale.white.lighter},
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
});
CharacterTags.displayName = 'CharacterTags';

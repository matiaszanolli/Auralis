import { css } from '@emotion/react';
import { tokens } from '@/design-system/tokens';
import { themeVars } from '@/theme/semanticTheme';

/**
 * Utility classes, scroll-animation classes and the loading skeleton. Split out
 * of globalStyles.ts (#5841).
 */
export const utilityStyles = css`
  /* Utility classes */
  .gradient-text {
    background: ${tokens.gradients.aurora};
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    color: transparent;
  }

  /* Scroll animation classes */
  .animate-fade-in {
    animation: fadeIn 0.6s ${tokens.transitions.easeOut} forwards;
  }

  .animate-fade-in-up {
    animation: fadeInUp 0.6s ${tokens.transitions.easeOut} forwards;
  }

  .animate-fade-in-down {
    animation: fadeInDown 0.6s ${tokens.transitions.easeOut} forwards;
  }

  .animate-fade-in-left {
    animation: fadeInLeft 0.6s ${tokens.transitions.easeOut} forwards;
  }

  .animate-fade-in-right {
    animation: fadeInRight 0.6s ${tokens.transitions.easeOut} forwards;
  }

  .animate-scale-in {
    animation: scaleIn 0.6s ${tokens.transitions.easeOut} forwards;
  }

  .hover-lift {
    transition: transform ${tokens.transitions.slow};
  }

  .hover-lift:hover {
    transform: translateY(-4px);
  }

  .hover-scale {
    transition: transform ${tokens.transitions.slow};
  }

  .hover-scale:hover {
    transform: scale(1.05);
  }

  .smooth-transition {
    transition: ${tokens.transitions.all};
  }

  .glow-effect {
    animation: glow 2s ease-in-out infinite;
  }

  .pulse-effect {
    animation: pulse ${tokens.animations.pulse.duration} ${tokens.animations.pulse.timing} ${tokens.animations.pulse.iteration};
  }

  /* Loading skeleton */
  .skeleton {
    background: linear-gradient(
      90deg,
      ${themeVars.surfaceSecondary} 0%,
      ${themeVars.surfaceRaised} 50%,
      ${themeVars.surfaceSecondary} 100%
    );
    background-size: 200% 100%;
    animation: shimmer 1.5s infinite;
    border-radius: ${tokens.borderRadius.sm};
  }
`;

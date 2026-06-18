import { css } from '@emotion/react';
import { tokens } from '@/design-system/tokens';

/**
 * Global Styles
 *
 * Uses design system tokens as single source of truth.
 * All color, spacing, and animation values come from tokens.ts
 */
export const globalStyles = css`
  :root {
    /* Color variables - mapped from tokens */
    --bg-primary: ${tokens.colors.bg.level1};
    --bg-secondary: ${tokens.colors.bg.level2};
    --bg-surface: ${tokens.colors.bg.level3};
    --bg-hover: ${tokens.colors.bg.level4};

    --text-primary: ${tokens.colors.text.primary};
    --text-secondary: ${tokens.colors.text.secondary};
    --text-disabled: ${tokens.colors.text.disabled};

    /* Gradient variables - from tokens */
    --gradient-aurora: ${tokens.gradients.aurora};
    --gradient-aqua: ${tokens.gradients.aqua};

    /* Glow shadow variables — single source for keyframe animations so a
       brand-color change propagates to all glow/pulse animations (#3982). */
    --glow-accent-medium: ${tokens.shadows.glowAccentMedium};
    --glow-accent-strong: ${tokens.shadows.glowAccentStrong};
    --glow-aqua-medium: ${tokens.shadows.glowAquaMedium};
    --glow-aqua-strong: ${tokens.shadows.glowAquaStrong};

    /* Accent color RGB channels (accent.primary #7366F0) so keyframes can use
       rgba(var(--accent-rgb), <opacity>) and inherit brand-color changes (#3982). */
    --accent-rgb: 115, 102, 240;
  }

  * {
    box-sizing: border-box;
  }

  body {
    margin: 0;
    padding: 0;
    overflow: hidden;
    background: ${tokens.colors.bg.level0};
    color: ${tokens.colors.text.primary};
    font-family: ${tokens.typography.fontFamily.primary};
  }

  /* Custom scrollbar */
  ::-webkit-scrollbar {
    width: 12px;
    height: 12px;
  }

  ::-webkit-scrollbar-track {
    background: ${tokens.colors.bg.level2};
  }

  ::-webkit-scrollbar-thumb {
    background: ${tokens.colors.bg.level3};
    border-radius: 6px;
    border: 2px solid ${tokens.colors.bg.level2};
  }

  ::-webkit-scrollbar-thumb:hover {
    background: ${tokens.colors.bg.level4};
  }

  /* Firefox scrollbar */
  * {
    scrollbar-width: thin;
    scrollbar-color: ${tokens.colors.bg.level3} ${tokens.colors.bg.level2};
  }

  /* Animation keyframes */
  @keyframes pulse {
    0%, 100% {
      opacity: 1;
    }
    50% {
      opacity: 0.6;
    }
  }

  @keyframes glow {
    0%, 100% {
      filter: drop-shadow(0 0 8px ${tokens.colors.opacityScale.accent.veryStrong});
    }
    50% {
      filter: drop-shadow(0 0 16px ${tokens.colors.opacityScale.accent.vivid});
    }
  }

  @keyframes shimmer {
    0% {
      background-position: -1000px 0;
    }
    100% {
      background-position: 1000px 0;
    }
  }

  @keyframes slideInUp {
    from {
      transform: translateY(20px);
      opacity: 0;
    }
    to {
      transform: translateY(0);
      opacity: 1;
    }
  }

  @keyframes fadeIn {
    from {
      opacity: 0;
    }
    to {
      opacity: 1;
    }
  }

  @keyframes scaleIn {
    from {
      transform: scale(0.95);
      opacity: 0;
    }
    to {
      transform: scale(1);
      opacity: 1;
    }
  }

  @keyframes fadeInUp {
    from {
      opacity: 0;
      transform: translateY(30px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  @keyframes fadeInDown {
    from {
      opacity: 0;
      transform: translateY(-30px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  @keyframes fadeInLeft {
    from {
      opacity: 0;
      transform: translateX(-30px);
    }
    to {
      opacity: 1;
      transform: translateX(0);
    }
  }

  @keyframes fadeInRight {
    from {
      opacity: 0;
      transform: translateX(30px);
    }
    to {
      opacity: 1;
      transform: translateX(0);
    }
  }

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
    animation: pulse 2s ease-in-out infinite;
  }

  /* Loading skeleton */
  .skeleton {
    background: linear-gradient(
      90deg,
      ${tokens.colors.bg.level3} 0%,
      ${tokens.colors.bg.level4} 50%,
      ${tokens.colors.bg.level3} 100%
    );
    background-size: 200% 100%;
    animation: shimmer 1.5s infinite;
    border-radius: ${tokens.borderRadius.sm};
  }

  /* Selection color */
  ::selection {
    background: ${tokens.colors.opacityScale.accent.strong};
    color: ${tokens.colors.text.primary};
  }

  /* Focus outline - using accent color */
  :focus-visible {
    outline: 2px solid ${tokens.colors.accent.primary};
    outline-offset: 2px;
  }

  /* Smooth scrolling */
  html {
    scroll-behavior: smooth;
  }
`;

export default globalStyles;

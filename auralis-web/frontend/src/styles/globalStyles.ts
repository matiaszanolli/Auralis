import { css } from '@emotion/react';
import { tokens } from '@/design-system/tokens';
import { getSemanticTheme, themeVars } from '@/theme/semanticTheme';

const defaultTheme = getSemanticTheme('dark');

/**
 * Global Styles
 *
 * Uses design system tokens as single source of truth.
 * All color, spacing, and animation values come from tokens.ts
 */
export const globalStyles = css`
  :root {
    color-scheme: dark;
    --app-canvas: ${defaultTheme.canvas};
    --app-surface-primary: ${defaultTheme.surfacePrimary};
    --app-surface-secondary: ${defaultTheme.surfaceSecondary};
    --app-surface-raised: ${defaultTheme.surfaceRaised};
    --app-surface-overlay: ${defaultTheme.surfaceOverlay};
    --app-surface-translucent: ${defaultTheme.surfaceTranslucent};
    --app-text-primary: ${defaultTheme.textPrimary};
    --app-text-strong: ${defaultTheme.textStrong};
    --app-text-secondary: ${defaultTheme.textSecondary};
    --app-text-muted: ${defaultTheme.textMuted};
    --app-text-disabled: ${defaultTheme.textDisabled};
    --app-border-subtle: ${defaultTheme.borderSubtle};
    --app-border-default: ${defaultTheme.borderDefault};
    --app-border-strong: ${defaultTheme.borderStrong};
    --app-accent: ${defaultTheme.accent};
    --app-accent-hover: ${defaultTheme.accentHover};
    --app-accent-soft: ${defaultTheme.accentSoft};
    --app-on-accent: ${defaultTheme.onAccent};
    --app-focus-ring: ${defaultTheme.focusRing};
    --app-success: ${defaultTheme.success};
    --app-warning: ${defaultTheme.warning};
    --app-error: ${defaultTheme.error};
    --app-info: ${defaultTheme.info};
    --app-error-soft: ${defaultTheme.errorSoft};
    --app-on-error: ${defaultTheme.onError};
    --app-backdrop: ${defaultTheme.backdrop};
    --app-shadow-raised: ${defaultTheme.shadowRaised};
    --app-shadow-overlay: ${defaultTheme.shadowOverlay};

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

  html,
  body,
  #root {
    width: 100%;
    height: 100%;
  }

  body {
    margin: 0;
    padding: 0;
    overflow: hidden;
    background: ${themeVars.canvas};
    color: ${themeVars.textPrimary};
    font-family: ${tokens.typography.fontFamily.primary};
    text-rendering: optimizeLegibility;
    transition:
      background-color ${tokens.transitions.state_inOut},
      color ${tokens.transitions.state_inOut};
  }

  /* Custom scrollbar */
  ::-webkit-scrollbar {
    width: 10px;
    height: 10px;
  }

  ::-webkit-scrollbar-track {
    background: ${themeVars.surfacePrimary};
  }

  ::-webkit-scrollbar-thumb {
    background: ${themeVars.surfaceRaised};
    border-radius: ${tokens.borderRadius.full};
    border: 2px solid ${themeVars.surfacePrimary};
  }

  ::-webkit-scrollbar-thumb:hover {
    background: ${themeVars.accent};
  }

  /* Firefox scrollbar */
  * {
    scrollbar-width: thin;
    scrollbar-color: ${themeVars.surfaceRaised} ${themeVars.surfacePrimary};
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

  /* Spinner rotation — was injected per-render via inline <style> in
     BufferingIndicator (#4188). */
  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }

  /* Connection-status ring pulse. Defined once here (uniquely named to avoid
     colliding with the opacity 'pulse' above); the runtime status colour is fed
     via the --pulse-shadow-start/--pulse-shadow-end custom properties set on the
     element, instead of re-injecting a colour-interpolated <style> on every
     status change (#4188). */
  @keyframes connection-status-pulse {
    0% {
      box-shadow: 0 0 0 0 var(--pulse-shadow-start, transparent);
    }
    70% {
      box-shadow: 0 0 0 10px var(--pulse-shadow-end, transparent);
    }
    100% {
      box-shadow: 0 0 0 0 var(--pulse-shadow-end, transparent);
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
      ${themeVars.surfaceSecondary} 0%,
      ${themeVars.surfaceRaised} 50%,
      ${themeVars.surfaceSecondary} 100%
    );
    background-size: 200% 100%;
    animation: shimmer 1.5s infinite;
    border-radius: ${tokens.borderRadius.sm};
  }

  /* Selection color */
  ::selection {
    background: ${themeVars.focusRing};
    color: ${themeVars.textStrong};
  }

  /* Focus outline - using accent color */
  :focus-visible {
    outline: 2px solid ${themeVars.accent};
    outline-offset: 2px;
  }

  .app-ambient-background {
    opacity: 0.14;
    filter: saturate(0.75);
    transition: opacity ${tokens.transitions.slow_inOut};
  }

  html[data-theme='light'] .app-ambient-background {
    opacity: 0.035;
  }

  @media (prefers-reduced-motion: reduce) {
    *,
    *::before,
    *::after {
      scroll-behavior: auto !important;
      animation-duration: 0.01ms !important;
      animation-iteration-count: 1 !important;
      transition-duration: 0.01ms !important;
    }
  }
`;

export default globalStyles;

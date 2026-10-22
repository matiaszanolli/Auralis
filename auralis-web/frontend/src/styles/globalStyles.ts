import { css } from '@emotion/react';
import { tokens } from '@/design-system/tokens';
import { getSemanticTheme, themeVars } from '@/theme/semanticTheme';
import { keyframeStyles } from './globalKeyframes';
import { utilityStyles } from './globalUtilities';

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

  ${keyframeStyles}

  ${utilityStyles}

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

import { css } from '@emotion/react';
import { tokens } from '@/design-system/tokens';
import { getSemanticCssVariables, themeVars } from '@/theme/semanticTheme';
import { keyframeStyles } from './globalKeyframes';
import { utilityStyles } from './globalUtilities';

// Dark defaults for every --app-* variable, generated from the same contract
// ThemeProvider writes so a newly added role cannot be missing here (#6057).
const darkRootVariables = Object.entries(getSemanticCssVariables('dark'))
  .map(([property, value]) => `${property}: ${value};`)
  .join('\n    ');

/**
 * Global Styles
 *
 * Uses design system tokens as single source of truth.
 * All color, spacing, and animation values come from tokens.ts
 */
export const globalStyles = css`
  :root {
    color-scheme: dark;
    ${darkRootVariables}

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

  /* Scrollbars use the standard properties only: Chromium >= 121 (Electron)
     ignores the webkit scrollbar pseudo-elements once scrollbar-width or
     scrollbar-color is non-auto, so a webkit block here would be dead (#6058). */
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

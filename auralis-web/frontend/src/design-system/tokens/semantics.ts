/**
 * Auralis Design System Tokens — see ./README or tokens barrel.
 * Split from the former monolithic tokens.ts (#4079). Do not add cross-category
 * references here; each category is self-contained and merged in the barrel.
 */


  /**
   * Numbers Policy (Style Guide §7.3)
   * Numbers exist, but are hidden by default.
   * Engineers can inspect. Listeners can listen.
   */
export const numbersPolicy = {
    // Default visibility
    defaultVisibility: 'hidden',

    // Reveal behavior
    revealOn: 'interaction', // 'hover' | 'click' | 'interaction'
    revealTransition: '300ms cubic-bezier(0.4, 0, 0.6, 1)',

    // Hierarchy when visible
    hierarchy: 'secondary', // Numbers are never primary

    // Styling when revealed
    revealed: {
      opacity: 0.7,
      fontSize: '11px',
      fontFamily: "'JetBrains Mono', monospace",
    },
} as const;

  /**
   * Visualization Guidelines (Style Guide §7)
   * Visuals answer: "What is the music doing now?"
   * Not: "What are the numbers?"
   */
export const visualization = {
    // Allowed visual forms
    allowed: [
      'flowingWaves',
      'halos',
      'breathingGradients',
      'softArcs',
      'ambientFields',
    ],

    // Disallowed (NEVER use these)
    disallowed: [
      'barGraphs',
      'meters',
      'percentIndicators', // when always-on
      'gridLines',
      'hardEdges',
    ],

    // Wave visualization defaults
    wave: {
      strokeWidth: 2,
      smoothing: 0.4,        // Bezier curve smoothing
      glowBlur: '8px',
      glowOpacity: 0.3,
    },

    // Halo/glow visualization defaults
    halo: {
      blur: '24px',
      opacity: 0.25,
      pulseDuration: '3s',   // Slow, breathing
    },

    // Gradient visualization defaults
    gradient: {
      noiseIntensity: 0.03,  // Subtle grain
      transitionDuration: '2s',
      depth: 'radial',       // Radial or diagonal, never flat
    },
} as const;

  /**
   * Component-Specific Tokens
   * Predefined sizes and styles for major UI components
   */
  /**
   * Component-Specific Tokens (Design Language §4)
   * Surfaces, not cards. Hierarchy by space and subtle glass borders.
   * Sidebar is muscle memory UI (low contrast, no visual drama).
   */
export const components = {
    playerBar: {
      height: '96px',
      zIndex: 1030,
      background: 'rgba(11, 16, 32, 0.85)',        // Deep blue-black (translucent)
      backdropFilter: 'blur(24px) saturate(1.2)',
      borderTop: 'none',                           // Top edge blends with content
      shadow: '0 -8px 32px rgba(0, 0, 0, 0.28)',   // Depth via shadow
    },

    sidebar: {
      width: '256px',
      collapsedWidth: '72px',
      background: 'rgba(16, 23, 41, 0.20)',
      backdropFilter: 'blur(6px) saturate(0.95)',
      borderRight: 'none',  // No hard border - use bevel shadow instead
      // Glass bevel: outer shadow + right edge highlight
      shadow: '2px 0 8px rgba(0, 0, 0, 0.08), inset -1px 0 0 rgba(255, 255, 255, 0.05)',
    },

    rightPanel: {
      width: '360px',
      minWidth: '300px',
      // Match sidebar's subtle transparency (muscle memory UI)
      background: 'rgba(16, 23, 41, 0.20)',
      backdropFilter: 'blur(6px) saturate(0.95)',
      borderLeft: 'none',
      // Glass bevel: mirrored from sidebar (left edge highlight)
      shadow: '-2px 0 8px rgba(0, 0, 0, 0.08), inset 1px 0 0 rgba(255, 255, 255, 0.05)',
    },

    albumCard: {
      size: '200px',               // Increased from 160px
      borderRadius: '12px',        // lg (12px minimum for cards)
      hoverScale: 1.04,            // Increased from 1.05 for subtlety
      hoverShadow: '0 8px 24px rgba(0, 0, 0, 0.24)',
    },

    albumCover: {
      borderRadius: '16px',        // xl (large panels)
      shadow: '0 12px 32px rgba(0, 0, 0, 0.28)',
      hoverShadow: '0 16px 40px rgba(0, 0, 0, 0.32)',
    },

    button: {
      primary: {
        padding: '12px 24px',
        borderRadius: '8px',
        fontSize: '14px',
        fontWeight: 500,
      },
      icon: {
        size: '56px',
        borderRadius: '9999px',  // full circle
      },
    },

    searchBar: {
      height: '48px',
      borderRadius: '24px',  // Pill shape
      background: 'rgba(31, 41, 54, 0.60)',
      padding: '0 16px',
    },

    // Input surface backgrounds at rest / hover / focus (#3981 — was raw rgba
    // in design-system/primitives/Input.tsx). Base color #1F2936 = rgb(31,41,54).
    inputSurface: {
      base: 'rgba(31, 41, 54, 0.60)',
      hover: 'rgba(31, 41, 54, 0.80)',
      focus: 'rgba(31, 41, 54, 0.95)',
    },
} as const;

/**
 * Auralis Design System Tokens
 *
 * Single source of truth for all design values.
 * ALL components MUST use these tokens - no hardcoded values allowed.
 *
 * @see docs/guides/UI_DESIGN_GUIDELINES.md
 */

export const tokens = {
  /**
   * Color System - Premium Audio Player (Tidal + FabFilter + macOS aesthetic)
   * Elevation-based backgrounds with Soft Violet + Electric Aqua brand colors
   */
  colors: {
    // Background colors (Elevation Levels)
    bg: {
      level0: '#0A0C10',       // Root background (darkest void)
      level1: '#0D111A',       // Primary background (main content area)
      level2: '#131A24',       // Secondary background (panels, sidebars)
      level3: '#1B232E',       // Tertiary background (cards, raised elements)
      level4: '#1F2936',       // Surface background (overlays, modals)
      // Backwards compatibility
      primary: '#0D111A',
      secondary: '#131A24',
      tertiary: '#1B232E',
      elevated: '#1F2936',
      overlay: 'rgba(13, 17, 26, 0.95)',
    },

    // Brand colors (Soft Violet + Electric Aqua)
    accent: {
      primary: '#7366F0',      // Soft Violet - primary brand accent
      secondary: '#47D6FF',    // Electric Aqua - audio-reactive, glows
      tertiary: '#C1C8EF',     // Lavender Smoke - secondary text
    },

    // Semantic accent colors
    semantic: {
      success: '#10B981',      // Success (positive)
      warning: '#F59E0B',      // Warning (caution)
      error: '#EF4444',        // Error (critical)
      info: '#3B82F6',         // Info (informational)
    },

    // Text colors
    text: {
      primary: '#FFFFFF',      // Ultra White - titles, emphasis
      secondary: '#C1C8EF',    // Lavender Smoke - secondary text, labels
      tertiary: '#8B92B0',     // Muted purple-gray - tertiary text
      muted: '#6B7194',        // Muted - disabled, hint text
      disabled: '#4A5073',     // Disabled text (very muted)
      inverse: '#0D111A',      // For light backgrounds
    },

    // Border colors (using soft opacity + brand colors)
    border: {
      light: 'rgba(115, 102, 240, 0.12)',   // Subtle borders (soft violet)
      medium: 'rgba(115, 102, 240, 0.24)',  // Standard borders
      heavy: 'rgba(115, 102, 240, 0.40)',   // Emphasized borders
      accent: '#7366F0',                     // Accent borders (soft violet)
    },
  },

  /**
   * Spacing System
   * Based on 8px grid system
   */
  spacing: {
    xs: '4px',
    sm: '8px',
    md: '16px',
    lg: '24px',
    xl: '32px',
    xxl: '48px',
    xxxl: '64px',
  },

  /**
   * Typography System
   * Plus Jakarta Sans (headers), Inter (body), JetBrains Mono (technical)
   */
  typography: {
    fontFamily: {
      primary: 'Inter, "Segoe UI", sans-serif',                                    // Body text
      header: "'Plus Jakarta Sans', Arial, sans-serif",                            // Headers & titles
      mono: "'JetBrains Mono', 'Courier New', monospace",                         // Technical readouts (dB, Hz, LUFS)
      system: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif',
    },

    fontSize: {
      xs: '11px',      // Caption, tiny labels
      sm: '12px',      // Small text, metadata
      base: '14px',    // Standard body text
      md: '16px',      // Larger body, input labels
      lg: '18px',      // Subtitle, secondary headers
      xl: '20px',      // Section headers (H3)
      '2xl': '24px',   // Page headers (H2)
      '3xl': '32px',   // Large headers (H1)
      '4xl': '48px',   // Display, hero text
    },

    fontWeight: {
      normal: 400,
      medium: 500,
      semibold: 600,
      bold: 700,
    },

    lineHeight: {
      tight: 1.2,      // Headers
      normal: 1.5,     // Body text
      relaxed: 1.75,   // Long-form
    },

    letterSpacing: {
      normal: '0',
      tight: '-0.01em',
      loose: '0.02em',
    },
  },

  /**
   * Border Radius System
   */
  borderRadius: {
    none: '0',
    sm: '4px',
    md: '8px',
    lg: '12px',
    xl: '16px',
    full: '9999px',  // Pill shape
  },

  /**
   * Shadow System (Ambient opacity - no harsh black)
   * Elevation levels + audio-reactive glows
   */
  shadows: {
    none: 'none',

    // Elevation shadows (ambient opacity for depth)
    xs: '0 1px 2px rgba(0, 0, 0, 0.05)',
    sm: '0 2px 4px rgba(0, 0, 0, 0.08)',
    base: '0 2px 4px rgba(0, 0, 0, 0.10)',
    md: '0 4px 12px rgba(0, 0, 0, 0.16)',         // Card shadow (elevation 1)
    lg: '0 8px 24px rgba(0, 0, 0, 0.20)',        // Raised panel (elevation 2)
    xl: '0 12px 32px rgba(0, 0, 0, 0.28)',       // Modal (elevation 3)
    '2xl': '0 16px 40px rgba(0, 0, 0, 0.32)',    // Top-level (elevation 4)

    // Glow shadows (audio-reactive elements)
    glowSoft: '0 0 16px rgba(115, 102, 240, 0.20)',      // Soft violet glow
    glowMd: '0 0 24px rgba(115, 102, 240, 0.32)',        // Violet glow (medium)
    glowAqua: '0 0 20px rgba(71, 214, 255, 0.24)',       // Electric Aqua glow
    glowAquaIntense: '0 0 32px rgba(71, 214, 255, 0.40)', // Aqua glow (processing)
  },

  /**
   * Elevation System (UX Polish - Phase 4b)
   * Standardized depth patterns for consistent visual hierarchy
   *
   * Based on shadow-based depth (no hard borders) established in Phases 1-4a:
   * - Cards use resting + hover elevations
   * - Panels use separation shadows (left/right)
   * - Sections use subtle background differences + spacing
   */
  elevation: {
    // Card elevations (track cards, album cards)
    card: {
      resting: '0 2px 8px rgba(0, 0, 0, 0.15)',     // Subtle depth at rest
      hover: '0 8px 24px rgba(0, 0, 0, 0.25)',      // Clear elevation on hover
    },

    // Panel separations (sidebar, right panel)
    panel: {
      left: '-2px 0 16px rgba(0, 0, 0, 0.12)',      // Right panel (left shadow)
      right: '2px 0 16px rgba(0, 0, 0, 0.12)',      // Sidebar (right shadow)
    },

    // Section depth (internal components)
    section: {
      subtle: '0 1px 4px rgba(0, 0, 0, 0.08)',      // Very subtle separation
      medium: '0 2px 8px rgba(0, 0, 0, 0.12)',      // Medium depth
    },
  },

  /**
   * Opacity System (UX Polish - Phase 4b)
   * Standardized opacity levels for fading UI elements
   *
   * Based on fade patterns established in Phases 1-4a:
   * - Infrastructure elements (labels, dividers) fade more (~40-60%)
   * - Inactive content (icons, text) fade less (~15-30%)
   * - Duration badges and secondary UI fade moderately (~20-40%)
   */
  opacity: {
    // Infrastructure (should recede into background)
    infrastructure: {
      labels: 0.6,        // Section labels, dividers (~40% fade)
      dividers: 0.5,      // Dividers between sections (~50% fade)
    },

    // Inactive states (reduce prominence, not hide)
    inactive: {
      icons: 0.7,         // Inactive navigation icons (~30% fade)
      text: 0.75,         // Inactive navigation text (~25% fade)
      labels: 0.85,       // Parameter labels (~15% fade)
    },

    // Secondary UI elements
    secondary: {
      badges: 0.6,        // Duration badges at rest (~40% fade)
      headers: 0.8,       // Section headers (~20% fade)
    },

    // Active/visible states (full visibility)
    active: {
      full: 1.0,          // Active/important elements
      emphasized: 1.0,    // Emphasized content
    },
  },

  /**
   * Transition System (smooth, intentional animations)
   */
  transitions: {
    // Durations
    fast: '100ms',
    base: '200ms',
    slow: '300ms',
    verySlow: '500ms',

    // Easing functions
    easeOut: 'cubic-bezier(0.4, 0, 0.2, 1)',    // Quick, sharp (100ms)
    easeInOut: 'cubic-bezier(0.4, 0, 0.6, 1)',  // Natural (200ms)
    easeSmooth: 'cubic-bezier(0.25, 0.46, 0.45, 0.94)', // Audio-like fluidity

    // Combined (duration + easing)
    fast_out: '100ms cubic-bezier(0.4, 0, 0.2, 1)',
    base_inOut: '200ms cubic-bezier(0.4, 0, 0.6, 1)',
    slow_inOut: '300ms cubic-bezier(0.4, 0, 0.6, 1)',
    verySlow_inOut: '500ms cubic-bezier(0.4, 0, 0.6, 1)',

    // Property-specific
    color: '200ms color cubic-bezier(0.4, 0, 0.6, 1)',
    background: '200ms background-color cubic-bezier(0.4, 0, 0.6, 1)',
    transform: '200ms transform cubic-bezier(0.4, 0, 0.6, 1)',
    opacity: '200ms opacity cubic-bezier(0.4, 0, 0.6, 1)',
    all: '200ms all cubic-bezier(0.4, 0, 0.6, 1)',
  },

  /**
   * Z-Index Scale
   */
  zIndex: {
    base: 0,
    dropdown: 1000,
    sticky: 1020,
    fixed: 1030,
    modalBackdrop: 1040,
    modal: 1050,
    popover: 1060,
    tooltip: 1070,
    toast: 1300,
  },

  /**
   * Breakpoint System (responsive design)
   * Based on common device widths
   */
  breakpoints: {
    xs: '0px',       // Mobile (portrait)
    sm: '600px',     // Mobile (landscape) / Small tablet
    md: '900px',     // Tablet
    lg: '1200px',    // Desktop
    xl: '1536px',    // Large desktop / Wide screens
  },

  /**
   * Component-Specific Tokens
   * Predefined sizes and styles for major UI components
   */
  components: {
    playerBar: {
      height: '96px',
      zIndex: 1030,
      background: 'rgba(13, 17, 26, 0.92)',
      backdropFilter: 'blur(12px)',
      borderTop: '1px solid rgba(115, 102, 240, 0.12)',
      shadow: '0 -8px 32px rgba(0, 0, 0, 0.24)',
    },

    sidebar: {
      width: '256px',
      collapsedWidth: '72px',
      background: '#131A24',
      borderRight: '1px solid rgba(115, 102, 240, 0.08)',
      shadow: '2px 0 16px rgba(0, 0, 0, 0.12)',
    },

    rightPanel: {
      width: '360px',
      minWidth: '300px',
      background: '#131A24',
      borderLeft: '1px solid rgba(115, 102, 240, 0.08)',
      shadow: '-2px 0 16px rgba(0, 0, 0, 0.12)',
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
  },

  /**
   * Gradient System (Soft Violet + Electric Aqua + subtle dark)
   */
  gradients: {
    aurora: 'linear-gradient(135deg, #7366F0 0%, #5A5CC4 100%)',              // Aurora (Soft Violet → darker)
    auroraSoft: 'linear-gradient(135deg, rgba(115, 102, 240, 0.80) 0%, rgba(90, 92, 196, 0.80) 100%)', // Aurora soft (overlays)
    auroraVertical: 'linear-gradient(180deg, #7366F0 0%, #5A5CC4 100%)',      // Aurora vertical (headers)
    aqua: 'linear-gradient(135deg, #47D6FF 0%, #00BCC4 100%)',                // Aqua (audio-reactive)
    darkSubtle: 'linear-gradient(180deg, #1B232E 0%, #131A24 100%)',          // Dark subtle (background transitions)
  },

  /**
   * Animation System
   */
  animations: {
    pulse: {
      keyframes: `
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
      `,
      duration: '2s',
      timing: 'ease-in-out',
      iteration: 'infinite',
    },

    fadeIn: {
      keyframes: `
        @keyframes fadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }
      `,
      duration: '200ms',
      timing: 'ease',
    },

    slideUp: {
      keyframes: `
        @keyframes slideUp {
          from { transform: translateY(10px); opacity: 0; }
          to { transform: translateY(0); opacity: 1; }
        }
      `,
      duration: '300ms',
      timing: 'ease-out',
    },
  },
} as const;

/**
 * Helper function to get color with opacity
 */
export function withOpacity(color: string, opacity: number): string {
  // Simple hex to rgba conversion for 6-digit hex colors
  if (color.startsWith('#') && color.length === 7) {
    const r = parseInt(color.slice(1, 3), 16);
    const g = parseInt(color.slice(3, 5), 16);
    const b = parseInt(color.slice(5, 7), 16);
    return `rgba(${r}, ${g}, ${b}, ${opacity})`;
  }
  return color;
}

/**
 * Type exports for TypeScript autocomplete
 */
export type DesignTokens = typeof tokens;
export type ColorToken = keyof typeof tokens.colors;
export type SpacingToken = keyof typeof tokens.spacing;
export type TypographyToken = keyof typeof tokens.typography;

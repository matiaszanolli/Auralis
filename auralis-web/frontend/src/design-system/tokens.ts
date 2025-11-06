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
   * Color System
   * Based on Aurora gradient aesthetic with dark navy backgrounds
   */
  colors: {
    // Background colors
    bg: {
      primary: '#0A0E27',      // Deep navy - main background
      secondary: '#1a1f3a',    // Lighter navy - elevated surfaces
      tertiary: '#252a47',     // Card backgrounds
      elevated: '#2d3350',     // Hover/active states
      overlay: 'rgba(10, 14, 39, 0.95)', // Modal/dialog overlays
    },

    // Accent colors (Aurora gradient theme)
    accent: {
      primary: '#667eea',      // Primary purple
      secondary: '#764ba2',    // Secondary purple
      tertiary: '#f093fb',     // Pink accent
      success: '#00d4aa',      // Turquoise - success states
      warning: '#f59e0b',      // Amber - warnings
      error: '#ef4444',        // Red - errors
      info: '#3b82f6',         // Blue - info
      purple: '#a855f7',       // Purple accent for processing
    },

    // Text colors
    text: {
      primary: '#ffffff',      // White - primary text
      secondary: '#8b92b0',    // Muted purple-gray - secondary text
      tertiary: '#6b7194',     // More muted - tertiary text
      disabled: '#4a5073',     // Disabled text
      inverse: '#0A0E27',      // For light backgrounds
    },

    // Border colors
    border: {
      light: 'rgba(139, 146, 176, 0.2)',   // Subtle borders
      medium: 'rgba(139, 146, 176, 0.4)',  // Standard borders
      heavy: 'rgba(139, 146, 176, 0.6)',   // Emphasized borders
      accent: '#667eea',                    // Accent borders
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
   */
  typography: {
    fontFamily: {
      primary: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
      mono: '"SF Mono", Monaco, "Cascadia Code", "Roboto Mono", Consolas, "Courier New", monospace',
    },

    fontSize: {
      xs: '11px',
      sm: '12px',
      base: '14px',
      md: '16px',
      lg: '18px',
      xl: '20px',
      '2xl': '24px',
      '3xl': '32px',
      '4xl': '48px',
    },

    fontWeight: {
      normal: 400,
      medium: 500,
      semibold: 600,
      bold: 700,
    },

    lineHeight: {
      tight: 1.2,
      normal: 1.5,
      relaxed: 1.75,
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
   * Shadow System
   */
  shadows: {
    none: 'none',
    sm: '0 1px 2px rgba(0, 0, 0, 0.05)',
    base: '0 2px 4px rgba(0, 0, 0, 0.1)',
    md: '0 4px 8px rgba(0, 0, 0, 0.15)',
    lg: '0 8px 16px rgba(0, 0, 0, 0.2)',
    xl: '0 12px 24px rgba(0, 0, 0, 0.25)',
    '2xl': '0 16px 32px rgba(0, 0, 0, 0.3)',
    glow: '0 0 20px rgba(102, 126, 234, 0.3)',  // Aurora glow
    glowStrong: '0 0 30px rgba(102, 126, 234, 0.5)',
  },

  /**
   * Transition System
   */
  transitions: {
    fast: '100ms ease',
    base: '200ms ease',
    slow: '300ms ease',
    verySlow: '500ms ease',

    // Specific properties
    color: '200ms color ease',
    background: '200ms background-color ease',
    transform: '200ms transform ease',
    opacity: '200ms opacity ease',
    all: '200ms all ease',
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
   * Component-Specific Tokens
   */
  components: {
    playerBar: {
      height: '90px',
      zIndex: 1030,
      background: 'rgba(26, 31, 58, 0.95)',
    },

    sidebar: {
      width: '240px',
      background: '#1a1f3a',
    },

    rightPanel: {
      width: '320px',
      background: '#1a1f3a',
    },

    albumCard: {
      size: '160px',
      borderRadius: '8px',
      hoverScale: 1.05,
    },

    searchBar: {
      height: '48px',
      borderRadius: '24px',  // Pill shape
      background: 'rgba(37, 42, 71, 0.6)',
    },
  },

  /**
   * Gradient System
   * Aurora-themed gradients
   */
  gradients: {
    aurora: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
    auroraSoft: 'linear-gradient(135deg, rgba(102, 126, 234, 0.8) 0%, rgba(118, 75, 162, 0.8) 100%)',
    auroraVertical: 'linear-gradient(180deg, #667eea 0%, #764ba2 100%)',
    pink: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
    turquoise: 'linear-gradient(135deg, #00d4aa 0%, #00a896 100%)',
    dark: 'linear-gradient(180deg, #1a1f3a 0%, #0A0E27 100%)',
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

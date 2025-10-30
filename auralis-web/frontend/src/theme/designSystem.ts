/**
 * Auralis Design System
 * =====================
 *
 * Comprehensive design system for the Auralis music player application.
 * This file serves as the single source of truth for all design tokens,
 * ensuring consistency across the entire application.
 *
 * **Design Philosophy:**
 * - Dark theme with aurora gradient branding
 * - Classic library player aesthetic (iTunes, Rhythmbox)
 * - Modern touches from Spotify and Cider
 * - Neon retro-futuristic accents
 * - Smooth animations and transitions
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3
 */

// ============================================================================
// SPACING SCALE
// ============================================================================
/**
 * Consistent spacing scale following 8px grid system.
 * Use these values for margins, padding, gaps, and positioning.
 *
 * **Usage:**
 * ```tsx
 * <Box sx={{ p: `${spacing.md}px`, mb: `${spacing.sm}px` }}>
 * ```
 */
export const spacing = {
  none: 0,
  xxs: 2,    // Minimal spacing (icon padding, borders)
  xs: 4,     // Very tight spacing (list items, inline elements)
  sm: 8,     // Tight spacing (compact UI, card padding)
  md: 16,    // Standard spacing (default padding, margins)
  lg: 24,    // Loose spacing (section gaps, card spacing)
  xl: 32,    // Extra loose spacing (page margins, major sections)
  xxl: 48,   // Large spacing (hero sections, page headers)
  xxxl: 64,  // Huge spacing (major page sections)
  huge: 96,  // Massive spacing (landing pages)
} as const;

// ============================================================================
// SHADOWS
// ============================================================================
/**
 * Elevation system using box-shadows.
 * Provides depth hierarchy for cards, modals, and floating elements.
 *
 * **Usage:**
 * ```tsx
 * <Card sx={{ boxShadow: shadows.md }}>
 * ```
 */
export const shadows = {
  none: 'none',
  xs: '0 1px 2px rgba(0, 0, 0, 0.08)',
  sm: '0 2px 4px rgba(0, 0, 0, 0.1)',
  md: '0 4px 12px rgba(0, 0, 0, 0.15)',
  lg: '0 8px 24px rgba(0, 0, 0, 0.2)',
  xl: '0 16px 48px rgba(0, 0, 0, 0.3)',
  xxl: '0 24px 64px rgba(0, 0, 0, 0.4)',

  // Aurora glow effects (signature Auralis brand)
  glowPurple: '0 8px 24px rgba(102, 126, 234, 0.3)',
  glowPink: '0 8px 24px rgba(255, 107, 157, 0.3)',
  glowBlue: '0 8px 24px rgba(75, 123, 236, 0.3)',
  glowCyan: '0 8px 24px rgba(38, 222, 129, 0.3)',

  // Interactive states
  hoverCard: '0 8px 24px rgba(102, 126, 234, 0.2)',
  activeCard: '0 4px 12px rgba(102, 126, 234, 0.4)',
  focusRing: '0 0 0 3px rgba(102, 126, 234, 0.3)',
} as const;

// ============================================================================
// BORDER RADIUS
// ============================================================================
/**
 * Border radius scale for consistent rounded corners.
 *
 * **Usage:**
 * ```tsx
 * <Box sx={{ borderRadius: `${borderRadius.md}px` }}>
 * ```
 */
export const borderRadius = {
  none: 0,
  xs: 4,      // Subtle rounding (buttons, inputs)
  sm: 8,      // Standard rounding (cards, panels)
  md: 12,     // Medium rounding (modals, popovers)
  lg: 16,     // Large rounding (images, featured content)
  xl: 24,     // Extra large rounding (hero images)
  xxl: 32,    // Huge rounding (decorative elements)
  full: 9999, // Circular/pill shape (avatars, tags)
} as const;

// ============================================================================
// ANIMATION TIMINGS
// ============================================================================
/**
 * Animation duration and easing functions.
 * Ensures consistent motion design across the app.
 *
 * **Guidelines:**
 * - Use `fast` for micro-interactions (hover, click)
 * - Use `normal` for standard transitions (page changes, modals)
 * - Use `slow` for complex animations (slide-ins, reveals)
 * - Use `bounce` for playful interactions (success states)
 *
 * **Usage:**
 * ```tsx
 * <Box sx={{ transition: transitions.fast }}>
 * ```
 */
export const transitions = {
  instant: '0ms',
  fast: '150ms ease-in-out',
  normal: '250ms ease-in-out',
  slow: '350ms ease-in-out',
  slower: '500ms ease-in-out',

  // Specialized easing
  bounce: '350ms cubic-bezier(0.68, -0.55, 0.265, 1.55)',
  smooth: '400ms cubic-bezier(0.4, 0, 0.2, 1)',
  snappy: '200ms cubic-bezier(0.4, 0, 0.6, 1)',

  // Component-specific durations
  hover: '150ms ease-in-out',
  modal: '300ms ease-in-out',
  page: '400ms ease-in-out',
  tooltip: '100ms ease-in-out',
} as const;

// ============================================================================
// GRADIENTS
// ============================================================================
/**
 * Aurora gradient system - Auralis brand signature.
 *
 * **Primary brand gradient:** `gradients.aurora`
 *
 * **Usage:**
 * ```tsx
 * <Box sx={{ background: gradients.aurora }}>
 * ```
 */
export const gradients = {
  // Primary brand gradients
  aurora: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
  auroraReverse: 'linear-gradient(135deg, #764ba2 0%, #667eea 100%)',
  auroraVertical: 'linear-gradient(180deg, #667eea 0%, #764ba2 100%)',

  // Secondary brand gradients
  neonSunset: 'linear-gradient(135deg, #ff6b9d 0%, #ffa502 100%)',
  deepOcean: 'linear-gradient(135deg, #4b7bec 0%, #26de81 100%)',
  electricPurple: 'linear-gradient(135deg, #c44569 0%, #667eea 100%)',
  cosmicBlue: 'linear-gradient(135deg, #0f2027 0%, #203a43 50%, #2c5364 100%)',

  // State gradients
  success: 'linear-gradient(135deg, #00d4aa 0%, #26de81 100%)',
  error: 'linear-gradient(135deg, #ff4757 0%, #c44569 100%)',
  warning: 'linear-gradient(135deg, #ffa502 0%, #ff6b9d 100%)',
  info: 'linear-gradient(135deg, #4b7bec 0%, #667eea 100%)',
} as const;

// ============================================================================
// COLOR PALETTE
// ============================================================================
/**
 * Comprehensive color system based on dark theme.
 * All colors are tested for WCAG AA accessibility on dark backgrounds.
 *
 * **Color categories:**
 * - Background: Surface colors for layouts
 * - Text: Typography colors with hierarchy
 * - Accent: Brand and UI accent colors
 * - Neon: Vibrant retro-futuristic colors
 * - Semantic: Status and feedback colors
 */
export const colors = {
  // Background colors (layered depth)
  background: {
    primary: '#0A0E27',      // Main app background (deep navy)
    secondary: '#1a1f3a',    // Elevated surfaces (panels, cards)
    surface: '#252b45',      // Interactive surfaces (hover states)
    elevated: '#2a3150',     // Raised surfaces (modals, dropdowns)
    hover: '#313858',        // Hover overlay
    active: '#3a4168',       // Active/pressed state
    glass: 'rgba(26, 31, 58, 0.7)',  // Glassmorphism background
  },

  // Text colors (hierarchy)
  text: {
    primary: '#ffffff',      // Main headings, important text
    secondary: '#8b92b0',    // Body text, descriptions
    tertiary: '#6b7299',     // Subtle text, hints
    disabled: '#5a5f7a',     // Disabled state
    hint: '#4a5070',         // Placeholder text
    inverse: '#0A0E27',      // Text on light backgrounds
  },

  // Brand accent colors
  accent: {
    primary: '#667eea',      // Primary brand purple
    primaryLight: '#8b9cf7', // Lighter variant
    primaryDark: '#5166d6',  // Darker variant
    secondary: '#764ba2',    // Secondary brand purple
    secondaryLight: '#9668c4',
    secondaryDark: '#5d3c82',
  },

  // Neon accent colors (retro-futuristic)
  neon: {
    pink: '#ff6b9d',
    purple: '#c44569',
    blue: '#4b7bec',
    cyan: '#26de81',
    orange: '#ffa502',
    yellow: '#fed330',
    green: '#00d4aa',
  },

  // Semantic colors (status, feedback)
  semantic: {
    success: '#00d4aa',      // Success states, confirmations
    successDark: '#00a388',
    error: '#ff4757',        // Errors, destructive actions
    errorDark: '#e63946',
    warning: '#ffa502',      // Warnings, caution
    warningDark: '#e68a00',
    info: '#4b7bec',         // Info messages, tips
    infoDark: '#3d68d4',
  },

  // Glassmorphism effects
  glass: {
    border: 'rgba(255, 255, 255, 0.1)',
    highlight: 'rgba(255, 255, 255, 0.05)',
    shadow: 'rgba(0, 0, 0, 0.3)',
  },
} as const;

// ============================================================================
// TYPOGRAPHY SCALE
// ============================================================================
/**
 * Typography system with semantic headings.
 * Font: Montserrat (loaded via CDN or local)
 *
 * **Usage:**
 * ```tsx
 * <Typography variant="h1" sx={{ ...typography.h1 }}>
 * ```
 */
export const typography = {
  fontFamily: {
    primary: '"Montserrat", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
    mono: '"Fira Code", "Roboto Mono", Menlo, Monaco, "Courier New", monospace',
  },

  // Heading scale
  h1: {
    fontSize: '32px',
    fontWeight: 700,
    lineHeight: 1.2,
    letterSpacing: '-0.5px',
  },
  h2: {
    fontSize: '28px',
    fontWeight: 700,
    lineHeight: 1.3,
    letterSpacing: '-0.25px',
  },
  h3: {
    fontSize: '24px',
    fontWeight: 600,
    lineHeight: 1.4,
    letterSpacing: '0px',
  },
  h4: {
    fontSize: '20px',
    fontWeight: 600,
    lineHeight: 1.5,
    letterSpacing: '0px',
  },
  h5: {
    fontSize: '18px',
    fontWeight: 600,
    lineHeight: 1.5,
    letterSpacing: '0px',
  },
  h6: {
    fontSize: '16px',
    fontWeight: 600,
    lineHeight: 1.5,
    letterSpacing: '0px',
  },

  // Body text
  body1: {
    fontSize: '16px',
    fontWeight: 400,
    lineHeight: 1.6,
    letterSpacing: '0px',
  },
  body2: {
    fontSize: '14px',
    fontWeight: 400,
    lineHeight: 1.6,
    letterSpacing: '0px',
  },

  // Supporting text
  caption: {
    fontSize: '12px',
    fontWeight: 400,
    lineHeight: 1.4,
    letterSpacing: '0.4px',
  },
  overline: {
    fontSize: '12px',
    fontWeight: 600,
    lineHeight: 1.2,
    letterSpacing: '1px',
    textTransform: 'uppercase' as const,
  },

  // UI elements
  button: {
    fontSize: '14px',
    fontWeight: 600,
    lineHeight: 1.5,
    letterSpacing: '0.2px',
    textTransform: 'none' as const,
  },
  input: {
    fontSize: '16px',
    fontWeight: 400,
    lineHeight: 1.5,
    letterSpacing: '0px',
  },
} as const;

// ============================================================================
// COMPONENT SIZES
// ============================================================================
/**
 * Standard sizes for common UI components.
 * Ensures consistency across buttons, inputs, avatars, etc.
 */
export const sizes = {
  // Button heights
  button: {
    xs: 24,
    sm: 32,
    md: 40,
    lg: 48,
    xl: 56,
  },

  // Input heights
  input: {
    sm: 32,
    md: 40,
    lg: 48,
  },

  // Icon sizes
  icon: {
    xs: 16,
    sm: 20,
    md: 24,
    lg: 32,
    xl: 48,
    xxl: 64,
  },

  // Avatar sizes
  avatar: {
    xs: 24,
    sm: 32,
    md: 40,
    lg: 56,
    xl: 72,
    xxl: 96,
  },

  // Album art sizes
  albumArt: {
    xs: 40,
    sm: 64,
    md: 96,
    lg: 160,
    xl: 240,
    xxl: 320,
    hero: 480,
  },
} as const;

// ============================================================================
// Z-INDEX SCALE
// ============================================================================
/**
 * Z-index layering system for stacking contexts.
 * Prevents z-index conflicts across components.
 */
export const zIndex = {
  base: 0,
  dropdown: 1000,
  sticky: 1100,
  overlay: 1200,
  modal: 1300,
  popover: 1400,
  tooltip: 1500,
  notification: 1600,
  max: 9999,
} as const;

// ============================================================================
// BREAKPOINTS (Responsive Design)
// ============================================================================
/**
 * Screen size breakpoints for responsive layouts.
 * Matches Material-UI default breakpoints.
 */
export const breakpoints = {
  xs: 0,      // Mobile portrait
  sm: 600,    // Mobile landscape
  md: 900,    // Tablet portrait
  lg: 1200,   // Tablet landscape / Desktop
  xl: 1536,   // Large desktop
} as const;

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================
/**
 * Generate rgba color with opacity.
 * @param color - Hex color code (e.g., '#667eea')
 * @param opacity - Opacity value 0-1
 */
export const rgba = (color: string, opacity: number): string => {
  const hex = color.replace('#', '');
  const r = parseInt(hex.substring(0, 2), 16);
  const g = parseInt(hex.substring(2, 4), 16);
  const b = parseInt(hex.substring(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${opacity})`;
};

/**
 * Generate hover effect styles.
 * Standard hover behavior for interactive elements.
 */
export const hoverEffect = {
  card: {
    transform: 'translateY(-4px)',
    boxShadow: shadows.hoverCard,
    transition: transitions.hover,
  },
  button: {
    transform: 'scale(1.05)',
    transition: transitions.hover,
  },
  icon: {
    transform: 'scale(1.1)',
    transition: transitions.hover,
  },
  subtle: {
    backgroundColor: colors.background.hover,
    transition: transitions.hover,
  },
} as const;

/**
 * Generate focus ring styles for accessibility.
 */
export const focusRing = {
  outline: 'none',
  boxShadow: shadows.focusRing,
} as const;

// ============================================================================
// EXPORT ALL
// ============================================================================
export const designSystem = {
  spacing,
  shadows,
  borderRadius,
  transitions,
  gradients,
  colors,
  typography,
  sizes,
  zIndex,
  breakpoints,
  hoverEffect,
  focusRing,
  rgba,
} as const;

export default designSystem;

/**
 * Color Styles - Reusable color and gradient presets
 *
 * Consolidates all hardcoded color values and gradients used across components
 * for consistent coloring throughout the application.
 *
 * Uses aurora color palette (#667eea, #764ba2) with opacity variants
 * as the primary design system colors.
 *
 * Color Categories:
 * - Aurora colors: Primary brand colors with opacity variants
 * - Gradient presets: Aurora gradient combinations
 * - Opacity variants: Standardized opacity levels for consistent usage
 */

/**
 * Aurora primary color (purple-blue)
 * Base hex color used throughout the application
 */
export const colorAuroraPrimary = '#667eea';

/**
 * Aurora secondary color (purple)
 * Complementary color to primary aurora
 */
export const colorAuroraSecondary = '#764ba2';

/**
 * Aurora color with opacity variants
 * Standardized opacity levels for consistent application across components
 *
 * Opacity scale:
 * - minimal: 5% - Barely visible, use for disabled states
 * - ultraLight: 8% - Very subtle backgrounds
 * - veryLight: 10% - Light borders, subtle backgrounds (MOST COMMON)
 * - light: 12% - Track current state, soft hover
 * - lighter: 15% - Hover states, gentle glows
 * - standard: 20% - Standard backgrounds, medium opacity
 * - strong: 30% - Focus states, button shadows (VERY COMMON)
 * - veryStrong: 40% - Strong glows, prominent shadows
 * - stronger: 50% - Very strong emphasis, dashed borders
 */
export const auroraOpacity = {
  minimal: 'rgba(102, 126, 234, 0.05)',
  ultraLight: 'rgba(102, 126, 234, 0.08)',
  veryLight: 'rgba(102, 126, 234, 0.1)',
  light: 'rgba(102, 126, 234, 0.12)',
  lighter: 'rgba(102, 126, 234, 0.15)',
  standard: 'rgba(102, 126, 234, 0.2)',
  strong: 'rgba(102, 126, 234, 0.3)',
  veryStrong: 'rgba(102, 126, 234, 0.4)',
  stronger: 'rgba(102, 126, 234, 0.5)',
  intense: 'rgba(102, 126, 234, 0.6)',
  veryIntense: 'rgba(102, 126, 234, 0.7)',
  saturated: 'rgba(102, 126, 234, 0.8)',
  vivid: 'rgba(102, 126, 234, 0.9)',
  fullAlpha: 'rgba(102, 126, 234, 1.0)',
};

/**
 * White color with opacity variants
 * Used for light UI elements and overlays
 */
export const whiteOpacity = {
  veryLight: 'rgba(255, 255, 255, 0.05)',
  light: 'rgba(255, 255, 255, 0.1)',
  lighter: 'rgba(255, 255, 255, 0.15)',
  standard: 'rgba(255, 255, 255, 0.2)',
  strong: 'rgba(255, 255, 255, 0.3)',
  veryStrong: 'rgba(255, 255, 255, 0.5)',
  nearOpaque: 'rgba(255, 255, 255, 0.7)',
};

/**
 * Black color with opacity variants
 * Used for dark UI elements and overlays
 */
export const blackOpacity = {
  veryLight: 'rgba(0, 0, 0, 0.05)',
  light: 'rgba(0, 0, 0, 0.1)',
  lighter: 'rgba(0, 0, 0, 0.15)',
  standard: 'rgba(0, 0, 0, 0.2)',
  strong: 'rgba(0, 0, 0, 0.3)',
  veryStrong: 'rgba(0, 0, 0, 0.4)',
  strongerDark: 'rgba(0, 0, 0, 0.5)',
};

/**
 * Aurora gradient presets
 * Common gradient combinations used throughout the application
 */
export const gradientPresets = {
  // Main aurora gradient - primary design element
  aurora: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
  // 45-degree variant
  aurora45: 'linear-gradient(45deg, #667eea 0%, #764ba2 100%)',
  // Hover variant with increased opacity
  auroraHover: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
};

/**
 * Status colors for connection indicators and alerts
 * Used for showing system status, connectivity, and notifications
 */
export const statusColors = {
  // Connection status indicators
  connected: '#4ade80', // Green - active/successful
  connecting: '#facc15', // Yellow - pending/loading
  disconnected: '#ef4444', // Red - error/offline

  // Alternative status colors for emphasis
  success: '#10b981', // Emerald green
  warning: '#f59e0b', // Amber
  error: '#ef4444', // Red
  info: '#3b82f6', // Blue
};

/**
 * Utility color presets for common use cases
 */
export const colorUtility = {
  // Borders and separators
  border: {
    subtle: auroraOpacity.veryLight,
    standard: auroraOpacity.light,
    strong: auroraOpacity.lighter,
  },

  // Backgrounds and overlays
  background: {
    hover: auroraOpacity.ultraLight,
    subtle: auroraOpacity.veryLight,
    standard: auroraOpacity.light,
    strong: auroraOpacity.standard,
  },

  // Focus and interaction states
  focus: {
    ring: auroraOpacity.veryLight,
    glow: auroraOpacity.strong,
    glowStrong: auroraOpacity.veryStrong,
  },

  // Shadows and glows
  shadow: {
    subtle: auroraOpacity.light,
    standard: auroraOpacity.standard,
    strong: auroraOpacity.strong,
    veryStrong: auroraOpacity.veryStrong,
  },

  // Button states
  button: {
    hover: auroraOpacity.ultraLight,
    active: auroraOpacity.standard,
    disabled: auroraOpacity.minimal,
  },

  // Error/destructive colors
  error: '#ff4757',
  errorHover: '#ff3838',

  // Success colors
  success: '#2ed573',
  successHover: '#26de81',

  // Warning colors
  warning: '#ffa502',
  warningHover: '#ff9500',
};

/**
 * Color combination presets for common patterns
 */
export const colorCombos = {
  // For hover states (background + text)
  hoverState: {
    background: auroraOpacity.ultraLight,
    text: colorAuroraPrimary,
  },

  // For active/selected states
  activeState: {
    background: auroraOpacity.standard,
    text: '#ffffff',
  },

  // For focus rings and outlines
  focusRing: {
    ring: `0 0 0 3px ${auroraOpacity.veryLight}`,
    glow: `0 0 12px ${auroraOpacity.strong}`,
  },

  // For disabled states
  disabledState: {
    background: auroraOpacity.minimal,
    text: 'rgba(255, 255, 255, 0.3)',
  },
};

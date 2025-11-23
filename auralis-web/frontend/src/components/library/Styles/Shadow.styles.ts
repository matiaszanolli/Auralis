/**
 * Shadow Styles - Reusable elevation and shadow presets
 *
 * Consolidates all shadow patterns used across components for consistent
 * depth and elevation effects throughout the application.
 *
 * Color values are imported from Color.styles.ts for consistency.
 *
 * Shadow Categories:
 * - Button shadows: Hover/active state glows
 * - Card shadows: Card elevation and hover effects
 * - Container shadows: Search results, dropdowns, modals
 * - Focus shadows: Input focus rings
 * - Glow shadows: Aurora glow effects (purple)
 */

import { auroraOpacity, blackOpacity } from './Color.styles';

/**
 * Button shadow presets - Used for button hover/active states
 */
export const buttonShadows = {
  // Primary action button hover shadow (3px offset, 12px blur)
  primary: `0 4px 12px ${auroraOpacity.veryStrong}`,
  // Subtle button hover shadow (2px offset, 8px blur, medium opacity)
  secondary: `0 2px 8px ${auroraOpacity.strong}`,
  // Subtle button focus/hover shadow (low opacity)
  tertiary: `0 2px 8px ${auroraOpacity.standard}`,
  // Dark button shadow (for contrast backgrounds)
  dark: `0 4px 12px ${blackOpacity.standard}`,
};

/**
 * Card shadow presets - Used for cards, modals, and elevated surfaces
 */
export const cardShadows = {
  // Large dropdown/modal shadow (8px offset, 32px blur)
  dropdown: `0 8px 32px ${auroraOpacity.strong}`,
  // Large dropdown/modal shadow (dark variant)
  dropdownDark: `0 8px 32px ${blackOpacity.veryStrong}`,
  // Card hover shadow (8px offset, 32px blur, strong opacity)
  hoverGlow: `0 8px 32px ${auroraOpacity.veryStrong}`,
  // Medium card elevation shadow (8px offset, 24px blur)
  hover: `0 8px 24px ${auroraOpacity.standard}`,
  // Dark card shadow variant
  dark: `0 8px 24px ${blackOpacity.standard}`,
  // Small context menu shadow (12px offset, 48px blur)
  contextMenu: `0 12px 48px ${blackOpacity.stronger}`,
};

/**
 * Container shadow presets - Used for large containers and grouped elements
 */
export const containerShadows = {
  // Results container/dropdown shadow (8px offset, 32px blur, dark)
  dropdown: `0 8px 32px ${blackOpacity.veryStrong}`,
  // Search results container shadow (same as results panel)
  resultsPanel: `0 8px 32px ${blackOpacity.stronger}`,
};

/**
 * Focus shadow presets - Used for input focus states
 */
export const focusShadows = {
  // Input focus ring shadow (3px spread)
  ring: `0 0 0 3px ${auroraOpacity.veryLight}`,
  // Input glow on focus (12px blur)
  glow: `0 0 12px ${auroraOpacity.strong}`,
  // Strong focus glow (20px blur)
  glowStrong: `0 0 20px ${auroraOpacity.veryStrong}`,
};

/**
 * Glow shadow presets - Used for aurora/ambient glow effects
 */
export const glowShadows = {
  // Aurora purple glow (medium)
  purple: `0 8px 32px ${auroraOpacity.strong}`,
  // Aurora purple glow (strong)
  purpleStrong: `0 8px 32px ${auroraOpacity.veryStrong}`,
  // Subtle ambient glow
  subtle: `0 4px 12px ${auroraOpacity.strong}`,
  // Strong ambient glow
  strong: `0 4px 12px ${auroraOpacity.veryStrong}`,
};

/**
 * Notification shadow presets - Used for toasts, alerts, notifications
 */
export const notificationShadows = {
  // Toast/notification shadow (4px offset, 12px blur)
  toast: '0 4px 12px rgba(0, 0, 0, 0.3)',
};

/**
 * Compound shadow presets - Complex multi-layer shadows
 */
export const compoundShadows = {
  // Player button shadow (large base + subtle top)
  playerButton: '0 4px 16px rgba(102, 126, 234, 0.2), 0 0 24px rgba(102, 126, 234, 0.1)',
  // Player button hover (large base + strong top)
  playerButtonHover: '0 8px 24px rgba(102, 126, 234, 0.3), 0 0 32px rgba(102, 126, 234, 0.2)',
  // Player container (negative Y for top-facing shadow)
  playerContainer: '0 -8px 32px rgba(102, 126, 234, 0.15), 0 -2px 8px rgba(102, 126, 234, 0.1)',
};

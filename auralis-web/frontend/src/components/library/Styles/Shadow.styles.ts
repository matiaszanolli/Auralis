/**
 * Shadow Styles - Reusable elevation and shadow presets
 *
 * Consolidates all shadow patterns used across components for consistent
 * depth and elevation effects throughout the application.
 *
 * Color values are sourced from '@/design-system' tokens.
 *
 * Shadow Categories:
 * - Button shadows: Hover/active state glows
 * - Card shadows: Card elevation and hover effects
 * - Container shadows: Search results, dropdowns, modals
 * - Focus shadows: Input focus rings
 * - Glow shadows: Aurora glow effects (purple)
 */

import { tokens } from '@/design-system';

/**
 * Button shadow presets - Used for button hover/active states
 */
export const buttonShadows = {
  // Primary action button hover shadow (3px offset, 12px blur)
  primary: `0 4px 12px ${tokens.colors.opacityScale.accent.veryStrong}`,
  // Subtle button hover shadow (2px offset, 8px blur, medium opacity)
  secondary: `0 2px 8px ${tokens.colors.opacityScale.accent.strong}`,
  // Subtle button focus/hover shadow (low opacity)
  tertiary: `0 2px 8px ${tokens.colors.opacityScale.accent.standard}`,
  // Dark button shadow (for contrast backgrounds)
  dark: `0 4px 12px ${tokens.colors.opacityScale.dark.standard}`,
};

/**
 * Card shadow presets - Used for cards, modals, and elevated surfaces
 */
export const cardShadows = {
  // Large dropdown/modal shadow (8px offset, 32px blur)
  dropdown: `0 8px 32px ${tokens.colors.opacityScale.accent.strong}`,
  // Large dropdown/modal shadow (dark variant)
  dropdownDark: `0 8px 32px ${tokens.colors.opacityScale.dark.veryStrong}`,
  // Card hover shadow (8px offset, 32px blur, strong opacity)
  hoverGlow: `0 8px 32px ${tokens.colors.opacityScale.accent.veryStrong}`,
  // Medium card elevation shadow (8px offset, 24px blur)
  hover: `0 8px 24px ${tokens.colors.opacityScale.accent.standard}`,
  // Dark card shadow variant
  dark: `0 8px 24px ${tokens.colors.opacityScale.dark.standard}`,
  // Small context menu shadow (12px offset, 48px blur)
  contextMenu: `0 12px 48px ${tokens.colors.opacityScale.dark.veryStrong}`,
};

/**
 * Container shadow presets - Used for large containers and grouped elements
 */
export const containerShadows = {
  // Results container/dropdown shadow (8px offset, 32px blur, dark)
  dropdown: `0 8px 32px ${tokens.colors.opacityScale.dark.veryStrong}`,
  // Search results container shadow (same as results panel)
  resultsPanel: `0 8px 32px ${tokens.colors.opacityScale.dark.veryStrong}`,
};

/**
 * Focus shadow presets - Used for input focus states
 */
export const focusShadows = {
  // Input focus ring shadow (3px spread)
  ring: `0 0 0 3px ${tokens.colors.opacityScale.accent.veryLight}`,
  // Input glow on focus (12px blur)
  glow: `0 0 12px ${tokens.colors.opacityScale.accent.strong}`,
  // Strong focus glow (20px blur)
  glowStrong: `0 0 20px ${tokens.colors.opacityScale.accent.veryStrong}`,
};

/**
 * Glow shadow presets - Used for aurora/ambient glow effects
 */
export const glowShadows = {
  // Aurora purple glow (medium)
  purple: `0 8px 32px ${tokens.colors.opacityScale.accent.strong}`,
  // Aurora purple glow (strong)
  purpleStrong: `0 8px 32px ${tokens.colors.opacityScale.accent.veryStrong}`,
  // Subtle ambient glow
  subtle: `0 4px 12px ${tokens.colors.opacityScale.accent.strong}`,
  // Strong ambient glow
  strong: `0 4px 12px ${tokens.colors.opacityScale.accent.veryStrong}`,
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
// Compound shadows use auroraOpacity (accent #7366F0) instead of deprecated #667eea (fixes #2356).
export const compoundShadows = {
  // Player button shadow (large base + subtle top)
  playerButton: `0 4px 16px ${tokens.colors.opacityScale.accent.standard}, 0 0 24px ${tokens.colors.opacityScale.accent.veryLight}`,
  // Player button hover (large base + strong top)
  playerButtonHover: `0 8px 24px ${tokens.colors.opacityScale.accent.strong}, 0 0 32px ${tokens.colors.opacityScale.accent.standard}`,
  // Player container (negative Y for top-facing shadow)
  playerContainer: `0 -8px 32px ${tokens.colors.opacityScale.accent.lighter}, 0 -2px 8px ${tokens.colors.opacityScale.accent.veryLight}`,
};

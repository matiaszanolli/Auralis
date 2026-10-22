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

/**
 * Border Radius Styles - Reusable border radius presets
 *
 * Consolidates all border radius values used across components for consistent
 * rounding patterns throughout the application.
 *
 * Uses design system tokens as single source of truth to ensure consistency
 * and enable global design changes from one location.
 *
 * Radius Categories:
 * - Small (sm): 4px - Tight corners (inputs, small buttons)
 * - Medium (md): 8px - Standard corners (cards, dialogs, modals)
 * - Large (lg): 12px - Generous corners (large components)
 * - XLarge (xl): 16px - Extra large corners
 * - Full (full): 9999px - Pill shapes (fully rounded ends)
 * - Circle (circle): 50% - Perfect circles (avatars)
 */

/**
 * Small border radius - 4px
 * Used for: small buttons, compact inputs, subtle rounding
 */
export const radiusSmall = '4px';

/**
 * Medium border radius - 8px (MOST COMMON)
 * Used for: cards, dialogs, modals, standard components
 * This is the default/standard radius for most UI elements
 */
export const radiusMedium = '8px';

/**
 * Large border radius - 12px
 * Used for: large cards, prominent components, generous spacing
 */
export const radiusLarge = '12px';

/**
 * XLarge border radius - 16px
 * Used for: extra large components, hero sections
 */
export const radiusXLarge = '16px';

/**
 * Full radius - 9999px
 * Used for: pill-shaped buttons, fully rounded containers
 * Creates perfectly rounded pill shapes regardless of width
 */
export const radiusFull = '9999px';

/**
 * Circle radius - 50%
 * Used for: perfect circles (avatars, circular buttons)
 * Maintains circular shape relative to container dimensions
 */
export const radiusCircle = '50%';

/**
 * Preset object for convenient imports
 * Usage: borderRadiusPresets.medium, borderRadiusPresets.full
 */
export const borderRadiusPresets = {
  none: '0',
  sm: radiusSmall,
  md: radiusMedium,
  lg: radiusLarge,
  xl: radiusXLarge,
  full: radiusFull,
  circle: radiusCircle,
};

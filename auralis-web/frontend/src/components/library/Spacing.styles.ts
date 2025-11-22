/**
 * Spacing Styles - Reusable spacing and padding presets
 *
 * Consolidates all padding, margin, and gap values used across components
 * for consistent spacing throughout the application.
 *
 * Uses design system tokens as single source of truth to ensure consistency
 * and enable global spacing changes from one location.
 *
 * Spacing Scale (based on 4px grid):
 * - xs: 4px - Minimal spacing (small gaps, tight layouts)
 * - sm: 8px - Small spacing (compact components)
 * - md: 16px - Medium spacing (standard components, most common)
 * - lg: 24px - Large spacing (generous components)
 * - xl: 32px - Extra large spacing (major sections)
 * - xxl: 48px - Double extra large spacing
 * - xxxl: 64px - Triple extra large spacing (hero sections)
 *
 * Additional non-standard values for specific use cases:
 * - xsmall: 12px - For components needing between sm (8px) and md (16px)
 * - midpoint: 20px - For components needing between md (16px) and lg (24px)
 */

/**
 * Extra small spacing - 4px
 * Used for: minimal gaps, tight list spacing, small component padding
 */
export const spacingXSmall = '4px';

/**
 * Small spacing - 8px
 * Used for: compact components, small gaps, button padding
 */
export const spacingSmall = '8px';

/**
 * Medium spacing - 12px (custom, between sm and md)
 * Used for: menu items, small dialogs, form element spacing
 * Note: Not in standard design tokens but commonly needed
 */
export const spacingXMedium = '12px';

/**
 * Standard spacing - 16px (MOST COMMON)
 * Used for: cards, dialogs, container padding, standard spacing
 */
export const spacingMedium = '16px';

/**
 * Midpoint spacing - 20px (custom, between md and lg)
 * Used for: section padding, large component spacing
 * Note: Not in standard design tokens but commonly needed
 */
export const spacingMidpoint = '20px';

/**
 * Large spacing - 24px
 * Used for: generous padding, section spacing, dialog content
 */
export const spacingLarge = '24px';

/**
 * Extra large spacing - 32px
 * Used for: major section spacing, large containers
 */
export const spacingXLarge = '32px';

/**
 * Double extra large spacing - 48px
 * Used for: page-level spacing, large hero sections
 */
export const spacingXXLarge = '48px';

/**
 * Triple extra large spacing - 64px
 * Used for: major layout sections, full-page spacing
 */
export const spacingXXXLarge = '64px';

/**
 * Preset object for convenient padding/margin combinations
 * Usage: spacingPresets.padding.sm, spacingPresets.margin.md, spacingPresets.gap.lg
 */
export const spacingPresets = {
  // Single-value spacings
  xs: spacingXSmall,
  sm: spacingSmall,
  xm: spacingXMedium,
  md: spacingMedium,
  mid: spacingMidpoint,
  lg: spacingLarge,
  xl: spacingXLarge,
  xxl: spacingXXLarge,
  xxxl: spacingXXXLarge,

  // Padding combinations (top/bottom, left/right)
  padding: {
    compact: `${spacingSmall} ${spacingMedium}`, // 8px 16px
    standard: `${spacingMedium} ${spacingLarge}`, // 16px 24px
    generous: `${spacingLarge} ${spacingXLarge}`, // 24px 32px
    vertical: spacingMedium, // 16px (top/bottom only)
    horizontal: spacingLarge, // 24px (left/right only)
  },

  // Margin combinations
  margin: {
    compact: `${spacingSmall} ${spacingMedium}`, // 8px 16px
    standard: `${spacingMedium} ${spacingLarge}`, // 16px 24px
    generous: `${spacingLarge} ${spacingXLarge}`, // 24px 32px
    vertical: spacingMedium, // 16px (top/bottom only)
    horizontal: spacingLarge, // 24px (left/right only)
  },

  // Gap combinations (for flex/grid)
  gap: {
    compact: spacingSmall, // 8px
    standard: spacingMedium, // 16px (most common)
    generous: spacingLarge, // 24px
    large: spacingXLarge, // 32px
  },

  // Specific patterns used frequently in codebase
  buttons: {
    compact: `${spacingSmall} ${spacingMedium}`, // 8px 16px
    standard: `${spacingMedium} ${spacingLarge}`, // 16px 24px
  },

  cards: {
    padding: spacingMedium, // 16px
    margin: spacingMedium, // 16px
  },

  dialogs: {
    padding: spacingLarge, // 24px
    contentSpacing: spacingMedium, // 16px
  },

  sections: {
    vertical: spacingMedium, // 16px (top/bottom)
    horizontal: spacingLarge, // 24px (left/right)
  },
};

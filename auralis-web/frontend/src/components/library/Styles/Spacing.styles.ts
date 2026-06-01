/**
 * Spacing Styles - Reusable spacing and padding presets
 *
 * Consolidates the padding, margin, and gap values used across components.
 *
 * Derived from the design-system spacing tokens (#3947) so global spacing
 * changes from `tokens.spacing` actually propagate here — previously these were
 * a parallel hardcoded scale (16/24/32/48/64) that drifted 4-8px above the token
 * scale and ignored token changes entirely. Each constant now maps to its
 * semantic token level, so the computed layout follows the token scale (which is
 * slightly tighter, e.g. "medium" = tokens.spacing.md = 12px, "large" =
 * tokens.spacing.lg = 20px).
 *
 * Token scale (single source of truth — see design-system/tokens.ts):
 * - xs 4px · sm 6px · md 12px · lg 20px · xl 28px · xxl 40px · xxxl 56px
 */

import { tokens } from '@/design-system';

/** Extra small — tokens.spacing.xs. Minimal gaps, tight list spacing. */
export const spacingXSmall = tokens.spacing.xs;

/** Small — tokens.spacing.sm. Compact components, small gaps, button padding. */
export const spacingSmall = tokens.spacing.sm;

/**
 * Between small and medium — tokens.spacing.md. Menu items, small dialogs,
 * form element spacing. (Collapses onto md in the token scale.)
 */
export const spacingXMedium = tokens.spacing.md;

/** Standard / most common — tokens.spacing.md. Cards, dialogs, container padding. */
export const spacingMedium = tokens.spacing.md;

/**
 * Midpoint — tokens.spacing.lg. Section padding, large component spacing.
 * (Collapses onto lg in the token scale.)
 */
export const spacingMidpoint = tokens.spacing.lg;

/** Large — tokens.spacing.lg. Generous padding, section spacing, dialog content. */
export const spacingLarge = tokens.spacing.lg;

/** Extra large — tokens.spacing.xl. Major section spacing, large containers. */
export const spacingXLarge = tokens.spacing.xl;

/** Double extra large — tokens.spacing.xxl. Page-level spacing, hero sections. */
export const spacingXXLarge = tokens.spacing.xxl;

/** Triple extra large — tokens.spacing.xxxl. Major layout sections. */
export const spacingXXXLarge = tokens.spacing.xxxl;

/**
 * Preset object for convenient padding/margin combinations.
 * Usage: spacingPresets.padding.sm, spacingPresets.margin.md, spacingPresets.gap.lg
 *
 * All values derive from the constants above (and therefore from tokens.spacing).
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
    compact: `${spacingSmall} ${spacingMedium}`, // sm md
    standard: `${spacingMedium} ${spacingLarge}`, // md lg
    generous: `${spacingLarge} ${spacingXLarge}`, // lg xl
    vertical: spacingMedium, // md (top/bottom only)
    horizontal: spacingLarge, // lg (left/right only)
  },

  // Margin combinations
  margin: {
    compact: `${spacingSmall} ${spacingMedium}`, // sm md
    standard: `${spacingMedium} ${spacingLarge}`, // md lg
    generous: `${spacingLarge} ${spacingXLarge}`, // lg xl
    vertical: spacingMedium, // md (top/bottom only)
    horizontal: spacingLarge, // lg (left/right only)
  },

  // Gap combinations (for flex/grid)
  gap: {
    compact: spacingSmall, // sm
    standard: spacingMedium, // md (most common)
    generous: spacingLarge, // lg
    large: spacingXLarge, // xl
  },

  // Specific patterns used frequently in codebase
  buttons: {
    compact: `${spacingSmall} ${spacingMedium}`, // sm md
    standard: `${spacingMedium} ${spacingLarge}`, // md lg
  },

  cards: {
    padding: spacingMedium, // md
    margin: spacingMedium, // md
  },

  dialogs: {
    padding: spacingLarge, // lg
    contentSpacing: spacingMedium, // md
  },

  sections: {
    vertical: spacingMedium, // md (top/bottom)
    horizontal: spacingLarge, // lg (left/right)
  },
};

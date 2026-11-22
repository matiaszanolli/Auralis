/**
 * Spacing Styles - Reusable spacing and padding presets
 *
 * Every value is a design-system spacing token (#3947), so global spacing
 * changes from `tokens.spacing` propagate here. These used to be a parallel
 * hardcoded scale (16/24/32/48/64) that drifted 4-8px above the token scale.
 *
 * Token scale (single source of truth — see design-system/tokens.ts):
 * - xs 4px · sm 6px · md 12px · lg 20px · xl 28px · xxl 40px · xxxl 56px
 */

import { tokens } from '@/design-system';

const { xs, sm, md, lg, xl, xxl, xxxl } = tokens.spacing;

/**
 * Preset object for convenient padding/margin combinations.
 * Usage: spacingPresets.padding.sm, spacingPresets.margin.md, spacingPresets.gap.lg
 *
 * All values are tokens.spacing levels.
 */
export const spacingPresets = {
  // Single-value spacings
  xs,
  sm,
  xm: md,
  md,
  mid: lg,
  lg,
  xl,
  xxl,
  xxxl,

  // Padding combinations (top/bottom, left/right)
  padding: {
    compact: `${sm} ${md}`,
    standard: `${md} ${lg}`,
    generous: `${lg} ${xl}`,
    vertical: md, // top/bottom only
    horizontal: lg, // left/right only
  },

  // Margin combinations
  margin: {
    compact: `${sm} ${md}`,
    standard: `${md} ${lg}`,
    generous: `${lg} ${xl}`,
    vertical: md, // top/bottom only
    horizontal: lg, // left/right only
  },

  // Gap combinations (for flex/grid)
  gap: {
    compact: sm,
    standard: md, // most common
    generous: lg,
    large: xl,
  },

  // Specific patterns used frequently in codebase
  buttons: {
    compact: `${sm} ${md}`,
    standard: `${md} ${lg}`,
  },

  cards: {
    padding: md,
    margin: md,
  },

  dialogs: {
    padding: lg,
    contentSpacing: md,
  },

  sections: {
    vertical: md, // top/bottom
    horizontal: lg, // left/right
  },
};

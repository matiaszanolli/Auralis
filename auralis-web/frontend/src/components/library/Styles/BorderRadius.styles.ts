/**
 * Border Radius Styles - Reusable border radius presets
 *
 * Thin aliases over `tokens.borderRadius` so consumers can keep using the
 * existing `radiusSmall` / `radiusMedium` / ... names while values stay
 * automatically in sync with the design system.
 *
 * #3599: previous version held hard-coded strings ('4px', '8px', ...) that
 * were one scale step behind the current tokens, so skeleton loaders
 * rendered with tighter corners than the real content they replaced.
 */

import { tokens } from '@/design-system';

/** Small border radius — currently tokens.borderRadius.sm (8px). */
export const radiusSmall = tokens.borderRadius.sm;

/** Medium border radius — currently tokens.borderRadius.md (12px). MOST COMMON. */
export const radiusMedium = tokens.borderRadius.md;

/** Large border radius — currently tokens.borderRadius.lg (16px). */
export const radiusLarge = tokens.borderRadius.lg;

/** XLarge border radius — currently tokens.borderRadius.xl (20px). */
export const radiusXLarge = tokens.borderRadius.xl;

/** Full radius — pill shapes regardless of width. */
export const radiusFull = tokens.borderRadius.full;

/** Circle radius (50%) — used for avatars / circular buttons. */
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

/**
 * Auralis Design System Tokens — barrel.
 *
 * Single source of truth for all design values. ALL components MUST use these
 * tokens — no hardcoded values allowed.
 *
 * #4079: the former 948-line monolith was split by category into ./tokens/*.
 * This barrel re-merges them so every existing `tokens.<category>` reference and
 * `import { tokens } from '@/design-system'` resolves identically.
 *
 * @see docs/UI_STYLE_GUIDE.md
 */

import { colors } from './tokens/colors';
import { typography } from './tokens/typography';
import { spacing, borderRadius, blur, opacity, zIndex, breakpoints } from './tokens/layout';
import { shadows, elevation, transitions, audioReactive, animations } from './tokens/effects';
import { gradients, glass } from './tokens/surfaces';
import { numbersPolicy, visualization, components } from './tokens/semantics';

export const tokens = {
  colors, spacing, typography, borderRadius, shadows, blur, elevation,
  opacity, transitions, audioReactive, numbersPolicy, visualization,
  zIndex, breakpoints, components, gradients, glass, animations,
} as const;

export { withOpacity } from './tokens/with-opacity';

export type DesignTokens = typeof tokens;
export type ColorToken = keyof typeof tokens.colors;
export type SpacingToken = keyof typeof tokens.spacing;
export type TypographyToken = keyof typeof tokens.typography;

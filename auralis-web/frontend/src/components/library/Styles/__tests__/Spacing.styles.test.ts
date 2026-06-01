/**
 * Spacing.styles regression tests (#3947)
 *
 * The spacing constants used to be a hardcoded parallel scale (16/24/32…) that
 * drifted above tokens.spacing and ignored token changes. These tests pin the
 * constants to their semantic tokens so the layout follows the token scale and
 * global token edits propagate.
 */

import { describe, it, expect } from 'vitest';
import { tokens } from '@/design-system';
import {
  spacingXSmall,
  spacingSmall,
  spacingXMedium,
  spacingMedium,
  spacingMidpoint,
  spacingLarge,
  spacingXLarge,
  spacingXXLarge,
  spacingXXXLarge,
  spacingPresets,
} from '../Spacing.styles';

describe('Spacing.styles derives from tokens.spacing (#3947)', () => {
  it('maps each constant to its semantic spacing token', () => {
    expect(spacingXSmall).toBe(tokens.spacing.xs);
    expect(spacingSmall).toBe(tokens.spacing.sm);
    expect(spacingXMedium).toBe(tokens.spacing.md);
    expect(spacingMedium).toBe(tokens.spacing.md);
    expect(spacingMidpoint).toBe(tokens.spacing.lg);
    expect(spacingLarge).toBe(tokens.spacing.lg);
    expect(spacingXLarge).toBe(tokens.spacing.xl);
    expect(spacingXXLarge).toBe(tokens.spacing.xxl);
    expect(spacingXXXLarge).toBe(tokens.spacing.xxxl);
  });

  it('no longer hardcodes the old 16/24px scale', () => {
    // The previous bug: spacingMedium=16px (vs token md=12px), large=24px (vs 20px).
    expect(spacingMedium).not.toBe('16px');
    expect(spacingLarge).not.toBe('24px');
    expect(spacingMedium).toBe('12px'); // = tokens.spacing.md
    expect(spacingLarge).toBe('20px'); // = tokens.spacing.lg
  });

  it('builds presets from the token-derived constants', () => {
    expect(spacingPresets.md).toBe(tokens.spacing.md);
    expect(spacingPresets.lg).toBe(tokens.spacing.lg);
    // Combination presets compose the token values.
    expect(spacingPresets.padding.standard).toBe(
      `${tokens.spacing.md} ${tokens.spacing.lg}`
    );
    expect(spacingPresets.gap.standard).toBe(tokens.spacing.md);
  });
});

/**
 * Spacing.styles regression tests (#3947)
 *
 * The spacing presets used to be built on a hardcoded parallel scale (16/24/32…)
 * that drifted above tokens.spacing and ignored token changes. These tests pin
 * the presets to the semantic tokens so the layout follows the token scale and
 * global token edits propagate.
 */

import { describe, it, expect } from 'vitest';
import { tokens } from '@/design-system';
import { spacingPresets } from '../Spacing.styles';

describe('Spacing.styles derives from tokens.spacing (#3947)', () => {
  it('maps each single-value preset to its semantic spacing token', () => {
    expect(spacingPresets.xs).toBe(tokens.spacing.xs);
    expect(spacingPresets.sm).toBe(tokens.spacing.sm);
    expect(spacingPresets.xm).toBe(tokens.spacing.md);
    expect(spacingPresets.md).toBe(tokens.spacing.md);
    expect(spacingPresets.mid).toBe(tokens.spacing.lg);
    expect(spacingPresets.lg).toBe(tokens.spacing.lg);
    expect(spacingPresets.xl).toBe(tokens.spacing.xl);
    expect(spacingPresets.xxl).toBe(tokens.spacing.xxl);
    expect(spacingPresets.xxxl).toBe(tokens.spacing.xxxl);
  });

  it('no longer hardcodes the old 16/24px scale', () => {
    // The previous bug: medium=16px (vs token md=12px), large=24px (vs 20px).
    expect(spacingPresets.md).toBe('12px'); // = tokens.spacing.md
    expect(spacingPresets.lg).toBe('20px'); // = tokens.spacing.lg
  });

  it('composes the combination presets from the token values', () => {
    expect(spacingPresets.padding.standard).toBe(`${tokens.spacing.md} ${tokens.spacing.lg}`);
    // The two presets BatchActionsToolbar renders with.
    expect(spacingPresets.buttons.compact).toBe(`${tokens.spacing.sm} ${tokens.spacing.md}`);
    expect(spacingPresets.gap.standard).toBe(tokens.spacing.md);
  });
});

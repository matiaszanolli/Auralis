/**
 * Starfield glass token regression test (#3950 / DS-5)
 *
 * App-shell glass surfaces previously hardcoded five different blue-black
 * rgba() tuples. They are now unified behind tokens.glass.starfield (one base
 * tint at the opacity steps the shell uses). This pins the token's shape and
 * values so the unified scale can't silently regress.
 */

import { describe, it, expect } from 'vitest';
import { tokens } from '@/design-system';

describe('tokens.glass.starfield (#3950)', () => {
  it('exposes the unified blue-black scale', () => {
    expect(tokens.glass.starfield).toEqual({
      faint: 'rgba(21, 29, 47, 0.25)',
      subtle: 'rgba(21, 29, 47, 0.40)',
      soft: 'rgba(21, 29, 47, 0.45)',
      medium: 'rgba(21, 29, 47, 0.50)',
      strong: 'rgba(21, 29, 47, 0.55)',
      solid: 'rgba(21, 29, 47, 0.65)',
      sharp: 'rgba(21, 29, 47, 0.70)',
    });
  });

  it('every variant shares the single base tint (21, 29, 47)', () => {
    for (const value of Object.values(tokens.glass.starfield)) {
      expect(value).toMatch(/^rgba\(21, 29, 47, /);
    }
  });

  it('keeps the ultraLight white token used by glass bevels', () => {
    expect(tokens.colors.opacityScale.white.ultraLight).toBe('rgba(255, 255, 255, 0.03)');
  });
});

/**
 * themeConfig token-derivation regression tests (#3948, #3949)
 *
 * #3948: glassEffects.strong/minimal backgrounds were raw rgba() literals with
 *        no token equivalent (esp. for light mode).
 * #3949: the MUI palette light/dark shades and darkColors.neon.purple were
 *        magic hex with no token backing.
 *
 * These tests pin the values to their new tokens so the design-system stays the
 * single source of truth (and the rendered values don't drift).
 */

import { describe, it, expect } from 'vitest';
import { tokens } from '@/design-system';
import { glassEffects, darkColors, gradients } from '../themeConfig';

describe('glassEffects backgrounds derive from glass tokens (#3948)', () => {
  it('strong glass uses tokens.glass.strong.background{Dark,Light}', () => {
    expect(glassEffects.strong(true).background).toBe(tokens.glass.strong.backgroundDark);
    expect(glassEffects.strong(false).background).toBe(tokens.glass.strong.backgroundLight);
  });

  it('minimal glass uses tokens.glass.medium.background{Dark,Light}', () => {
    expect(glassEffects.minimal(true).background).toBe(tokens.glass.medium.backgroundDark);
    expect(glassEffects.minimal(false).background).toBe(tokens.glass.medium.backgroundLight);
  });

  it('preserves the original rendered values (no visual change)', () => {
    expect(tokens.glass.strong.backgroundDark).toBe('rgba(21, 29, 47, 0.65)');
    expect(tokens.glass.strong.backgroundLight).toBe('rgba(255, 255, 255, 0.85)');
    expect(tokens.glass.medium.backgroundDark).toBe('rgba(21, 29, 47, 0.45)');
    expect(tokens.glass.medium.backgroundLight).toBe('rgba(255, 255, 255, 0.6)');
  });
});

describe('palette accents derive from tokens (#3949)', () => {
  it('neon.purple is the harmonicDark token, not a magic hex', () => {
    expect(darkColors.neon.purple).toBe(tokens.colors.audioSemantic.harmonicDark);
  });

  it('the brand accent shades exist as tokens with the expected values', () => {
    expect(tokens.colors.accent.primaryLight).toBe('#8B7CF7');
    expect(tokens.colors.accent.primaryDark).toBe('#5A5CC4');
    expect(tokens.colors.accent.secondaryLight).toBe('#6FE0FF');
    expect(tokens.colors.accent.secondaryDark).toBe('#00BCC4');
    expect(tokens.colors.audioSemantic.harmonicDark).toBe('#C44569');
  });

  it('DS-12: the auroraReverse gradient references the primaryDark token (single source)', () => {
    expect(gradients.auroraReverse).toContain(tokens.colors.accent.primaryDark);
  });
});

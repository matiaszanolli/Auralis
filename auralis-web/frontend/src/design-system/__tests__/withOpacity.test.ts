/**
 * Hex→rgba derivation lives in one place (#4463, #4464)
 *
 * Four call sites carried their own copy of the `parseInt(hex.slice(...), 16)`
 * conversion the design system already exported as `withOpacity()`, and the
 * artwork-extraction fallback transcribed the brand accent's hex *and* its
 * channel numbers by hand — both of which drift silently the moment a token
 * changes. These tests pin the shared helper's behaviour and the token
 * derivation that replaced the transcribed literals.
 */

import { describe, it, expect } from 'vitest';
import { tokens, withOpacity, hexToRgb } from '@/design-system';
import { getToastBackgroundColor, getToastBorderColor } from '@/components/shared/Toast/toastColors';

describe('hexToRgb', () => {
  it('parses a 6-digit hex colour', () => {
    expect(hexToRgb('#7366F0')).toEqual({ r: 115, g: 102, b: 240 });
  });

  it('is case-insensitive', () => {
    expect(hexToRgb('#7366f0')).toEqual(hexToRgb('#7366F0'));
  });

  it.each(['rgba(0, 0, 0, 0.5)', 'var(--app-surface-raised)', '#fff', 'transparent', ''])(
    'returns null for non-hex input (%s)',
    (input) => {
      expect(hexToRgb(input)).toBeNull();
    }
  );

  it('returns null rather than NaN channels for a malformed hex', () => {
    expect(hexToRgb('#zzzzzz')).toBeNull();
  });
});

describe('withOpacity', () => {
  it('emits rgba() from a hex token', () => {
    expect(withOpacity(tokens.colors.accent.primary, 0.15)).toBe('rgba(115, 102, 240, 0.15)');
  });

  it('passes non-hex values through untouched, so a CSS variable stays valid', () => {
    expect(withOpacity('var(--app-surface-raised)', 0.5)).toBe('var(--app-surface-raised)');
  });
});

describe('brand accent derivation (#4463)', () => {
  it('the token still resolves to the channels the old literals hard-coded', () => {
    // If the brand accent is ever changed, this assertion is the one place
    // that has to move — every former copy of 115/102/240 now derives from it.
    expect(hexToRgb(tokens.colors.accent.primary)).toEqual({ r: 115, g: 102, b: 240 });
  });
});

describe('toastColors uses the shared helper (#4464)', () => {
  it('background matches withOpacity() on the semantic token', () => {
    expect(getToastBackgroundColor('success')).toBe(withOpacity(tokens.colors.semantic.success, 0.15));
    expect(getToastBackgroundColor('error')).toBe(withOpacity(tokens.colors.semantic.error, 0.15));
  });

  it('border returns the opaque semantic token', () => {
    expect(getToastBorderColor('warning')).toBe(tokens.colors.semantic.warning);
  });
});

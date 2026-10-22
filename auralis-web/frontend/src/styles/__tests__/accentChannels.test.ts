/**
 * --accent-rgb tracks the accent token (#5801)
 *
 * globalStyles publishes the accent colour's RGB channels so keyframes can write
 * rgba(var(--accent-rgb), <opacity>) and follow a brand-colour change (#3982).
 * The triple is a hand-typed copy of tokens.colors.accent.primary, and
 * animations.ts used to repeat it again as a var() fallback that could never
 * apply (the variable is always defined). Pin the one remaining copy to the
 * token so changing the brand colour cannot leave the glows on the old one.
 */

import { describe, it, expect } from 'vitest';
import { tokens } from '@/design-system';
import { globalStyles } from '../globalStyles';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

const hexToChannels = (hex: string): string => {
  const n = parseInt(hex.replace('#', ''), 16);
  return `${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}`;
};

describe('--accent-rgb', () => {
  it('equals the RGB channels of tokens.colors.accent.primary', () => {
    const match = /--accent-rgb:\s*([\d, ]+);/.exec(globalStyles.styles);
    expect(match).not.toBeNull();
    expect(match![1].trim()).toBe(hexToChannels(tokens.colors.accent.primary));
  });

  it('is consumed without a hard-coded fallback in the album pane animations', () => {
    const source = readFileSync(
      join(__dirname, '..', '..', 'components', 'library', 'AlbumCharacterPane', 'animations.ts'),
      'utf8'
    );

    expect(source).toContain('rgba(var(--accent-rgb)');
    expect(source).not.toMatch(/var\(--accent-rgb\s*,/);
  });
});

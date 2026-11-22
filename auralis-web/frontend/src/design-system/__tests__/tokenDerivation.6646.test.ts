/**
 * Token rgba strings derive from their base colour (#6646)
 *
 * effects.ts, surfaces.ts and colors.ts used to re-spell the brand accent's channels (115, 102, 240)
 * and the glass surface's (21, 29, 47) in every variant. They are now built with withOpacity from
 * colors.accent.primary / colors.bg.level2; these tests pin the exact strings the derivation must
 * produce and keep the raw triplets from coming back.
 */

import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, it, expect } from 'vitest';
import { tokens, energyGradient } from '@/design-system';

const TOKENS_DIR = resolve(__dirname, '../tokens');

describe('derived token strings (#6646)', () => {
  it('keeps the exact accent glow, border and opacity-scale spellings', () => {
    expect(tokens.shadows.glowSoft).toBe('0 0 16px rgba(115, 102, 240, 0.20)');
    expect(tokens.shadows.glowMd).toBe('0 0 24px rgba(115, 102, 240, 0.32)');
    expect(tokens.colors.border.medium).toBe('rgba(115, 102, 240, 0.24)');
    expect(tokens.colors.opacityScale.accent.standard).toBe('rgba(115, 102, 240, 0.20)');
    expect(tokens.colors.opacityScale.accent.full).toBe('rgba(115, 102, 240, 1.0)');
  });

  it('builds the glass backgrounds from the level-2 surface colour', () => {
    expect(tokens.colors.bg.level2).toBe('#151D2F');
    expect(tokens.glass.starfield.strong).toBe('rgba(21, 29, 47, 0.55)');
    expect(tokens.glass.subtle.background).toBe('rgba(21, 29, 47, 0.25)');
  });

  it('leaves no raw accent or glass channel triplet in the token files', () => {
    for (const file of ['colors.ts', 'effects.ts', 'surfaces.ts']) {
      const source = readFileSync(resolve(TOKENS_DIR, file), 'utf8');
      expect(source, file).not.toMatch(/115,\s*102,\s*240|21,\s*29,\s*47/);
    }
  });

  it('draws the energy ramp the meter used to inline', () => {
    expect(energyGradient(0.3)).toBe(`linear-gradient(to right,
            hsla(210, 80%, 60%, 0.3) 0%,
            hsla(45, 90%, 55%, 0.3) 50%,
            hsla(15, 95%, 55%, 0.3) 100%)`);
  });
});
